"""Memory-related MCP tools."""

from mcp.server import Server

from ..emulator.thread import EmulatorThread, CommandType


def register_memory_tools(server: Server, emu_thread: EmulatorThread) -> None:
    """Register memory-related tools with the MCP server."""

    @server.tool()
    async def read_memory(address: int, length: int = 1) -> dict:
        """
        Read bytes from Game Boy memory.

        Args:
            address: Memory address (0x0000-0xFFFF)
            length: Number of bytes to read (default 1, max 256)

        Returns:
            Dictionary with hex string of memory contents
        """
        if length > 256:
            length = 256
        if length < 1:
            length = 1

        result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
            "start": address & 0xFFFF,
            "length": length
        })

        data = result.get("data", b"")
        return {
            "address": f"0x{address:04X}",
            "length": len(data),
            "hex": data.hex(),
            "bytes": list(data),
        }

    @server.tool()
    async def write_memory(address: int, value: int) -> dict:
        """
        Write a byte to Game Boy memory.

        Args:
            address: Memory address (0x0000-0xFFFF)
            value: Byte value to write (0x00-0xFF)

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.WRITE_MEMORY, {
            "address": address & 0xFFFF,
            "value": value & 0xFF
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "address": f"0x{address:04X}",
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
