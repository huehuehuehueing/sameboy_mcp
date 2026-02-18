# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""ROM disassembly MCP tools."""

from typing import Union

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import parse_address, require_rom


def register_disasm_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register disassembly tools with the MCP server."""

    @server.tool()
    async def disassemble_rom(start: Union[int, str] = 0, end: Union[int, str, None] = None, max_instructions: int = 1000) -> dict:
        """
        Disassemble a range of the loaded ROM.

        This provides a full disassembly of ROM code, useful for understanding
        game logic, finding functions, and reverse engineering.

        Args:
            start: Starting address (default 0). Accepts int or hex string.
            end: Ending address (default: start + max_instructions * 3 or ROM end). Accepts int or hex string.
            max_instructions: Maximum instructions to disassemble (default 1000, max 10000)

        Returns:
            Disassembly with instructions, header info, and metadata
        """
        if err := require_rom(emu_thread):
            return err
        if max_instructions > 10000:
            max_instructions = 10000
        if max_instructions < 1:
            max_instructions = 1

        start_addr = parse_address(start) if isinstance(start, str) else start
        end_addr = parse_address(end) if isinstance(end, str) else end

        result = emu_thread.send_command(CommandType.DISASSEMBLE_ROM, {
            "start": start_addr,
            "end": end_addr,
            "max_instructions": max_instructions
        })

        if result.get("error"):
            return {"error": result["error"]}

        return result

    @server.tool()
    async def disassemble_function(address: Union[int, str], max_size: int = 256) -> dict:
        """
        Disassemble a function starting at the given address.

        Follows linear code flow until an unconditional return (RET/RETI)
        or unconditional jump is encountered.

        Args:
            address: Starting address of the function. Accepts int or hex string.
            max_size: Maximum bytes to disassemble (default 256, max 4096)

        Returns:
            Function disassembly with control flow information
        """
        if err := require_rom(emu_thread):
            return err
        if max_size > 4096:
            max_size = 4096
        if max_size < 1:
            max_size = 1

        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.DISASSEMBLE_FUNCTION, {
            "address": addr,
            "max_size": max_size
        })

        if result.get("error"):
            return {"error": result["error"]}

        return result

    @server.tool()
    async def get_rom_header() -> dict:
        """
        Get ROM header information.

        Returns metadata about the loaded ROM including title, cartridge type,
        ROM/RAM sizes, CGB support, and checksums.

        Returns:
            ROM header information
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.GET_ROM_HEADER)

        if result.get("error"):
            return {"error": result["error"]}

        return result

    @server.tool()
    async def find_functions(scan_range: tuple[int, int] | None = None) -> dict:
        """
        Scan ROM for likely function entry points.

        Identifies potential functions by looking for common patterns:
        - PUSH instructions at the start
        - Addresses called via CALL instructions
        - RST vectors

        Args:
            scan_range: Optional (start, end) tuple to limit scan area

        Returns:
            List of potential function addresses with context
        """
        if err := require_rom(emu_thread):
            return err
        params = {}
        if scan_range:
            params["scan_start"] = scan_range[0]
            params["scan_end"] = scan_range[1]

        result = emu_thread.send_command(CommandType.FIND_FUNCTIONS, params)

        if result.get("error"):
            return {"error": result["error"]}

        return result
