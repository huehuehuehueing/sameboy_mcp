"""LLM Agent that uses MCP tools via function calling.

Instead of parsing verbal LLM output, this agent instructs the LLM
to call MCP tools directly using OpenAI-compatible function calling.
"""

import json
from typing import Callable, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import AgentConfig


# MCP tools exposed to the LLM as OpenAI functions
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
            "name": "press_key",
            "description": "Press a Game Boy button for a number of frames",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": ["a", "b", "start", "select", "up", "down", "left", "right"]},
                    "frames": {"type": "integer", "description": "Frames to hold button", "default": 8},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_frames",
            "description": "Run the emulator for N frames without input",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of frames to run"},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Capture the current screen as a PNG image",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["png"], "default": "png"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_registers",
            "description": "Get CPU register values (AF, BC, DE, HL, SP, PC)",
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

    def __init__(self, config: AgentConfig, call_tool: Callable):
        """
        Args:
            config: Agent configuration
            call_tool: Async function to call MCP tools: call_tool(name, args) -> result
        """
        self.config = config
        self._call_tool = call_tool
        self._verbose = config.verbose

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

    async def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute an MCP tool and return the result."""
        if name == "report_result":
            # Special tool - just return the args as the result
            return args

        self._log(f"executing tool: {name}({args})")
        result = await self._call_tool(name, args)
        self._log(f"  result: {str(result)[:200]}")
        return result

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
            return {"action": "wait", "frames": 60}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

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
                self._log(f"LLM error: {e}")
                return {"action": "wait", "frames": 60}

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
                # No tool calls and no useful response - return default
                return {"action": "wait", "frames": 60}

        self._log(f"max turns reached without result")
        return {"action": "wait", "frames": 60}


# System prompts for different decision types

BATTLE_SYSTEM_PROMPT = """You are a Pokemon battle AI. Use the provided tools to analyze the battle state and decide your action.

Available memory addresses for battle info:
- 0xD057: Battle type (1=wild, 2=trainer)
- 0xCFE5: Enemy HP (2 bytes, little-endian)
- 0xD014: Your active Pokemon HP (2 bytes)

After analyzing the state, call report_result with your decision:
- action: "move" with index 0-3 for which move to use
- action: "run" to flee from wild battles
- action: "switch" with index 0-5 for party Pokemon
- action: "item" with index for bag item

Always call report_result to provide your final decision."""

STRATEGY_SYSTEM_PROMPT = """You are a Pokemon game AI deciding what to do in the overworld.

You can use tools to read game memory and analyze the situation:
- read_memory: Check game state (map ID at 0xD35E, player X at 0xD361, player Y at 0xD362)
- capture_screen: See what's on screen
- get_registers: Get CPU state

The Area Analysis section in the context tells you about:
- NPCs nearby (including TRAINERS you might need to battle)
- Items you can collect
- Exits/warps from this area

After analyzing, call report_result with your decision:
- action: "explore" with direction (up/down/left/right) and steps - walk around
- action: "collect_item" - go pick up the nearest item
- action: "find_exit" - navigate towards an exit/warp
- action: "heal" to go to Pokecenter
- action: "interact" to talk to NPC/object in front
- action: "wait" with frames to pause

Priority suggestions:
1. If low HP, consider healing
2. If items nearby, consider collecting them
3. If you see trainers, prepare for battle or find alternate route
4. Explore new areas to progress

Always call report_result to provide your final decision."""
