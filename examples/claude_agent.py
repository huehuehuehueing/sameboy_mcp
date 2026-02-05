#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
Claude Agent - AI-powered Game Boy interaction using Claude and MCP.

This script demonstrates the full AI agent workflow:
1. Connects to the SameBoy MCP server
2. Uses Claude (Anthropic API) to interpret natural language commands
3. Claude calls MCP tools to interact with the emulator
4. Results are displayed back to the user

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python examples/claude_agent.py --rom roms/game.gb

Examples:
    # Interactive mode
    python examples/claude_agent.py --rom roms/game.gb

    # With live display
    python examples/claude_agent.py --rom roms/game.gb --display

    # Single prompt
    python examples/claude_agent.py --rom roms/game.gb -p "What game is loaded?"
"""

import argparse
import asyncio
import json
import os
import sys
import base64
from pathlib import Path
from typing import Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

if not anthropic and not openai:
    print("Error: Neither anthropic nor openai package installed.")
    print("Install with: pip install anthropic  OR  pip install openai")
    sys.exit(1)

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession


class ClaudeGameBoyAgent:
    """
    AI agent that uses Claude to interact with Game Boy emulator via MCP.

    Supports both:
    - Anthropic's native API (default)
    - OpenAI-compatible endpoints (for services like Dartmouth's chat.dartmouth.edu)
    """

    SYSTEM_PROMPT = """You are an AI agent controlling a Game Boy emulator through MCP (Model Context Protocol) tools.

You have access to tools for:
- **ROM Management**: load_rom, get_status
- **Execution**: run_frames, step_frame, step_instruction, pause, resume, reset
- **Input**: press_key, press_keys, set_key (keys: a, b, start, select, up, down, left, right)
- **Memory**: read_memory, write_memory, find_value, take_memory_snapshot, compare_memory_snapshot
- **Display**: capture_screen, get_sprites, enable_live_display, disable_live_display
- **CPU**: get_registers, disassemble
- **Save States**: save_state, load_state, list_states
- **Debugging**: set_breakpoint, remove_breakpoint, list_breakpoints, enable_trace, get_trace
- **ROM Analysis**: disassemble_rom, disassemble_function, get_rom_header, find_functions

When the user asks you to do something:
1. Think about which tools you need to use
2. Call the appropriate tools
3. Interpret the results and explain what happened
4. If the user wants to see the screen, use capture_screen

For game interaction:
- Use press_key with the key name and number of frames to hold
- Common sequences: "start" to start game, "a" to select, directional keys to move
- Run frames between inputs to let the game process: run_frames with count parameter

For memory analysis:
- Use take_memory_snapshot before a change, then compare_memory_snapshot after
- Use find_value to search for specific values (like lives count, score)
- Memory regions: 0xC000-0xDFFF is Work RAM, 0xFF80-0xFFFE is High RAM

Be helpful and explain what you're doing. If something doesn't work, try alternative approaches."""

    def __init__(self, lib_path: str, rom_path: str | None = None,
                 model: str = "CGB_E", claude_model: str = "claude-sonnet-4-20250514",
                 base_url: str | None = None, api_key: str | None = None,
                 use_openai_compat: bool = False):
        """
        Initialize the Claude agent.

        Args:
            lib_path: Path to libsameboy.so
            rom_path: Optional ROM to load on startup
            model: Game Boy model
            claude_model: Claude model to use
            base_url: Custom API base URL (for Dartmouth, etc.)
            api_key: API key (or use ANTHROPIC_API_KEY env var)
            use_openai_compat: Use OpenAI-compatible API (for services like Dartmouth)
        """
        self.lib_path = lib_path
        self.rom_path = rom_path
        self.gb_model = model
        self.claude_model = claude_model
        self.use_openai_compat = use_openai_compat

        # MCP client state
        self._session: ClientSession | None = None
        self._client_ctx = None
        self._session_ctx = None

        # Initialize API client
        if use_openai_compat:
            if not openai:
                raise RuntimeError("OpenAI package not installed. Run: pip install openai")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        else:
            if not anthropic:
                raise RuntimeError("Anthropic package not installed. Run: pip install anthropic")
            client_kwargs = {}
            if base_url:
                client_kwargs["base_url"] = base_url
            if api_key:
                client_kwargs["api_key"] = api_key
            self.client = anthropic.Anthropic(**client_kwargs)

        # Conversation history
        self.messages: list[dict] = []

        # Available tools (populated on connect)
        self.tools: list[dict] = []
        self.openai_tools: list[dict] = []  # OpenAI format tools

    async def connect(self) -> None:
        """Connect to the MCP server."""
        args = [
            '-m', 'sameboy_mcp.server',
            '--lib', self.lib_path,
            '--model', self.gb_model,
        ]
        if self.rom_path:
            args.extend(['--rom', self.rom_path])

        server_params = StdioServerParameters(
            command='python',
            args=args,
            cwd=str(Path(__file__).parent.parent)
        )

        self._client_ctx = stdio_client(server_params)
        read, write = await self._client_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

        # Get available tools and convert to API format
        result = await self._session.list_tools()
        self.tools = self._convert_tools_to_anthropic(result.tools)
        self.openai_tools = self._convert_tools_to_openai(result.tools)

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
        self._session = None

    def _convert_tools_to_anthropic(self, mcp_tools) -> list[dict]:
        """Convert MCP tools to Anthropic tool format."""
        anthropic_tools = []
        for tool in mcp_tools:
            # Build input schema from MCP tool
            input_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }

            if tool.inputSchema:
                schema = tool.inputSchema
                if isinstance(schema, dict):
                    input_schema = schema

            anthropic_tools.append({
                "name": tool.name,
                "description": tool.description or f"MCP tool: {tool.name}",
                "input_schema": input_schema
            })

        return anthropic_tools

    def _convert_tools_to_openai(self, mcp_tools) -> list[dict]:
        """Convert MCP tools to OpenAI tool format."""
        openai_tools = []
        for tool in mcp_tools:
            # Build parameters schema from MCP tool
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }

            if tool.inputSchema:
                schema = tool.inputSchema
                if isinstance(schema, dict):
                    parameters = schema

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "parameters": parameters
                }
            })

        return openai_tools

    async def call_tool(self, name: str, args: dict) -> Any:
        """Call an MCP tool."""
        if not self._session:
            raise RuntimeError("Not connected")

        result = await self._session.call_tool(name, args)
        if result.content:
            text = result.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return None

    async def chat(self, user_message: str) -> str:
        """
        Send a message to Claude and process the response.

        Args:
            user_message: The user's message

        Returns:
            Claude's response text
        """
        if self.use_openai_compat:
            return await self._chat_openai(user_message)
        else:
            return await self._chat_anthropic(user_message)

    async def _chat_anthropic(self, user_message: str) -> str:
        """Chat using Anthropic's native API."""
        # Add user message to history
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        # Call Claude with tools
        response = self.client.messages.create(
            model=self.claude_model,
            max_tokens=4096,
            system=self.SYSTEM_PROMPT,
            tools=self.tools,
            messages=self.messages
        )

        # Process response
        assistant_content = []
        response_text_parts = []

        while response.stop_reason == "tool_use":
            # Process all content blocks
            for block in response.content:
                if block.type == "text":
                    response_text_parts.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            # Add assistant message
            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })

            # Execute tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [Tool: {block.name}]", flush=True)
                    try:
                        result = await self.call_tool(block.name, block.input)
                        result_str = self._format_tool_result(block.name, result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str
                        })
                    except Exception as e:
                        print(f"    -> Error: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True
                        })

            # Add tool results
            self.messages.append({
                "role": "user",
                "content": tool_results
            })

            # Continue conversation
            response = self.client.messages.create(
                model=self.claude_model,
                max_tokens=4096,
                system=self.SYSTEM_PROMPT,
                tools=self.tools,
                messages=self.messages
            )
            assistant_content = []

        # Get final text response
        for block in response.content:
            if block.type == "text":
                response_text_parts.append(block.text)
                assistant_content.append({"type": "text", "text": block.text})

        # Add final assistant message
        if assistant_content:
            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })

        return "\n".join(response_text_parts)

    async def _chat_openai(self, user_message: str) -> str:
        """Chat using OpenAI-compatible API."""
        # Build messages with system prompt
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(self.messages)
        messages.append({"role": "user", "content": user_message})

        # Call API with tools
        response = self.client.chat.completions.create(
            model=self.claude_model,
            max_tokens=4096,
            tools=self.openai_tools,
            messages=messages
        )

        response_text_parts = []

        # Process response and handle tool calls
        while response.choices[0].finish_reason == "tool_calls":
            message = response.choices[0].message

            # Collect any text content
            if message.content:
                response_text_parts.append(message.content)

            # Add assistant message with tool calls
            messages.append(message.model_dump())

            # Execute tool calls
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                print(f"  [Tool: {func_name}]", flush=True)
                try:
                    result = await self.call_tool(func_name, func_args)
                    result_str = self._format_tool_result(func_name, result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str
                    })
                except Exception as e:
                    print(f"    -> Error: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)})
                    })

            # Continue conversation
            response = self.client.chat.completions.create(
                model=self.claude_model,
                max_tokens=4096,
                tools=self.openai_tools,
                messages=messages
            )

        # Get final response
        final_message = response.choices[0].message
        if final_message.content:
            response_text_parts.append(final_message.content)

        # Update conversation history (simplified for OpenAI format)
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": final_message.content or ""})

        return "\n".join(response_text_parts)

    def _format_tool_result(self, tool_name: str, result: Any) -> str:
        """Format tool result for display and API."""
        if tool_name == "capture_screen" and isinstance(result, dict):
            if "data_base64" in result:
                print(f"    -> Screenshot: {result.get('width')}x{result.get('height')}")
                return json.dumps(result)
            else:
                return json.dumps(result)
        else:
            result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            display = result_str[:200] + "..." if len(result_str) > 200 else result_str
            print(f"    -> {display}")
            return result_str

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []


async def interactive_mode(agent: ClaudeGameBoyAgent):
    """Run interactive chat mode."""
    print("\n" + "=" * 60)
    print("Claude Game Boy Agent - Interactive Mode")
    print("=" * 60)
    print("\nYou can give natural language commands to interact with the emulator.")
    print("Examples:")
    print("  - 'What game is loaded?'")
    print("  - 'Run the game for 2 seconds'")
    print("  - 'Press start to begin'")
    print("  - 'Take a screenshot and describe what you see'")
    print("  - 'Find where the lives counter is stored in memory'")
    print("  - 'Show me the CPU registers'")
    print("\nCommands: 'quit' to exit, 'clear' to reset conversation")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('quit', 'exit', 'q'):
                break

            if user_input.lower() == 'clear':
                agent.clear_history()
                print("Conversation cleared.")
                continue

            if user_input.lower() == 'help':
                print("\nAvailable commands:")
                print("  quit/exit/q - Exit the agent")
                print("  clear       - Clear conversation history")
                print("  help        - Show this help")
                print("\nOr just type natural language to interact with the emulator!")
                continue

            print("\nClaude:", flush=True)
            response = await agent.chat(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\nUse 'quit' to exit")
        except Exception as e:
            print(f"\nError: {e}")


async def single_prompt(agent: ClaudeGameBoyAgent, prompt: str):
    """Run a single prompt."""
    print(f"\nPrompt: {prompt}")
    print("\nClaude:", flush=True)
    response = await agent.chat(prompt)
    print(response)


async def main():
    parser = argparse.ArgumentParser(
        description="Claude-powered Game Boy agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--lib", default=None, help="Path to libsameboy.so")
    parser.add_argument("--rom", "-r", required=True, help="ROM file to load")
    parser.add_argument("--model", "-m", default="CGB_E", help="Game Boy model")
    parser.add_argument("--claude-model", default="claude-sonnet-4-20250514",
                        help="Claude model to use")
    parser.add_argument("--base-url", default=None,
                        help="Custom API base URL (e.g., https://chat.dartmouth.edu/api/v1)")
    parser.add_argument("--api-key", default=None,
                        help="API key (or use ANTHROPIC_API_KEY env var)")
    parser.add_argument("--openai-compat", action="store_true",
                        help="Use OpenAI-compatible API (for services like Dartmouth)")
    parser.add_argument("--display", "-d", action="store_true",
                        help="Enable live display on startup")
    parser.add_argument("-p", "--prompt", help="Single prompt (non-interactive)")

    args = parser.parse_args()

    # Check API key
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: API key not provided")
        print("Use --api-key or set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    # Find libsameboy.so
    lib_path = args.lib
    if not lib_path:
        default_path = Path(__file__).parent.parent / "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
        if default_path.exists():
            lib_path = str(default_path)
        else:
            print("Error: Could not find libsameboy.so. Use --lib to specify path.")
            sys.exit(1)

    # Validate ROM
    if not Path(args.rom).exists():
        print(f"Error: ROM file not found: {args.rom}")
        sys.exit(1)

    # Create agent
    agent = ClaudeGameBoyAgent(
        lib_path=lib_path,
        rom_path=args.rom,
        model=args.model,
        claude_model=args.claude_model,
        base_url=args.base_url,
        api_key=api_key,
        use_openai_compat=args.openai_compat
    )

    try:
        print("Connecting to SameBoy MCP server...")
        await agent.connect()
        print(f"Connected! {len(agent.tools)} tools available.")

        # Enable display if requested
        if args.display:
            print("Enabling live display...")
            await agent.call_tool("enable_live_display", {"scale": 2})

        if args.prompt:
            await single_prompt(agent, args.prompt)
        else:
            await interactive_mode(agent)

    finally:
        print("\nDisconnecting...")
        await agent.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
