#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
Live Player - Interactive emulator with live display ready for agent connection.

This script loads a ROM with optional save state and presents a live display
window with keyboard controls. It can run standalone or be connected to by
an AI agent via the MCP server.

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
"""

import argparse
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sameboy_mcp.emulator.core import SameBoyEmulator, EmulatorState
from sameboy_mcp.emulator.display import is_available as sdl_available


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


def main():
    parser = argparse.ArgumentParser(
        description="Live emulator player with display ready for agent connection",
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
    parser.add_argument("--lib", help="Path to libsameboy.so (optional)")

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

    # Enable turbo if requested
    if args.turbo:
        emu.set_turbo(True)
        print("Turbo mode: ON")

    # Enable live display
    title = f"SameBoy - {emu.rom_title}"
    if not emu.enable_live_display(scale=args.scale):
        print("Error: Failed to enable live display")
        emu.free()
        sys.exit(1)

    print(f"\nLive display opened!")
    print("Controls: Arrow keys=D-pad, Z=A, X=B, Enter=Start, Shift=Select")
    print("          Space=Pause, Escape=Quit, F1=Save, F2=Load")
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
        while running and emu.live_display_enabled:
            current_time = time.time()

            if not paused:
                # Run frame
                emu.run_frame()

                # Frame timing
                elapsed = time.time() - last_frame_time
                if elapsed < frame_duration:
                    time.sleep(frame_duration - elapsed)
                last_frame_time = time.time()
            else:
                # When paused, sleep to prevent CPU spinning
                time.sleep(0.016)

            # Check for special keys via SDL events (handled in display thread)
            # Note: Game controls are handled by the display's input callback

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    # Cleanup
    print("\nShutting down...")
    emu.disable_live_display()
    emu.free()
    print("Done!")


if __name__ == "__main__":
    main()
