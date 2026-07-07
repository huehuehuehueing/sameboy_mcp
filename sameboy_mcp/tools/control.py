# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Emulation control MCP tools."""

import asyncio
import sys

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import require_rom

# Module-level state for macOS main-thread SDL display
_macos_display = None
_macos_pump_task = None


def register_control_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register emulation control tools with the MCP server."""

    @server.tool()
    async def pause() -> dict:
        """
        Pause emulation.

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
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
        if err := require_rom(emu_thread):
            return err
        global _macos_display, _macos_pump_task

        if scale < 1:
            scale = 1
        if scale > 4:
            scale = 4

        # On macOS, SDL2 must create windows on the main thread.
        # The async tool handler runs on the main thread (via asyncio),
        # so we create the display here instead of in the emulator thread.
        if sys.platform == "darwin":
            from ..emulator.display import LiveDisplay, is_available

            if not is_available():
                return {"error": "SDL2 (pysdl2) is not available. Install with: pip install pysdl2 pysdl2-dll"}

            if _macos_display and _macos_display.is_running:
                return {
                    "success": True,
                    "enabled": True,
                    "scale": scale,
                    "message": "Live display already running."
                }

            emu = emu_thread.emulator
            width, height = emu.get_screen_size()
            title = f"GameBoy emulator - {emu.rom_title}" if emu.rom_title else "GameBoy emulator"

            display = LiveDisplay(width=width, height=height, scale=scale, title=title)

            def on_input(key: str, pressed: bool):
                try:
                    emu.set_key(key, pressed)
                except ValueError:
                    pass

            display.set_input_callback(on_input)

            if not display.init_window():
                return {"error": "Failed to create SDL window on macOS"}

            # Wire display to emulator so vblank callback feeds frames
            emu._live_display = display
            _macos_display = display

            # Start asyncio task to pump SDL events periodically
            async def _pump_sdl_events():
                try:
                    while _macos_display and _macos_display.is_running:
                        if not _macos_display.pump_events():
                            break
                        await asyncio.sleep(1 / 60)
                except asyncio.CancelledError:
                    pass
                finally:
                    # Clean up if the window was closed by user
                    if _macos_display:
                        _macos_display.cleanup()
                        emu._live_display = None

            _macos_pump_task = asyncio.create_task(_pump_sdl_events())

            return {
                "success": True,
                "enabled": True,
                "scale": scale,
                "message": "Live display window opened. Close the window or call disable_live_display to stop."
            }
        else:
            # Non-macOS: use threaded approach (works fine on Linux)
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
        if err := require_rom(emu_thread):
            return err
        global _macos_display, _macos_pump_task

        if sys.platform == "darwin" and _macos_display:
            # Cancel the pump task
            if _macos_pump_task and not _macos_pump_task.done():
                _macos_pump_task.cancel()
                try:
                    await _macos_pump_task
                except asyncio.CancelledError:
                    pass
            _macos_pump_task = None

            # Clean up display
            _macos_display.cleanup()
            emu_thread.emulator._live_display = None
            _macos_display = None

            return {
                "success": True,
                "enabled": False,
                "message": "Live display window closed."
            }
        else:
            result = emu_thread.send_command(CommandType.DISABLE_LIVE_DISPLAY)

            if result.get("error"):
                return {"error": result["error"]}

            return {
                "success": True,
                "enabled": False,
                "message": "Live display window closed."
            }

    @server.tool()
    async def set_user_input(enabled: bool) -> dict:
        """
        Enable or disable user keyboard input on the live display.

        When disabled, keyboard input from the display window is blocked,
        allowing agents to perform automated analysis or operations without
        user interference. This is useful when:
        - Running automated input sequences
        - Performing memory analysis that requires specific game states
        - Executing precise frame-by-frame operations

        Any currently pressed keys are automatically released when disabling
        to prevent stuck inputs.

        Args:
            enabled: True to allow user input, False to block it

        Returns:
            Status of user input setting
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.SET_USER_INPUT_ENABLED, {
            "enabled": enabled
        })

        if result.get("error"):
            return {"error": result["error"]}

        status = "enabled" if result.get("user_input_enabled") else "disabled"
        return {
            "success": result.get("success", False),
            "user_input_enabled": result.get("user_input_enabled", False),
            "live_display_active": result.get("live_display_active", False),
            "message": f"User keyboard input {status}."
        }

    # ============ Battery (Game Save Files) ============

    @server.tool()
    async def save_battery(path: str) -> dict:
        """
        Save the game's battery-backed RAM (SRAM) to a file.

        This saves the in-game save data (e.g., Pokemon save file) to disk.
        The file can be loaded later with load_battery to restore game progress.

        Args:
            path: File path to save to (typically .sav extension)

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.SAVE_BATTERY, {"path": path})

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "path": path,
        }

    @server.tool()
    async def load_battery(path: str) -> dict:
        """
        Load battery-backed RAM (SRAM) from a file.

        Restores in-game save data from a previously saved .sav file.

        Args:
            path: File path to load from

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.LOAD_BATTERY, {"path": path})

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": result.get("success", False),
            "path": path,
        }

    # ============ Rewind ============

    @server.tool()
    async def enable_rewind(seconds: float = 10.0) -> dict:
        """
        Enable the rewind buffer with a specified length.

        Once enabled, the emulator records state snapshots that can be
        rewound frame-by-frame using rewind_pop. Useful for undoing
        mistakes without full save states.

        Args:
            seconds: How many seconds of rewind history to keep (default 10, max 60)

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        if seconds < 0.1:
            seconds = 0.1
        if seconds > 60.0:
            seconds = 60.0

        result = emu_thread.send_command(CommandType.SET_REWIND_LENGTH, {
            "seconds": seconds
        })

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "success": True,
            "rewind_seconds": seconds,
            "message": f"Rewind buffer set to {seconds}s. Use rewind_pop to step back.",
        }

    @server.tool()
    async def rewind_pop() -> dict:
        """
        Pop one rewind state, stepping the emulator back in time.

        Each call rewinds by approximately one frame. Call multiple times
        to rewind further. Returns false if the rewind buffer is empty.

        Returns:
            Whether the rewind was successful
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.REWIND_POP)

        if result.get("error"):
            return {"error": result["error"]}

        success = result.get("success", False)
        return {
            "success": success,
            "message": "Rewound one frame." if success else "Rewind buffer empty.",
        }

    @server.tool()
    async def rewind_reset() -> dict:
        """
        Clear the rewind buffer.

        Discards all stored rewind history. Use enable_rewind to start
        recording again.

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.REWIND_RESET)

        if result.get("error"):
            return {"error": result["error"]}

        return {"success": True, "message": "Rewind buffer cleared."}

    # ============ Rendering Control ============

    @server.tool()
    async def set_rendering_disabled(disabled: bool) -> dict:
        """
        Disable or enable pixel rendering.

        When rendering is disabled, the emulator skips all pixel drawing,
        significantly speeding up execution. Useful when the agent doesn't
        need to see the screen (e.g., advancing through text, running many
        frames with turbo). Screen captures will return blank frames while
        rendering is disabled.

        Args:
            disabled: True to disable rendering, False to re-enable

        Returns:
            Confirmation message
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.SET_RENDERING_DISABLED, {
            "disabled": disabled
        })

        if result.get("error"):
            return {"error": result["error"]}

        status = "disabled" if disabled else "enabled"
        return {
            "success": True,
            "rendering": status,
            "message": f"Pixel rendering {status}.",
        }
