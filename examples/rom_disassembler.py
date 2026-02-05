#!/usr/bin/env python3
# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""
ROM Disassembler - Interactive disassembly tool for Game Boy ROMs.

This tool provides a command-line interface for disassembling and analyzing
Game Boy ROM files. Useful for reverse engineering, understanding game logic,
and exploring ROM structure.

Usage:
    python examples/rom_disassembler.py <rom_path> [options]

Examples:
    # Disassemble entire ROM to file
    python examples/rom_disassembler.py game.gb --output game.asm

    # Interactive mode
    python examples/rom_disassembler.py game.gb --interactive

    # Show header and entry point
    python examples/rom_disassembler.py game.gb --header
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sameboy_mcp.emulator.disasm import Disassembler, disassemble_rom


def print_header(disasm: Disassembler) -> None:
    """Print ROM header information."""
    header = disasm.get_rom_header()
    print("\n=== ROM Header ===")
    for key, value in header.items():
        print(f"  {key}: {value}")
    print()


def print_function(disasm: Disassembler, address: int, max_size: int = 256) -> None:
    """Print disassembly of a function."""
    instructions = disasm.disassemble_function(address, max_size)
    print(f"\n=== Function at 0x{address:04X} ===")
    for inst in instructions:
        print(str(inst))
    print()


def print_range(disasm: Disassembler, start: int, end: int) -> None:
    """Print disassembly of an address range."""
    print(f"\n=== 0x{start:04X} - 0x{end:04X} ===")
    for inst in disasm.disassemble_range(start, end):
        print(str(inst))
    print()


def find_functions(disasm: Disassembler, scan_start: int = 0x0150, scan_end: int | None = None) -> list[int]:
    """Find likely function entry points."""
    if scan_end is None:
        scan_end = disasm.size

    # PUSH opcodes (common function starts)
    push_opcodes = {0xC5, 0xD5, 0xE5, 0xF5}

    # Find CALL targets
    call_targets = set()
    for inst in disasm.disassemble_range(scan_start, scan_end):
        if inst.is_call and inst.jump_target:
            if 0 <= inst.jump_target < disasm.size:
                call_targets.add(inst.jump_target)

    return sorted(call_targets)


def interactive_mode(disasm: Disassembler) -> None:
    """Run interactive disassembly session."""
    print("\n=== Interactive Disassembly Mode ===")
    print("Commands:")
    print("  header          - Show ROM header")
    print("  range <start> <end> - Disassemble address range")
    print("  func <address>  - Disassemble function at address")
    print("  find            - Find function entry points")
    print("  read <address> [len] - Read bytes at address")
    print("  search <hex>    - Search for byte pattern")
    print("  quit            - Exit")
    print()

    while True:
        try:
            cmd = input("> ").strip().split()
            if not cmd:
                continue

            if cmd[0] == "quit" or cmd[0] == "q":
                break

            elif cmd[0] == "header":
                print_header(disasm)

            elif cmd[0] == "range":
                if len(cmd) < 3:
                    print("Usage: range <start> <end>")
                    continue
                start = int(cmd[1], 16) if cmd[1].startswith("0x") else int(cmd[1], 16)
                end = int(cmd[2], 16) if cmd[2].startswith("0x") else int(cmd[2], 16)
                print_range(disasm, start, end)

            elif cmd[0] == "func":
                if len(cmd) < 2:
                    print("Usage: func <address>")
                    continue
                addr = int(cmd[1], 16) if cmd[1].startswith("0x") else int(cmd[1], 16)
                max_size = int(cmd[2]) if len(cmd) > 2 else 256
                print_function(disasm, addr, max_size)

            elif cmd[0] == "find":
                print("\nSearching for function entry points...")
                funcs = find_functions(disasm)
                print(f"Found {len(funcs)} potential functions:")
                for i, addr in enumerate(funcs[:50]):  # Limit display
                    inst = disasm.disassemble_one(addr)
                    print(f"  0x{addr:04X}: {inst.mnemonic} {inst.operands}")
                if len(funcs) > 50:
                    print(f"  ... and {len(funcs) - 50} more")
                print()

            elif cmd[0] == "read":
                if len(cmd) < 2:
                    print("Usage: read <address> [length]")
                    continue
                addr = int(cmd[1], 16)
                length = int(cmd[2]) if len(cmd) > 2 else 16
                data = disasm.rom[addr:addr + length]
                hex_str = " ".join(f"{b:02X}" for b in data)
                print(f"0x{addr:04X}: {hex_str}")

            elif cmd[0] == "search":
                if len(cmd) < 2:
                    print("Usage: search <hex_bytes>")
                    continue
                pattern = bytes.fromhex(cmd[1])
                results = []
                for i in range(len(disasm.rom) - len(pattern) + 1):
                    if disasm.rom[i:i + len(pattern)] == pattern:
                        results.append(i)
                print(f"Found {len(results)} matches:")
                for addr in results[:20]:
                    print(f"  0x{addr:04X}")
                if len(results) > 20:
                    print(f"  ... and {len(results) - 20} more")

            else:
                print(f"Unknown command: {cmd[0]}")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Game Boy ROM Disassembler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("rom", help="Path to ROM file (.gb or .gbc)")
    parser.add_argument("--output", "-o", help="Output file for disassembly")
    parser.add_argument("--header", "-H", action="store_true", help="Show ROM header")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--start", type=str, default="0x0000", help="Start address (hex)")
    parser.add_argument("--end", type=str, help="End address (hex)")
    parser.add_argument("--func", type=str, help="Disassemble function at address (hex)")
    parser.add_argument("--find-functions", "-f", action="store_true", help="Find function entry points")

    args = parser.parse_args()

    # Validate ROM path
    rom_path = Path(args.rom)
    if not rom_path.exists():
        print(f"Error: ROM file not found: {rom_path}")
        sys.exit(1)

    # Load ROM
    print(f"Loading: {rom_path}")
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    print(f"ROM size: {len(rom_data)} bytes ({len(rom_data) // 1024}KB)")

    disasm = Disassembler(rom_data)

    # Show header if requested
    if args.header:
        print_header(disasm)

    # Find functions if requested
    if args.find_functions:
        print("\nSearching for function entry points...")
        funcs = find_functions(disasm)
        print(f"Found {len(funcs)} potential functions:")
        for addr in funcs[:100]:
            inst = disasm.disassemble_one(addr)
            print(f"  0x{addr:04X}: {inst.mnemonic} {inst.operands}")
        if len(funcs) > 100:
            print(f"  ... and {len(funcs) - 100} more")
        print()

    # Disassemble function if requested
    if args.func:
        addr = int(args.func, 16)
        print_function(disasm, addr)

    # Interactive mode
    if args.interactive:
        interactive_mode(disasm)
        return

    # Full disassembly to file
    if args.output:
        print(f"Disassembling to {args.output}...")
        result = disassemble_rom(str(rom_path), args.output)
        print(f"Done! Wrote {len(result)} bytes")
        return

    # If no specific action, show header and entry point
    if not args.header and not args.find_functions and not args.func:
        print_header(disasm)
        print("Entry point disassembly:")
        print_range(disasm, 0x0100, 0x0150)
        print("\nUse --interactive for exploration or --output <file> for full disassembly")


if __name__ == "__main__":
    main()
