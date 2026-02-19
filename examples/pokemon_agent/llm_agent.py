"""LLM Agent that uses MCP tools via function calling.

Instead of parsing verbal LLM output, this agent instructs the LLM
to call MCP tools directly using OpenAI-compatible function calling.
Includes cost tracking and history summarization.
"""

import json
from pathlib import Path
from typing import Callable, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import AgentConfig
from .cost_tracker import CostTracker


# ============================================================
# Per-mode tool sets — only these tools are visible to the LLM.
# The LLM can still *execute* any MCP tool via _execute_tool(),
# but limiting visibility reduces context tokens by ~90%.
# ============================================================

BATTLE_TOOLS = {
    "read_memory", "press_and_read", "decode_screen_text", "report_result",
}
STRATEGY_TOOLS = {
    "press_and_read", "wait_and_read", "render_ascii_map", "decode_screen_text",
    "read_memory", "write_memory", "read_inventory", "set_inventory",
    "read_money", "set_money", "report_result",
}
DIALOG_TOOLS = {
    "press_and_read", "wait_and_read", "decode_screen_text", "report_result",
}


def filter_tools(all_tools: list[dict], allowed: set[str]) -> list[dict]:
    """Filter an OpenAI tool list to only include tools in the allowed set."""
    return [t for t in all_tools if t["function"]["name"] in allowed]


# report_result is a synthetic tool (not on the MCP server) that the LLM
# calls to return its decision to the agent.
REPORT_RESULT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_result",
        "description": (
            "REQUIRED — call this to report your decision. "
            "You MUST call this before your turns run out."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "move", "run", "switch", "item",
                        "explore", "heal", "interact", "wait",
                        "collect_item", "find_exit",
                        "navigate_to", "collect_hidden", "find_pokecenter",
                        "navigate_route",
                    ],
                },
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "index": {"type": "integer", "description": "Move/item/pokemon index (0-based)"},
                "steps": {"type": "integer", "description": "Number of steps to take"},
                "frames": {"type": "integer", "description": "Frames to wait"},
                "x": {"type": "integer", "description": "Target x coordinate (from ASCII map)"},
                "y": {"type": "integer", "description": "Target y coordinate (from ASCII map)"},
                "interact": {"type": "boolean", "description": "Press A on arrival (default false)"},
                "dest_map_id": {"type": "integer", "description": "Target map ID for navigate_route"},
                "dest_map_name": {"type": "string", "description": "Target map name for navigate_route (e.g. 'Pallet Town')"},
                "reasoning": {"type": "string", "description": "Brief explanation"},
            },
            "required": ["action"],
        },
    },
}


def _sanitize_schema(schema: dict) -> dict:
    """Sanitize a JSON Schema for OpenAI function-calling compatibility.

    OpenAI rejects schemas that use newer JSON Schema features like
    prefixItems, anyOf-with-null, or arrays without 'items'.
    """
    if not isinstance(schema, dict):
        return schema

    schema = dict(schema)  # shallow copy

    # anyOf with null → collapse to the non-null branch
    if "anyOf" in schema:
        branches = schema["anyOf"]
        non_null = [b for b in branches if b.get("type") != "null"]
        if len(non_null) == 1:
            # Replace this node with the non-null branch (+ nullable hint)
            merged = _sanitize_schema(non_null[0])
            schema.pop("anyOf")
            schema.update(merged)
        else:
            schema["anyOf"] = [_sanitize_schema(b) for b in branches]

    # Array with prefixItems but no items → convert to items
    if schema.get("type") == "array":
        if "prefixItems" in schema and "items" not in schema:
            prefix = schema.pop("prefixItems")
            # Use the first element type as items type, or generic
            if prefix:
                schema["items"] = _sanitize_schema(prefix[0])
            else:
                schema["items"] = {}
        elif "items" not in schema:
            schema["items"] = {}
        else:
            schema["items"] = _sanitize_schema(schema["items"])

    # Recurse into properties
    if "properties" in schema:
        schema["properties"] = {
            k: _sanitize_schema(v) for k, v in schema["properties"].items()
        }

    return schema


def mcp_tools_to_openai(mcp_tools) -> list[dict]:
    """Convert MCP Tool objects to OpenAI function-calling format.

    Args:
        mcp_tools: List of MCP Tool objects (from session.list_tools().tools)

    Returns:
        List of OpenAI tool dicts, plus the synthetic report_result tool.
    """
    openai_tools = []
    for tool in mcp_tools:
        schema = tool.inputSchema or {"type": "object", "properties": {}}
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": _sanitize_schema(schema),
            },
        })

    # Always append the synthetic report_result tool
    openai_tools.append(REPORT_RESULT_TOOL)
    return openai_tools


class LLMToolAgent:
    """LLM agent that uses MCP tools via function calling."""

    def __init__(self, config: AgentConfig, call_tool: Callable,
                 cost_tracker: CostTracker | None = None,
                 event_sink=None):
        """
        Args:
            config: Agent configuration
            call_tool: Async function to call MCP tools: call_tool(name, args) -> result
            cost_tracker: Optional shared cost tracker instance
            event_sink: Optional AgentEventSink for dashboard integration
        """
        self.config = config
        self._call_tool = call_tool
        self._verbose = config.verbose
        self.cost_tracker = cost_tracker or CostTracker()
        self._event_sink = event_sink
        self._tools: list[dict] = [REPORT_RESULT_TOOL]  # Set via set_tools()
        self._panel_tools: dict[str, str] = {}  # tool_name -> panel_id

        # History summarization
        self._max_history = config.max_history
        self._message_history: list[dict] = []  # Persistent history across calls
        self._history_summarized = False

        # LLM availability (set to False on connection errors, retried periodically)
        self._llm_available = False
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3  # Disable after N consecutive failures
        self._retry_interval = 20  # Re-check every N calls when disabled
        self._calls_since_disable = 0

        # Initialize OpenAI client
        llm_cfg = config.get_llm_config()
        self._client = None
        self._model = llm_cfg["model"]

        if OpenAI and llm_cfg.get("base_url"):
            base_url = llm_cfg["base_url"]
            self._client = OpenAI(
                base_url=base_url,
                api_key=llm_cfg.get("api_key") or "not-needed",
                timeout=30.0,  # 30s per API call; prevents indefinite hangs
            )

            # Query actual model name from server (vLLM uses "default" as placeholder)
            if self._model == "default":
                try:
                    import httpx
                    models_url = base_url.rstrip("/") + "/models"
                    resp = httpx.get(models_url, timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("data") and len(data["data"]) > 0:
                            self._model = data["data"][0].get("id", "default")
                            if self._verbose:
                                print(f"  [llm-agent] discovered model: {self._model}")
                except Exception as e:
                    if self._verbose:
                        print(f"  [llm-agent] model discovery failed: {e}")

    def _log(self, msg: str):
        if self._verbose:
            print(f"  [llm-agent] {msg}")

    def _check_stop(self) -> bool:
        """Check if the dashboard sent a STOP signal."""
        if not self._event_sink:
            return False
        pending = self._event_sink.get_pending_actions()
        if pending:
            action_id = pending[0].get("action_id", "")
            if action_id == "stop":
                return True
        return False

    def check_connection(self) -> bool:
        """Verify LLM is reachable. Returns True if healthy."""
        if not self._client:
            return False
        try:
            self._client.models.list()
            self._llm_available = True
            self._consecutive_errors = 0
            return True
        except Exception as e:
            self._log(f"LLM connection check failed: {e}")
            self._llm_available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._llm_available

    def set_tools(self, openai_tools: list[dict]) -> None:
        """Set the tools available to the LLM.

        Args:
            openai_tools: List of OpenAI function-calling tool dicts
                          (from mcp_tools_to_openai()).
        """
        self._tools = openai_tools
        tool_names = [t["function"]["name"] for t in openai_tools]
        self._log(f"tools set: {', '.join(tool_names)}")

    def set_panel_tools(self, mapping: dict[str, str]) -> None:
        """Set which tools emit to which dashboard panels.

        Args:
            mapping: Dict of tool_name -> panel_id
        """
        self._panel_tools = mapping

    @staticmethod
    def _compact_summary(name: str, result: Any) -> str:
        """Return a compact human-readable summary of a tool result."""
        if not isinstance(result, dict):
            return str(result)[:120]

        if name == "render_ascii_map":
            mn = result.get("map_name", "?")
            dims = result.get("dimensions", {})
            w = dims.get("width_steps", "?")
            h = dims.get("height_steps", "?")
            p = result.get("player", {})
            px = p.get("x", "?")
            py = p.get("y", "?")
            nw = len(result.get("warps", []))
            ns = len(result.get("sprites", []))
            return f"{mn} ({w}x{h}) player=({px},{py}) warps={nw} sprites={ns}"

        if name in ("decode_screen_text", "press_and_read", "wait_and_read"):
            lines = result.get("text_lines", [])
            key = result.get("key")
            preview = " | ".join(lines[:3]) if lines else "(blank)"
            if len(preview) > 100:
                preview = preview[:100] + "..."
            prefix = f"[{key}] " if key else ""
            pos = ""
            if "player_x" in result:
                pos = f" @({result['player_x']},{result['player_y']})"
            return f"{prefix}{preview}{pos}"

        if name == "read_memory":
            addr = result.get("address", "?")
            val = result.get("hex", result.get("value", "?"))
            return f"[{addr}] = {val}"

        return str(result)[:120]

    async def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute an MCP tool and return the result."""
        if name == "report_result":
            # Emit decision to dashboard
            if self._event_sink:
                self._event_sink.emit_decision(args)
            return args

        self._log(f"executing tool: {name}({args})")
        result = await self._call_tool(name, args)

        summary = self._compact_summary(name, result)
        self._log(f"  result: {summary}")

        # Emit to dashboard
        if self._event_sink:
            # Send full result to dedicated panel if this tool has one
            panel_id = self._panel_tools.get(name)
            if panel_id and isinstance(result, dict):
                self._event_sink.emit_panel_data(panel_id, result, panel_id)

            # Always send compact summary to agent log
            self._event_sink.emit_tool_call(name, args, summary)

        return result

    async def _summarize_history(self):
        """Summarize conversation history when it exceeds max_history.

        Replaces the entire history with a single summary message.
        """
        if not self._client or len(self._message_history) < self._max_history:
            return

        self._log(f"summarizing history ({len(self._message_history)} messages)")

        summary_prompt = SUMMARY_PROMPT

        try:
            summary_messages = list(self._message_history) + [
                {"role": "user", "content": summary_prompt}
            ]
            response = self._client.chat.completions.create(
                model=self._model,
                messages=summary_messages,
                max_tokens=512,
                temperature=0.3,
            )

            # Track summary cost
            if response.usage:
                step_cost = self.cost_tracker.track_openai(response.usage, self._model)
                self._log(f"summary cost: ${step_cost:.6f}")

            summary_text = response.choices[0].message.content or "No summary generated."

            # Replace history with summary
            self._message_history = [
                {
                    "role": "user",
                    "content": (
                        f"CONVERSATION HISTORY SUMMARY "
                        f"(representing {self._max_history} previous messages):\n"
                        f"{summary_text}\n\n"
                        "Continue playing based on this context."
                    ),
                }
            ]
            self._history_summarized = True
            self._log(f"history summarized to 1 message")

        except Exception as e:
            self._log(f"summarization failed: {e}")
            # On failure, just trim the oldest messages
            self._message_history = self._message_history[-10:]

    async def run_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int = 5,
        tools: list[dict] | None = None,
        cache_key: str | None = None,
    ) -> dict:
        """
        Run the LLM with tool access until it reports a result.

        Args:
            system_prompt: System instructions for the LLM
            user_message: User message describing the task
            max_turns: Maximum tool-calling turns
            tools: Override tool list (use filter_tools() to build per-mode sets).
                   Falls back to self._tools if None.
            cache_key: Optional prompt cache key for OpenAI routing optimization.
                       Use a stable string per mode (e.g. "battle", "strategy").

        Returns:
            The result from the report_result tool call
        """
        if not self._client:
            self._log("no LLM client, returning default")
            return {"action": "explore", "direction": "down", "steps": 1,
                    "_no_llm": True}

        # If LLM was disabled due to errors, periodically retry
        if not self._llm_available:
            self._calls_since_disable += 1
            if self._calls_since_disable < self._retry_interval:
                return {"action": "explore", "direction": "down", "steps": 1,
                        "_no_llm": True}
            # Time to retry
            self._calls_since_disable = 0
            if not self.check_connection():
                print(f"  [llm-agent] still unreachable, will retry in {self._retry_interval} cycles")
                return {"action": "explore", "direction": "down", "steps": 1,
                        "_no_llm": True}
            print(f"  [llm-agent] reconnected!")

        # Check if history needs summarization
        if len(self._message_history) >= self._max_history:
            await self._summarize_history()

        # Check for prompt injections from dashboard
        if self._event_sink:
            injections = self._event_sink.get_pending_injections()
            if injections:
                injection_text = "\n".join(
                    f"[OPERATOR INSTRUCTION: {inj}]" for inj in injections
                )
                user_message = f"{injection_text}\n\n{user_message}"
                self._log(f"injected {len(injections)} prompt(s)")

        # NOTE: We intentionally do NOT emit the raw user_message to the
        # dashboard here.  The full strategy_context is verbose internal LLM
        # prompt text that clutters the agent log.  Compact, human-readable
        # action lines are emitted by PokemonAgent._log_action() instead.

        # Add current context to persistent history
        self._message_history.append({"role": "user", "content": user_message})

        # Build messages: system + history
        messages = [
            {"role": "system", "content": system_prompt},
        ] + list(self._message_history)

        # Resolve tool list: per-mode override or full set
        active_tools = tools if tools is not None else self._tools
        if tools is not None:
            tool_names = [t["function"]["name"] for t in active_tools]
            self._log(f"mode tools: {', '.join(tool_names)}")

        # Build extra_body for prompt cache routing (OpenAI)
        extra_body = {}
        if cache_key:
            extra_body["prompt_cache_key"] = cache_key

        consecutive_blanks = 0
        BLANK_THRESHOLD = 3

        for turn in range(max_turns):
            # Check for STOP signal from dashboard before each LLM call
            if self._check_stop():
                self._log("STOP signal received — aborting LLM turn")
                return {"action": "wait", "frames": 60, "_stopped": True}

            self._log(f"turn {turn + 1}/{max_turns}")

            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=active_tools,
                    tool_choice="auto",
                    max_tokens=1024,
                    temperature=0.3,
                    **({"extra_body": extra_body} if extra_body else {}),
                )
            except Exception as e:
                self._consecutive_errors += 1
                self._log(f"LLM error ({self._consecutive_errors}/{self._max_consecutive_errors}): {e}")
                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._llm_available = False
                    self._calls_since_disable = 0
                    print(f"  [llm-agent] DISABLED after {self._consecutive_errors} consecutive errors. "
                          f"Will retry in {self._retry_interval} cycles.")
                return {"action": "explore", "direction": "down", "steps": 1,
                        "_no_llm": True}

            # Success — reset error counter
            self._consecutive_errors = 0

            # Track cost and cache hits
            if response.usage:
                step_cost = self.cost_tracker.track_openai(response.usage, self._model)
                # Log cache hit info
                total_input = response.usage.prompt_tokens or 0
                cached = 0
                details = getattr(response.usage, "prompt_tokens_details", None)
                if details and hasattr(details, "cached_tokens"):
                    cached = details.cached_tokens or 0
                if cached > 0:
                    pct = cached / total_input * 100 if total_input else 0
                    self._log(f"step cost: ${step_cost:.6f} | cache hit: {cached}/{total_input} ({pct:.0f}%) | total: ${self.cost_tracker.total_cost:.4f}")
                else:
                    self._log(f"step cost: ${step_cost:.6f} | no cache hit ({total_input} tokens) | total: ${self.cost_tracker.total_cost:.4f}")

            choice = response.choices[0]
            message = choice.message

            # Check if LLM wants to call tools
            if message.tool_calls:
                # Add assistant message with tool calls
                messages.append(message)

                # Execute each tool call
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    # Check for STOP signal before executing each tool
                    if self._check_stop():
                        self._log("STOP signal received — aborting mid-turn")
                        return {"action": "wait", "frames": 60, "_stopped": True}

                    # Execute the tool
                    result = await self._execute_tool(func_name, func_args)

                    # If this is the report_result tool, we're done
                    if func_name == "report_result":
                        # Save assistant response to history
                        self._message_history.append(
                            {"role": "assistant", "content": json.dumps(result)}
                        )
                        return result

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    })

                    # Track consecutive blank press_and_read results
                    if func_name in ("press_and_read", "wait_and_read"):
                        text_lines = result.get("text_lines", []) if isinstance(result, dict) else []
                        if not any(line.strip() for line in text_lines):
                            consecutive_blanks += 1
                        else:
                            consecutive_blanks = 0

                        if consecutive_blanks >= BLANK_THRESHOLD:
                            warning = (
                                f"WARNING: {consecutive_blanks} consecutive blank "
                                f"screen results. Your button presses are having no "
                                f"visible effect. Check the player_x, player_y from "
                                f"your last press_and_read — if your position hasn't "
                                f"changed, you are ADJACENT to something. Press A to "
                                f"interact! If you are lost, call render_ascii_map "
                                f"to see your position and navigate toward your target."
                            )
                            self._log(f"  *** blank screen warning ({consecutive_blanks}x)")
                            messages.append({
                                "role": "user",
                                "content": warning,
                            })
                            consecutive_blanks = 0  # reset so warning fires again after another streak
            else:
                # No tool calls — try to parse text content as a JSON decision
                # (some models return the decision as text instead of calling report_result)
                if message.content:
                    self._log(f"LLM response (no tools): {message.content[:200]}")
                    text = message.content.strip()
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict) and "action" in parsed:
                            self._log(f"parsed text as decision: {parsed.get('action')}")
                            self._message_history.append(
                                {"role": "assistant", "content": text}
                            )
                            if self._event_sink:
                                self._event_sink.emit_decision(parsed)
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
                    self._message_history.append(
                        {"role": "assistant", "content": message.content}
                    )
                    if self._event_sink:
                        self._event_sink.emit_llm_message("assistant", message.content[:500])
                # No tool calls and no parseable response - return default
                return {"action": "wait", "frames": 60}

        self._log(f"max turns reached without result")
        return {"action": "wait", "frames": 60}


# System prompts loaded from prompts/ directory
_PROMPTS_DIR = Path(__file__).parent / "prompts"

BATTLE_SYSTEM_PROMPT = (_PROMPTS_DIR / "battle_tool_agent.txt").read_text()
STRATEGY_SYSTEM_PROMPT = (_PROMPTS_DIR / "strategy_tool_agent.txt").read_text()
DIALOG_SYSTEM_PROMPT = (_PROMPTS_DIR / "dialog_tool_agent.txt").read_text()
SUMMARY_PROMPT = (_PROMPTS_DIR / "summarization.txt").read_text()
