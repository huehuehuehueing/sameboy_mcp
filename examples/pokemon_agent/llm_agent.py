"""LLM Agent that uses MCP tools via function calling.

Instead of parsing verbal LLM output, this agent instructs the LLM
to call MCP tools directly using OpenAI-compatible function calling.
Includes cost tracking and history summarization.
"""

import json
from typing import Callable, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import AgentConfig
from .cost_tracker import CostTracker


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
                    ],
                },
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "index": {"type": "integer", "description": "Move/item/pokemon index (0-based)"},
                "steps": {"type": "integer", "description": "Number of steps to take"},
                "frames": {"type": "integer", "description": "Frames to wait"},
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

        summary_prompt = (
            "Create a brief summary of our conversation so far. Include:\n"
            "1. Key game events and milestones reached\n"
            "2. Important decisions made\n"
            "3. Current objectives\n"
            "4. Current location and Pokemon team status\n"
            "5. Strategies and plans mentioned\n"
            "Be concise - this will replace the full history."
        )

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
    ) -> dict:
        """
        Run the LLM with tool access until it reports a result.

        Args:
            system_prompt: System instructions for the LLM
            user_message: User message describing the task
            max_turns: Maximum tool-calling turns

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

        consecutive_blanks = 0
        BLANK_THRESHOLD = 3

        for turn in range(max_turns):
            self._log(f"turn {turn + 1}/{max_turns}")

            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=self._tools,
                    tool_choice="auto",
                    max_tokens=1024,
                    temperature=0.3,
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

            # Track cost
            if response.usage:
                step_cost = self.cost_tracker.track_openai(response.usage, self._model)
                self._log(f"step cost: ${step_cost:.6f} (total: ${self.cost_tracker.total_cost:.4f})")

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


# System prompts for different decision types

BATTLE_SYSTEM_PROMPT = """You are a Pokemon battle AI. You have access to all emulator and game tools.

STRATEGY:
1. Use press_and_read(key="a") or decode_screen_text to read the battle menu/options.
2. Use read_memory if you need HP or stats (e.g. 0xD014 = your HP, 0xCFE5 = enemy HP).
3. Call report_result with your decision.

CRITICAL: You MUST call report_result. Use at most 3 observation tools, then decide.

report_result battle actions:
- "move" with index 0-3 for which move to use
- "run" to flee from wild battles
- "switch" with index 0-5 for party Pokemon
- "item" with index for bag item"""

STRATEGY_SYSTEM_PROMPT = """You are a Pokemon game AI controlling Pokemon Yellow via emulator tools.

You have plenty of turns. Use them to COMPLETE the task — do not stop early.

PRIMARY TOOLS (use these for 90% of actions):
- press_and_read(key, frames=16, wait=60) — press button + wait + read screen text. YOUR MAIN TOOL. Returns text_lines showing what's on screen.
- wait_and_read(wait=60) — wait without pressing, then read screen. Use when text is still printing.
- render_ascii_map — see area layout. Legend: . walkable, # wall, @ player, W warp, G grass, N NPC, T trainer, I item, C PC, B bookshelf, ! sign.
- read_inventory(storage="bag"|"pc"|"both") — see items and quantities.
- read_money / set_money — read or set player's money.
- set_inventory(storage, items="id:qty,...") — directly set items in bag or PC.

OTHER TOOLS (use sparingly):
- press_key / run_frames / decode_screen_text — low-level versions. Avoid these — use press_and_read instead.
- read_memory / write_memory — check or modify specific game memory addresses.
- report_result — REQUIRED as your FINAL call to hand control back.

COORDINATE NAVIGATION (CRITICAL):
The ASCII map uses (x, y) coordinates. @ marks your position.
- Target is LEFT of you (smaller x) → press_and_read(key="left")
- Target is RIGHT of you (larger x) → press_and_read(key="right")
- Target is ABOVE you (smaller y) → press_and_read(key="up")
- Target is BELOW you (larger y) → press_and_read(key="down")
Example: You are @ at (3,5). PC marked C is at (3,2). You need to go UP 3 times (y: 5→4→3→2), then press A.
Example: NPC marked N is at (5,5). You need to go RIGHT 2 times (x: 3→4→5), then press A.
To interact with an object, you must be ADJACENT to it and FACING it. Press the direction toward it (to face it), then press A. You do NOT walk onto the object's tile.

STUCK DETECTION (CRITICAL):
press_and_read returns player_x and player_y. CHECK THESE after every directional press.
- If position CHANGED → you moved. Keep navigating.
- If position DID NOT CHANGE → you are BLOCKED in that direction.
  - If your target (C, N, I, !, B) is in that direction → you are ADJACENT. Press A to interact!
  - Otherwise → obstacle in the way. Try a different route.
- NEVER press the same direction more than 2 times if your position isn't changing.

WORKFLOW:
1. ORIENT: Call render_ascii_map. Note your @ position and the target's position.
2. NAVIGATE: Calculate direction (compare coordinates). Walk step by step toward the target.
3. INTERACT: When adjacent, press the direction key toward the target to face it, then press A.
4. READ: Check text_lines. If text appears, the interaction worked. Navigate the menu.
5. VERIFY: Confirm the goal is done from screen text. Call report_result.

BLANK SCREEN = NO INTERACTION:
Empty text_lines after pressing A means you're not adjacent to or facing anything interactable.
- STOP pressing A blindly. Call render_ascii_map to see your current position.
- Compare your position to the target and navigate toward it.
- If you get 3+ blank results in a row, you MUST call render_ascii_map before any more button presses.

MENU NAVIGATION (PC, shops, NPCs):
- A confirms/advances, B cancels/backs out. Arrow keys navigate menu items.
- ▶ or ▷ markers show cursor position in menus.
- When you see a menu with items (e.g. "WITHDRAW ITEM"), press A to select.
- When prompted for quantity (e.g. "×1"), press A to confirm the amount.
- Keep pressing A through ALL confirmation dialogs until you see the result message.
- Pokemon Yellow menus often need 3-5 A presses to complete an action.
- NEVER press B unless you intentionally want to CANCEL or EXIT a menu.

VERIFICATION — NEVER assume or hallucinate:
- Read text_lines after EVERY action to see what ACTUALLY happened.
- In report_result reasoning, QUOTE actual screen text that confirms completion.
- If you cannot confirm the goal from screen text, say so honestly in reasoning.
- NEVER claim "item obtained" or "task complete" without quoting the confirmation text.

When an operator instruction is present, follow it until the goal is verified on screen.

report_result actions (call this as your LAST tool call):
- "explore" with direction and steps (1-5)
- "interact" — completed a multi-step interaction
- "find_exit" — request auto-navigation to nearest exit
- "collect_item" — pick up nearest item
- "heal" — go to Pokecenter
- "wait" with frames"""

DIALOG_SYSTEM_PROMPT = """You are a Pokemon game AI handling a dialog or menu that is currently open.

YOUR ONLY TOOLS:
- press_and_read(key, frames=16, wait=60) — press button + read screen. YOUR MAIN TOOL.
- wait_and_read(wait=60) — wait then read screen.
- decode_screen_text — read current screen text.
- report_result — REQUIRED as your FINAL call.

RULES:
1. You are ONLY handling the current menu/dialog. Do NOT explore or move around.
2. Use press_and_read to navigate menus (A=confirm, B=cancel, arrows=navigate).
3. When text_lines becomes BLANK (empty), the menu/dialog has CLOSED. Call report_result IMMEDIATELY.
4. Do NOT press movement keys (up/down/left/right) unless navigating a menu cursor.
5. Do NOT call render_ascii_map — you are in a menu, not on the overworld.
6. Call report_result after completing the menu interaction OR when the screen goes blank.

MENU TIPS:
- A confirms, B cancels/exits. Arrow keys move cursor between options.
- ▶ or ▷ markers show the current cursor position.
- Keep pressing A through confirmation dialogs (select item → confirm quantity → done).
- Pokemon Yellow menus need 3-5 A presses to complete an action.

report_result actions:
- "interact" — menu/dialog completed successfully
- "wait" with frames — if unsure what happened"""
