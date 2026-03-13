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

from mcp.server import FastMCP

from .emulator.core import SameBoyEmulator, EmulatorState
from .emulator.thread import EmulatorThread, CommandType
from .tools import memory, cpu, display, state, debug, control, monitor, disasm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("sameboy-mcp")
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)


def create_server(
    lib_path: str | None = None,
    rom_path: str | None = None,
    boot_rom_path: str | None = None,
    model: str = "CGB_E",
) -> tuple[FastMCP, SameBoyEmulator, EmulatorThread]:
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
    server = FastMCP("sameboy-mcp")

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

    # Register all built-in tool modules
    memory.register_memory_tools(server, emu_thread)
    cpu.register_cpu_tools(server, emu_thread)
    display.register_display_tools(server, emu_thread)
    state.register_state_tools(server, emu_thread)
    debug.register_debug_tools(server, emu_thread)
    control.register_control_tools(server, emu_thread)
    monitor.register_monitor_tools(server, emu_thread)
    disasm.register_disasm_tools(server, emu_thread)

    # Plugins are loaded later by run_server() so the dashboard can be passed in.
    # For direct callers of create_server(), use load_plugins() after.

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
                    "disassemble - Disassemble at current PC",
                ],
                "ROM Disassembly": [
                    "disassemble_rom - Disassemble ROM range",
                    "disassemble_function - Disassemble a function",
                    "get_rom_header - Get ROM metadata",
                    "find_functions - Find function entry points",
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
                    "set_rendering_disabled - Skip pixel rendering for speed",
                ],
                "Save States": [
                    "save_state - Save current state",
                    "load_state - Load a saved state",
                    "list_states - List saved states",
                    "delete_state - Delete a saved state",
                    "export_state - Export state as base64",
                    "import_state - Import state from base64",
                ],
                "Battery (Game Saves)": [
                    "save_battery - Save SRAM to .sav file",
                    "load_battery - Load SRAM from .sav file",
                ],
                "Rewind": [
                    "enable_rewind - Set rewind buffer length",
                    "rewind_pop - Step back one frame",
                    "rewind_reset - Clear rewind buffer",
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


def install_dashboard_hooks(server: FastMCP, dashboard_server) -> None:
    """Wrap all MCP tool calls to support dashboard prompt injection and logging.

    When a dashboard is active:
    - Pending prompt injections are drained and appended to tool responses
    - If verbose mode is enabled, tool calls are logged to the dashboard
    """
    import functools
    import json as _json

    tm = server._tool_manager
    original_call_tool = tm.call_tool

    @functools.wraps(original_call_tool)
    async def wrapped_call_tool(name, arguments, context=None, convert_result=False):
        result = await original_call_tool(name, arguments, context=context, convert_result=convert_result)

        # Log tool call to dashboard if verbose
        if dashboard_server._verbose:
            try:
                result_summary = str(result)
                if len(result_summary) > 200:
                    result_summary = result_summary[:200] + "..."
            except Exception:
                result_summary = None
            dashboard_server.emit_tool_call(name, arguments, result_summary)

        # Run post-tool hooks (e.g. refresh dashboard text after load_state)
        for hook in dashboard_server.get_post_tool_hooks(name):
            try:
                hook()
            except Exception:
                pass

        # Drain pending prompt injections and piggy-back on response
        prompts = dashboard_server.drain_prompts()
        if prompts:
            # Append dashboard prompts to the tool result
            # Result can be a list of ContentBlock or a dict
            if isinstance(result, dict):
                result["_dashboard_prompts"] = prompts
            elif isinstance(result, (list, tuple)):
                # For structured content, wrap in a text content block
                from mcp.types import TextContent
                prompt_text = "\n".join(
                    f"[DASHBOARD MESSAGE]: {p}" for p in prompts
                )
                result = list(result) + [TextContent(type="text", text=prompt_text)]
            else:
                # Fallback: wrap result
                from mcp.types import TextContent
                prompt_text = "\n".join(
                    f"[DASHBOARD MESSAGE]: {p}" for p in prompts
                )
                result = [result, TextContent(type="text", text=prompt_text)]

        return result

    tm.call_tool = wrapped_call_tool


def load_plugins(
    server: FastMCP,
    emu_thread: EmulatorThread,
    plugins: list[str] | None = None,
    dashboard_server=None,
) -> None:
    """Load plugin modules and register their tools."""
    import importlib
    import inspect
    for module_path in (plugins or []):
        try:
            mod = importlib.import_module(module_path)
            sig = inspect.signature(mod.register_tools)
            if "dashboard" in sig.parameters:
                mod.register_tools(server, emu_thread, dashboard=dashboard_server)
            else:
                mod.register_tools(server, emu_thread)
            logger.info(f"Loaded plugin: {module_path}")
        except Exception:
            logger.exception(f"Failed to load plugin: {module_path}")


async def run_server(
    lib_path: str | None = None,
    rom_path: str | None = None,
    boot_rom_path: str | None = None,
    model: str = "CGB_E",
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
    plugins: list[str] | None = None,
    dashboard: bool = False,
    dashboard_port: int = 8766,
    dashboard_verbose: bool = False,
) -> None:
    """
    Run the MCP server.

    Args:
        lib_path: Path to libsameboy.so
        rom_path: Optional path to ROM file
        boot_rom_path: Optional path to boot ROM
        model: Game Boy model
        transport: Transport type ("stdio" or "sse")
        host: Host to bind SSE server (default: 127.0.0.1)
        port: Port for SSE server (default: 8765)
        plugins: Optional list of plugin module paths
        dashboard: Enable web dashboard
        dashboard_port: Port for standalone dashboard (stdio mode only)
        dashboard_verbose: Log MCP tool calls to dashboard agent log
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

    dashboard_server = None

    try:
        if transport == "sse":
            # Run the MCP server with SSE transport using uvicorn
            import uvicorn
            logger.info(f"Starting MCP server on SSE at http://{host}:{port}/sse")
            print(f"MCP Server running at: http://{host}:{port}/sse", file=sys.stderr)
            print(f"Connect with: --server-url http://{host}:{port}/sse", file=sys.stderr)
            app = server.sse_app()

            if dashboard:
                from .dashboard import DashboardServer
                dashboard_server = DashboardServer(emu_thread, verbose=dashboard_verbose)
                dashboard_server.mount(app)
                dashboard_server.start()
                print(f"Dashboard: http://{host}:{port}/dashboard/", file=sys.stderr)

            # Load plugins after dashboard so they can register snapshot hooks
            load_plugins(server, emu_thread, plugins, dashboard_server)

            if dashboard_server:
                install_dashboard_hooks(server, dashboard_server)

            config = uvicorn.Config(app, host=host, port=port, log_level="warning")
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
        else:
            # Run the MCP server with stdio transport
            logger.info("Starting MCP server on stdio")

            if dashboard:
                import uvicorn
                from .dashboard import DashboardServer
                dashboard_server = DashboardServer(emu_thread, verbose=dashboard_verbose)
                dash_app = dashboard_server.create_app()

                dash_config = uvicorn.Config(
                    dash_app, host=host, port=dashboard_port, log_level="warning"
                )
                dash_uvicorn = uvicorn.Server(dash_config)
                # Run dashboard server in background task
                dash_task = asyncio.create_task(dash_uvicorn.serve())
                print(f"Dashboard: http://{host}:{dashboard_port}/dashboard/", file=sys.stderr)

            # Load plugins after dashboard so they can register snapshot hooks
            load_plugins(server, emu_thread, plugins, dashboard_server)

            if dashboard_server:
                install_dashboard_hooks(server, dashboard_server)

            await server.run_stdio_async()
    finally:
        # Cleanup
        logger.info("Shutting down")
        if dashboard_server:
            await dashboard_server.stop()
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
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Use SSE transport instead of stdio (allows external connections)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind SSE server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for SSE server (default: 8765)",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Python module path providing register_tools(server, emu_thread). Repeatable.",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Enable web dashboard for live emulator monitoring",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8766,
        help="Port for standalone dashboard in stdio mode (default: 8766)",
    )
    parser.add_argument(
        "--dashboard-verbose",
        action="store_true",
        help="Log all MCP tool calls to the dashboard agent log",
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
            transport="sse" if args.sse else "stdio",
            host=args.host,
            port=args.port,
            plugins=args.plugin,
            dashboard=args.dashboard,
            dashboard_port=args.dashboard_port,
            dashboard_verbose=args.dashboard_verbose,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
