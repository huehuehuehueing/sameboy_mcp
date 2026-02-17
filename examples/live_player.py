#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
Live Player - Interactive emulator with live display and audio.

This script loads a ROM with optional save state and presents a live display
window with keyboard controls and audio output. It can run standalone or be
connected to by an AI agent via the MCP server.

Usage:
    python examples/live_player.py <rom_path> [options]

Examples:
    # Basic usage
    python examples/live_player.py roms/game.gb

    # With save state
    python examples/live_player.py roms/game.gb --state saves/game.sav

    # Auto-detect save state (looks for .sav/.state file next to ROM)
    python examples/live_player.py roms/game.gb --auto-state

    # With specific model and scale
    python examples/live_player.py roms/game.gbc --model CGB_E --scale 3

    # Start paused (for agent connection)
    python examples/live_player.py roms/game.gb --paused

    # Disable audio
    python examples/live_player.py roms/game.gb --no-audio

    # Enable MCP server for Claude agent connection
    python examples/live_player.py roms/game.gb --mcp --mcp-port 8765
    # Then connect with: claude_agent.py --server-url http://localhost:8765/sse

Controls:
    Arrow Keys  - D-pad
    Z           - A button
    X           - B button
    Enter       - Start
    Shift       - Select
    Escape      - Quit
    Space       - Pause/Resume
    F1          - Save state to file
    F2          - Load state from file
    M           - Toggle audio mute
    1-4         - Toggle audio channels (Square1, Square2, Wave, Noise)
"""

import argparse
import asyncio
import sys
import time
import threading
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sameboy_mcp.emulator.core import SameBoyEmulator, EmulatorState
from sameboy_mcp.emulator.display import is_available as sdl_available
from sameboy_mcp.emulator.audio import is_available as audio_available, AudioHandler


def find_save_state(rom_path: Path) -> Path | None:
    """Look for a save state file next to the ROM."""
    # Common save state extensions
    extensions = ['.sav', '.state', '.ss0', '.ss1', '.savestate']

    for ext in extensions:
        state_path = rom_path.with_suffix(ext)
        if state_path.exists():
            return state_path

    # Also check for .gb.sav or .gbc.sav pattern
    for ext in extensions:
        state_path = Path(str(rom_path) + ext)
        if state_path.exists():
            return state_path

    return None


def run_with_mcp(rom_path: Path, model: str, scale: int, state_path: Path | None,
                 lib_path: str | None, no_audio: bool, paused: bool,
                 mcp_host: str, mcp_port: int):
    """Run the emulator with MCP server enabled."""
    from mcp.server import FastMCP
    from sameboy_mcp.emulator.thread import EmulatorThread, CommandType
    from sameboy_mcp.tools import memory, cpu, display, state, debug, control, monitor, disasm

    print(f"Loading ROM: {rom_path}")
    print(f"Model: {model}")
    print(f"Scale: {scale}x")
    print(f"MCP Server: http://{mcp_host}:{mcp_port}/sse")

    # Initialize emulator
    try:
        emu = SameBoyEmulator(lib_path)
        emu.init(model)
    except Exception as e:
        print(f"Error initializing emulator: {e}")
        sys.exit(1)

    # Load ROM
    if not emu.load_rom(str(rom_path)):
        print(f"Error: Failed to load ROM: {rom_path}")
        emu.free()
        sys.exit(1)

    print(f"ROM Title: {emu.rom_title}")

    # Load save state if provided
    if state_path:
        try:
            state_data = state_path.read_bytes()
            if emu.load_state(state_data):
                print(f"Loaded save state: {state_path}")
            else:
                print(f"Warning: Failed to load save state")
        except Exception as e:
            print(f"Warning: Error loading save state: {e}")

    # Create emulator thread
    emu_thread = EmulatorThread(emu)

    # Create MCP server
    server = FastMCP("sameboy-live")

    # Register all tools
    memory.register_memory_tools(server, emu_thread)
    cpu.register_cpu_tools(server, emu_thread)
    display.register_display_tools(server, emu_thread)
    state.register_state_tools(server, emu_thread)
    debug.register_debug_tools(server, emu_thread)
    control.register_control_tools(server, emu_thread)
    monitor.register_monitor_tools(server, emu_thread)
    disasm.register_disasm_tools(server, emu_thread)

    # Add load_rom and get_status tools
    @server.tool()
    async def load_rom(path: str) -> dict:
        """Load a Game Boy ROM file."""
        result = emu_thread.send_command(CommandType.LOAD_ROM, {"path": path})
        if result.get("error"):
            return {"error": result["error"]}
        if result.get("success"):
            return {"success": True, "path": path, "title": result.get("title", "Unknown")}
        return {"error": f"Failed to load ROM: {path}"}

    @server.tool()
    async def get_status() -> dict:
        """Get current emulator status."""
        result = emu_thread.send_command(CommandType.GET_STATUS)
        if result.get("error"):
            return {"error": result["error"]}
        return result

    # Start emulator thread
    emu_thread.start()

    # On macOS, SDL2 must create windows on the main thread.
    use_main_thread_sdl = sys.platform == "darwin"
    display_obj = None

    if use_main_thread_sdl:
        from sameboy_mcp.emulator.display import LiveDisplay
        width, height = emu.get_screen_size()
        title = f"SameBoy MCP - {emu.rom_title}" if emu.rom_title else "SameBoy MCP"
        display_obj = LiveDisplay(width=width, height=height, scale=scale, title=title)

        def on_input(key: str, pressed: bool):
            try:
                emu.set_key(key, pressed)
            except ValueError:
                pass

        display_obj.set_input_callback(on_input)
        if not display_obj.init_window():
            print("Warning: Failed to enable live display")
            display_obj = None
        else:
            emu._live_display = display_obj
    else:
        result = emu_thread.send_command(CommandType.ENABLE_LIVE_DISPLAY, {"scale": scale})
        if not result.get("success"):
            print(f"Warning: Failed to enable live display: {result.get('error')}")

    # Initialize audio
    audio_handler = None
    if not no_audio and audio_available():
        try:
            audio_handler = AudioHandler(emu.lib, emu.gb)
            if audio_handler.enable():
                print("Audio: Enabled (48kHz stereo)")
            else:
                audio_handler = None
        except Exception as e:
            print(f"Audio: Error - {e}")

    # Set initial state
    if paused:
        emu_thread.send_command(CommandType.PAUSE)
        print("Started in PAUSED state.")
    else:
        emu_thread.send_command(CommandType.RESUME)

    print(f"\nLive display opened!")
    print("Controls: Arrow keys=D-pad, Z=A, X=B, Enter=Start, Shift=Select")
    print(f"\nMCP Server ready at: http://{mcp_host}:{mcp_port}/sse")
    print(f"Connect with: python examples/claude_agent.py --server-url http://{mcp_host}:{mcp_port}/sse ...")
    print("\nPress Ctrl+C to quit.")

    # Run SSE server
    async def run_sse_server():
        import uvicorn
        app = server.sse_app()
        config = uvicorn.Config(app, host=mcp_host, port=mcp_port, log_level="warning")
        uvicorn_server = uvicorn.Server(config)
        await uvicorn_server.serve()

    try:
        if use_main_thread_sdl and display_obj:
            # macOS: run SSE server in background, SDL event loop on main thread
            server_thread = threading.Thread(
                target=lambda: asyncio.run(run_sse_server()),
                daemon=True
            )
            server_thread.start()

            while display_obj.is_running:
                if not display_obj.pump_events():
                    break
                import time
                time.sleep(0.001)
        else:
            asyncio.run(run_sse_server())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("\nShutting down...")
        if audio_handler:
            audio_handler.disable()
        if display_obj:
            display_obj.cleanup()
            emu._live_display = None
        emu_thread.stop()
        emu.free()
        print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description="Live emulator player with display and audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("rom", help="Path to ROM file (.gb or .gbc)")
    parser.add_argument("--state", "-s", help="Path to save state file to load")
    parser.add_argument("--auto-state", "-a", action="store_true",
                        help="Auto-detect and load save state next to ROM")
    parser.add_argument("--model", "-m", default=None,
                        choices=["DMG_B", "DMG_C", "MGB", "SGB", "SGB2",
                                "CGB_0", "CGB_A", "CGB_B", "CGB_C", "CGB_D", "CGB_E",
                                "AGB", "GBP"],
                        help="Game Boy model (auto-detected if not specified)")
    parser.add_argument("--scale", type=int, default=3, choices=[1, 2, 3, 4],
                        help="Display scale factor (default: 3)")
    parser.add_argument("--paused", "-p", action="store_true",
                        help="Start in paused state (for agent connection)")
    parser.add_argument("--turbo", "-t", action="store_true",
                        help="Start with turbo mode enabled")
    parser.add_argument("--no-audio", action="store_true",
                        help="Disable audio output")
    parser.add_argument("--lib", help="Path to libsameboy.so (optional)")
    parser.add_argument("--mcp", action="store_true",
                        help="Enable MCP server for AI agent connections")
    parser.add_argument("--mcp-port", type=int, default=8765,
                        help="Port for MCP SSE server (default: 8765)")
    parser.add_argument("--mcp-host", default="127.0.0.1",
                        help="Host for MCP SSE server (default: 127.0.0.1)")

    args = parser.parse_args()

    # Validate ROM path
    rom_path = Path(args.rom)
    if not rom_path.exists():
        print(f"Error: ROM file not found: {rom_path}")
        sys.exit(1)

    # Check SDL availability
    if not sdl_available():
        print("Error: PySDL2 is not installed.")
        print("Install with: pip install pysdl2 pysdl2-dll")
        sys.exit(1)

    # Auto-detect model based on file extension if not specified
    if args.model is None:
        if rom_path.suffix.lower() == '.gbc':
            model = "CGB_E"
        else:
            model = "DMG_B"
    else:
        model = args.model

    # Find save state
    state_path = None
    if args.state:
        state_path = Path(args.state)
        if not state_path.exists():
            print(f"Warning: Save state not found: {state_path}")
            state_path = None
    elif args.auto_state:
        state_path = find_save_state(rom_path)
        if state_path:
            print(f"Found save state: {state_path}")

    # If MCP mode is enabled, use the MCP server version
    if args.mcp:
        run_with_mcp(
            rom_path=rom_path,
            model=model,
            scale=args.scale,
            state_path=state_path,
            lib_path=args.lib,
            no_audio=args.no_audio,
            paused=args.paused,
            mcp_host=args.mcp_host,
            mcp_port=args.mcp_port,
        )
        return

    print(f"Loading ROM: {rom_path}")
    print(f"Model: {model}")
    print(f"Scale: {args.scale}x")

    # Initialize emulator
    try:
        emu = SameBoyEmulator(args.lib)
        emu.init(model)
    except Exception as e:
        print(f"Error initializing emulator: {e}")
        sys.exit(1)

    # Load ROM
    if not emu.load_rom(str(rom_path)):
        print(f"Error: Failed to load ROM: {rom_path}")
        emu.free()
        sys.exit(1)

    print(f"ROM Title: {emu.rom_title}")
    print(f"CGB Mode: {emu.is_cgb}")

    # Load save state if provided
    if state_path:
        try:
            state_data = state_path.read_bytes()
            if emu.load_state(state_data):
                print(f"Loaded save state: {state_path}")
            else:
                print(f"Warning: Failed to load save state")
        except Exception as e:
            print(f"Warning: Error loading save state: {e}")

    # Initialize audio
    audio_handler = None
    audio_muted = False
    channel_muted = [False, False, False, False]  # Square1, Square2, Wave, Noise

    if not args.no_audio and audio_available():
        try:
            audio_handler = AudioHandler(emu.lib, emu.gb)
            if audio_handler.enable():
                print("Audio: Enabled (48kHz stereo)")
            else:
                print("Audio: Failed to initialize")
                audio_handler = None
        except Exception as e:
            print(f"Audio: Error - {e}")
            audio_handler = None
    elif args.no_audio:
        print("Audio: Disabled (--no-audio)")
    else:
        print("Audio: SDL2 not available")

    # Enable turbo if requested
    if args.turbo:
        emu.set_turbo(True)
        print("Turbo mode: ON")

    # Enable live display
    # On macOS, SDL2 must create windows on the main thread.
    # We use init_window() + pump_events() instead of the threaded start().
    use_main_thread_sdl = sys.platform == "darwin"

    if use_main_thread_sdl:
        from sameboy_mcp.emulator.display import LiveDisplay

        width, height = emu.get_screen_size()
        title = f"SameBoy MCP - {emu.rom_title}" if emu.rom_title else "SameBoy MCP"
        display = LiveDisplay(width=width, height=height, scale=args.scale, title=title)

        def on_input(key: str, pressed: bool):
            try:
                emu.set_key(key, pressed)
            except ValueError:
                pass

        display.set_input_callback(on_input)

        if not display.init_window():
            print("Error: Failed to enable live display")
            if audio_handler:
                audio_handler.disable()
            emu.free()
            sys.exit(1)

        # Wire vblank to feed frames to display
        emu._live_display = display
    else:
        if not emu.enable_live_display(scale=args.scale):
            print("Error: Failed to enable live display")
            if audio_handler:
                audio_handler.disable()
            emu.free()
            sys.exit(1)

    print(f"\nLive display opened!")
    print("Controls: Arrow keys=D-pad, Z=A, X=B, Enter=Start, Shift=Select")
    print("          Space=Pause, Escape=Quit, F1=Save, F2=Load")
    if audio_handler:
        print("          M=Mute, 1-4=Toggle channels")
    print("\nReady for agent connection via MCP server.")
    if args.paused:
        print("Started in PAUSED state. Press Space to resume.")
        emu.pause()
    else:
        print("Running... Press Space to pause.")
        emu.resume()

    # Main loop
    running = True
    paused = args.paused
    last_frame_time = time.time()
    frame_duration = 1.0 / 60.0  # 60 FPS

    try:
        if use_main_thread_sdl:
            # macOS: SDL events on main thread, emulator runs frames here too
            while running and display.is_running:
                if not paused:
                    emu.run_frame()
                    elapsed = time.time() - last_frame_time
                    if elapsed < frame_duration:
                        time.sleep(frame_duration - elapsed)
                    last_frame_time = time.time()
                else:
                    time.sleep(0.016)

                # Pump SDL events on main thread
                if not display.pump_events():
                    running = False
        else:
            # Linux/other: SDL runs in its own thread
            while running and emu.live_display_enabled:
                if not paused:
                    emu.run_frame()
                    elapsed = time.time() - last_frame_time
                    if elapsed < frame_duration:
                        time.sleep(frame_duration - elapsed)
                    last_frame_time = time.time()
                else:
                    time.sleep(0.016)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    # Cleanup
    print("\nShutting down...")
    if audio_handler:
        audio_handler.disable()
    if use_main_thread_sdl:
        display.cleanup()
        emu._live_display = None
    else:
        emu.disable_live_display()
    emu.free()
    print("Done!")


if __name__ == "__main__":
    main()
