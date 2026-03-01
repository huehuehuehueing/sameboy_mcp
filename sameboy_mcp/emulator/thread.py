# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Emulator thread management for background execution."""

import threading
import time
from queue import Queue, Empty
from typing import Any, Callable
from dataclasses import dataclass
from enum import Enum, auto

from .core import SameBoyEmulator, EmulatorState


class CommandType(Enum):
    """Types of commands that can be sent to the emulator thread."""
    # Execution control
    PAUSE = auto()
    RESUME = auto()
    STEP_FRAME = auto()
    STEP_INSTRUCTION = auto()
    RESET = auto()

    # Memory
    READ_MEMORY = auto()
    READ_MEMORY_RANGE = auto()
    WRITE_MEMORY = auto()
    GET_DIRECT_ACCESS = auto()

    # Registers
    GET_REGISTERS = auto()

    # Display
    GET_SCREEN = auto()
    GET_SCREEN_SIZE = auto()
    GET_OAM = auto()

    # State
    SAVE_STATE = auto()
    LOAD_STATE = auto()

    # Input
    SET_KEY = auto()
    PRESS_KEY = auto()

    # Debug
    DISASSEMBLE = auto()
    SET_BREAKPOINT = auto()
    REMOVE_BREAKPOINT = auto()
    LIST_BREAKPOINTS = auto()
    CLEAR_BREAKPOINTS = auto()

    # Trace
    SET_TRACE = auto()
    GET_TRACE = auto()
    CLEAR_TRACE = auto()

    # Monitor
    ADD_MONITORS = auto()
    REMOVE_MONITORS = auto()
    GET_MEMORY_CHANGES = auto()
    CLEAR_MEMORY_CHANGES = auto()
    TAKE_SNAPSHOT = auto()
    COMPARE_SNAPSHOT = auto()

    # Status
    GET_STATUS = auto()

    # ROM
    LOAD_ROM = auto()
    LOAD_BOOT_ROM = auto()

    # Misc
    SET_TURBO = auto()

    # Live display
    ENABLE_LIVE_DISPLAY = auto()
    DISABLE_LIVE_DISPLAY = auto()
    SET_USER_INPUT_ENABLED = auto()

    # ROM disassembly
    DISASSEMBLE_ROM = auto()
    DISASSEMBLE_FUNCTION = auto()
    GET_ROM_HEADER = auto()
    FIND_FUNCTIONS = auto()

    # Battery (game save files)
    SAVE_BATTERY = auto()
    LOAD_BATTERY = auto()

    # Rewind
    SET_REWIND_LENGTH = auto()
    REWIND_POP = auto()
    REWIND_RESET = auto()

    # Rendering
    SET_RENDERING_DISABLED = auto()

    # ROM patching
    PATCH_ROM = auto()

    # Cheats
    ADD_CHEAT = auto()
    REMOVE_CHEAT = auto()
    REMOVE_ALL_CHEATS = auto()
    LIST_CHEATS = auto()
    SET_CHEATS_ENABLED = auto()
    IMPORT_CHEAT = auto()

    # Dashboard
    DASHBOARD_SNAPSHOT = auto()


@dataclass
class Command:
    """Command to send to the emulator thread."""
    type: CommandType
    args: dict
    response_queue: Queue


class EmulatorThread:
    """
    Manages the emulation loop in a background thread.

    Commands are sent via a thread-safe queue and responses
    are returned via per-command response queues.
    """

    def __init__(self, emulator: SameBoyEmulator):
        """
        Initialize the emulator thread manager.

        Args:
            emulator: The SameBoyEmulator instance to manage.
        """
        self.emulator = emulator
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._command_queue: Queue[Command] = Queue()

        # Target frame rate (approximately)
        self._target_fps = 59.7
        self._frame_time = 1.0 / self._target_fps

        # Track last frame-advancing command for activity detection
        self._last_command_frame = 0

    def start(self) -> None:
        """Start the emulator thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="EmulatorThread")
        self._thread.start()

    def stop(self) -> None:
        """Stop the emulator thread."""
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_running(self) -> bool:
        """Check if the emulator thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def send_command(self, cmd_type: CommandType, args: dict | None = None, timeout: float = 5.0) -> Any:
        """
        Send a command to the emulator thread and wait for response.

        Args:
            cmd_type: Type of command to execute.
            args: Command arguments.
            timeout: Maximum time to wait for response.

        Returns:
            Command result.

        Raises:
            TimeoutError: If response not received within timeout.
        """
        response_queue: Queue[Any] = Queue()
        cmd = Command(type=cmd_type, args=args or {}, response_queue=response_queue)
        self._command_queue.put(cmd)

        try:
            return response_queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(f"Command {cmd_type.name} timed out after {timeout}s")

    def _run_loop(self) -> None:
        """Main emulation loop running in background thread."""
        last_frame_time = time.perf_counter()

        while not self._stop_flag.is_set():
            # Process all pending commands
            self._process_commands()

            # Run emulation based on state
            state = self.emulator.state

            if state == EmulatorState.RUNNING:
                # Run one frame
                self.emulator.run_frame()

                # Check for breakpoint hit
                if self.emulator.breakpoint_hit:
                    self.emulator.state = EmulatorState.PAUSED

                # Frame timing for ~60fps when running
                current_time = time.perf_counter()
                elapsed = current_time - last_frame_time
                if elapsed < self._frame_time:
                    time.sleep(self._frame_time - elapsed)
                last_frame_time = time.perf_counter()

            elif state == EmulatorState.STEPPING:
                # Already handled by command, just switch to paused
                self.emulator.state = EmulatorState.PAUSED

            else:
                # Paused or stopped - sleep briefly to avoid busy-waiting
                time.sleep(0.01)

    def _process_commands(self) -> None:
        """Process all pending commands in the queue."""
        while True:
            try:
                cmd = self._command_queue.get_nowait()
                result = self._execute_command(cmd)
                cmd.response_queue.put(result)
            except Empty:
                break

    def _execute_command(self, cmd: Command) -> Any:
        """Execute a command and return the result."""
        emu = self.emulator
        args = cmd.args

        try:
            match cmd.type:
                # Execution control
                case CommandType.PAUSE:
                    emu.pause()
                    return {"success": True}

                case CommandType.RESUME:
                    emu.resume()
                    return {"success": True}

                case CommandType.STEP_FRAME:
                    emu.run_frame()
                    self._last_command_frame = emu.frame_count
                    return {
                        "success": True,
                        "frame": emu.frame_count,
                        "breakpoint_hit": emu.breakpoint_hit,
                    }

                case CommandType.STEP_INSTRUCTION:
                    cycles = emu.run_instruction()
                    return {
                        "success": True,
                        "cycles": cycles,
                        "breakpoint_hit": emu.breakpoint_hit,
                    }

                case CommandType.RESET:
                    emu.reset()
                    return {"success": True}

                # Memory
                case CommandType.READ_MEMORY:
                    value = emu.read_memory(args["address"])
                    return {"value": value}

                case CommandType.READ_MEMORY_RANGE:
                    data = emu.read_memory_range(args["start"], args["length"])
                    return {"data": data}

                case CommandType.WRITE_MEMORY:
                    emu.write_memory(args["address"], args["value"])
                    return {"success": True}

                case CommandType.GET_DIRECT_ACCESS:
                    data, bank = emu.get_direct_access(args["region"])
                    return {"data": data, "bank": bank}

                # Registers
                case CommandType.GET_REGISTERS:
                    return emu.get_registers()

                # Display
                case CommandType.GET_SCREEN:
                    return {"pixels": emu.get_screen_pixels()}

                case CommandType.GET_SCREEN_SIZE:
                    width, height = emu.get_screen_size()
                    return {"width": width, "height": height}

                case CommandType.GET_OAM:
                    return {"sprites": emu.get_oam_info()}

                # State
                case CommandType.SAVE_STATE:
                    data = emu.save_state()
                    return {"data": data}

                case CommandType.LOAD_STATE:
                    success = emu.load_state(args["data"])
                    return {"success": success}

                # Input
                case CommandType.SET_KEY:
                    emu.set_key(args["key"], args["pressed"])
                    return {"success": True}

                case CommandType.PRESS_KEY:
                    emu.press_key(args["key"], args.get("frames", 1))
                    self._last_command_frame = emu.frame_count
                    return {"success": True}

                # Debug
                case CommandType.DISASSEMBLE:
                    text = emu.disassemble(args.get("address"), args.get("count", 10))
                    return {"disassembly": text}

                case CommandType.SET_BREAKPOINT:
                    emu.set_breakpoint(args["address"], args.get("enabled", True))
                    return {"success": True}

                case CommandType.REMOVE_BREAKPOINT:
                    success = emu.remove_breakpoint(args["address"])
                    return {"success": success}

                case CommandType.LIST_BREAKPOINTS:
                    return {"breakpoints": emu.list_breakpoints()}

                case CommandType.CLEAR_BREAKPOINTS:
                    emu.clear_breakpoints()
                    return {"success": True}

                # Trace
                case CommandType.SET_TRACE:
                    emu.set_trace_enabled(args["enabled"], args.get("limit", 10000))
                    return {"success": True}

                case CommandType.GET_TRACE:
                    trace = emu.get_trace(args.get("count", 100))
                    return {"trace": trace}

                case CommandType.CLEAR_TRACE:
                    emu.clear_trace()
                    return {"success": True}

                # Monitor
                case CommandType.ADD_MONITORS:
                    emu.add_memory_monitors(args["addresses"])
                    return {"success": True}

                case CommandType.REMOVE_MONITORS:
                    emu.remove_memory_monitors(args.get("addresses"))
                    return {"success": True}

                case CommandType.GET_MEMORY_CHANGES:
                    changes = emu.get_memory_changes(args.get("since_frame"))
                    return {"changes": changes}

                case CommandType.CLEAR_MEMORY_CHANGES:
                    emu.clear_memory_changes()
                    return {"success": True}

                case CommandType.TAKE_SNAPSHOT:
                    emu.take_memory_snapshot()
                    return {"success": True}

                case CommandType.COMPARE_SNAPSHOT:
                    changes = emu.compare_memory_snapshot()
                    formatted = {
                        f"0x{addr:04X}": {"old": old, "new": new}
                        for addr, (old, new) in changes.items()
                    }
                    return {"changes": formatted}

                # Status
                case CommandType.GET_STATUS:
                    return emu.get_status()

                # ROM
                case CommandType.LOAD_ROM:
                    success = emu.load_rom(args["path"])
                    return {"success": success, "title": emu.rom_title if success else None}

                case CommandType.LOAD_BOOT_ROM:
                    success = emu.load_boot_rom(args["path"])
                    return {"success": success}

                # Misc
                case CommandType.SET_TURBO:
                    emu.set_turbo(args["enabled"], args.get("no_frame_skip", False))
                    return {"success": True}

                # Live display
                case CommandType.ENABLE_LIVE_DISPLAY:
                    success = emu.enable_live_display(args.get("scale", 2))
                    return {"success": success, "enabled": emu.live_display_enabled}

                case CommandType.DISABLE_LIVE_DISPLAY:
                    emu.disable_live_display()
                    return {"success": True, "enabled": False}

                case CommandType.SET_USER_INPUT_ENABLED:
                    success = emu.set_user_input_enabled(args["enabled"])
                    return {
                        "success": success,
                        "user_input_enabled": emu.user_input_enabled,
                        "live_display_active": emu.live_display_enabled
                    }

                # ROM disassembly
                case CommandType.DISASSEMBLE_ROM:
                    result = emu.disassemble_rom(
                        args.get("start", 0),
                        args.get("end"),
                        args.get("max_instructions", 1000)
                    )
                    return result

                case CommandType.DISASSEMBLE_FUNCTION:
                    result = emu.disassemble_function(
                        args["address"],
                        args.get("max_size", 256)
                    )
                    return result

                case CommandType.GET_ROM_HEADER:
                    return emu.get_rom_header()

                case CommandType.FIND_FUNCTIONS:
                    result = emu.find_functions(
                        args.get("scan_start"),
                        args.get("scan_end")
                    )
                    return result

                # Battery (game save files)
                case CommandType.SAVE_BATTERY:
                    success = emu.save_battery(args["path"])
                    return {"success": success}

                case CommandType.LOAD_BATTERY:
                    success = emu.load_battery(args["path"])
                    return {"success": success}

                # Rewind
                case CommandType.SET_REWIND_LENGTH:
                    emu.set_rewind_length(args["seconds"])
                    return {"success": True}

                case CommandType.REWIND_POP:
                    success = emu.rewind_pop()
                    return {"success": success}

                case CommandType.REWIND_RESET:
                    emu.rewind_reset()
                    return {"success": True}

                # Rendering
                case CommandType.SET_RENDERING_DISABLED:
                    emu.set_rendering_disabled(args["disabled"])
                    return {"success": True}

                # ROM patching
                case CommandType.PATCH_ROM:
                    old_val, new_val = emu.patch_rom(args["address"], args["value"])
                    return {
                        "success": True,
                        "address": f"0x{args['address']:X}",
                        "old_value": old_val,
                        "new_value": new_val,
                    }

                # Cheats
                case CommandType.ADD_CHEAT:
                    return emu.add_cheat(
                        args["description"], args["address"], args["bank"],
                        args["value"], args["old_value"], args["use_old_value"],
                        args["enabled"]
                    )

                case CommandType.REMOVE_CHEAT:
                    success = emu.remove_cheat(args["index"])
                    return {"success": success}

                case CommandType.REMOVE_ALL_CHEATS:
                    emu.remove_all_cheats()
                    return {"success": True}

                case CommandType.LIST_CHEATS:
                    cheats = emu.list_cheats()
                    return {
                        "cheats": cheats,
                        "count": len(cheats),
                        "globally_enabled": emu.cheats_enabled(),
                    }

                case CommandType.SET_CHEATS_ENABLED:
                    emu.set_cheats_enabled(args["enabled"])
                    return {"success": True, "enabled": args["enabled"]}

                case CommandType.IMPORT_CHEAT:
                    return emu.import_cheat(
                        args["code"], args["description"], args["enabled"]
                    )

                # Dashboard
                case CommandType.DASHBOARD_SNAPSHOT:
                    regs = emu.get_registers()
                    disasm = emu.disassemble(regs["PC"], 50)
                    status = emu.get_status()
                    activity = "active" if (emu.frame_count - self._last_command_frame) < 30 else "idle"
                    return {
                        "registers": regs,
                        "disassembly": disasm,
                        "status": status,
                        "frame_count": emu.frame_count,
                        "activity": activity,
                    }

                case _:
                    return {"error": f"Unknown command type: {cmd.type}"}

        except Exception as e:
            return {"error": str(e)}


# Convenience functions for common operations
def create_emulator_thread(lib_path: str | None = None, model: str = "CGB_E") -> tuple[SameBoyEmulator, EmulatorThread]:
    """
    Create and initialize an emulator with background thread.

    Args:
        lib_path: Path to libsameboy.so.
        model: Game Boy model.

    Returns:
        Tuple of (emulator, thread).
    """
    emulator = SameBoyEmulator(lib_path)
    emulator.init(model)
    thread = EmulatorThread(emulator)
    return emulator, thread
