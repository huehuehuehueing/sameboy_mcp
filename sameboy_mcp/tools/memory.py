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

    # ============ ROM Patching ============

    @server.tool()
    async def patch_rom(address: Union[int, str], value: int) -> dict:
        """
        Patch a byte directly in the ROM buffer.

        Unlike write_memory (which triggers MBC bank-switching for ROM addresses),
        this writes directly to the ROM data in memory. Use for code patching,
        NOP-ing out checks, etc.

        Args:
            address: ROM address (0 to ROM size - 1). Accepts int or hex string.
            value: Byte value to write (0x00-0xFF)

        Returns:
            Success status with old and new values
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.PATCH_ROM, {
            "address": addr,
            "value": value & 0xFF,
        })

        if result.get("error"):
            return {"error": result["error"]}

        return result

    # ============ Cheat System ============

    @server.tool()
    async def add_cheat(
        description: str,
        address: Union[int, str],
        value: int,
        bank: int = 0xFFFF,
        old_value: int = 0,
        use_old_value: bool = False,
        enabled: bool = True,
    ) -> dict:
        """
        Add a cheat code (GameShark-style value substitution).

        The cheat system intercepts memory reads and substitutes values.
        This is persistent — the value is applied every time the address is read.

        Args:
            description: Human-readable name for the cheat
            address: Memory address to patch (0x0000-0xFFFF)
            value: Value to substitute (0x00-0xFF)
            bank: ROM bank (0xFFFF = any bank, default)
            old_value: Only apply if current value matches (requires use_old_value=True)
            use_old_value: If True, only substitute when current value equals old_value
            enabled: Whether the cheat is active

        Returns:
            Cheat details
        """
        if err := require_rom(emu_thread):
            return err
        addr = parse_address(address)
        result = emu_thread.send_command(CommandType.ADD_CHEAT, {
            "description": description,
            "address": addr,
            "bank": bank & 0xFFFF,
            "value": value & 0xFF,
            "old_value": old_value & 0xFF,
            "use_old_value": use_old_value,
            "enabled": enabled,
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "description": result.get("description", description),
            "address": f"0x{result['address']:04X}",
            "bank": f"0x{result['bank']:04X}",
            "value": f"0x{result['value']:02X}",
            "enabled": result["enabled"],
        }

    @server.tool()
    async def remove_cheat(index: int) -> dict:
        """
        Remove a cheat by its index.

        Use list_cheats to see indices.

        Args:
            index: Cheat index (0-based)

        Returns:
            Success status
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.REMOVE_CHEAT, {"index": index})
        if result.get("error"):
            return {"error": result["error"]}
        return result

    @server.tool()
    async def remove_all_cheats() -> dict:
        """
        Remove all cheats.

        Returns:
            Success status
        """
        if err := require_rom(emu_thread):
            return err
        return emu_thread.send_command(CommandType.REMOVE_ALL_CHEATS, {})

    @server.tool()
    async def list_cheats() -> dict:
        """
        List all cheats with their index, description, address, value, and status.

        Returns:
            List of cheats and global enabled status
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.LIST_CHEATS, {})
        if result.get("error"):
            return {"error": result["error"]}

        # Format addresses as hex strings
        for cheat in result.get("cheats", []):
            cheat["address"] = f"0x{cheat['address']:04X}"
            cheat["bank"] = f"0x{cheat['bank']:04X}"
            cheat["value"] = f"0x{cheat['value']:02X}"
            cheat["old_value"] = f"0x{cheat['old_value']:02X}"

        return result

    @server.tool()
    async def set_cheats_enabled(enabled: bool) -> dict:
        """
        Enable or disable the cheat system globally.

        Individual cheats retain their enabled/disabled state, but the
        global toggle must be on for any cheats to take effect.

        Args:
            enabled: Whether to enable cheats globally

        Returns:
            Success status
        """
        if err := require_rom(emu_thread):
            return err
        return emu_thread.send_command(CommandType.SET_CHEATS_ENABLED, {"enabled": enabled})

    @server.tool()
    async def import_cheat(code: str, description: str = "", enabled: bool = True) -> dict:
        """
        Import a cheat from a GameShark or Game Genie code string.

        GameShark format: XXYYYY (XX=value, YYYY=address) or XXYYYY-ZZ (with old value)
        Game Genie format: XXX-XXX-XXX

        Args:
            code: GameShark or Game Genie code string
            description: Human-readable name for the cheat
            enabled: Whether the cheat is active

        Returns:
            Parsed cheat details
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.IMPORT_CHEAT, {
            "code": code,
            "description": description,
            "enabled": enabled,
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "code": code,
            "description": result.get("description", description),
            "address": f"0x{result['address']:04X}",
            "bank": f"0x{result['bank']:04X}",
            "value": f"0x{result['value']:02X}",
            "enabled": result["enabled"],
        }
