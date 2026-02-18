# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Debugging MCP tools."""

from typing import Union

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import parse_address, require_rom


def register_debug_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register debugging tools with the MCP server."""

    @server.tool()
    async def set_breakpoint(address: Union[int, str], enabled: bool = True) -> dict:
        """
        Set a breakpoint at an address.

        Args:
            address: Memory address for breakpoint (0x0000-0xFFFF). Accepts int or hex string.
            enabled: Whether breakpoint is active

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.SET_BREAKPOINT, {
            "address": addr,
            "enabled": enabled
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "address": f"0x{addr:04X}",
            "enabled": enabled,
        }

    @server.tool()
    async def remove_breakpoint(address: Union[int, str]) -> dict:
        """
        Remove a breakpoint.

        Args:
            address: Breakpoint address to remove. Accepts int or hex string.

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.REMOVE_BREAKPOINT, {
            "address": addr
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "address": f"0x{addr:04X}",
        }

    @server.tool()
    async def list_breakpoints() -> dict:
        """
        List all breakpoints.

        Returns:
            List of breakpoint objects
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.LIST_BREAKPOINTS)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "count": len(result.get("breakpoints", [])),
            "breakpoints": result.get("breakpoints", []),
        }

    @server.tool()
    async def clear_breakpoints() -> dict:
        """
        Clear all breakpoints.

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.CLEAR_BREAKPOINTS)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True}

    @server.tool()
    async def enable_trace(enabled: bool = True, limit: int = 10000) -> dict:
        """
        Enable or disable execution tracing.

        Args:
            enabled: Whether to enable tracing
            limit: Maximum trace entries to keep (default 10000)

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.SET_TRACE, {
            "enabled": enabled,
            "limit": limit
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "trace_enabled": enabled,
            "limit": limit,
        }

    @server.tool()
    async def get_trace(count: int = 100) -> dict:
        """
        Get recent execution trace entries.

        Args:
            count: Number of entries to retrieve (most recent)

        Returns:
            List of trace entries with address, opcode, frame
        """
        if err := require_rom(emu_thread):
            return err
        if count > 10000:
            count = 10000
        if count < 1:
            count = 1

        result = emu_thread.send_command(CommandType.GET_TRACE, {"count": count})

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "count": len(result.get("trace", [])),
            "trace": result.get("trace", []),
        }

    @server.tool()
    async def clear_trace() -> dict:
        """
        Clear the execution trace buffer.

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.CLEAR_TRACE)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True}
