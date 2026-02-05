# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""CPU-related MCP tools."""

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType


def register_cpu_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register CPU-related tools with the MCP server."""

    @server.tool()
    async def get_registers() -> dict:
        """
        Get current CPU register values.

        Returns:
            Dictionary with register names and values
        """
        result = emu_thread.send_command(CommandType.GET_REGISTERS)

        if result.get("error"):
            return {"error": result["error"]}

        # Format for readability
        return {
            "16-bit": {
                "AF": f"0x{result['AF']:04X}",
                "BC": f"0x{result['BC']:04X}",
                "DE": f"0x{result['DE']:04X}",
                "HL": f"0x{result['HL']:04X}",
                "SP": f"0x{result['SP']:04X}",
                "PC": f"0x{result['PC']:04X}",
            },
            "8-bit": {
                "A": f"0x{result['A']:02X}",
                "F": f"0x{result['F']:02X}",
                "B": f"0x{result['B']:02X}",
                "C": f"0x{result['C']:02X}",
                "D": f"0x{result['D']:02X}",
                "E": f"0x{result['E']:02X}",
                "H": f"0x{result['H']:02X}",
                "L": f"0x{result['L']:02X}",
            },
            "flags": result["flags"],
            "raw": {
                "AF": result['AF'],
                "BC": result['BC'],
                "DE": result['DE'],
                "HL": result['HL'],
                "SP": result['SP'],
                "PC": result['PC'],
            }
        }

    @server.tool()
    async def disassemble(address: int | None = None, count: int = 10) -> dict:
        """
        Disassemble instructions at an address.

        Args:
            address: Starting address (default: current PC)
            count: Number of instructions to disassemble (default 10, max 50)

        Returns:
            Disassembly listing
        """
        if count > 50:
            count = 50
        if count < 1:
            count = 1

        result = emu_thread.send_command(CommandType.DISASSEMBLE, {
            "address": address,
            "count": count
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "address": f"0x{address:04X}" if address is not None else "current PC",
            "count": count,
            "disassembly": result.get("disassembly", ""),
        }
