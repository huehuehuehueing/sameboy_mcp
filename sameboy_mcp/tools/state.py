# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Save state MCP tools."""

import base64
import time
import uuid

from mcp.server import Server

from ..emulator.thread import EmulatorThread, CommandType


# Global state cache (would be better as server attribute, but keeping simple)
_state_cache: dict[str, dict] = {}


def register_state_tools(server: Server, emu_thread: EmulatorThread) -> None:
    """Register save state tools with the MCP server."""

    @server.tool()
    async def save_state(name: str | None = None) -> dict:
        """
        Save the current emulator state.

        Args:
            name: Optional name for the save state

        Returns:
            State ID and metadata
        """
        result = emu_thread.send_command(CommandType.SAVE_STATE)

        if result.get("error"):
            return {"error": result["error"]}

        state_data = result["data"]
        state_id = str(uuid.uuid4())[:8]

        # Get current frame
        status = emu_thread.send_command(CommandType.GET_STATUS)
        frame = status.get("frame_count", 0)

        # Store in cache
        _state_cache[state_id] = {
            "data": state_data,
            "name": name,
            "timestamp": time.time(),
            "frame": frame,
            "size": len(state_data),
        }

        return {
            "state_id": state_id,
            "name": name,
            "size_bytes": len(state_data),
            "frame": frame,
        }

    @server.tool()
    async def load_state(state_id: str) -> dict:
        """
        Load a previously saved state.

        Args:
            state_id: ID returned from save_state

        Returns:
            Confirmation message
        """
        if state_id not in _state_cache:
            return {"error": f"State '{state_id}' not found"}

        state_info = _state_cache[state_id]
        result = emu_thread.send_command(CommandType.LOAD_STATE, {"data": state_info["data"]})

        if result.get("error"):
            return {"error": result["error"]}

        if result.get("success"):
            return {
                "success": True,
                "state_id": state_id,
                "name": state_info["name"],
                "restored_from_frame": state_info["frame"],
            }
        else:
            return {"error": "Failed to load state"}

    @server.tool()
    async def list_states() -> dict:
        """
        List all saved states.

        Returns:
            List of saved state metadata
        """
        states = [
            {
                "state_id": sid,
                "name": info["name"],
                "frame": info["frame"],
                "size_bytes": info["size"],
                "timestamp": info["timestamp"],
            }
            for sid, info in _state_cache.items()
        ]

        return {
            "count": len(states),
            "states": states,
        }

    @server.tool()
    async def delete_state(state_id: str) -> dict:
        """
        Delete a saved state.

        Args:
            state_id: ID of state to delete

        Returns:
            Confirmation message
        """
        if state_id not in _state_cache:
            return {"error": f"State '{state_id}' not found"}

        del _state_cache[state_id]
        return {"success": True, "state_id": state_id}

    @server.tool()
    async def export_state(state_id: str) -> dict:
        """
        Export a saved state as base64 for external storage.

        Args:
            state_id: ID of state to export

        Returns:
            Base64-encoded state data
        """
        if state_id not in _state_cache:
            return {"error": f"State '{state_id}' not found"}

        state_info = _state_cache[state_id]

        return {
            "state_id": state_id,
            "name": state_info["name"],
            "frame": state_info["frame"],
            "size_bytes": state_info["size"],
            "data_base64": base64.b64encode(state_info["data"]).decode("ascii"),
        }

    @server.tool()
    async def import_state(data_base64: str, name: str | None = None) -> dict:
        """
        Import a state from base64-encoded data.

        Args:
            data_base64: Base64-encoded state data
            name: Optional name for the imported state

        Returns:
            State ID and metadata
        """
        try:
            state_data = base64.b64decode(data_base64)
        except Exception as e:
            return {"error": f"Invalid base64 data: {e}"}

        state_id = str(uuid.uuid4())[:8]

        _state_cache[state_id] = {
            "data": state_data,
            "name": name or "imported",
            "timestamp": time.time(),
            "frame": 0,  # Unknown
            "size": len(state_data),
        }

        return {
            "state_id": state_id,
            "name": name or "imported",
            "size_bytes": len(state_data),
        }
