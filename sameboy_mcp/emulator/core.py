# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""SameBoy emulator wrapper class."""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any, TYPE_CHECKING
from enum import Enum, auto
from collections import deque
import threading

from .bindings import ffi, load_library, MODEL_MAP, KEY_MAP, DIRECT_ACCESS_MAP, DMG_PALETTES, create_palette

if TYPE_CHECKING:
    from .display import LiveDisplay


class EmulatorState(Enum):
    """Emulator execution state."""
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STEPPING = auto()


@dataclass
class ExecutionTraceEntry:
    """Single entry in execution trace."""
    address: int
    opcode: int
    frame: int

    def to_dict(self) -> dict:
        return {
            "address": f"0x{self.address:04X}",
            "opcode": f"0x{self.opcode:02X}",
            "frame": self.frame,
        }


@dataclass
class MemoryChange:
    """Record of a memory write."""
    address: int
    old_value: int
    new_value: int
    frame: int

    def to_dict(self) -> dict:
        return {
            "address": f"0x{self.address:04X}",
            "old_value": f"0x{self.old_value:02X}",
            "new_value": f"0x{self.new_value:02X}",
            "frame": self.frame,
        }


@dataclass
class Breakpoint:
    """Execution breakpoint."""
    address: int
    enabled: bool = True
    hit_count: int = 0


class SameBoyEmulator:
    """High-level wrapper around libsameboy."""

    # Screen dimensions
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144
    SCREEN_WIDTH_SGB = 256
    SCREEN_HEIGHT_SGB = 224

    def __init__(self, lib_path: str | None = None):
        """
        Initialize the emulator wrapper.

        Args:
            lib_path: Path to libsameboy.so. If None, searches default locations.
        """
        self.lib = load_library(lib_path)
        self.gb: Any = None  # GB_gameboy_t pointer

        # State management
        self._state_lock = threading.RLock()
        self._state = EmulatorState.STOPPED
        self._frame_count = 0

        # Frame buffer (max size for SGB border)
        self._pixel_buffer = ffi.new(f"uint32_t[{self.SCREEN_WIDTH_SGB * self.SCREEN_HEIGHT_SGB}]")

        # Execution tracing
        self._execution_trace: deque[ExecutionTraceEntry] = deque(maxlen=10000)
        self._trace_enabled = False

        # Memory monitoring
        self._memory_monitors: set[int] = set()
        self._memory_changes: list[MemoryChange] = []
        self._memory_snapshot: Optional[bytes] = None

        # Breakpoints
        self._breakpoints: dict[int, Breakpoint] = {}
        self._breakpoint_hit = False

        # Disassembly output capture
        self._disasm_output: list[str] = []

        # Store callbacks to prevent garbage collection
        self._callbacks: dict[str, Any] = {}

        # ROM info
        self._rom_loaded = False
        self._rom_title = ""

        # Live display
        self._live_display: Optional["LiveDisplay"] = None

        # Dashboard frame relay
        self._dashboard_frame_relay: Optional[Any] = None

        # Rendering and rewind state
        self._rendering_disabled = False
        self._rewind_seconds = 0.0

    def init(self, model: str = "CGB_E") -> None:
        """
        Initialize the Game Boy emulator.

        Args:
            model: Game Boy model (DMG_B, CGB_E, AGB, etc.)
        """
        if model not in MODEL_MAP:
            raise ValueError(f"Unknown model: {model}. Valid models: {list(MODEL_MAP.keys())}")

        self.gb = self.lib.GB_alloc()
        if self.gb == ffi.NULL:
            raise RuntimeError("Failed to allocate GB_gameboy_t")

        self.lib.GB_init(self.gb, MODEL_MAP[model])
        self.lib.GB_set_pixels_output(self.gb, self._pixel_buffer)

        # Set palette for DMG models (non-CGB models need a palette for rendering)
        # CGB models (0x200+) have their own color system, DMG models need explicit palette
        model_id = MODEL_MAP[model]
        if model_id < 0x200:
            palette = create_palette(DMG_PALETTES["dmg"])
            self.lib.GB_set_palette(self.gb, palette)
            # Keep reference to prevent garbage collection
            self._dmg_palette = palette

        self._setup_callbacks()
        self._state = EmulatorState.PAUSED

    def _setup_callbacks(self) -> None:
        """Register internal callbacks with the emulator."""
        # Vblank callback
        @ffi.callback("void(GB_gameboy_t*, GB_vblank_type_t)")
        def vblank_cb(gb, vblank_type):
            self._frame_count += 1
            # vblank_type 0 = normal frame, skip others to avoid duplicate frames
            if vblank_type != 0:
                return
            # Update live display if enabled
            if self._live_display and self._live_display.is_running:
                pixels = self.get_screen_pixels()
                self._live_display.update_frame(pixels)
            # Update dashboard frame relay if enabled
            if self._dashboard_frame_relay:
                if not (self._live_display and self._live_display.is_running):
                    pixels = self.get_screen_pixels()
                width, height = self.get_screen_size()
                self._dashboard_frame_relay.on_vblank(pixels, width, height)

        self._callbacks["vblank"] = vblank_cb
        self.lib.GB_set_vblank_callback(self.gb, vblank_cb)

        # Execution callback (for tracing and breakpoints)
        @ffi.callback("void(GB_gameboy_t*, uint16_t, uint8_t)")
        def execution_cb(gb, address, opcode):
            if self._trace_enabled:
                self._execution_trace.append(ExecutionTraceEntry(
                    address=address,
                    opcode=opcode,
                    frame=self._frame_count
                ))

            if address in self._breakpoints:
                bp = self._breakpoints[address]
                if bp.enabled:
                    bp.hit_count += 1
                    self._breakpoint_hit = True

        self._callbacks["execution"] = execution_cb
        self.lib.GB_set_execution_callback(self.gb, execution_cb)

        # Memory write callback (for monitoring)
        # Return True to allow the write, False to prevent it
        @ffi.callback("bool(GB_gameboy_t*, uint16_t, uint8_t)")
        def write_memory_cb(gb, address, value):
            if address in self._memory_monitors:
                old_value = self.lib.GB_safe_read_memory(self.gb, address)
                if old_value != value:
                    self._memory_changes.append(MemoryChange(
                        address=address,
                        old_value=old_value,
                        new_value=value,
                        frame=self._frame_count
                    ))
            return True  # Allow the write to proceed

        self._callbacks["write_memory"] = write_memory_cb
        self.lib.GB_set_write_memory_callback(self.gb, write_memory_cb)

        # Log callback (for disassembly capture)
        @ffi.callback("void(GB_gameboy_t*, const char*, GB_log_attributes_t)")
        def log_cb(gb, string, attributes):
            text = ffi.string(string).decode("utf-8", errors="replace")
            self._disasm_output.append(text)

        self._callbacks["log"] = log_cb
        self.lib.GB_set_log_callback(self.gb, log_cb)

        # RGB encode callback (standard ARGB format)
        @ffi.callback("uint32_t(GB_gameboy_t*, uint8_t, uint8_t, uint8_t)")
        def rgb_encode_cb(gb, r, g, b):
            return (0xFF << 24) | (r << 16) | (g << 8) | b

        self._callbacks["rgb_encode"] = rgb_encode_cb
        self.lib.GB_set_rgb_encode_callback(self.gb, rgb_encode_cb)

    def free(self) -> None:
        """Free emulator resources."""
        # Stop live display if running
        if self._live_display:
            self._live_display.stop()
            self._live_display = None

        if self.gb is not None and self.gb != ffi.NULL:
            self.lib.GB_free(self.gb)
            self.lib.GB_dealloc(self.gb)
            self.gb = None
            self._state = EmulatorState.STOPPED

    def _init_post_boot_state(self) -> None:
        """Initialize the emulator to post-boot ROM state.

        When no boot ROM is provided, we need to manually set up the
        hardware state that the boot ROM would normally configure.
        """
        # Skip the boot ROM by writing 1 to BANK register (0xFF50)
        self.lib.GB_write_memory(self.gb, 0xFF50, 1)

        # Set CPU registers to post-boot values
        regs = self.lib.GB_get_registers(self.gb)

        if self.is_cgb:
            # CGB post-boot register values
            regs.af = 0x1180  # A=0x11 indicates CGB
            regs.bc = 0x0000
            regs.de = 0xFF56
            regs.hl = 0x000D
            regs.sp = 0xFFFE
            regs.pc = 0x0100
        else:
            # DMG post-boot register values
            regs.af = 0x01B0
            regs.bc = 0x0013
            regs.de = 0x00D8
            regs.hl = 0x014D
            regs.sp = 0xFFFE
            regs.pc = 0x0100

        # Set I/O registers to post-boot values
        self.lib.GB_write_memory(self.gb, 0xFF40, 0x91)  # LCDC - LCD on, BG on
        self.lib.GB_write_memory(self.gb, 0xFF47, 0xFC)  # BGP - background palette

    def load_rom(self, path: str) -> bool:
        """
        Load a ROM file.

        Args:
            path: Path to the .gb or .gbc file.

        Returns:
            True if loaded successfully.
        """
        result = self.lib.GB_load_rom(self.gb, path.encode("utf-8"))
        if result == 0:
            self._rom_loaded = True
            title_buf = ffi.new("char[17]")
            self.lib.GB_get_rom_title(self.gb, title_buf)
            self._rom_title = ffi.string(title_buf).decode("utf-8", errors="replace").strip()
            self._init_post_boot_state()
            return True
        return False

    def load_rom_from_bytes(self, data: bytes) -> None:
        """Load ROM from memory."""
        buf = ffi.from_buffer("uint8_t[]", data)
        self.lib.GB_load_rom_from_buffer(self.gb, buf, len(data))
        self._rom_loaded = True
        self._init_post_boot_state()

    def load_boot_rom(self, path: str) -> bool:
        """Load a boot ROM file."""
        result = self.lib.GB_load_boot_rom(self.gb, path.encode("utf-8"))
        return result == 0

    def reset(self) -> None:
        """Reset the emulator."""
        self.lib.GB_reset(self.gb)
        self._frame_count = 0

    # ============ Execution Control ============

    def run_frame(self) -> int:
        """
        Run emulation for one frame.

        Returns:
            Time elapsed in nanoseconds.
        """
        self._breakpoint_hit = False
        return self.lib.GB_run_frame(self.gb)

    def run_instruction(self) -> int:
        """
        Run a single CPU instruction.

        Returns:
            Number of cycles executed.
        """
        self._breakpoint_hit = False
        return self.lib.GB_run(self.gb)

    @property
    def state(self) -> EmulatorState:
        """Get current emulator state."""
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, value: EmulatorState) -> None:
        """Set emulator state."""
        with self._state_lock:
            self._state = value

    def pause(self) -> None:
        """Pause emulation."""
        self.state = EmulatorState.PAUSED

    def resume(self) -> None:
        """Resume emulation."""
        self.state = EmulatorState.RUNNING

    @property
    def frame_count(self) -> int:
        """Get current frame count."""
        return self._frame_count

    @property
    def rom_title(self) -> str:
        """Get loaded ROM title."""
        return self._rom_title

    @property
    def is_cgb(self) -> bool:
        """Check if running in CGB mode."""
        return bool(self.lib.GB_is_cgb(self.gb))

    # ============ Memory Access ============

    def read_memory(self, address: int) -> int:
        """Read a byte from memory (safe, no side effects)."""
        return self.lib.GB_safe_read_memory(self.gb, address & 0xFFFF)

    def read_memory_range(self, start: int, length: int) -> bytes:
        """Read a range of bytes from memory."""
        return bytes(self.read_memory(start + i) for i in range(length))

    def write_memory(self, address: int, value: int) -> None:
        """Write a byte to memory."""
        self.lib.GB_write_memory(self.gb, address & 0xFFFF, value & 0xFF)

    def get_direct_access(self, region: str) -> tuple[bytes, int]:
        """
        Get direct access to a memory region.

        Args:
            region: Region name (rom, ram, vram, oam, hram, cart_ram, io)

        Returns:
            Tuple of (data bytes, current bank number)
        """
        if region.lower() not in DIRECT_ACCESS_MAP:
            raise ValueError(f"Unknown region: {region}")

        size = ffi.new("size_t*")
        bank = ffi.new("uint16_t*")
        ptr = self.lib.GB_get_direct_access(self.gb, DIRECT_ACCESS_MAP[region.lower()], size, bank)

        if ptr == ffi.NULL:
            return (b"", 0)

        data = bytes(ffi.buffer(ptr, size[0]))
        return (data, bank[0])

    def patch_rom(self, address: int, value: int) -> tuple[int, int]:
        """
        Patch a byte in the ROM buffer directly.

        Uses GB_get_direct_access to get a writable pointer to the ROM,
        bypassing MBC bank-switching that makes GB_write_memory fail for ROM.

        Args:
            address: ROM address (0 to ROM size - 1)
            value: Byte value to write (0x00-0xFF)

        Returns:
            Tuple of (old_value, new_value)

        Raises:
            RuntimeError: If ROM not loaded or address out of bounds
        """
        if not self._rom_loaded:
            raise RuntimeError("No ROM loaded")

        size = ffi.new("size_t*")
        bank = ffi.new("uint16_t*")
        ptr = self.lib.GB_get_direct_access(self.gb, DIRECT_ACCESS_MAP["rom"], size, bank)

        if ptr == ffi.NULL:
            raise RuntimeError("Failed to get ROM direct access")

        rom_size = size[0]
        if address < 0 or address >= rom_size:
            raise ValueError(f"Address 0x{address:X} out of ROM bounds (0x0-0x{rom_size - 1:X})")

        buf = ffi.buffer(ptr, rom_size)
        old_value = buf[address] if isinstance(buf[address], int) else buf[address][0]
        buf[address] = bytes([value & 0xFF])
        return (old_value, value & 0xFF)

    # ============ Registers ============

    def get_registers(self) -> dict:
        """Get all CPU registers."""
        regs = self.lib.GB_get_registers(self.gb)
        af = regs.af
        bc = regs.bc
        de = regs.de
        hl = regs.hl
        sp = regs.sp
        pc = regs.pc

        # Extract flags
        f = af & 0xFF
        flags = {
            "Z": bool(f & 0x80),
            "N": bool(f & 0x40),
            "H": bool(f & 0x20),
            "C": bool(f & 0x10),
        }

        return {
            "AF": af,
            "BC": bc,
            "DE": de,
            "HL": hl,
            "SP": sp,
            "PC": pc,
            "A": (af >> 8) & 0xFF,
            "F": f,
            "B": (bc >> 8) & 0xFF,
            "C": bc & 0xFF,
            "D": (de >> 8) & 0xFF,
            "E": de & 0xFF,
            "H": (hl >> 8) & 0xFF,
            "L": hl & 0xFF,
            "flags": flags,
        }

    # ============ Display ============

    def get_screen_size(self) -> tuple[int, int]:
        """Get current screen dimensions."""
        width = self.lib.GB_get_screen_width(self.gb)
        height = self.lib.GB_get_screen_height(self.gb)
        return (width, height)

    def get_screen_pixels(self) -> bytes:
        """
        Get current screen as ARGB pixel data.

        Returns:
            Raw pixel data (width * height * 4 bytes, ARGB format)
        """
        width, height = self.get_screen_size()
        pixels = self.lib.GB_get_pixels_output(self.gb)
        return bytes(ffi.buffer(pixels, width * height * 4))

    def get_oam_info(self) -> list[dict]:
        """Get sprite/OAM information."""
        oam_array = ffi.new("GB_oam_info_t[40]")
        object_height = ffi.new("uint8_t*")
        count = self.lib.GB_get_oam_info(self.gb, oam_array, object_height)

        sprites = []
        for i in range(count):
            oam = oam_array[i]
            sprites.append({
                "index": i,
                "x": oam.x,
                "y": oam.y,
                "tile": oam.tile,
                "flags": oam.flags,
                "oam_address": f"0x{oam.oam_addr:04X}",
                "obscured": oam.obscured_by_line_limit,
            })
        return sprites

    # ============ Save States ============

    def save_state(self) -> bytes:
        """Save emulator state to bytes."""
        size = self.lib.GB_get_save_state_size(self.gb)
        buffer = ffi.new(f"uint8_t[{size}]")
        self.lib.GB_save_state_to_buffer(self.gb, buffer)
        return bytes(ffi.buffer(buffer, size))

    def load_state(self, data: bytes) -> bool:
        """Load emulator state from bytes."""
        buf = ffi.from_buffer("uint8_t[]", data)
        result = self.lib.GB_load_state_from_buffer(self.gb, buf, len(data))
        return result == 0

    def save_state_to_file(self, path: str) -> bool:
        """Save state to file."""
        result = self.lib.GB_save_state(self.gb, path.encode("utf-8"))
        return result == 0

    def load_state_from_file(self, path: str) -> bool:
        """Load state from file."""
        result = self.lib.GB_load_state(self.gb, path.encode("utf-8"))
        return result == 0

    # ============ Input ============

    def set_key(self, key: str, pressed: bool) -> None:
        """Set joypad key state."""
        key_lower = key.lower()
        if key_lower not in KEY_MAP:
            raise ValueError(f"Unknown key: {key}. Valid keys: {list(KEY_MAP.keys())}")
        self.lib.GB_set_key_state(self.gb, KEY_MAP[key_lower], pressed)

    def press_key(self, key: str, frames: int = 1) -> None:
        """Press a key for a number of frames."""
        self.set_key(key, True)
        for _ in range(frames):
            self.run_frame()
        self.set_key(key, False)

    # ============ Debugging ============

    def disassemble(self, address: int | None = None, count: int = 10) -> str:
        """
        Disassemble instructions.

        Args:
            address: Starting address (None for current PC)
            count: Number of instructions

        Returns:
            Disassembly text
        """
        if address is None:
            regs = self.get_registers()
            address = regs["PC"]

        self._disasm_output.clear()
        self.lib.GB_cpu_disassemble(self.gb, address, count)
        return "".join(self._disasm_output)

    # ============ Breakpoints ============

    def set_breakpoint(self, address: int, enabled: bool = True) -> None:
        """Set a breakpoint at an address."""
        self._breakpoints[address] = Breakpoint(address=address, enabled=enabled)

    def remove_breakpoint(self, address: int) -> bool:
        """Remove a breakpoint."""
        if address in self._breakpoints:
            del self._breakpoints[address]
            return True
        return False

    def clear_breakpoints(self) -> None:
        """Clear all breakpoints."""
        self._breakpoints.clear()

    def list_breakpoints(self) -> list[dict]:
        """List all breakpoints."""
        return [
            {
                "address": f"0x{bp.address:04X}",
                "enabled": bp.enabled,
                "hit_count": bp.hit_count,
            }
            for bp in self._breakpoints.values()
        ]

    @property
    def breakpoint_hit(self) -> bool:
        """Check if a breakpoint was hit."""
        return self._breakpoint_hit

    # ============ Execution Tracing ============

    def set_trace_enabled(self, enabled: bool, limit: int = 10000) -> None:
        """Enable or disable execution tracing."""
        self._trace_enabled = enabled
        if limit != self._execution_trace.maxlen:
            old_entries = list(self._execution_trace)
            self._execution_trace = deque(old_entries[-limit:], maxlen=limit)

    def get_trace(self, count: int = 100) -> list[dict]:
        """Get recent trace entries."""
        entries = list(self._execution_trace)[-count:]
        return [e.to_dict() for e in entries]

    def clear_trace(self) -> None:
        """Clear execution trace."""
        self._execution_trace.clear()

    # ============ Memory Monitoring ============

    def add_memory_monitors(self, addresses: list[int]) -> None:
        """Add addresses to monitor for writes."""
        self._memory_monitors.update(addresses)

    def remove_memory_monitors(self, addresses: list[int] | None = None) -> None:
        """Remove monitored addresses."""
        if addresses is None:
            self._memory_monitors.clear()
        else:
            self._memory_monitors -= set(addresses)

    def get_memory_changes(self, since_frame: int | None = None) -> list[dict]:
        """Get detected memory changes."""
        changes = self._memory_changes
        if since_frame is not None:
            changes = [c for c in changes if c.frame > since_frame]
        return [c.to_dict() for c in changes]

    def clear_memory_changes(self) -> None:
        """Clear memory change log."""
        self._memory_changes.clear()

    def take_memory_snapshot(self) -> None:
        """Take a snapshot of RAM for comparison."""
        # Snapshot WRAM (0xC000-0xDFFF) and HRAM (0xFF80-0xFFFE)
        wram = self.read_memory_range(0xC000, 0x2000)
        hram = self.read_memory_range(0xFF80, 0x7F)
        self._memory_snapshot = wram + hram

    def compare_memory_snapshot(self) -> dict[int, tuple[int, int]]:
        """
        Compare current memory with snapshot.

        Returns:
            Dict mapping address to (old_value, new_value)
        """
        if self._memory_snapshot is None:
            return {}

        changes = {}

        # Compare WRAM
        for i in range(0x2000):
            addr = 0xC000 + i
            old_val = self._memory_snapshot[i]
            new_val = self.read_memory(addr)
            if old_val != new_val:
                changes[addr] = (old_val, new_val)

        # Compare HRAM
        for i in range(0x7F):
            addr = 0xFF80 + i
            old_val = self._memory_snapshot[0x2000 + i]
            new_val = self.read_memory(addr)
            if old_val != new_val:
                changes[addr] = (old_val, new_val)

        return changes

    # ============ Battery (Game Save Files) ============

    def save_battery(self, path: str) -> bool:
        """Save battery/SRAM to a file (.sav)."""
        result = self.lib.GB_save_battery(self.gb, path.encode("utf-8"))
        return result == 0

    def load_battery(self, path: str) -> bool:
        """Load battery/SRAM from a file (.sav)."""
        result = self.lib.GB_load_battery(self.gb, path.encode("utf-8"))
        return result == 0

    # ============ Rewind ============

    def set_rewind_length(self, seconds: float) -> None:
        """Set the rewind buffer length in seconds."""
        self.lib.GB_set_rewind_length(self.gb, seconds)
        self._rewind_seconds = seconds

    def rewind_pop(self) -> bool:
        """Pop one rewind state, stepping back in time."""
        return bool(self.lib.GB_rewind_pop(self.gb))

    def rewind_reset(self) -> None:
        """Clear the rewind buffer."""
        self.lib.GB_rewind_reset(self.gb)

    # ============ Rendering Control ============

    def set_rendering_disabled(self, disabled: bool) -> None:
        """Disable or enable pixel rendering (faster headless execution)."""
        self.lib.GB_set_rendering_disabled(self.gb, disabled)
        self._rendering_disabled = disabled

    # ============ Turbo Mode ============

    def set_turbo(self, enabled: bool, no_frame_skip: bool = False) -> None:
        """Enable or disable turbo mode."""
        self.lib.GB_set_turbo_mode(self.gb, enabled, no_frame_skip)

    # ============ Status ============

    def get_status(self) -> dict:
        """Get current emulator status."""
        return {
            "state": self.state.name,
            "rom_loaded": self._rom_loaded,
            "rom_title": self._rom_title,
            "frame_count": self._frame_count,
            "is_cgb": self.is_cgb if self._rom_loaded else None,
            "trace_enabled": self._trace_enabled,
            "breakpoint_count": len(self._breakpoints),
            "monitored_addresses": len(self._memory_monitors),
            "live_display": self._live_display.is_running if self._live_display else False,
        }

    # ============ Live Display ============

    def enable_live_display(self, scale: int = 2) -> bool:
        """
        Enable live display window showing frames in real-time.

        Args:
            scale: Display scaling factor (1-4)

        Returns:
            True if display was enabled successfully
        """
        from .display import LiveDisplay, is_available

        if not is_available():
            return False

        if self._live_display and self._live_display.is_running:
            return True  # Already running

        width, height = self.get_screen_size()
        title = f"SameBoy MCP - {self._rom_title}" if self._rom_title else "SameBoy MCP"

        self._live_display = LiveDisplay(
            width=width,
            height=height,
            scale=scale,
            title=title
        )

        # Set up input callback to forward keyboard input to emulator
        def on_input(key: str, pressed: bool):
            try:
                self.set_key(key, pressed)
            except ValueError:
                pass  # Ignore unknown keys

        self._live_display.set_input_callback(on_input)
        if not self._live_display.start():
            self._live_display = None
            return False
        return True

    def disable_live_display(self) -> None:
        """Disable and close the live display window."""
        if self._live_display:
            self._live_display.stop()
            self._live_display = None

    @property
    def live_display_enabled(self) -> bool:
        """Check if live display is enabled and running."""
        return self._live_display is not None and self._live_display.is_running

    def set_user_input_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable user keyboard input on the live display.

        When disabled, keyboard input from the display window is blocked,
        allowing agents to perform automated operations without user
        interference. Any currently pressed keys are released when disabling.

        Args:
            enabled: Whether to allow user keyboard input

        Returns:
            True if the setting was applied, False if no live display
        """
        if self._live_display and self._live_display.is_running:
            self._live_display.set_user_input_enabled(enabled)
            return True
        return False

    @property
    def user_input_enabled(self) -> bool:
        """Check if user keyboard input is enabled on the live display."""
        if self._live_display and self._live_display.is_running:
            return self._live_display.user_input_enabled
        return False

    # ============ Cheats ============

    def add_cheat(self, description: str, address: int, bank: int, value: int,
                  old_value: int, use_old_value: bool, enabled: bool) -> dict:
        """Add a cheat code."""
        cheat = self.lib.GB_add_cheat(
            self.gb, description.encode("utf-8"),
            address & 0xFFFF, bank & 0xFFFF, value & 0xFF,
            old_value & 0xFF, use_old_value, enabled
        )
        if cheat == ffi.NULL:
            return {"error": "Failed to add cheat"}
        return {
            "address": cheat.address,
            "bank": cheat.bank,
            "value": cheat.value,
            "description": ffi.string(cheat.description).decode("utf-8", errors="replace"),
            "enabled": cheat.enabled,
        }

    def remove_cheat(self, index: int) -> bool:
        """Remove a cheat by index."""
        size = ffi.new("size_t*")
        cheats_ptr = self.lib.GB_get_cheats(self.gb, size)
        if index < 0 or index >= size[0]:
            return False
        self.lib.GB_remove_cheat(self.gb, cheats_ptr[index])
        return True

    def remove_all_cheats(self) -> None:
        """Remove all cheats."""
        self.lib.GB_remove_all_cheats(self.gb)

    def list_cheats(self) -> list[dict]:
        """List all cheats."""
        size = ffi.new("size_t*")
        cheats_ptr = self.lib.GB_get_cheats(self.gb, size)
        result = []
        for i in range(size[0]):
            c = cheats_ptr[i]
            result.append({
                "index": i,
                "description": ffi.string(c.description).decode("utf-8", errors="replace"),
                "address": c.address,
                "bank": c.bank,
                "value": c.value,
                "old_value": c.old_value,
                "use_old_value": c.use_old_value,
                "enabled": c.enabled,
            })
        return result

    def cheats_enabled(self) -> bool:
        """Check if cheats are globally enabled."""
        return bool(self.lib.GB_cheats_enabled(self.gb))

    def set_cheats_enabled(self, enabled: bool) -> None:
        """Enable or disable cheats globally."""
        self.lib.GB_set_cheats_enabled(self.gb, enabled)

    def import_cheat(self, code: str, description: str, enabled: bool) -> dict:
        """Import a GameShark/Game Genie cheat code string."""
        cheat = self.lib.GB_import_cheat(
            self.gb, code.encode("utf-8"),
            description.encode("utf-8"), enabled
        )
        if cheat == ffi.NULL:
            return {"error": f"Failed to parse cheat code: {code}"}
        return {
            "address": cheat.address,
            "bank": cheat.bank,
            "value": cheat.value,
            "old_value": cheat.old_value,
            "use_old_value": cheat.use_old_value,
            "description": ffi.string(cheat.description).decode("utf-8", errors="replace"),
            "enabled": cheat.enabled,
        }

    # ============ Dashboard ============

    def set_dashboard_frame_relay(self, relay) -> None:
        """Set the dashboard frame relay for streaming frames to the web UI."""
        self._dashboard_frame_relay = relay

    # ============ ROM Disassembly ============

    def disassemble_rom(self, start: int = 0, end: int | None = None, max_instructions: int = 1000) -> dict:
        """
        Disassemble a range of the loaded ROM using the full disassembler.

        Args:
            start: Starting address (default 0)
            end: Ending address (default: based on max_instructions or ROM size)
            max_instructions: Maximum instructions to disassemble

        Returns:
            Disassembly result with instructions and metadata
        """
        if not self._rom_loaded:
            return {"error": "No ROM loaded"}

        from .disasm import Disassembler

        # Get ROM data via direct access
        rom_data, bank = self.get_direct_access("rom")
        if rom_data is None:
            return {"error": "Failed to access ROM data"}

        disasm = Disassembler(rom_data)

        # Determine end address
        if end is None:
            # Estimate based on max_instructions (average ~2 bytes per instruction)
            end = min(start + max_instructions * 3, len(rom_data))

        instructions = []
        addr = start
        count = 0

        for inst in disasm.disassemble_range(start, end):
            instructions.append({
                "address": f"0x{inst.address:04X}",
                "bytes": inst.bytes.hex(),
                "mnemonic": inst.mnemonic,
                "operands": inst.operands,
                "size": inst.size,
                "is_jump": inst.is_jump,
                "is_call": inst.is_call,
                "is_return": inst.is_return,
                "is_conditional": inst.is_conditional,
                "jump_target": f"0x{inst.jump_target:04X}" if inst.jump_target else None,
            })
            count += 1
            if count >= max_instructions:
                break
            addr = inst.address + inst.size

        return {
            "start": f"0x{start:04X}",
            "end": f"0x{addr:04X}",
            "instruction_count": len(instructions),
            "instructions": instructions,
            "rom_title": self._rom_title,
        }

    def disassemble_function(self, address: int, max_size: int = 256) -> dict:
        """
        Disassemble a function starting at address.

        Args:
            address: Starting address
            max_size: Maximum bytes to disassemble

        Returns:
            Function disassembly with control flow info
        """
        if not self._rom_loaded:
            return {"error": "No ROM loaded"}

        from .disasm import Disassembler

        # Get ROM data
        rom_data, bank = self.get_direct_access("rom")
        if rom_data is None:
            return {"error": "Failed to access ROM data"}

        disasm = Disassembler(rom_data)
        insts = disasm.disassemble_function(address, max_size)

        instructions = []
        call_targets = []
        jump_targets = []

        for inst in insts:
            instructions.append({
                "address": f"0x{inst.address:04X}",
                "bytes": inst.bytes.hex(),
                "mnemonic": inst.mnemonic,
                "operands": inst.operands,
                "text": str(inst),
            })

            if inst.is_call and inst.jump_target:
                call_targets.append(f"0x{inst.jump_target:04X}")
            elif inst.is_jump and inst.jump_target:
                jump_targets.append(f"0x{inst.jump_target:04X}")

        return {
            "address": f"0x{address:04X}",
            "size": sum(len(i["bytes"]) // 2 for i in instructions),
            "instruction_count": len(instructions),
            "instructions": instructions,
            "call_targets": list(set(call_targets)),
            "jump_targets": list(set(jump_targets)),
            "disassembly": "\n".join(str(i) for i in insts),
        }

    def get_rom_header(self) -> dict:
        """
        Get ROM header information.

        Returns:
            ROM header metadata
        """
        if not self._rom_loaded:
            return {"error": "No ROM loaded"}

        from .disasm import Disassembler

        # Get ROM data
        rom_data, bank = self.get_direct_access("rom")
        if rom_data is None:
            return {"error": "Failed to access ROM data"}

        disasm = Disassembler(rom_data)
        return disasm.get_rom_header()

    def find_functions(self, scan_start: int | None = None, scan_end: int | None = None) -> dict:
        """
        Scan ROM for likely function entry points.

        Args:
            scan_start: Start of scan range (default: 0x0150)
            scan_end: End of scan range (default: ROM size)

        Returns:
            List of potential function addresses
        """
        if not self._rom_loaded:
            return {"error": "No ROM loaded"}

        from .disasm import Disassembler, OPCODES

        # Get ROM data
        rom_data, bank = self.get_direct_access("rom")
        if rom_data is None:
            return {"error": "Failed to access ROM data"}

        disasm = Disassembler(rom_data)

        # Default scan range: after header to ROM end
        if scan_start is None:
            scan_start = 0x0150  # After ROM header
        if scan_end is None:
            scan_end = len(rom_data)

        functions = []

        # Standard entry points
        known_entries = [
            (0x0100, "Entry point"),
            (0x0040, "VBlank handler"),
            (0x0048, "LCD STAT handler"),
            (0x0050, "Timer handler"),
            (0x0058, "Serial handler"),
            (0x0060, "Joypad handler"),
        ]

        for addr, name in known_entries:
            if addr < len(rom_data):
                inst = disasm.disassemble_one(addr)
                functions.append({
                    "address": f"0x{addr:04X}",
                    "name": name,
                    "first_instruction": f"{inst.mnemonic} {inst.operands}".strip(),
                })

        # Find CALL targets
        call_targets = set()
        for inst in disasm.disassemble_range(scan_start, scan_end):
            if inst.is_call and inst.jump_target:
                if scan_start <= inst.jump_target < scan_end:
                    call_targets.add(inst.jump_target)

        # Find PUSH-starting blocks (common function pattern)
        push_opcodes = {0xC5, 0xD5, 0xE5, 0xF5}  # PUSH BC, DE, HL, AF

        for addr in sorted(call_targets):
            if addr < len(rom_data):
                opcode = rom_data[addr]
                inst = disasm.disassemble_one(addr)
                pattern = "CALL target"
                if opcode in push_opcodes:
                    pattern += ", starts with PUSH"

                functions.append({
                    "address": f"0x{addr:04X}",
                    "name": f"sub_{addr:04X}",
                    "first_instruction": f"{inst.mnemonic} {inst.operands}".strip(),
                    "pattern": pattern,
                })

        return {
            "scan_range": f"0x{scan_start:04X}-0x{scan_end:04X}",
            "function_count": len(functions),
            "functions": functions,
        }
