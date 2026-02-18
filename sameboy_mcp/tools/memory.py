# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Memory-related MCP tools."""

from typing import Union

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import parse_address, require_rom


def register_memory_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register memory-related tools with the MCP server."""

    @server.tool()
    async def read_memory(address: Union[int, str], length: int = 1) -> dict:
        """
        Read bytes from Game Boy memory.

        Args:
            address: Memory address (0x0000-0xFFFF). Accepts int or hex string (e.g. "0xC3A0").
            length: Number of bytes to read (default 1, max 4096)

        Returns:
            Dictionary with hex string of memory contents
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        if length > 4096:
            length = 4096
        if length < 1:
            length = 1

        result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
            "start": addr,
            "length": length
        })

        data = result.get("data", b"")
        return {
            "address": f"0x{addr:04X}",
            "length": len(data),
            "hex": data.hex(),
            "bytes": list(data),
        }

    @server.tool()
    async def write_memory(address: Union[int, str], value: int) -> dict:
        """
        Write a byte to Game Boy memory.

        Args:
            address: Memory address (0x0000-0xFFFF). Accepts int or hex string (e.g. "0xC3A0").
            value: Byte value to write (0x00-0xFF)

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.WRITE_MEMORY, {
            "address": addr,
            "value": value & 0xFF
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "address": f"0x{addr:04X}",
            "value": f"0x{value & 0xFF:02X}",
        }

    @server.tool()
    async def read_memory_region(region: str) -> dict:
        """
        Read an entire memory region.

        Args:
            region: Memory region name (rom, ram, vram, oam, hram, cart_ram, io)

        Returns:
            Base64-encoded region data with metadata
        """
        if err := require_rom(emu_thread):
            return err
        import base64

        result = emu_thread.send_command(CommandType.GET_DIRECT_ACCESS, {"region": region})

        if result.get("error"):
            return {"error": result["error"]}

        data = result.get("data", b"")
        bank = result.get("bank", 0)

        return {
            "region": region,
            "size": len(data),
            "bank": bank,
            "data_base64": base64.b64encode(data).decode("ascii"),
        }
