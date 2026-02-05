#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
Memory Scanner - Find game variables by monitoring memory changes.

This tool helps locate game variables (health, score, position, etc.) by
taking memory snapshots and comparing them after gameplay changes.

Usage:
    python examples/memory_scanner.py <rom_path> [options]

Workflow:
    1. Load the game and play until you have a known value (e.g., 3 lives)
    2. Take a snapshot with 'snap'
    3. Change the value in-game (e.g., lose a life, now 2 lives)
    4. Compare with 'compare' to find addresses that changed
    5. Repeat to narrow down the exact address
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sameboy_mcp.emulator.core import SameBoyEmulator
from sameboy_mcp.emulator.display import is_available as sdl_available


def format_address(addr: int) -> str:
    """Format address with memory region label."""
    if addr < 0x4000:
        return f"0x{addr:04X} (ROM0)"
    elif addr < 0x8000:
        return f"0x{addr:04X} (ROM1)"
    elif addr < 0xA000:
        return f"0x{addr:04X} (VRAM)"
    elif addr < 0xC000:
        return f"0x{addr:04X} (SRAM)"
    elif addr < 0xE000:
        return f"0x{addr:04X} (WRAM)"
    elif addr < 0xFE00:
        return f"0x{addr:04X} (ECHO)"
    elif addr < 0xFEA0:
        return f"0x{addr:04X} (OAM)"
    elif addr < 0xFF00:
        return f"0x{addr:04X} (----)"
    elif addr < 0xFF80:
        return f"0x{addr:04X} (I/O)"
    elif addr < 0xFFFF:
        return f"0x{addr:04X} (HRAM)"
    else:
        return f"0x{addr:04X} (IE)"


def main():
    parser = argparse.ArgumentParser(description="Memory scanner for finding game variables")
    parser.add_argument("rom", help="Path to ROM file")
    parser.add_argument("--model", "-m", default=None, help="Game Boy model")
    parser.add_argument("--scale", type=int, default=2, help="Display scale")
    parser.add_argument("--lib", help="Path to libsameboy.so")

    args = parser.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.exists():
        print(f"Error: ROM not found: {rom_path}")
        sys.exit(1)

    # Auto-detect model
    model = args.model or ("CGB_E" if rom_path.suffix.lower() == '.gbc' else "DMG_B")

    # Initialize
    emu = SameBoyEmulator(args.lib)
    emu.init(model)

    if not emu.load_rom(str(rom_path)):
        print(f"Error: Failed to load ROM")
        sys.exit(1)

    print(f"Loaded: {emu.rom_title}")

    # Enable display if available
    if sdl_available():
        emu.enable_live_display(scale=args.scale)
        print("Live display enabled. Play the game in the window.")
    else:
        print("No display available. Running headless.")

    # State
    snapshot = None
    candidates = None  # Set of candidate addresses

    print("\nCommands:")
    print("  run [frames]  - Run emulation (default: 60 frames)")
    print("  snap          - Take memory snapshot")
    print("  compare       - Compare current memory with snapshot")
    print("  find <value>  - Find addresses containing value")
    print("  filter <val>  - Filter candidates to those with value")
    print("  watch <addr>  - Monitor address for changes")
    print("  read <addr>   - Read memory at address")
    print("  write <addr> <val> - Write value to address")
    print("  candidates    - Show current candidate addresses")
    print("  quit          - Exit")

    while True:
        try:
            cmd = input("\n> ").strip().lower().split()
            if not cmd:
                continue

            if cmd[0] == "quit" or cmd[0] == "q":
                break

            elif cmd[0] == "run":
                frames = int(cmd[1]) if len(cmd) > 1 else 60
                for _ in range(frames):
                    emu.run_frame()
                print(f"Ran {frames} frames (total: {emu.frame_count})")

            elif cmd[0] == "snap":
                emu.take_memory_snapshot()
                snapshot = True
                print("Snapshot taken. Now change the value in-game and use 'compare'")

            elif cmd[0] == "compare":
                if not snapshot:
                    print("No snapshot taken. Use 'snap' first.")
                    continue

                changes = emu.compare_memory_snapshot()
                if not changes:
                    print("No changes detected.")
                    continue

                print(f"Found {len(changes)} changed addresses:")

                # Filter to candidates if we have them
                if candidates is not None:
                    filtered = {a: v for a, v in changes.items() if a in candidates}
                    if filtered:
                        changes = filtered
                        print(f"  (Filtered to {len(changes)} candidates)")

                # Update candidates
                candidates = set(changes.keys())

                # Show changes
                for addr, (old, new) in sorted(changes.items())[:20]:
                    diff = new - old
                    sign = "+" if diff > 0 else ""
                    print(f"  {format_address(addr)}: {old:3d} -> {new:3d} ({sign}{diff})")

                if len(changes) > 20:
                    print(f"  ... and {len(changes) - 20} more")

            elif cmd[0] == "find":
                if len(cmd) < 2:
                    print("Usage: find <value>")
                    continue

                value = int(cmd[1], 0)  # Support hex with 0x prefix
                found = []

                # Search WRAM and HRAM
                for addr in range(0xC000, 0xE000):
                    if emu.read_memory(addr) == value:
                        found.append(addr)
                for addr in range(0xFF80, 0xFFFF):
                    if emu.read_memory(addr) == value:
                        found.append(addr)

                candidates = set(found)
                print(f"Found {len(found)} addresses with value {value}:")
                for addr in found[:20]:
                    print(f"  {format_address(addr)}")
                if len(found) > 20:
                    print(f"  ... and {len(found) - 20} more")

            elif cmd[0] == "filter":
                if len(cmd) < 2:
                    print("Usage: filter <value>")
                    continue
                if candidates is None:
                    print("No candidates. Use 'find' or 'compare' first.")
                    continue

                value = int(cmd[1], 0)
                filtered = {a for a in candidates if emu.read_memory(a) == value}
                print(f"Filtered {len(candidates)} -> {len(filtered)} candidates")
                candidates = filtered

                for addr in sorted(candidates)[:20]:
                    print(f"  {format_address(addr)}: {emu.read_memory(addr)}")

            elif cmd[0] == "watch":
                if len(cmd) < 2:
                    print("Usage: watch <address>")
                    continue

                addr = int(cmd[1], 16) if cmd[1].startswith("0x") else int(cmd[1], 16)
                emu.add_memory_monitors([addr])
                print(f"Watching {format_address(addr)}")

            elif cmd[0] == "read":
                if len(cmd) < 2:
                    print("Usage: read <address> [length]")
                    continue

                addr = int(cmd[1], 16)
                length = int(cmd[2]) if len(cmd) > 2 else 1

                data = emu.read_memory_range(addr, length)
                print(f"{format_address(addr)}:")
                print("  " + " ".join(f"{b:02X}" for b in data))
                if length == 1:
                    print(f"  Decimal: {data[0]}")

            elif cmd[0] == "write":
                if len(cmd) < 3:
                    print("Usage: write <address> <value>")
                    continue

                addr = int(cmd[1], 16)
                value = int(cmd[2], 0)
                emu.write_memory(addr, value)
                print(f"Wrote {value} to {format_address(addr)}")

            elif cmd[0] == "candidates":
                if candidates is None:
                    print("No candidates. Use 'find' or 'compare' first.")
                else:
                    print(f"{len(candidates)} candidates:")
                    for addr in sorted(candidates)[:30]:
                        print(f"  {format_address(addr)}: {emu.read_memory(addr)}")

            else:
                print(f"Unknown command: {cmd[0]}")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")

    # Cleanup
    emu.disable_live_display()
    emu.free()
    print("Done!")


if __name__ == "__main__":
    main()
