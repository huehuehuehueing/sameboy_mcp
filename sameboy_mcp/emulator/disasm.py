# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Game Boy Z80 disassembler for full ROM analysis."""

from typing import Iterator
from dataclasses import dataclass


@dataclass
class Instruction:
    """Disassembled instruction."""
    address: int
    opcode: int
    bytes: bytes
    mnemonic: str
    operands: str
    size: int
    is_jump: bool = False
    is_call: bool = False
    is_return: bool = False
    is_conditional: bool = False
    jump_target: int | None = None

    def __str__(self) -> str:
        hex_bytes = " ".join(f"{b:02X}" for b in self.bytes)
        hex_bytes = hex_bytes.ljust(11)  # Pad for alignment
        if self.operands:
            return f"0x{self.address:04X}:  {hex_bytes}  {self.mnemonic} {self.operands}"
        return f"0x{self.address:04X}:  {hex_bytes}  {self.mnemonic}"


# Z80/GB instruction tables
# Format: (mnemonic, operands, size, flags)
# Flags: J=jump, C=call, R=return, ?=conditional

OPCODES = {
    0x00: ("NOP", "", 1, ""),
    0x01: ("LD", "BC, ${:04X}", 3, ""),
    0x02: ("LD", "(BC), A", 1, ""),
    0x03: ("INC", "BC", 1, ""),
    0x04: ("INC", "B", 1, ""),
    0x05: ("DEC", "B", 1, ""),
    0x06: ("LD", "B, ${:02X}", 2, ""),
    0x07: ("RLCA", "", 1, ""),
    0x08: ("LD", "(${:04X}), SP", 3, ""),
    0x09: ("ADD", "HL, BC", 1, ""),
    0x0A: ("LD", "A, (BC)", 1, ""),
    0x0B: ("DEC", "BC", 1, ""),
    0x0C: ("INC", "C", 1, ""),
    0x0D: ("DEC", "C", 1, ""),
    0x0E: ("LD", "C, ${:02X}", 2, ""),
    0x0F: ("RRCA", "", 1, ""),

    0x10: ("STOP", "", 1, ""),
    0x11: ("LD", "DE, ${:04X}", 3, ""),
    0x12: ("LD", "(DE), A", 1, ""),
    0x13: ("INC", "DE", 1, ""),
    0x14: ("INC", "D", 1, ""),
    0x15: ("DEC", "D", 1, ""),
    0x16: ("LD", "D, ${:02X}", 2, ""),
    0x17: ("RLA", "", 1, ""),
    0x18: ("JR", "${:04X}", 2, "J"),
    0x19: ("ADD", "HL, DE", 1, ""),
    0x1A: ("LD", "A, (DE)", 1, ""),
    0x1B: ("DEC", "DE", 1, ""),
    0x1C: ("INC", "E", 1, ""),
    0x1D: ("DEC", "E", 1, ""),
    0x1E: ("LD", "E, ${:02X}", 2, ""),
    0x1F: ("RRA", "", 1, ""),

    0x20: ("JR", "NZ, ${:04X}", 2, "J?"),
    0x21: ("LD", "HL, ${:04X}", 3, ""),
    0x22: ("LD", "(HL+), A", 1, ""),
    0x23: ("INC", "HL", 1, ""),
    0x24: ("INC", "H", 1, ""),
    0x25: ("DEC", "H", 1, ""),
    0x26: ("LD", "H, ${:02X}", 2, ""),
    0x27: ("DAA", "", 1, ""),
    0x28: ("JR", "Z, ${:04X}", 2, "J?"),
    0x29: ("ADD", "HL, HL", 1, ""),
    0x2A: ("LD", "A, (HL+)", 1, ""),
    0x2B: ("DEC", "HL", 1, ""),
    0x2C: ("INC", "L", 1, ""),
    0x2D: ("DEC", "L", 1, ""),
    0x2E: ("LD", "L, ${:02X}", 2, ""),
    0x2F: ("CPL", "", 1, ""),

    0x30: ("JR", "NC, ${:04X}", 2, "J?"),
    0x31: ("LD", "SP, ${:04X}", 3, ""),
    0x32: ("LD", "(HL-), A", 1, ""),
    0x33: ("INC", "SP", 1, ""),
    0x34: ("INC", "(HL)", 1, ""),
    0x35: ("DEC", "(HL)", 1, ""),
    0x36: ("LD", "(HL), ${:02X}", 2, ""),
    0x37: ("SCF", "", 1, ""),
    0x38: ("JR", "C, ${:04X}", 2, "J?"),
    0x39: ("ADD", "HL, SP", 1, ""),
    0x3A: ("LD", "A, (HL-)", 1, ""),
    0x3B: ("DEC", "SP", 1, ""),
    0x3C: ("INC", "A", 1, ""),
    0x3D: ("DEC", "A", 1, ""),
    0x3E: ("LD", "A, ${:02X}", 2, ""),
    0x3F: ("CCF", "", 1, ""),

    # LD instructions 0x40-0x7F
    0x40: ("LD", "B, B", 1, ""), 0x41: ("LD", "B, C", 1, ""),
    0x42: ("LD", "B, D", 1, ""), 0x43: ("LD", "B, E", 1, ""),
    0x44: ("LD", "B, H", 1, ""), 0x45: ("LD", "B, L", 1, ""),
    0x46: ("LD", "B, (HL)", 1, ""), 0x47: ("LD", "B, A", 1, ""),
    0x48: ("LD", "C, B", 1, ""), 0x49: ("LD", "C, C", 1, ""),
    0x4A: ("LD", "C, D", 1, ""), 0x4B: ("LD", "C, E", 1, ""),
    0x4C: ("LD", "C, H", 1, ""), 0x4D: ("LD", "C, L", 1, ""),
    0x4E: ("LD", "C, (HL)", 1, ""), 0x4F: ("LD", "C, A", 1, ""),

    0x50: ("LD", "D, B", 1, ""), 0x51: ("LD", "D, C", 1, ""),
    0x52: ("LD", "D, D", 1, ""), 0x53: ("LD", "D, E", 1, ""),
    0x54: ("LD", "D, H", 1, ""), 0x55: ("LD", "D, L", 1, ""),
    0x56: ("LD", "D, (HL)", 1, ""), 0x57: ("LD", "D, A", 1, ""),
    0x58: ("LD", "E, B", 1, ""), 0x59: ("LD", "E, C", 1, ""),
    0x5A: ("LD", "E, D", 1, ""), 0x5B: ("LD", "E, E", 1, ""),
    0x5C: ("LD", "E, H", 1, ""), 0x5D: ("LD", "E, L", 1, ""),
    0x5E: ("LD", "E, (HL)", 1, ""), 0x5F: ("LD", "E, A", 1, ""),

    0x60: ("LD", "H, B", 1, ""), 0x61: ("LD", "H, C", 1, ""),
    0x62: ("LD", "H, D", 1, ""), 0x63: ("LD", "H, E", 1, ""),
    0x64: ("LD", "H, H", 1, ""), 0x65: ("LD", "H, L", 1, ""),
    0x66: ("LD", "H, (HL)", 1, ""), 0x67: ("LD", "H, A", 1, ""),
    0x68: ("LD", "L, B", 1, ""), 0x69: ("LD", "L, C", 1, ""),
    0x6A: ("LD", "L, D", 1, ""), 0x6B: ("LD", "L, E", 1, ""),
    0x6C: ("LD", "L, H", 1, ""), 0x6D: ("LD", "L, L", 1, ""),
    0x6E: ("LD", "L, (HL)", 1, ""), 0x6F: ("LD", "L, A", 1, ""),

    0x70: ("LD", "(HL), B", 1, ""), 0x71: ("LD", "(HL), C", 1, ""),
    0x72: ("LD", "(HL), D", 1, ""), 0x73: ("LD", "(HL), E", 1, ""),
    0x74: ("LD", "(HL), H", 1, ""), 0x75: ("LD", "(HL), L", 1, ""),
    0x76: ("HALT", "", 1, ""),
    0x77: ("LD", "(HL), A", 1, ""),
    0x78: ("LD", "A, B", 1, ""), 0x79: ("LD", "A, C", 1, ""),
    0x7A: ("LD", "A, D", 1, ""), 0x7B: ("LD", "A, E", 1, ""),
    0x7C: ("LD", "A, H", 1, ""), 0x7D: ("LD", "A, L", 1, ""),
    0x7E: ("LD", "A, (HL)", 1, ""), 0x7F: ("LD", "A, A", 1, ""),

    # ALU operations 0x80-0xBF
    0x80: ("ADD", "A, B", 1, ""), 0x81: ("ADD", "A, C", 1, ""),
    0x82: ("ADD", "A, D", 1, ""), 0x83: ("ADD", "A, E", 1, ""),
    0x84: ("ADD", "A, H", 1, ""), 0x85: ("ADD", "A, L", 1, ""),
    0x86: ("ADD", "A, (HL)", 1, ""), 0x87: ("ADD", "A, A", 1, ""),
    0x88: ("ADC", "A, B", 1, ""), 0x89: ("ADC", "A, C", 1, ""),
    0x8A: ("ADC", "A, D", 1, ""), 0x8B: ("ADC", "A, E", 1, ""),
    0x8C: ("ADC", "A, H", 1, ""), 0x8D: ("ADC", "A, L", 1, ""),
    0x8E: ("ADC", "A, (HL)", 1, ""), 0x8F: ("ADC", "A, A", 1, ""),

    0x90: ("SUB", "B", 1, ""), 0x91: ("SUB", "C", 1, ""),
    0x92: ("SUB", "D", 1, ""), 0x93: ("SUB", "E", 1, ""),
    0x94: ("SUB", "H", 1, ""), 0x95: ("SUB", "L", 1, ""),
    0x96: ("SUB", "(HL)", 1, ""), 0x97: ("SUB", "A", 1, ""),
    0x98: ("SBC", "A, B", 1, ""), 0x99: ("SBC", "A, C", 1, ""),
    0x9A: ("SBC", "A, D", 1, ""), 0x9B: ("SBC", "A, E", 1, ""),
    0x9C: ("SBC", "A, H", 1, ""), 0x9D: ("SBC", "A, L", 1, ""),
    0x9E: ("SBC", "A, (HL)", 1, ""), 0x9F: ("SBC", "A, A", 1, ""),

    0xA0: ("AND", "B", 1, ""), 0xA1: ("AND", "C", 1, ""),
    0xA2: ("AND", "D", 1, ""), 0xA3: ("AND", "E", 1, ""),
    0xA4: ("AND", "H", 1, ""), 0xA5: ("AND", "L", 1, ""),
    0xA6: ("AND", "(HL)", 1, ""), 0xA7: ("AND", "A", 1, ""),
    0xA8: ("XOR", "B", 1, ""), 0xA9: ("XOR", "C", 1, ""),
    0xAA: ("XOR", "D", 1, ""), 0xAB: ("XOR", "E", 1, ""),
    0xAC: ("XOR", "H", 1, ""), 0xAD: ("XOR", "L", 1, ""),
    0xAE: ("XOR", "(HL)", 1, ""), 0xAF: ("XOR", "A", 1, ""),

    0xB0: ("OR", "B", 1, ""), 0xB1: ("OR", "C", 1, ""),
    0xB2: ("OR", "D", 1, ""), 0xB3: ("OR", "E", 1, ""),
    0xB4: ("OR", "H", 1, ""), 0xB5: ("OR", "L", 1, ""),
    0xB6: ("OR", "(HL)", 1, ""), 0xB7: ("OR", "A", 1, ""),
    0xB8: ("CP", "B", 1, ""), 0xB9: ("CP", "C", 1, ""),
    0xBA: ("CP", "D", 1, ""), 0xBB: ("CP", "E", 1, ""),
    0xBC: ("CP", "H", 1, ""), 0xBD: ("CP", "L", 1, ""),
    0xBE: ("CP", "(HL)", 1, ""), 0xBF: ("CP", "A", 1, ""),

    # Control flow 0xC0-0xFF
    0xC0: ("RET", "NZ", 1, "R?"),
    0xC1: ("POP", "BC", 1, ""),
    0xC2: ("JP", "NZ, ${:04X}", 3, "J?"),
    0xC3: ("JP", "${:04X}", 3, "J"),
    0xC4: ("CALL", "NZ, ${:04X}", 3, "C?"),
    0xC5: ("PUSH", "BC", 1, ""),
    0xC6: ("ADD", "A, ${:02X}", 2, ""),
    0xC7: ("RST", "$00", 1, "C"),
    0xC8: ("RET", "Z", 1, "R?"),
    0xC9: ("RET", "", 1, "R"),
    0xCA: ("JP", "Z, ${:04X}", 3, "J?"),
    0xCB: ("PREFIX", "CB", 1, ""),  # CB prefix
    0xCC: ("CALL", "Z, ${:04X}", 3, "C?"),
    0xCD: ("CALL", "${:04X}", 3, "C"),
    0xCE: ("ADC", "A, ${:02X}", 2, ""),
    0xCF: ("RST", "$08", 1, "C"),

    0xD0: ("RET", "NC", 1, "R?"),
    0xD1: ("POP", "DE", 1, ""),
    0xD2: ("JP", "NC, ${:04X}", 3, "J?"),
    # 0xD3 is invalid
    0xD4: ("CALL", "NC, ${:04X}", 3, "C?"),
    0xD5: ("PUSH", "DE", 1, ""),
    0xD6: ("SUB", "${:02X}", 2, ""),
    0xD7: ("RST", "$10", 1, "C"),
    0xD8: ("RET", "C", 1, "R?"),
    0xD9: ("RETI", "", 1, "R"),
    0xDA: ("JP", "C, ${:04X}", 3, "J?"),
    # 0xDB is invalid
    0xDC: ("CALL", "C, ${:04X}", 3, "C?"),
    # 0xDD is invalid
    0xDE: ("SBC", "A, ${:02X}", 2, ""),
    0xDF: ("RST", "$18", 1, "C"),

    0xE0: ("LDH", "(${:02X}), A", 2, ""),  # ($FF00+n)
    0xE1: ("POP", "HL", 1, ""),
    0xE2: ("LD", "($FF00+C), A", 1, ""),
    # 0xE3, 0xE4 invalid
    0xE5: ("PUSH", "HL", 1, ""),
    0xE6: ("AND", "${:02X}", 2, ""),
    0xE7: ("RST", "$20", 1, "C"),
    0xE8: ("ADD", "SP, ${:02X}", 2, ""),
    0xE9: ("JP", "HL", 1, "J"),
    0xEA: ("LD", "(${:04X}), A", 3, ""),
    # 0xEB, 0xEC, 0xED invalid
    0xEE: ("XOR", "${:02X}", 2, ""),
    0xEF: ("RST", "$28", 1, "C"),

    0xF0: ("LDH", "A, (${:02X})", 2, ""),  # ($FF00+n)
    0xF1: ("POP", "AF", 1, ""),
    0xF2: ("LD", "A, ($FF00+C)", 1, ""),
    0xF3: ("DI", "", 1, ""),
    # 0xF4 invalid
    0xF5: ("PUSH", "AF", 1, ""),
    0xF6: ("OR", "${:02X}", 2, ""),
    0xF7: ("RST", "$30", 1, "C"),
    0xF8: ("LD", "HL, SP+${:02X}", 2, ""),
    0xF9: ("LD", "SP, HL", 1, ""),
    0xFA: ("LD", "A, (${:04X})", 3, ""),
    0xFB: ("EI", "", 1, ""),
    # 0xFC, 0xFD invalid
    0xFE: ("CP", "${:02X}", 2, ""),
    0xFF: ("RST", "$38", 1, "C"),
}

# CB-prefixed instructions
CB_OPCODES = {}
cb_ops = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SWAP", "SRL"]
cb_regs = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]

for i, op in enumerate(cb_ops):
    for j, reg in enumerate(cb_regs):
        CB_OPCODES[i * 8 + j] = (op, reg, 2, "")

# BIT, RES, SET instructions
for bit in range(8):
    for j, reg in enumerate(cb_regs):
        CB_OPCODES[0x40 + bit * 8 + j] = ("BIT", f"{bit}, {reg}", 2, "")
        CB_OPCODES[0x80 + bit * 8 + j] = ("RES", f"{bit}, {reg}", 2, "")
        CB_OPCODES[0xC0 + bit * 8 + j] = ("SET", f"{bit}, {reg}", 2, "")


class Disassembler:
    """Game Boy ROM disassembler."""

    def __init__(self, rom_data: bytes):
        """Initialize with ROM data."""
        self.rom = rom_data
        self.size = len(rom_data)

    def read_byte(self, addr: int) -> int:
        """Read byte from ROM."""
        if 0 <= addr < self.size:
            return self.rom[addr]
        return 0xFF

    def read_word(self, addr: int) -> int:
        """Read 16-bit word (little-endian) from ROM."""
        lo = self.read_byte(addr)
        hi = self.read_byte(addr + 1)
        return (hi << 8) | lo

    def disassemble_one(self, addr: int) -> Instruction:
        """Disassemble a single instruction at address."""
        opcode = self.read_byte(addr)

        # Handle CB prefix
        if opcode == 0xCB:
            cb_opcode = self.read_byte(addr + 1)
            if cb_opcode in CB_OPCODES:
                mnemonic, operands, size, flags = CB_OPCODES[cb_opcode]
            else:
                mnemonic, operands, size, flags = "???", f"${cb_opcode:02X}", 2, ""

            return Instruction(
                address=addr,
                opcode=cb_opcode,
                bytes=bytes([opcode, cb_opcode]),
                mnemonic=mnemonic,
                operands=operands,
                size=size,
            )

        # Handle regular opcodes
        if opcode in OPCODES:
            mnemonic, operands_fmt, size, flags = OPCODES[opcode]
        else:
            # Invalid opcode
            return Instruction(
                address=addr,
                opcode=opcode,
                bytes=bytes([opcode]),
                mnemonic="???",
                operands=f"${opcode:02X}",
                size=1,
            )

        # Read operand bytes
        inst_bytes = [opcode]
        operands = operands_fmt

        if size == 2:
            imm = self.read_byte(addr + 1)
            inst_bytes.append(imm)

            # Handle relative jumps
            if "J" in flags and "{:04X}" in operands_fmt:
                # Signed offset
                offset = imm if imm < 128 else imm - 256
                target = (addr + 2 + offset) & 0xFFFF
                operands = operands_fmt.format(target)
            else:
                operands = operands_fmt.format(imm)

        elif size == 3:
            word = self.read_word(addr + 1)
            inst_bytes.extend([word & 0xFF, (word >> 8) & 0xFF])
            operands = operands_fmt.format(word)

        # Determine jump target
        jump_target = None
        if "J" in flags or "C" in flags:
            if size == 3:
                jump_target = self.read_word(addr + 1)
            elif size == 2 and "J" in flags:
                imm = self.read_byte(addr + 1)
                offset = imm if imm < 128 else imm - 256
                jump_target = (addr + 2 + offset) & 0xFFFF

        return Instruction(
            address=addr,
            opcode=opcode,
            bytes=bytes(inst_bytes),
            mnemonic=mnemonic,
            operands=operands,
            size=size,
            is_jump="J" in flags,
            is_call="C" in flags,
            is_return="R" in flags,
            is_conditional="?" in flags,
            jump_target=jump_target,
        )

    def disassemble_range(self, start: int, end: int) -> Iterator[Instruction]:
        """Disassemble instructions in address range."""
        addr = start
        while addr < end and addr < self.size:
            inst = self.disassemble_one(addr)
            yield inst
            addr += inst.size

    def disassemble_all(self) -> Iterator[Instruction]:
        """Disassemble entire ROM."""
        return self.disassemble_range(0, self.size)

    def disassemble_function(self, start: int, max_size: int = 0x1000) -> list[Instruction]:
        """
        Disassemble a function starting at address.

        Follows linear flow until RET/RETI or max_size reached.
        """
        instructions = []
        addr = start
        end = min(start + max_size, self.size)

        while addr < end:
            inst = self.disassemble_one(addr)
            instructions.append(inst)
            addr += inst.size

            # Stop at unconditional return
            if inst.is_return and not inst.is_conditional:
                break

            # Stop at unconditional jump (not call)
            if inst.is_jump and not inst.is_conditional and not inst.is_call:
                break

        return instructions

    def get_rom_header(self) -> dict:
        """Extract ROM header information."""
        if self.size < 0x150:
            return {"error": "ROM too small for header"}

        # Title at 0x134-0x143
        title_bytes = self.rom[0x134:0x144]
        title = title_bytes.split(b'\x00')[0].decode('ascii', errors='replace')

        # Cartridge type at 0x147
        cart_type = self.rom[0x147]
        cart_types = {
            0x00: "ROM ONLY", 0x01: "MBC1", 0x02: "MBC1+RAM",
            0x03: "MBC1+RAM+BATTERY", 0x05: "MBC2", 0x06: "MBC2+BATTERY",
            0x08: "ROM+RAM", 0x09: "ROM+RAM+BATTERY", 0x0B: "MMM01",
            0x0C: "MMM01+RAM", 0x0D: "MMM01+RAM+BATTERY",
            0x0F: "MBC3+TIMER+BATTERY", 0x10: "MBC3+TIMER+RAM+BATTERY",
            0x11: "MBC3", 0x12: "MBC3+RAM", 0x13: "MBC3+RAM+BATTERY",
            0x19: "MBC5", 0x1A: "MBC5+RAM", 0x1B: "MBC5+RAM+BATTERY",
            0x1C: "MBC5+RUMBLE", 0x1D: "MBC5+RUMBLE+RAM",
            0x1E: "MBC5+RUMBLE+RAM+BATTERY",
        }

        # ROM size at 0x148
        rom_size_code = self.rom[0x148]
        rom_sizes = {
            0: "32KB", 1: "64KB", 2: "128KB", 3: "256KB",
            4: "512KB", 5: "1MB", 6: "2MB", 7: "4MB", 8: "8MB",
        }

        # RAM size at 0x149
        ram_size_code = self.rom[0x149]
        ram_sizes = {
            0: "None", 1: "2KB", 2: "8KB", 3: "32KB", 4: "128KB", 5: "64KB",
        }

        # CGB flag at 0x143
        cgb_flag = self.rom[0x143]
        cgb_support = "CGB Only" if cgb_flag == 0xC0 else "CGB Compatible" if cgb_flag == 0x80 else "DMG"

        # Entry point at 0x100-0x103
        entry = self.rom[0x100:0x104]

        return {
            "title": title,
            "cartridge_type": cart_types.get(cart_type, f"Unknown (${cart_type:02X})"),
            "rom_size": rom_sizes.get(rom_size_code, f"Unknown (${rom_size_code:02X})"),
            "ram_size": ram_sizes.get(ram_size_code, f"Unknown (${ram_size_code:02X})"),
            "cgb_support": cgb_support,
            "entry_point": f"0x{entry[0]:02X} 0x{entry[1]:02X} 0x{entry[2]:02X} 0x{entry[3]:02X}",
            "header_checksum": f"0x{self.rom[0x14D]:02X}",
            "global_checksum": f"0x{self.rom[0x14E]:02X}{self.rom[0x14F]:02X}",
        }


def disassemble_rom(rom_path: str, output_path: str | None = None) -> str:
    """
    Disassemble an entire ROM file.

    Args:
        rom_path: Path to ROM file
        output_path: Optional path to write disassembly

    Returns:
        Disassembly as string
    """
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    disasm = Disassembler(rom_data)

    lines = []

    # Header info
    header = disasm.get_rom_header()
    lines.append("; ROM Disassembly")
    lines.append(f"; Title: {header.get('title', 'Unknown')}")
    lines.append(f"; Type: {header.get('cartridge_type', 'Unknown')}")
    lines.append(f"; ROM Size: {header.get('rom_size', 'Unknown')}")
    lines.append(f"; RAM Size: {header.get('ram_size', 'Unknown')}")
    lines.append(f"; CGB: {header.get('cgb_support', 'Unknown')}")
    lines.append("")
    lines.append("; Entry Point (0x0100):")

    # Disassemble
    for inst in disasm.disassemble_all():
        # Add labels for common addresses
        if inst.address == 0x0000:
            lines.append("\n; RST 00 / Reset vector")
        elif inst.address == 0x0008:
            lines.append("\n; RST 08")
        elif inst.address == 0x0010:
            lines.append("\n; RST 10")
        elif inst.address == 0x0018:
            lines.append("\n; RST 18")
        elif inst.address == 0x0020:
            lines.append("\n; RST 20")
        elif inst.address == 0x0028:
            lines.append("\n; RST 28")
        elif inst.address == 0x0030:
            lines.append("\n; RST 30")
        elif inst.address == 0x0038:
            lines.append("\n; RST 38")
        elif inst.address == 0x0040:
            lines.append("\n; VBlank Interrupt Handler")
        elif inst.address == 0x0048:
            lines.append("\n; LCD STAT Interrupt Handler")
        elif inst.address == 0x0050:
            lines.append("\n; Timer Interrupt Handler")
        elif inst.address == 0x0058:
            lines.append("\n; Serial Interrupt Handler")
        elif inst.address == 0x0060:
            lines.append("\n; Joypad Interrupt Handler")
        elif inst.address == 0x0100:
            lines.append("\n; Entry Point")
        elif inst.address == 0x0104:
            lines.append("\n; Nintendo Logo")
        elif inst.address == 0x0134:
            lines.append("\n; ROM Header")
        elif inst.address == 0x0150:
            lines.append("\n; Game Code Start")

        lines.append(str(inst))

    result = "\n".join(lines)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)

    return result
