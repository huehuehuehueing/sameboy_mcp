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


# MCP tools exposed to the LLM as OpenAI functions.
# NOTE: Only observation tools + report_result are provided.
# The LLM must NOT press keys or run frames directly — it reports
# a decision via report_result, and the agent executes it.
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read bytes from Game Boy memory at a specific address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "integer", "description": "Memory address (0x0000-0xFFFF)"},
                    "length": {"type": "integer", "description": "Number of bytes to read", "default": 1},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decode_screen_text",
            "description": "Read the current screen tile map and decode it to text using Pokemon Gen 1 character encoding. Returns the on-screen text (dialog boxes, menus, signs). This is the primary way to read what the game is showing.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_ascii_map",
            "description": "Render an ASCII top-down map of the current area. Legend: . = walkable, # = wall/blocked, @ = player, W = warp/door/stairs, G = grass, N = NPC, T = trainer, I = item ball, C = PC, B = bookshelf, ! = sign/interactable. Grid uses (x,y) coordinates shown in column/row headers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_result",
            "description": "Report the final result/decision back to the agent",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["move", "run", "switch", "item", "explore", "heal", "interact", "wait", "collect_item", "find_exit"],
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
    },
]


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

    async def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute an MCP tool and return the result."""
        if name == "report_result":
            # Emit decision to dashboard
            if self._event_sink:
                self._event_sink.emit_decision(args)
            return args

        self._log(f"executing tool: {name}({args})")
        result = await self._call_tool(name, args)
        self._log(f"  result: {str(result)[:200]}")

        # Emit tool call to dashboard
        if self._event_sink:
            result_preview = str(result)[:200] if result else None
            self._event_sink.emit_tool_call(name, args, result_preview)

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

        for turn in range(max_turns):
            self._log(f"turn {turn + 1}/{max_turns}")

            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=MCP_TOOLS,
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
            else:
                # No tool calls - check if there's content
                if message.content:
                    self._log(f"LLM response (no tools): {message.content[:200]}")
                    self._message_history.append(
                        {"role": "assistant", "content": message.content}
                    )
                    # Emit assistant message to dashboard
                    if self._event_sink:
                        self._event_sink.emit_llm_message("assistant", message.content[:500])
                # No tool calls and no useful response - return default
                return {"action": "wait", "frames": 60}

        self._log(f"max turns reached without result")
        return {"action": "wait", "frames": 60}


# System prompts for different decision types

BATTLE_SYSTEM_PROMPT = """You are a Pokemon battle AI. Analyze the state and decide.

You can use read_memory to check battle info:
- 0xD057: Battle type (1=wild, 2=trainer)
- 0xCFE5: Enemy HP (2 bytes, little-endian)
- 0xD014: Your active Pokemon HP (2 bytes)

You MUST call report_result with your decision. Do NOT skip it.
- action: "move" with index 0-3 for which move to use
- action: "run" to flee from wild battles
- action: "switch" with index 0-5 for party Pokemon
- action: "item" with index for bag item"""

STRATEGY_SYSTEM_PROMPT = """You are a Pokemon game AI. You observe the game state and report a decision. You do NOT control the game directly.

WORKFLOW: 1) Read the screen with decode_screen_text. 2) Optionally read the map with render_ascii_map. 3) Call report_result with your decision. That's it — observe then decide.

CRITICAL: You MUST call report_result before your turns run out. Do not waste turns — call it after 1-2 observation tools.

When an operator instruction is present, follow it exactly.

report_result actions:
- "explore" with direction (up/down/left/right) and steps (1-5)
- "interact" — press A to talk to NPC/object the player is facing
- "find_exit" — auto-navigate to nearest exit/warp
- "collect_item" — pick up nearest item
- "heal" — go to Pokecenter
- "wait" with frames to pause"""
