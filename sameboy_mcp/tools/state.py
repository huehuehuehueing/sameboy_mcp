# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Save state MCP tools."""

import base64
import time
import uuid

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import require_rom


# Global state cache (would be better as server attribute, but keeping simple)
_state_cache: dict[str, dict] = {}

# Currently loaded state (updated on load_state)
_current_state: dict | None = None


def get_current_state() -> dict | None:
    """Return the currently loaded save state info, or None."""
    return _current_state


def register_state_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
        if state_id not in _state_cache:
            return {"error": f"State '{state_id}' not found"}

        state_info = _state_cache[state_id]
        result = emu_thread.send_command(CommandType.LOAD_STATE, {"data": state_info["data"]})

        if result.get("error"):
            return {"error": result["error"]}

        if result.get("success"):
            global _current_state
            _current_state = {"state_id": state_id, "name": state_info["name"]}
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
    async def export_state(state_id: str, file_path: str | None = None) -> dict:
        """
        Export a saved state to a file or as base64.

        Args:
            state_id: ID of state to export
            file_path: Optional path to save the state file

        Returns:
            Success confirmation or base64-encoded state data
        """
        if state_id not in _state_cache:
            return {"error": f"State '{state_id}' not found"}

        state_info = _state_cache[state_id]

        if file_path:
            import os
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(state_info["data"])
                return {
                    "success": True,
                    "state_id": state_id,
                    "name": state_info["name"],
                    "file_path": file_path,
                    "size_bytes": state_info["size"],
                }
            except Exception as e:
                return {"error": f"Failed to write file: {e}"}
        else:
            return {
                "state_id": state_id,
                "name": state_info["name"],
                "frame": state_info["frame"],
                "size_bytes": state_info["size"],
                "data_base64": base64.b64encode(state_info["data"]).decode("ascii"),
            }

    @server.tool()
    async def import_state(
        data_base64: str | None = None,
        file_path: str | None = None,
        name: str | None = None,
    ) -> dict:
        """
        Import a state from base64-encoded data or a file.

        Args:
            data_base64: Base64-encoded state data (mutually exclusive with file_path)
            file_path: Path to a saved state file (mutually exclusive with data_base64)
            name: Optional name for the imported state

        Returns:
            State ID and metadata
        """
        state_data = None

        if file_path:
            try:
                with open(file_path, "rb") as f:
                    state_data = f.read()
                if name is None:
                    import os
                    name = os.path.basename(file_path).replace(".sav", "")
            except Exception as e:
                return {"error": f"Failed to read file: {e}"}
        elif data_base64:
            try:
                state_data = base64.b64decode(data_base64)
            except Exception as e:
                return {"error": f"Invalid base64 data: {e}"}
        else:
            return {"error": "Must provide either data_base64 or file_path"}

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
