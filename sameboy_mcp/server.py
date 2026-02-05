# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""
SameBoy MCP Server - Game Boy emulator integration for AI agents.

This MCP server provides tools for interacting with a Game Boy emulator,
enabling AI agents to:
- Read/write memory
- Capture screenshots
- Control game input
- Set breakpoints and trace execution
- Save/load states
- Monitor memory changes

Usage:
    python -m sameboy_mcp.server --lib /path/to/libsameboy.so [--rom /path/to/game.gb]

Or via MCP configuration:
    {
        "mcpServers": {
            "sameboy": {
                "command": "python",
                "args": ["-m", "sameboy_mcp.server", "--lib", "/path/to/libsameboy.so"]
            }
        }
    }
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .emulator.core import SameBoyEmulator, EmulatorState
from .emulator.thread import EmulatorThread, CommandType
from .tools import memory, cpu, display, state, debug, control, monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("sameboy-mcp")


def create_server(
    lib_path: str | None = None,
    rom_path: str | None = None,
    boot_rom_path: str | None = None,
    model: str = "CGB_E",
) -> tuple[Server, SameBoyEmulator, EmulatorThread]:
    """
    Create and configure the MCP server with emulator.

    Args:
        lib_path: Path to libsameboy.so
        rom_path: Optional path to ROM file to load
        boot_rom_path: Optional path to boot ROM
        model: Game Boy model (DMG_B, CGB_E, etc.)

    Returns:
        Tuple of (server, emulator, thread)
    """
    # Create MCP server
    server = Server("sameboy-mcp")

    # Initialize emulator
    logger.info(f"Initializing SameBoy emulator (model: {model})")
    emulator = SameBoyEmulator(lib_path)
    emulator.init(model)

    # Load boot ROM if provided
    if boot_rom_path:
        logger.info(f"Loading boot ROM: {boot_rom_path}")
        if not emulator.load_boot_rom(boot_rom_path):
            logger.warning(f"Failed to load boot ROM: {boot_rom_path}")

    # Load ROM if provided
    if rom_path:
        logger.info(f"Loading ROM: {rom_path}")
        if emulator.load_rom(rom_path):
            logger.info(f"ROM loaded: {emulator.rom_title}")
        else:
            logger.error(f"Failed to load ROM: {rom_path}")

    # Create emulator thread
    emu_thread = EmulatorThread(emulator)

    # Register all tool modules
    memory.register_memory_tools(server, emu_thread)
    cpu.register_cpu_tools(server, emu_thread)
    display.register_display_tools(server, emu_thread)
    state.register_state_tools(server, emu_thread)
    debug.register_debug_tools(server, emu_thread)
    control.register_control_tools(server, emu_thread)
    monitor.register_monitor_tools(server, emu_thread)

    # Register server-level tools
    @server.tool()
    async def load_rom(path: str) -> dict:
        """
        Load a Game Boy ROM file.

        Args:
            path: Path to the ROM file (.gb or .gbc)

        Returns:
            ROM information and load status
        """
        result = emu_thread.send_command(CommandType.LOAD_ROM, {"path": path})

        if result.get("error"):
            return {"error": result["error"]}

        if result.get("success"):
            return {
                "success": True,
                "path": path,
                "title": result.get("title", "Unknown"),
            }
        else:
            return {"error": f"Failed to load ROM: {path}"}

    @server.tool()
    async def load_boot_rom(path: str) -> dict:
        """
        Load a Game Boy boot ROM.

        Args:
            path: Path to the boot ROM file

        Returns:
            Load status
        """
        result = emu_thread.send_command(CommandType.LOAD_BOOT_ROM, {"path": path})

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "path": path,
        }

    @server.tool()
    async def get_status() -> dict:
        """
        Get current emulator status.

        Returns:
            Status information including state, frame count, ROM info
        """
        result = emu_thread.send_command(CommandType.GET_STATUS)

        if result.get("error"):
            return {"error": result["error"]}

        return result

    @server.tool()
    async def help() -> dict:
        """
        Get information about available tools.

        Returns:
            List of available tool categories and their purposes
        """
        return {
            "categories": {
                "ROM Management": [
                    "load_rom - Load a Game Boy ROM file",
                    "load_boot_rom - Load a boot ROM",
                    "get_status - Get emulator status",
                ],
                "Memory": [
                    "read_memory - Read bytes from memory",
                    "write_memory - Write a byte to memory",
                    "read_memory_region - Read entire memory region",
                ],
                "CPU": [
                    "get_registers - Get CPU register values",
                    "disassemble - Disassemble instructions",
                ],
                "Display": [
                    "capture_screen - Get screenshot as PNG",
                    "get_sprites - Get sprite/OAM information",
                    "get_screen_info - Get screen dimensions",
                ],
                "Control": [
                    "pause - Pause emulation",
                    "resume - Resume emulation",
                    "step_frame - Execute one frame",
                    "step_instruction - Execute one instruction",
                    "reset - Reset the emulator",
                    "press_key - Press a button",
                    "press_keys - Press multiple buttons",
                    "run_frames - Run multiple frames",
                    "set_turbo - Enable/disable turbo mode",
                ],
                "Save States": [
                    "save_state - Save current state",
                    "load_state - Load a saved state",
                    "list_states - List saved states",
                    "delete_state - Delete a saved state",
                    "export_state - Export state as base64",
                    "import_state - Import state from base64",
                ],
                "Debugging": [
                    "set_breakpoint - Set execution breakpoint",
                    "remove_breakpoint - Remove breakpoint",
                    "list_breakpoints - List all breakpoints",
                    "clear_breakpoints - Clear all breakpoints",
                    "enable_trace - Enable/disable execution tracing",
                    "get_trace - Get execution trace",
                    "clear_trace - Clear trace buffer",
                ],
                "Memory Monitoring": [
                    "monitor_memory - Watch addresses for changes",
                    "stop_monitor - Stop monitoring addresses",
                    "get_memory_changes - Get detected changes",
                    "clear_memory_changes - Clear change log",
                    "take_memory_snapshot - Snapshot RAM state",
                    "compare_memory_snapshot - Compare with snapshot",
                    "find_value - Search memory for value",
                ],
            },
            "keys": ["a", "b", "start", "select", "up", "down", "left", "right"],
            "models": ["DMG_B", "CGB_E", "AGB", "SGB", "SGB2"],
        }

    return server, emulator, emu_thread


async def run_server(
    lib_path: str | None = None,
    rom_path: str | None = None,
    boot_rom_path: str | None = None,
    model: str = "CGB_E",
) -> None:
    """
    Run the MCP server.

    Args:
        lib_path: Path to libsameboy.so
        rom_path: Optional path to ROM file
        boot_rom_path: Optional path to boot ROM
        model: Game Boy model
    """
    server, emulator, emu_thread = create_server(
        lib_path=lib_path,
        rom_path=rom_path,
        boot_rom_path=boot_rom_path,
        model=model,
    )

    # Start emulator thread
    logger.info("Starting emulator thread")
    emu_thread.start()

    try:
        # Run the MCP server
        logger.info("Starting MCP server on stdio")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Cleanup
        logger.info("Shutting down")
        emu_thread.stop()
        emulator.free()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SameBoy MCP Server - Game Boy emulator for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start with default library path
    python -m sameboy_mcp.server

    # Specify library path
    python -m sameboy_mcp.server --lib /path/to/libsameboy.so

    # Load a ROM on startup
    python -m sameboy_mcp.server --lib /path/to/libsameboy.so --rom /path/to/game.gb

    # Use DMG model
    python -m sameboy_mcp.server --model DMG_B
        """,
    )

    parser.add_argument(
        "--lib",
        type=str,
        default=None,
        help="Path to libsameboy.so (searches default locations if not specified)",
    )
    parser.add_argument(
        "--rom",
        type=str,
        default=None,
        help="Path to ROM file to load on startup",
    )
    parser.add_argument(
        "--boot-rom",
        type=str,
        default=None,
        help="Path to boot ROM file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="CGB_E",
        choices=["DMG_B", "DMG_C", "MGB", "SGB", "SGB2", "CGB_0", "CGB_A", "CGB_B", "CGB_C", "CGB_D", "CGB_E", "AGB", "GBP"],
        help="Game Boy model to emulate (default: CGB_E)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(run_server(
            lib_path=args.lib,
            rom_path=args.rom,
            boot_rom_path=args.boot_rom,
            model=args.model,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
