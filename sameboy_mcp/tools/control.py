# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Emulation control MCP tools."""

from mcp.server import Server

from ..emulator.thread import EmulatorThread, CommandType


def register_control_tools(server: Server, emu_thread: EmulatorThread) -> None:
    """Register emulation control tools with the MCP server."""

    @server.tool()
    async def pause() -> dict:
        """
        Pause emulation.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.PAUSE)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True, "state": "paused"}

    @server.tool()
    async def resume() -> dict:
        """
        Resume emulation.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.RESUME)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True, "state": "running"}

    @server.tool()
    async def step_frame() -> dict:
        """
        Execute one frame and pause.

        Returns:
            Frame information including whether a breakpoint was hit
        """
        result = emu_thread.send_command(CommandType.STEP_FRAME)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "frame": result.get("frame", 0),
            "breakpoint_hit": result.get("breakpoint_hit", False),
        }

    @server.tool()
    async def step_instruction() -> dict:
        """
        Execute one CPU instruction and pause.

        Returns:
            Instruction info and cycle count
        """
        result = emu_thread.send_command(CommandType.STEP_INSTRUCTION)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "cycles": result.get("cycles", 0),
            "breakpoint_hit": result.get("breakpoint_hit", False),
        }

    @server.tool()
    async def reset() -> dict:
        """
        Reset the emulator.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.RESET)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True}

    @server.tool()
    async def press_key(key: str, frames: int = 1) -> dict:
        """
        Press a joypad button for a number of frames.

        Args:
            key: Button name (a, b, start, select, up, down, left, right)
            frames: Number of frames to hold the button (default 1)

        Returns:
            Confirmation message
        """
        if frames < 1:
            frames = 1
        if frames > 600:  # Max 10 seconds at 60fps
            frames = 600

        result = emu_thread.send_command(CommandType.PRESS_KEY, {
            "key": key,
            "frames": frames
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "key": key,
            "frames": frames,
        }

    @server.tool()
    async def set_key(key: str, pressed: bool) -> dict:
        """
        Set a joypad button state without advancing frames.

        Args:
            key: Button name (a, b, start, select, up, down, left, right)
            pressed: Whether the button is pressed

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.SET_KEY, {
            "key": key,
            "pressed": pressed
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "key": key,
            "pressed": pressed,
        }

    @server.tool()
    async def press_keys(keys: list[str], frames: int = 1) -> dict:
        """
        Press multiple joypad buttons simultaneously.

        Args:
            keys: List of button names
            frames: Number of frames to hold the buttons (default 1)

        Returns:
            Confirmation message
        """
        if frames < 1:
            frames = 1
        if frames > 600:
            frames = 600

        # Press all keys
        for key in keys:
            result = emu_thread.send_command(CommandType.SET_KEY, {
                "key": key,
                "pressed": True
            })
            if result.get("error"):
                return {"error": result["error"]}

        # Run frames
        for _ in range(frames):
            result = emu_thread.send_command(CommandType.STEP_FRAME)
            if result.get("error"):
                return {"error": result["error"]}

        # Release all keys
        for key in keys:
            emu_thread.send_command(CommandType.SET_KEY, {
                "key": key,
                "pressed": False
            })

        return {
            "success": True,
            "keys": keys,
            "frames": frames,
        }

    @server.tool()
    async def run_frames(count: int) -> dict:
        """
        Run emulation for a specific number of frames.

        Args:
            count: Number of frames to run (max 3600 = 1 minute at 60fps)

        Returns:
            Execution summary
        """
        if count < 1:
            count = 1
        if count > 3600:
            count = 3600

        breakpoint_hit = False
        frames_run = 0

        for _ in range(count):
            result = emu_thread.send_command(CommandType.STEP_FRAME)
            if result.get("error"):
                return {"error": result["error"]}
            frames_run += 1
            if result.get("breakpoint_hit"):
                breakpoint_hit = True
                break

        return {
            "success": True,
            "frames_requested": count,
            "frames_run": frames_run,
            "breakpoint_hit": breakpoint_hit,
        }

    @server.tool()
    async def set_turbo(enabled: bool, no_frame_skip: bool = False) -> dict:
        """
        Enable or disable turbo mode (fast-forward).

        Args:
            enabled: Whether to enable turbo mode
            no_frame_skip: If true, render all frames even in turbo mode

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.SET_TURBO, {
            "enabled": enabled,
            "no_frame_skip": no_frame_skip
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "turbo_enabled": enabled,
            "no_frame_skip": no_frame_skip,
        }

    @server.tool()
    async def enable_live_display(scale: int = 2) -> dict:
        """
        Enable a live display window showing emulator frames in real-time.

        The window shows the game screen updating at 60fps. Keyboard input
        in the window is forwarded to the emulator:
        - Arrow keys: D-pad
        - Z: A button
        - X: B button
        - Enter: Start
        - Shift/Backspace: Select

        Args:
            scale: Display scaling factor (1-4, default 2)

        Returns:
            Status of the live display
        """
        if scale < 1:
            scale = 1
        if scale > 4:
            scale = 4

        result = emu_thread.send_command(CommandType.ENABLE_LIVE_DISPLAY, {
            "scale": scale
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "enabled": result.get("enabled", False),
            "scale": scale,
            "message": "Live display window opened. Close the window or call disable_live_display to stop."
        }

    @server.tool()
    async def disable_live_display() -> dict:
        """
        Disable and close the live display window.

        Returns:
            Confirmation message
        """
        result = emu_thread.send_command(CommandType.DISABLE_LIVE_DISPLAY)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "enabled": False,
            "message": "Live display window closed."
        }
