"""Debugging MCP tools."""

from mcp.server import Server

from ..emulator.thread import EmulatorThread, CommandType


def register_debug_tools(server: Server, emu_thread: EmulatorThread) -> None:
    """Register debugging tools with the MCP server."""

    @server.tool()
    async def set_breakpoint(address: int, enabled: bool = True) -> dict:
        """
        Set a breakpoint at an address.

        Args:
            address: Memory address for breakpoint (0x0000-0xFFFF)
            enabled: Whether breakpoint is active

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.SET_BREAKPOINT, {
            "address": address & 0xFFFF,
            "enabled": enabled
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "address": f"0x{address:04X}",
            "enabled": enabled,
        }

    @server.tool()
    async def remove_breakpoint(address: int) -> dict:
        """
        Remove a breakpoint.

        Args:
            address: Breakpoint address to remove

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.REMOVE_BREAKPOINT, {
            "address": address & 0xFFFF
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "address": f"0x{address:04X}",
        }

    @server.tool()
    async def list_breakpoints() -> dict:
        """
        List all breakpoints.

        Returns:
            List of breakpoint objects
        """
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
        result = emu_thread.send_command(CommandType.CLEAR_TRACE)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True}
