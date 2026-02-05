#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
Reference MCP Client - Interactive client for the SameBoy MCP Server.

This script demonstrates how to connect to and interact with the SameBoy
MCP server programmatically. It provides both an interactive REPL and
can be used as a library for building AI agents.

Usage:
    python examples/mcp_client.py [options]

Examples:
    # Interactive mode
    python examples/mcp_client.py --rom roms/game.gb

    # Run a script
    python examples/mcp_client.py --rom roms/game.gb --script script.txt

    # One-shot command
    python examples/mcp_client.py --rom roms/game.gb -c "run_frames 60"
"""

import argparse
import asyncio
import json
import base64
import sys
from pathlib import Path
from typing import Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession


class SameBoyMCPClient:
    """
    Reference MCP client for the SameBoy emulator.

    Provides a high-level interface to all MCP tools with
    convenient Python methods.
    """

    def __init__(self, lib_path: str, rom_path: str | None = None, model: str = "CGB_E"):
        """
        Initialize the MCP client.

        Args:
            lib_path: Path to libsameboy.so
            rom_path: Optional path to ROM to load on startup
            model: Game Boy model (DMG_B, CGB_E, etc.)
        """
        self.lib_path = lib_path
        self.rom_path = rom_path
        self.model = model
        self._session: ClientSession | None = None
        self._read = None
        self._write = None
        self._client_ctx = None
        self._session_ctx = None

    async def connect(self) -> None:
        """Connect to the MCP server."""
        args = [
            '-m', 'sameboy_mcp.server',
            '--lib', self.lib_path,
            '--model', self.model,
        ]
        if self.rom_path:
            args.extend(['--rom', self.rom_path])

        server_params = StdioServerParameters(
            command='python',
            args=args,
            cwd=str(Path(__file__).parent.parent)
        )

        self._client_ctx = stdio_client(server_params)
        self._read, self._write = await self._client_ctx.__aenter__()
        self._session_ctx = ClientSession(self._read, self._write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
        self._session = None

    async def call_tool(self, name: str, args: dict | None = None) -> Any:
        """
        Call an MCP tool and return the parsed result.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Parsed JSON result or raw text
        """
        if not self._session:
            raise RuntimeError("Not connected to MCP server")

        result = await self._session.call_tool(name, args or {})
        if result.content:
            text = result.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return None

    async def list_tools(self) -> list[dict]:
        """List all available tools."""
        if not self._session:
            raise RuntimeError("Not connected to MCP server")
        result = await self._session.list_tools()
        return [{"name": t.name, "description": t.description} for t in result.tools]

    # ============ ROM Management ============

    async def load_rom(self, path: str) -> dict:
        """Load a ROM file."""
        return await self.call_tool('load_rom', {'path': path})

    async def get_status(self) -> dict:
        """Get emulator status."""
        return await self.call_tool('get_status')

    # ============ Execution Control ============

    async def pause(self) -> dict:
        """Pause emulation."""
        return await self.call_tool('pause')

    async def resume(self) -> dict:
        """Resume emulation."""
        return await self.call_tool('resume')

    async def reset(self) -> dict:
        """Reset the emulator."""
        return await self.call_tool('reset')

    async def run_frames(self, count: int) -> dict:
        """Run emulation for N frames."""
        return await self.call_tool('run_frames', {'count': count})

    async def step_frame(self) -> dict:
        """Execute one frame."""
        return await self.call_tool('step_frame')

    async def step_instruction(self) -> dict:
        """Execute one CPU instruction."""
        return await self.call_tool('step_instruction')

    # ============ Input ============

    async def press_key(self, key: str, frames: int = 1) -> dict:
        """Press a button for N frames."""
        return await self.call_tool('press_key', {'key': key, 'frames': frames})

    async def press_keys(self, keys: list[str], frames: int = 1) -> dict:
        """Press multiple buttons simultaneously."""
        return await self.call_tool('press_keys', {'keys': keys, 'frames': frames})

    async def set_key(self, key: str, pressed: bool) -> dict:
        """Set button state without advancing frames."""
        return await self.call_tool('set_key', {'key': key, 'pressed': pressed})

    # ============ Memory ============

    async def read_memory(self, address: int, length: int = 1) -> dict:
        """Read memory bytes."""
        return await self.call_tool('read_memory', {'address': address, 'length': length})

    async def write_memory(self, address: int, value: int) -> dict:
        """Write a byte to memory."""
        return await self.call_tool('write_memory', {'address': address, 'value': value})

    async def read_memory_region(self, region: str) -> dict:
        """Read an entire memory region."""
        return await self.call_tool('read_memory_region', {'region': region})

    # ============ CPU ============

    async def get_registers(self) -> dict:
        """Get CPU registers."""
        return await self.call_tool('get_registers')

    async def disassemble(self, address: int | None = None, count: int = 10) -> dict:
        """Disassemble instructions."""
        args = {'count': count}
        if address is not None:
            args['address'] = address
        return await self.call_tool('disassemble', args)

    # ============ Display ============

    async def capture_screen(self, format: str = "png") -> dict:
        """Capture the screen."""
        return await self.call_tool('capture_screen', {'format': format})

    async def save_screenshot(self, path: str) -> None:
        """Capture screen and save to file."""
        result = await self.capture_screen('png')
        if 'data_base64' in result:
            data = base64.b64decode(result['data_base64'])
            Path(path).write_bytes(data)

    async def get_sprites(self) -> dict:
        """Get sprite/OAM information."""
        return await self.call_tool('get_sprites')

    # ============ Save States ============

    async def save_state(self, name: str | None = None) -> dict:
        """Save current state."""
        args = {}
        if name:
            args['name'] = name
        return await self.call_tool('save_state', args)

    async def load_state(self, state_id: str) -> dict:
        """Load a saved state."""
        return await self.call_tool('load_state', {'state_id': state_id})

    async def list_states(self) -> dict:
        """List saved states."""
        return await self.call_tool('list_states')

    # ============ Debugging ============

    async def set_breakpoint(self, address: int) -> dict:
        """Set a breakpoint."""
        return await self.call_tool('set_breakpoint', {'address': address})

    async def remove_breakpoint(self, address: int) -> dict:
        """Remove a breakpoint."""
        return await self.call_tool('remove_breakpoint', {'address': address})

    async def list_breakpoints(self) -> dict:
        """List all breakpoints."""
        return await self.call_tool('list_breakpoints')

    async def enable_trace(self, enabled: bool = True, limit: int = 10000) -> dict:
        """Enable/disable execution tracing."""
        return await self.call_tool('enable_trace', {'enabled': enabled, 'limit': limit})

    async def get_trace(self, count: int = 100) -> dict:
        """Get execution trace."""
        return await self.call_tool('get_trace', {'count': count})

    # ============ Memory Monitoring ============

    async def monitor_memory(self, addresses: list[int]) -> dict:
        """Start monitoring memory addresses."""
        return await self.call_tool('monitor_memory', {'addresses': addresses})

    async def get_memory_changes(self, since_frame: int | None = None) -> dict:
        """Get detected memory changes."""
        args = {}
        if since_frame is not None:
            args['since_frame'] = since_frame
        return await self.call_tool('get_memory_changes', args)

    async def take_memory_snapshot(self) -> dict:
        """Take a memory snapshot."""
        return await self.call_tool('take_memory_snapshot')

    async def compare_memory_snapshot(self) -> dict:
        """Compare current memory with snapshot."""
        return await self.call_tool('compare_memory_snapshot')

    async def find_value(self, value: int, size: int = 1, region: str = "ram") -> dict:
        """Search memory for a value."""
        return await self.call_tool('find_value', {'value': value, 'size': size, 'region': region})

    # ============ ROM Disassembly ============

    async def disassemble_rom(self, start: int = 0, end: int | None = None,
                              max_instructions: int = 1000) -> dict:
        """Disassemble ROM range."""
        args = {'start': start, 'max_instructions': max_instructions}
        if end is not None:
            args['end'] = end
        return await self.call_tool('disassemble_rom', args)

    async def disassemble_function(self, address: int, max_size: int = 256) -> dict:
        """Disassemble a function."""
        return await self.call_tool('disassemble_function',
                                    {'address': address, 'max_size': max_size})

    async def get_rom_header(self) -> dict:
        """Get ROM header information."""
        return await self.call_tool('get_rom_header')

    async def find_functions(self) -> dict:
        """Find function entry points in ROM."""
        return await self.call_tool('find_functions')

    # ============ Live Display ============

    async def enable_live_display(self, scale: int = 2) -> dict:
        """Enable live display window."""
        return await self.call_tool('enable_live_display', {'scale': scale})

    async def disable_live_display(self) -> dict:
        """Disable live display window."""
        return await self.call_tool('disable_live_display')

    async def set_user_input(self, enabled: bool) -> dict:
        """Enable/disable user keyboard input on live display."""
        return await self.call_tool('set_user_input', {'enabled': enabled})


async def interactive_repl(client: SameBoyMCPClient):
    """Run an interactive REPL session."""
    print("\nSameBoy MCP Client - Interactive Mode")
    print("Type 'help' for commands, 'quit' to exit\n")

    commands = {
        'help': 'Show this help message',
        'status': 'Get emulator status',
        'run [frames]': 'Run N frames (default: 60)',
        'step': 'Step one frame',
        'pause': 'Pause emulation',
        'resume': 'Resume emulation',
        'reset': 'Reset emulator',
        'press <key> [frames]': 'Press button (a/b/start/select/up/down/left/right)',
        'regs': 'Show CPU registers',
        'read <addr> [len]': 'Read memory (hex address)',
        'write <addr> <val>': 'Write memory (hex address, hex value)',
        'disasm [addr] [count]': 'Disassemble instructions',
        'screen [file]': 'Capture screenshot',
        'save [name]': 'Save state',
        'load <id>': 'Load state',
        'states': 'List saved states',
        'bp <addr>': 'Set breakpoint (hex address)',
        'bplist': 'List breakpoints',
        'bpclear': 'Clear all breakpoints',
        'find <value>': 'Find value in memory',
        'snap': 'Take memory snapshot',
        'diff': 'Compare with snapshot',
        'header': 'Show ROM header',
        'funcs': 'Find functions in ROM',
        'display [scale]': 'Enable live display',
        'nodisplay': 'Disable live display',
        'tools': 'List all MCP tools',
        'call <tool> [json_args]': 'Call any tool directly',
        'quit': 'Exit',
    }

    while True:
        try:
            line = input("sameboy> ").strip()
            if not line:
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == 'quit' or cmd == 'q':
                break

            elif cmd == 'help':
                print("\nCommands:")
                for c, desc in commands.items():
                    print(f"  {c:25} {desc}")
                print()

            elif cmd == 'status':
                result = await client.get_status()
                print(f"State: {result.get('state')}")
                print(f"ROM: {result.get('rom_title')}")
                print(f"Frame: {result.get('frame_count')}")
                print(f"CGB: {result.get('is_cgb')}")

            elif cmd == 'run':
                frames = int(args) if args else 60
                result = await client.run_frames(frames)
                print(f"Ran {result.get('frames_run')} frames")
                if result.get('breakpoint_hit'):
                    print("Breakpoint hit!")

            elif cmd == 'step':
                result = await client.step_frame()
                print(f"Frame: {result.get('frame')}")

            elif cmd == 'pause':
                await client.pause()
                print("Paused")

            elif cmd == 'resume':
                await client.resume()
                print("Resumed")

            elif cmd == 'reset':
                await client.reset()
                print("Reset")

            elif cmd == 'press':
                parts = args.split()
                key = parts[0] if parts else 'a'
                frames = int(parts[1]) if len(parts) > 1 else 1
                await client.press_key(key, frames)
                print(f"Pressed {key} for {frames} frames")

            elif cmd == 'regs':
                result = await client.get_registers()
                print("16-bit registers:")
                for name, val in result.get('16-bit', {}).items():
                    print(f"  {name}: {val}")
                print("Flags:", result.get('flags'))

            elif cmd == 'read':
                parts = args.split()
                addr = int(parts[0], 16) if parts else 0xC000
                length = int(parts[1]) if len(parts) > 1 else 16
                result = await client.read_memory(addr, length)
                print(f"{result.get('address')}: {result.get('hex')}")

            elif cmd == 'write':
                parts = args.split()
                if len(parts) >= 2:
                    addr = int(parts[0], 16)
                    val = int(parts[1], 16)
                    await client.write_memory(addr, val)
                    print(f"Wrote 0x{val:02X} to 0x{addr:04X}")
                else:
                    print("Usage: write <addr> <value>")

            elif cmd == 'disasm':
                parts = args.split()
                addr = int(parts[0], 16) if parts else None
                count = int(parts[1]) if len(parts) > 1 else 10
                result = await client.disassemble(addr, count)
                print(result.get('disassembly', 'N/A'))

            elif cmd == 'screen':
                path = args if args else 'screenshot.png'
                await client.save_screenshot(path)
                print(f"Saved to {path}")

            elif cmd == 'save':
                name = args if args else None
                result = await client.save_state(name)
                print(f"State saved: {result.get('state_id')}")

            elif cmd == 'load':
                if args:
                    result = await client.load_state(args)
                    print(f"Loaded state: {result.get('state_id')}")
                else:
                    print("Usage: load <state_id>")

            elif cmd == 'states':
                result = await client.list_states()
                states = result.get('states', [])
                if states:
                    for s in states:
                        print(f"  {s.get('state_id')}: {s.get('name', 'unnamed')} (frame {s.get('frame')})")
                else:
                    print("No saved states")

            elif cmd == 'bp':
                if args:
                    addr = int(args, 16)
                    await client.set_breakpoint(addr)
                    print(f"Breakpoint set at 0x{addr:04X}")
                else:
                    print("Usage: bp <address>")

            elif cmd == 'bplist':
                result = await client.list_breakpoints()
                bps = result.get('breakpoints', [])
                if bps:
                    for bp in bps:
                        status = "enabled" if bp.get('enabled') else "disabled"
                        print(f"  {bp.get('address')}: {status}, hits: {bp.get('hit_count')}")
                else:
                    print("No breakpoints")

            elif cmd == 'bpclear':
                await client.call_tool('clear_breakpoints')
                print("Breakpoints cleared")

            elif cmd == 'find':
                if args:
                    value = int(args, 0)
                    result = await client.find_value(value)
                    matches = result.get('matches', [])
                    print(f"Found {result.get('match_count')} matches:")
                    for addr in matches[:20]:
                        print(f"  {addr}")
                    if len(matches) > 20:
                        print(f"  ... and {len(matches) - 20} more")
                else:
                    print("Usage: find <value>")

            elif cmd == 'snap':
                await client.take_memory_snapshot()
                print("Snapshot taken")

            elif cmd == 'diff':
                result = await client.compare_memory_snapshot()
                changes = result.get('changes', {})
                if changes:
                    print(f"Found {len(changes)} changes:")
                    for addr, vals in list(changes.items())[:20]:
                        print(f"  {addr}: {vals.get('old')} -> {vals.get('new')}")
                else:
                    print("No changes detected")

            elif cmd == 'header':
                result = await client.get_rom_header()
                for key, val in result.items():
                    print(f"  {key}: {val}")

            elif cmd == 'funcs':
                result = await client.find_functions()
                funcs = result.get('functions', [])
                print(f"Found {result.get('function_count')} functions:")
                for f in funcs[:30]:
                    print(f"  {f.get('address')}: {f.get('name')} - {f.get('first_instruction')}")

            elif cmd == 'display':
                scale = int(args) if args else 2
                result = await client.enable_live_display(scale)
                if result.get('success'):
                    print(f"Live display enabled ({scale}x)")
                else:
                    print(f"Failed: {result.get('error', 'unknown')}")

            elif cmd == 'nodisplay':
                await client.disable_live_display()
                print("Live display disabled")

            elif cmd == 'tools':
                tools = await client.list_tools()
                print(f"\n{len(tools)} tools available:")
                for t in tools:
                    print(f"  {t['name']}")
                print()

            elif cmd == 'call':
                parts = args.split(None, 1)
                if parts:
                    tool_name = parts[0]
                    tool_args = json.loads(parts[1]) if len(parts) > 1 else {}
                    result = await client.call_tool(tool_name, tool_args)
                    print(json.dumps(result, indent=2))
                else:
                    print("Usage: call <tool_name> [json_args]")

            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")


async def run_script(client: SameBoyMCPClient, script_path: str):
    """Run commands from a script file."""
    with open(script_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                print(f"> {line}")
                # Parse and execute command
                # (simplified - would need full command parsing)
                parts = line.split()
                if parts:
                    result = await client.call_tool(parts[0],
                        json.loads(parts[1]) if len(parts) > 1 else {})
                    print(json.dumps(result, indent=2))


async def main():
    parser = argparse.ArgumentParser(
        description="Reference MCP client for SameBoy emulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--lib", default=None,
                        help="Path to libsameboy.so")
    parser.add_argument("--rom", "-r", help="ROM file to load")
    parser.add_argument("--model", "-m", default="CGB_E",
                        help="Game Boy model (default: CGB_E)")
    parser.add_argument("--script", "-s", help="Run commands from script file")
    parser.add_argument("-c", "--command", help="Run single command and exit")

    args = parser.parse_args()

    # Find libsameboy.so
    lib_path = args.lib
    if not lib_path:
        default_path = Path(__file__).parent.parent / "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
        if default_path.exists():
            lib_path = str(default_path)
        else:
            print("Error: Could not find libsameboy.so. Use --lib to specify path.")
            sys.exit(1)

    # Create client
    client = SameBoyMCPClient(lib_path, args.rom, args.model)

    try:
        print("Connecting to SameBoy MCP server...")
        await client.connect()
        print("Connected!")

        if args.command:
            # Single command mode
            parts = args.command.split(None, 1)
            tool_name = parts[0]
            tool_args = json.loads(parts[1]) if len(parts) > 1 else {}
            result = await client.call_tool(tool_name, tool_args)
            print(json.dumps(result, indent=2))

        elif args.script:
            # Script mode
            await run_script(client, args.script)

        else:
            # Interactive mode
            await interactive_repl(client)

    finally:
        print("\nDisconnecting...")
        await client.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
