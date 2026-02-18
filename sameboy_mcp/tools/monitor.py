# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Memory monitoring MCP tools."""

from typing import Union

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import parse_address


def register_monitor_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register memory monitoring tools with the MCP server."""

    @server.tool()
    async def monitor_memory(addresses: list[Union[int, str]]) -> dict:
        """
        Start monitoring memory addresses for changes.

        Args:
            addresses: List of addresses to monitor (max 256). Each can be int or hex string.

        Returns:
            Confirmation message
        """
        if len(addresses) > 256:
            addresses = addresses[:256]

        # Normalize addresses
        addresses = [parse_address(addr) for addr in addresses]

        result = emu_thread.send_command(CommandType.ADD_MONITORS, {
            "addresses": addresses
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "addresses_added": len(addresses),
            "addresses": [f"0x{addr:04X}" for addr in addresses],
        }

    @server.tool()
    async def stop_monitor(addresses: list[Union[int, str]] | None = None) -> dict:
        """
        Stop monitoring memory addresses.

        Args:
            addresses: Addresses to stop monitoring (None for all). Each can be int or hex string.

        Returns:
            Confirmation message
        """
        if addresses is not None:
            addresses = [parse_address(addr) for addr in addresses]

        result = emu_thread.send_command(CommandType.REMOVE_MONITORS, {
            "addresses": addresses
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "cleared_all": addresses is None,
        }

    @server.tool()
    async def get_memory_changes(since_frame: int | None = None) -> dict:
        """
        Get detected memory changes.

        Args:
            since_frame: Only return changes after this frame (optional)

        Returns:
            List of memory change events
        """
        result = emu_thread.send_command(CommandType.GET_MEMORY_CHANGES, {
            "since_frame": since_frame
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "count": len(result.get("changes", [])),
            "since_frame": since_frame,
            "changes": result.get("changes", []),
        }

    @server.tool()
    async def clear_memory_changes() -> dict:
        """
        Clear the memory change log.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.CLEAR_MEMORY_CHANGES)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True}

    @server.tool()
    async def take_memory_snapshot() -> dict:
        """
        Take a snapshot of current RAM state for comparison.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.TAKE_SNAPSHOT)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "note": "Snapshot taken. Use compare_memory_snapshot to find changes.",
        }

    @server.tool()
    async def compare_memory_snapshot() -> dict:
        """
        Compare current RAM with previous snapshot.

        Returns:
            Dictionary of changed addresses with old/new values
        """
        result = emu_thread.send_command(CommandType.COMPARE_SNAPSHOT)

        if result.get("error"):
            return {"error": result["error"]}

        changes = result.get("changes", {})

        return {
            "change_count": len(changes),
            "changes": changes,
        }

    @server.tool()
    async def find_value(value: int, size: int = 1, region: str = "ram") -> dict:
        """
        Search memory for a specific value.

        Args:
            value: Value to search for
            size: Size in bytes (1, 2, or 4)
            region: Memory region to search ("ram" for WRAM, "all" for full address space)

        Returns:
            List of addresses containing the value
        """
        if size not in (1, 2, 4):
            return {"error": "Size must be 1, 2, or 4 bytes"}

        matches = []

        if region == "ram":
            start, end = 0xC000, 0xE000
        elif region == "hram":
            start, end = 0xFF80, 0xFFFF
        elif region == "all":
            start, end = 0x0000, 0x10000
        else:
            start, end = 0xC000, 0xE000

        # Read in bulk chunks of 4096 bytes for speed
        chunk_size = 4096
        for chunk_start in range(start, end, chunk_size):
            chunk_len = min(chunk_size, end - chunk_start)
            result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
                "start": chunk_start,
                "length": chunk_len
            })

            if result.get("error"):
                continue

            data = result.get("data", b"")
            if not data:
                continue

            # Scan chunk for value
            for i in range(len(data) - size + 1):
                found_value = int.from_bytes(data[i:i + size], byteorder="little")
                if found_value == value:
                    matches.append(chunk_start + i)
                    if len(matches) >= 100:
                        break

            if len(matches) >= 100:
                break

        return {
            "value": value,
            "size": size,
            "region": region,
            "match_count": len(matches),
            "matches": [f"0x{addr:04X}" for addr in matches],
            "truncated": len(matches) >= 100,
        }
