# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""cffi bindings for libsameboy."""

from cffi import FFI
from pathlib import Path
import os

ffi = FFI()

# C declarations for SameBoy types and functions
ffi.cdef("""
    // Forward declaration - opaque struct
    typedef struct GB_gameboy_s GB_gameboy_t;

    // Model types (from model.h)
    typedef enum {
        GB_MODEL_DMG_B = 0x002,
        GB_MODEL_DMG_C = 0x003,
        GB_MODEL_MGB = 0x100,
        GB_MODEL_SGB_NTSC = 0x010,
        GB_MODEL_SGB_PAL = 0x011,
        GB_MODEL_SGB_NTSC_NO_SFC = 0x110,
        GB_MODEL_SGB_PAL_NO_SFC = 0x111,
        GB_MODEL_SGB2 = 0x020,
        GB_MODEL_SGB2_NO_SFC = 0x120,
        GB_MODEL_CGB_0 = 0x200,
        GB_MODEL_CGB_A = 0x201,
        GB_MODEL_CGB_B = 0x202,
        GB_MODEL_CGB_C = 0x203,
        GB_MODEL_CGB_D = 0x204,
        GB_MODEL_CGB_E = 0x205,
        GB_MODEL_AGB_A = 0x206,
        GB_MODEL_GBP_A = 0x207,
    } GB_model_t;

    // Key types (from joypad.h)
    typedef enum {
        GB_KEY_RIGHT,
        GB_KEY_LEFT,
        GB_KEY_UP,
        GB_KEY_DOWN,
        GB_KEY_A,
        GB_KEY_B,
        GB_KEY_SELECT,
        GB_KEY_START,
        GB_KEY_MAX
    } GB_key_t;

    // Vblank type (from display.h)
    typedef enum {
        GB_VBLANK_TYPE_NORMAL_FRAME,
        GB_VBLANK_TYPE_LCD_OFF,
        GB_VBLANK_TYPE_ARTIFICIAL,
        GB_VBLANK_TYPE_REPEAT,
        GB_VBLANK_TYPE_SKIPPED_FRAME,
    } GB_vblank_type_t;

    // Direct access types (from gb.h)
    typedef enum {
        GB_DIRECT_ACCESS_ROM,
        GB_DIRECT_ACCESS_RAM,
        GB_DIRECT_ACCESS_CART_RAM,
        GB_DIRECT_ACCESS_VRAM,
        GB_DIRECT_ACCESS_HRAM,
        GB_DIRECT_ACCESS_IO,
        GB_DIRECT_ACCESS_BOOTROM,
        GB_DIRECT_ACCESS_OAM,
        GB_DIRECT_ACCESS_BGP,
        GB_DIRECT_ACCESS_OBP,
        GB_DIRECT_ACCESS_IE,
        GB_DIRECT_ACCESS_ROM0,
    } GB_direct_access_t;

    // Log attributes
    typedef enum {
        GB_LOG_BOLD = 1,
        GB_LOG_DASHED_UNDERLINE = 2,
        GB_LOG_UNDERLINE = 4,
    } GB_log_attributes_t;

    // OAM info structure (from display.h)
    typedef struct {
        uint32_t image[128];
        uint8_t x, y, tile, flags;
        uint16_t oam_addr;
        bool obscured_by_line_limit;
    } GB_oam_info_t;

    // Registers structure (from gb.h)
    typedef union {
        uint16_t registers[6];
        struct {
            uint16_t af, bc, de, hl, sp, pc;
        };
    } GB_registers_t;

    // Palette structure (from display.h)
    typedef struct {
        struct {
            uint8_t r, g, b;
        } colors[5];
    } GB_palette_t;

    // Callback types
    typedef void (*GB_vblank_callback_t)(GB_gameboy_t *gb, GB_vblank_type_t type);
    typedef void (*GB_execution_callback_t)(GB_gameboy_t *gb, uint16_t address, uint8_t opcode);
    typedef uint8_t (*GB_read_memory_callback_t)(GB_gameboy_t *gb, uint16_t addr, uint8_t data);
    typedef bool (*GB_write_memory_callback_t)(GB_gameboy_t *gb, uint16_t addr, uint8_t data);
    typedef void (*GB_log_callback_t)(GB_gameboy_t *gb, const char *string, GB_log_attributes_t attributes);
    typedef uint32_t (*GB_rgb_encode_callback_t)(GB_gameboy_t *gb, uint8_t r, uint8_t g, uint8_t b);
    typedef void (*GB_update_input_hint_callback_t)(GB_gameboy_t *gb);

    // ============ Lifecycle Functions ============
    GB_gameboy_t *GB_alloc(void);
    GB_gameboy_t *GB_init(GB_gameboy_t *gb, GB_model_t model);
    void GB_free(GB_gameboy_t *gb);
    void GB_dealloc(GB_gameboy_t *gb);
    void GB_reset(GB_gameboy_t *gb);
    bool GB_is_inited(GB_gameboy_t *gb);
    bool GB_is_cgb(const GB_gameboy_t *gb);
    GB_model_t GB_get_model(GB_gameboy_t *gb);

    // ============ ROM Loading ============
    int GB_load_rom(GB_gameboy_t *gb, const char *path);
    void GB_load_rom_from_buffer(GB_gameboy_t *gb, const uint8_t *buffer, size_t size);
    int GB_load_boot_rom(GB_gameboy_t *gb, const char *path);
    void GB_load_boot_rom_from_buffer(GB_gameboy_t *gb, const unsigned char *buffer, size_t size);

    // ============ Battery/Save ============
    int GB_save_battery(GB_gameboy_t *gb, const char *path);
    int GB_load_battery(GB_gameboy_t *gb, const char *path);

    // ============ Execution ============
    unsigned GB_run(GB_gameboy_t *gb);
    uint64_t GB_run_frame(GB_gameboy_t *gb);

    // ============ Memory Access ============
    uint8_t GB_read_memory(GB_gameboy_t *gb, uint16_t addr);
    uint8_t GB_safe_read_memory(GB_gameboy_t *gb, uint16_t addr);
    void GB_write_memory(GB_gameboy_t *gb, uint16_t addr, uint8_t value);
    void *GB_get_direct_access(GB_gameboy_t *gb, GB_direct_access_t access, size_t *size, uint16_t *bank);

    // ============ Registers ============
    GB_registers_t *GB_get_registers(GB_gameboy_t *gb);

    // ============ Display ============
    uint32_t *GB_get_pixels_output(GB_gameboy_t *gb);
    void GB_set_pixels_output(GB_gameboy_t *gb, uint32_t *output);
    unsigned GB_get_screen_width(GB_gameboy_t *gb);
    unsigned GB_get_screen_height(GB_gameboy_t *gb);
    double GB_get_usual_frame_rate(GB_gameboy_t *gb);
    uint8_t GB_get_oam_info(GB_gameboy_t *gb, GB_oam_info_t *dest, uint8_t *object_height);
    void GB_set_rendering_disabled(GB_gameboy_t *gb, bool disabled);
    void GB_set_palette(GB_gameboy_t *gb, const GB_palette_t *palette);
    const GB_palette_t *GB_get_palette(GB_gameboy_t *gb);

    // ============ Save States ============
    int GB_save_state(GB_gameboy_t *gb, const char *path);
    size_t GB_get_save_state_size(GB_gameboy_t *gb);
    void GB_save_state_to_buffer(GB_gameboy_t *gb, uint8_t *buffer);
    int GB_load_state(GB_gameboy_t *gb, const char *path);
    int GB_load_state_from_buffer(GB_gameboy_t *gb, const uint8_t *buffer, size_t length);

    // ============ Input ============
    void GB_set_key_state(GB_gameboy_t *gb, GB_key_t index, bool pressed);

    // ============ Debugger ============
    void GB_debugger_break(GB_gameboy_t *gb);
    bool GB_debugger_is_stopped(GB_gameboy_t *gb);
    void GB_debugger_set_disabled(GB_gameboy_t *gb, bool disabled);
    void GB_cpu_disassemble(GB_gameboy_t *gb, uint16_t pc, uint16_t count);

    // ============ Callbacks ============
    void GB_set_vblank_callback(GB_gameboy_t *gb, GB_vblank_callback_t callback);
    void GB_set_execution_callback(GB_gameboy_t *gb, GB_execution_callback_t callback);
    void GB_set_read_memory_callback(GB_gameboy_t *gb, GB_read_memory_callback_t callback);
    void GB_set_write_memory_callback(GB_gameboy_t *gb, GB_write_memory_callback_t callback);
    void GB_set_log_callback(GB_gameboy_t *gb, GB_log_callback_t callback);
    void GB_set_rgb_encode_callback(GB_gameboy_t *gb, GB_rgb_encode_callback_t callback);
    void GB_set_update_input_hint_callback(GB_gameboy_t *gb, GB_update_input_hint_callback_t callback);

    // ============ User Data ============
    void *GB_get_user_data(GB_gameboy_t *gb);
    void GB_set_user_data(GB_gameboy_t *gb, void *data);

    // ============ Turbo/Speed ============
    void GB_set_turbo_mode(GB_gameboy_t *gb, bool on, bool no_frame_skip);
    uint32_t GB_get_clock_rate(GB_gameboy_t *gb);
    void GB_set_clock_multiplier(GB_gameboy_t *gb, double multiplier);

    // ============ ROM Info ============
    void GB_get_rom_title(GB_gameboy_t *gb, char *title);
    uint32_t GB_get_rom_crc32(GB_gameboy_t *gb);

    // ============ Rewind ============
    bool GB_rewind_pop(GB_gameboy_t *gb);
    void GB_set_rewind_length(GB_gameboy_t *gb, double seconds);
    void GB_rewind_reset(GB_gameboy_t *gb);
""")


def load_library(lib_path: str | None = None) -> any:
    """
    Load the libsameboy shared library.

    Args:
        lib_path: Path to libsameboy.so/dylib/dll. If None, searches default locations.

    Returns:
        The loaded library object.
    """
    if lib_path is None:
        # Search in common locations
        search_paths = [
            # Relative to this package
            Path(__file__).parent.parent.parent / "sameboy_src" / "SameBoy-1.0.2" / "build" / "lib" / "libsameboy.so",
            # System paths
            Path("/usr/local/lib/libsameboy.so"),
            Path("/usr/lib/libsameboy.so"),
        ]

        for path in search_paths:
            if path.exists():
                lib_path = str(path)
                break

        if lib_path is None:
            raise FileNotFoundError(
                "Could not find libsameboy.so. Please build it with "
                "'make lib CONF=release' in the SameBoy source directory, "
                "or specify the path explicitly."
            )

    return ffi.dlopen(lib_path)


# Model name mappings
MODEL_MAP = {
    "DMG_B": 0x002,
    "DMG_C": 0x003,
    "MGB": 0x100,
    "SGB": 0x010,
    "SGB2": 0x020,
    "CGB_0": 0x200,
    "CGB_A": 0x201,
    "CGB_B": 0x202,
    "CGB_C": 0x203,
    "CGB_D": 0x204,
    "CGB_E": 0x205,
    "AGB": 0x206,
    "GBP": 0x207,
}

# Key name mappings
KEY_MAP = {
    "right": 0,
    "left": 1,
    "up": 2,
    "down": 3,
    "a": 4,
    "b": 5,
    "select": 6,
    "start": 7,
}

# Direct access region mappings
DIRECT_ACCESS_MAP = {
    "rom": 0,
    "ram": 1,
    "cart_ram": 2,
    "vram": 3,
    "hram": 4,
    "io": 5,
    "bootrom": 6,
    "oam": 7,
    "bgp": 8,
    "obp": 9,
    "ie": 10,
    "rom0": 11,
}

# Predefined DMG palettes (matching SameBoy's built-in palettes)
# Format: 5 colors, each with (r, g, b) - darkest to lightest, plus background
DMG_PALETTES = {
    "grey": [
        (0x00, 0x00, 0x00),  # Black
        (0x55, 0x55, 0x55),  # Dark grey
        (0xAA, 0xAA, 0xAA),  # Light grey
        (0xFF, 0xFF, 0xFF),  # White
        (0xFF, 0xFF, 0xFF),  # Background
    ],
    "dmg": [
        (0x08, 0x18, 0x10),  # Darkest green
        (0x39, 0x61, 0x39),  # Dark green
        (0x84, 0xA5, 0x63),  # Light green
        (0xC6, 0xDE, 0x8C),  # Lightest green
        (0xD2, 0xE6, 0xA6),  # Background
    ],
    "mgb": [
        (0x07, 0x10, 0x0E),
        (0x3A, 0x4C, 0x3A),
        (0x81, 0x8D, 0x66),
        (0xC2, 0xCE, 0x93),
        (0xCF, 0xDA, 0xAC),
    ],
    "gbl": [
        (0x0A, 0x1C, 0x15),
        (0x35, 0x78, 0x62),
        (0x56, 0xB4, 0x95),
        (0x7F, 0xE2, 0xC3),
        (0x91, 0xEA, 0xD0),
    ],
}


def create_palette(colors: list[tuple[int, int, int]]) -> any:
    """Create a GB_palette_t from a list of RGB tuples."""
    palette = ffi.new("GB_palette_t*")
    for i, (r, g, b) in enumerate(colors[:5]):
        palette.colors[i].r = r
        palette.colors[i].g = g
        palette.colors[i].b = b
    return palette
