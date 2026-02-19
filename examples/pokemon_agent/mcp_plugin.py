"""Pokemon Yellow MCP plugin — game-specific tools for sameboy_mcp.

Provides:
  - decode_screen_text / read_screen_tiles  (Gen 1 character decoding)
  - render_ascii_map  (ASCII map renderer with collision, warps, sprites)

Usage:
    python -m sameboy_mcp.server --lib ... --plugin examples.pokemon_agent.mcp_plugin
"""

import logging
from mcp.server import FastMCP
from sameboy_mcp.emulator.thread import EmulatorThread, CommandType

logger = logging.getLogger("pokemon-plugin")


# ============================================================
# Gen 1 Character Encoding (from pret/pokeyellow charmap.asm)
# ============================================================

GEN1_CHAR_ENCODING = {
    0x80: "A", 0x81: "B", 0x82: "C", 0x83: "D", 0x84: "E",
    0x85: "F", 0x86: "G", 0x87: "H", 0x88: "I", 0x89: "J",
    0x8A: "K", 0x8B: "L", 0x8C: "M", 0x8D: "N", 0x8E: "O",
    0x8F: "P", 0x90: "Q", 0x91: "R", 0x92: "S", 0x93: "T",
    0x94: "U", 0x95: "V", 0x96: "W", 0x97: "X", 0x98: "Y",
    0x99: "Z",
    0x9A: "(", 0x9B: ")", 0x9C: ":", 0x9D: ";", 0x9E: "[", 0x9F: "]",
    0xA0: "a", 0xA1: "b", 0xA2: "c", 0xA3: "d", 0xA4: "e",
    0xA5: "f", 0xA6: "g", 0xA7: "h", 0xA8: "i", 0xA9: "j",
    0xAA: "k", 0xAB: "l", 0xAC: "m", 0xAD: "n", 0xAE: "o",
    0xAF: "p", 0xB0: "q", 0xB1: "r", 0xB2: "s", 0xB3: "t",
    0xB4: "u", 0xB5: "v", 0xB6: "w", 0xB7: "x", 0xB8: "y",
    0xB9: "z",
    0xBA: "é",
    0xBB: "'d", 0xBC: "'l", 0xBD: "'s", 0xBE: "'t", 0xBF: "'v",
    0xE0: "'",
    0xE1: "PK", 0xE2: "MN",
    0xE3: "-",
    0xE4: "'r", 0xE5: "'m",
    0xE6: "?", 0xE7: "!", 0xE8: ".",
    0xEC: "▷", 0xED: "▶", 0xEE: "▼",
    0xEF: "♂",
    0xF0: "¥", 0xF1: "×",
    0xF3: "/", 0xF4: ",",
    0xF5: "♀",
    0xF6: "0", 0xF7: "1", 0xF8: "2", 0xF9: "3", 0xFA: "4",
    0xFB: "5", 0xFC: "6", 0xFD: "7", 0xFE: "8", 0xFF: "9",
    0x50: "@",   # String terminator
    0x4F: "\n",  # Line break
    0x51: "*",   # End of page
}

_SPACE_TILES = {0x00, 0x01, 0x7F, 0x10, 0x11, 0x12, 0x13}
_BOX_TILES = {
    0x79: "┌", 0x7A: "─", 0x7B: "┐",
    0x7C: "│", 0x7D: "└", 0x7E: "┘",
}


def _decode_tile(tile_id: int) -> str:
    if tile_id in _SPACE_TILES:
        return " "
    if tile_id in _BOX_TILES:
        return _BOX_TILES[tile_id]
    return GEN1_CHAR_ENCODING.get(tile_id, "")


def _extract_text_lines(rows: list[str]) -> list[str]:
    lines = []
    for row in rows:
        text = row.replace("┌", "").replace("─", "").replace("┐", "")
        text = text.replace("│", "").replace("└", "").replace("┘", "")
        text = text.strip()
        if text:
            lines.append(text)
    return lines


# ============================================================
# Collision Tile IDs — walkable tiles per tileset
# From pokeyellow/data/tilesets/collision_tile_ids.asm
# These are tile IDs within blockset data that are PASSABLE.
# ============================================================

COLLISION_TILE_IDS: dict[int, list[int]] = {
    # 0: Overworld
    0:  [0x00, 0x10, 0x1B, 0x20, 0x21, 0x23, 0x2C, 0x2D, 0x2E, 0x30,
         0x31, 0x33, 0x39, 0x3C, 0x3E, 0x52, 0x54, 0x58, 0x5B],
    # 1: RedsHouse1  (shared with 4: RedsHouse2)
    1:  [0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x14, 0x1C, 0x1A],
    # 2: Mart  (shared with 6: Pokecenter)
    2:  [0x11, 0x1A, 0x1C, 0x3C, 0x5E],
    # 3: Forest
    3:  [0x1E, 0x20, 0x2E, 0x30, 0x34, 0x37, 0x39, 0x3A, 0x40,
         0x51, 0x52, 0x5A, 0x5C, 0x5E, 0x5F],
    # 4: RedsHouse2  (same collision list as RedsHouse1)
    4:  [0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x14, 0x1C, 0x1A],
    # 5: Dojo  (shared with 7: Gym)
    5:  [0x11, 0x16, 0x19, 0x2B, 0x3C, 0x3D, 0x3F, 0x4A, 0x4C, 0x4D, 0x03],
    # 6: Pokecenter  (same as Mart)
    6:  [0x11, 0x1A, 0x1C, 0x3C, 0x5E],
    # 7: Gym  (same as Dojo)
    7:  [0x11, 0x16, 0x19, 0x2B, 0x3C, 0x3D, 0x3F, 0x4A, 0x4C, 0x4D, 0x03],
    # 8: House
    8:  [0x01, 0x12, 0x14, 0x28, 0x32, 0x37, 0x44, 0x54, 0x5C],
    # 9: ForestGate  (shared with 10: Museum, 12: Gate)
    9:  [0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E],
    # 10: Museum  (same as ForestGate)
    10: [0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E],
    # 11: Underground
    11: [0x0B, 0x0C, 0x13, 0x15, 0x18],
    # 12: Gate  (same as ForestGate)
    12: [0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E],
    # 13: Ship
    13: [0x04, 0x0D, 0x17, 0x1D, 0x1E, 0x23, 0x34, 0x37, 0x39, 0x4A],
    # 14: ShipPort
    14: [0x0A, 0x1A, 0x32, 0x3B],
    # 15: Cemetery
    15: [0x01, 0x10, 0x13, 0x1B, 0x22, 0x42, 0x52],
    # 16: Interior
    16: [0x04, 0x0F, 0x15, 0x1F, 0x3B, 0x45, 0x47, 0x55, 0x56],
    # 17: Cavern
    17: [0x05, 0x15, 0x18, 0x1A, 0x20, 0x21, 0x22, 0x2A, 0x2D, 0x30],
    # 18: Lobby
    18: [0x14, 0x17, 0x1A, 0x1C, 0x20, 0x38, 0x45],
    # 19: Mansion
    19: [0x01, 0x05, 0x11, 0x12, 0x14, 0x1A, 0x1C, 0x2C, 0x53],
    # 20: Lab
    20: [0x0C, 0x26, 0x16, 0x1E, 0x34, 0x37],
    # 21: Club
    21: [0x0F, 0x1A, 0x1F, 0x26, 0x28, 0x29, 0x2C, 0x2D, 0x2E, 0x2F, 0x41],
    # 22: Facility
    22: [0x01, 0x10, 0x11, 0x13, 0x1B, 0x20, 0x21, 0x22, 0x30, 0x31,
         0x32, 0x42, 0x43, 0x48, 0x52, 0x55, 0x58, 0x5E],
    # 23: Plateau
    23: [0x1B, 0x23, 0x2C, 0x2D, 0x3B, 0x45],
    # 24: BeachHouse
    24: [0x01, 0x11, 0x12, 0x14],
}


# ============================================================
# Warp Tile IDs per tileset
# From pokeyellow/data/tilesets/warp_tile_ids.asm
# Accounts for fallthrough chains in the ASM.
# ============================================================

WARP_TILE_IDS: dict[int, list[int]] = {
    0:  [0x1B, 0x58],                       # Overworld
    1:  [0x1A, 0x1C],                       # RedsHouse1
    2:  [0x5E],                             # Mart
    3:  [0x5A, 0x5C, 0x3A],                # Forest
    4:  [0x1A, 0x1C],                       # RedsHouse2
    5:  [0x4A],                             # Dojo
    6:  [0x5E],                             # Pokecenter
    7:  [0x4A],                             # Gym
    8:  [0x54, 0x5C, 0x32],                # House
    9:  [0x3B, 0x1A, 0x1C],                # ForestGate (db $3B; fallthrough RedsHouse1)
    10: [0x3B, 0x1A, 0x1C],                # Museum (same)
    11: [0x13],                             # Underground
    12: [0x3B, 0x1A, 0x1C],                # Gate (same)
    13: [0x37, 0x39, 0x1E, 0x4A],          # Ship
    14: [],                                 # ShipPort (fallthrough to empty)
    15: [0x1B, 0x13],                       # Cemetery (db $1B; fallthrough Underground)
    16: [0x15, 0x55, 0x04],                # Interior
    17: [0x18, 0x1A, 0x22],                # Cavern
    18: [0x1A, 0x1C, 0x38],                # Lobby
    19: [0x1A, 0x1C, 0x53],                # Mansion
    20: [0x34],                             # Lab
    21: [],                                 # Club (fallthrough to empty)
    22: [0x43, 0x58, 0x20, 0x1B, 0x13],    # Facility (db ...; fall Cemetery; fall Underground)
    23: [0x1B, 0x3B],                       # Plateau (db $1B,$3B; fall to empty)
    24: [],                                 # BeachHouse
}


# ============================================================
# Grass tile per tileset (from tileset_headers.asm)
# -1 means no grass encounters on this tileset.
# ============================================================

GRASS_TILES: dict[int, int] = {
    0:  0x52,   # Overworld
    3:  0x20,   # Forest
    23: 0x45,   # Plateau
}


# ============================================================
# Bookshelf tile IDs per tileset
# From pokeyellow/data/tilesets/bookshelf_tile_ids.asm
# Tiles that trigger text when you press A facing them.
# ============================================================

BOOKSHELF_TILE_IDS: dict[int, set[int]] = {
    23: {0x30},             # PLATEAU: statues
    8:  {0x3D, 0x1E},       # HOUSE: town map, bookshelf
    19: {0x32},              # MANSION: bookshelf
    1:  {0x32},              # REDS_HOUSE_1: bookshelf
    20: {0x28},              # LAB: bookshelf
    18: {0x16, 0x50, 0x52},  # LOBBY: elevator, pokemon stuff
    7:  {0x1D},              # GYM: bookshelf
    5:  {0x1D},              # DOJO: bookshelf
    12: {0x22},              # GATE: bookshelf
    2:  {0x54, 0x55},        # MART: pokemon stuff
    6:  {0x54, 0x55},        # POKECENTER: pokemon stuff
    13: {0x36},              # SHIP: bookshelf
}


# ============================================================
# PC tile IDs per tileset
# Determined empirically from blockset data at known PC positions.
# ============================================================

PC_TILE_IDS: dict[int, set[int]] = {
    1:  {0x42},   # RedsHouse1
    4:  {0x42},   # RedsHouse2
    2:  {0x42},   # Mart
    6:  {0x42},   # Pokecenter
    20: {0x02},   # Lab
}


# ============================================================
# Sprite classification
# ============================================================

TRAINER_SPRITE_IDS = {
    0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
    0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11,
    0x12, 0x13, 0x14, 0x15,
}
ITEM_BALL_SPRITE_ID = 0x29


# ============================================================
# WRAM addresses used by this plugin
# ============================================================

WRAM_TILE_MAP        = 0xC3A0
WRAM_CUR_MAP         = 0xD35D
WRAM_Y_COORD         = 0xD360
WRAM_X_COORD         = 0xD361
WRAM_CUR_MAP_TILESET = 0xD366
WRAM_CUR_MAP_HEIGHT  = 0xD367
WRAM_CUR_MAP_WIDTH   = 0xD368
WRAM_MAP_DATA        = 0xC6E8
WRAM_NUM_WARPS       = 0xD3AD
WRAM_WARP_ENTRIES    = 0xD3AE
WRAM_NUM_SIGNS       = 0xD4AF
WRAM_SIGN_COORDS     = 0xD4B0
WRAM_SIGN_TEXT_IDS   = 0xD4D0
WRAM_NUM_SPRITES     = 0xD4E0
WRAM_SPRITE_DATA_1   = 0xC100
WRAM_SPRITE_DATA_2   = 0xC200
WRAM_NUM_BAG_ITEMS   = 0xD31C
WRAM_BAG_ITEMS       = 0xD31D  # pairs of (item_id, qty), max 20 + terminator
WRAM_MONEY           = 0xD346  # 3 bytes BCD big-endian (max 999999)
WRAM_NUM_BOX_ITEMS   = 0xD539
WRAM_BOX_ITEMS       = 0xD53A  # pairs of (item_id, qty), max 50 + terminator
WRAM_TILESET_BANK    = 0xD52A
WRAM_TILESET_BLOCKS_PTR = 0xD52B
WRAM_TILESET_COLLISION_PTR = 0xD52F
WRAM_GRASS_TILE      = 0xD534


# ============================================================
# Helper: read bytes via emulator thread
# ============================================================

def _read_bytes(emu_thread: EmulatorThread, addr: int, length: int) -> list[int]:
    """Read bytes from memory, handling >256 byte reads."""
    all_bytes = []
    remaining = length
    offset = 0
    while remaining > 0:
        chunk = min(remaining, 256)
        result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
            "start": (addr + offset) & 0xFFFF,
            "length": chunk,
        })
        data = result.get("data", b"")
        all_bytes.extend(data)
        offset += chunk
        remaining -= chunk
    return all_bytes


def _read_byte(emu_thread: EmulatorThread, addr: int) -> int:
    result = emu_thread.send_command(CommandType.READ_MEMORY, {"address": addr})
    return result.get("value", 0)


def _read_word_le(emu_thread: EmulatorThread, addr: int) -> int:
    lo = _read_byte(emu_thread, addr)
    hi = _read_byte(emu_thread, addr + 1)
    return (hi << 8) | lo


def _write_byte(emu_thread: EmulatorThread, addr: int, value: int) -> None:
    emu_thread.send_command(CommandType.WRITE_MEMORY, {
        "address": addr,
        "value": value & 0xFF,
    })


# ============================================================
# Plugin entry point
# ============================================================

def _require_rom(emu_thread: EmulatorThread) -> dict | None:
    """Return an error dict if no ROM is loaded, else None."""
    if not emu_thread.emulator._rom_loaded:
        return {"error": "No ROM loaded. Use load_rom() first."}
    return None


def register_tools(server: FastMCP, emu_thread: EmulatorThread, dashboard=None) -> None:
    """Register Pokemon Yellow-specific MCP tools."""

    # Register dashboard snapshot hook for live game state
    if dashboard is not None:
        from .pokemon_data import MAP_NAMES

        def pokemon_snapshot_hook(emu_thread):
            map_id = _read_byte(emu_thread, 0xD35D)
            return {
                "map_id": map_id,
                "map_name": MAP_NAMES.get(map_id, f"Map {map_id}"),
                "player_x": _read_byte(emu_thread, 0xD361),
                "player_y": _read_byte(emu_thread, 0xD360),
                "party_count": _read_byte(emu_thread, 0xD162),
                "badge_count": bin(_read_byte(emu_thread, 0xD355)).count("1"),
                "in_battle": _read_byte(emu_thread, 0xD056),
            }

        dashboard.register_snapshot_hook(pokemon_snapshot_hook)

        dashboard.register_panels([
            {"id": "ascii_map",   "title": "ASCII Map",   "type": "ascii_map",
             "tools": ["render_ascii_map"]},
            {"id": "screen_text", "title": "Screen Text", "type": "screen_text",
             "tools": ["decode_screen_text", "press_and_read", "wait_and_read"]},
        ])

    # ----------------------------------------------------------
    # decode_screen_text
    # ----------------------------------------------------------
    @server.tool()
    async def decode_screen_text(
        address: int = 0xC3A0,
        width: int = 20,
        height: int = 18,
    ) -> dict:
        """
        Read the screen tile map from RAM and decode it to text.

        Reads tile data and decodes using Gen 1 Pokemon character encoding.
        Default address 0xC3A0 is the wTileMap for Pokemon Red/Blue/Yellow.

        Args:
            address: RAM address of the tile map (default: 0xC3A0 for Pokemon)
            width: Screen width in tiles (default: 20)
            height: Screen height in tiles (default: 18)

        Returns:
            Decoded text rows, extracted text lines, and raw tile grid
        """
        if err := _require_rom(emu_thread):
            return err
        total = width * height
        if total > 1024:
            return {"error": f"Tile map too large: {total} tiles (max 1024)"}

        all_bytes = _read_bytes(emu_thread, address, total)

        if len(all_bytes) < total:
            return {"error": f"Read only {len(all_bytes)} of {total} bytes"}

        rows = []
        tile_grid = []
        for y in range(height):
            row_start = y * width
            row_tiles = all_bytes[row_start:row_start + width]
            tile_grid.append([f"0x{t:02X}" for t in row_tiles])
            row_text = "".join(_decode_tile(t) for t in row_tiles)
            rows.append(row_text)

        text_lines = _extract_text_lines(rows)

        return {
            "address": f"0x{address:04X}",
            "width": width,
            "height": height,
            "rows": rows,
            "text_lines": text_lines,
        }

    # ----------------------------------------------------------
    # read_screen_tiles
    # ----------------------------------------------------------
    @server.tool()
    async def read_screen_tiles(
        address: int = 0xC3A0,
        width: int = 20,
        height: int = 18,
    ) -> dict:
        """
        Read raw tile IDs from the screen tile map in RAM.

        Returns the tile map as a grid of hex tile IDs without decoding.
        Useful for analyzing tile patterns or non-text screens.

        Args:
            address: RAM address of the tile map (default: 0xC3A0 for Pokemon)
            width: Screen width in tiles (default: 20)
            height: Screen height in tiles (default: 18)

        Returns:
            Grid of tile IDs (hex strings) organized by row
        """
        if err := _require_rom(emu_thread):
            return err
        total = width * height
        if total > 1024:
            return {"error": f"Tile map too large: {total} tiles (max 1024)"}

        all_bytes = _read_bytes(emu_thread, address, total)

        if len(all_bytes) < total:
            return {"error": f"Read only {len(all_bytes)} of {total} bytes"}

        tile_grid = []
        for y in range(height):
            row_start = y * width
            row_tiles = all_bytes[row_start:row_start + width]
            tile_grid.append([f"0x{t:02X}" for t in row_tiles])

        return {
            "address": f"0x{address:04X}",
            "width": width,
            "height": height,
            "tile_grid": tile_grid,
        }

    # ----------------------------------------------------------
    # render_ascii_map
    # ----------------------------------------------------------
    @server.tool()
    async def render_ascii_map(include_legend: bool = True) -> dict:
        """
        Render an ASCII map of the current area showing collision, warps, sprites, and player.

        Reads map block data, tileset collision info, sprite positions, and warp entries
        from Game Boy memory/ROM to produce a faithful top-down ASCII grid.

        Each cell represents one player-movement step (16x16 pixels = 2x2 graphical tiles).

        Legend: . walkable  # blocked  C pc  B bookshelf  ! interactable  G grass  W warp  @ player  N npc  T trainer  I item

        Returns:
            Map metadata, ASCII grid, warp list, and sprite list
        """
        if err := _require_rom(emu_thread):
            return err
        from .pokemon_data import MAP_NAMES, TILESET_NAMES

        # --- Read basic map info ---
        map_id = _read_byte(emu_thread, WRAM_CUR_MAP)
        tileset_id = _read_byte(emu_thread, WRAM_CUR_MAP_TILESET)
        width_blocks = _read_byte(emu_thread, WRAM_CUR_MAP_WIDTH)
        height_blocks = _read_byte(emu_thread, WRAM_CUR_MAP_HEIGHT)
        player_x = _read_byte(emu_thread, WRAM_X_COORD)
        player_y = _read_byte(emu_thread, WRAM_Y_COORD)

        map_name = MAP_NAMES.get(map_id, f"Map {map_id}")
        tileset_name = TILESET_NAMES.get(tileset_id, f"tileset_{tileset_id}")

        if width_blocks == 0 or height_blocks == 0:
            return {"error": "Invalid map dimensions (0x0)"}

        step_w = width_blocks * 2
        step_h = height_blocks * 2

        # --- Read map block data ---
        # wOverworldMap has a 3-block border on all sides. The actual map blocks
        # are embedded with stride = width_blocks + 6, starting at offset 3*stride+3.
        buf_stride = width_blocks + 6
        map_start = WRAM_MAP_DATA + 3 * buf_stride + 3
        map_data = []
        for row in range(height_blocks):
            row_data = _read_bytes(emu_thread, map_start + row * buf_stride, width_blocks)
            map_data.extend(row_data)

        # --- Read ROM for blockset data ---
        rom_result = emu_thread.send_command(CommandType.GET_DIRECT_ACCESS, {"region": "rom"})
        rom_data = rom_result.get("data", b"")

        bank = _read_byte(emu_thread, WRAM_TILESET_BANK)
        blocks_ptr = _read_word_le(emu_thread, WRAM_TILESET_BLOCKS_PTR)

        # --- Build walkable tile set ---
        # Use hardcoded collision tables from pokeyellow/data/tilesets/collision_tile_ids.asm.
        # Dynamic ROM reading doesn't work because wTilesetBank is the blockset bank,
        # but the collision list may be in a different ROM bank.
        coll_list = COLLISION_TILE_IDS.get(tileset_id, [])
        walkable_set = set(coll_list)

        # --- Grass tile ---
        grass_tile_id = _read_byte(emu_thread, WRAM_GRASS_TILE)
        if grass_tile_id == 0xFF:
            grass_tile_id = GRASS_TILES.get(tileset_id, -1)

        # --- Warp tile set ---
        warp_tile_set = set(WARP_TILE_IDS.get(tileset_id, []))

        # --- Bookshelf and PC tile sets ---
        bookshelf_set = BOOKSHELF_TILE_IDS.get(tileset_id, set())
        pc_tile_set = PC_TILE_IDS.get(tileset_id, set())

        # --- Build collision grid (step_w x step_h) ---
        # grid[y][x] = char, tile_id_grid[y][x] = tile ID for overlay use
        grid = [["#"] * step_w for _ in range(step_h)]
        tile_id_grid = [[0] * step_w for _ in range(step_h)]

        for block_idx, block_id in enumerate(map_data):
            bx = block_idx % width_blocks
            by = block_idx // width_blocks

            # Read 16 bytes of tile data for this block from ROM blockset
            if rom_data and blocks_ptr:
                block_rom_addr = bank * 0x4000 + (blocks_ptr & 0x3FFF) + block_id * 16
                if 0 <= block_rom_addr < len(rom_data) - 15:
                    block_tiles = rom_data[block_rom_addr:block_rom_addr + 16]
                else:
                    block_tiles = None
            else:
                block_tiles = None

            for dy in range(2):
                for dx in range(2):
                    sx = bx * 2 + dx
                    sy = by * 2 + dy
                    if sx >= step_w or sy >= step_h:
                        continue

                    if block_tiles:
                        # Representative tile: top-left of the 2x2 graphical tile quadrant
                        tile_row = dy * 2
                        tile_col = dx * 2
                        tile_id = block_tiles[tile_row * 4 + tile_col]
                        tile_id_grid[sy][sx] = tile_id

                        # Collect all 4 tiles in this 2x2 quadrant for
                        # bookshelf/PC checks (these tiles may not be the
                        # representative top-left tile).
                        quad_tiles = {
                            block_tiles[tile_row * 4 + tile_col],
                            block_tiles[tile_row * 4 + tile_col + 1],
                            block_tiles[(tile_row + 1) * 4 + tile_col],
                            block_tiles[(tile_row + 1) * 4 + tile_col + 1],
                        }

                        if tile_id in warp_tile_set:
                            grid[sy][sx] = "W"
                        elif tile_id == grass_tile_id and grass_tile_id != -1:
                            grid[sy][sx] = "G"
                        elif tile_id in walkable_set:
                            grid[sy][sx] = "."
                        elif quad_tiles & pc_tile_set:
                            grid[sy][sx] = "C"
                        elif quad_tiles & bookshelf_set:
                            grid[sy][sx] = "B"
                        else:
                            grid[sy][sx] = "#"
                    else:
                        # No ROM data — use hardcoded heuristic
                        if block_id <= 0x10:
                            grid[sy][sx] = "."
                        else:
                            grid[sy][sx] = "#"

        # --- Read warp entries ---
        num_warps = _read_byte(emu_thread, WRAM_NUM_WARPS)
        warps = []
        for i in range(min(num_warps, 32)):
            base = WRAM_WARP_ENTRIES + i * 4
            data = _read_bytes(emu_thread, base, 4)
            if len(data) >= 4:
                wy, wx, warp_id, dest_map = data[0], data[1], data[2], data[3]
                warps.append({
                    "x": wx, "y": wy,
                    "dest_map": dest_map,
                    "dest_name": MAP_NAMES.get(dest_map, f"Map {dest_map}"),
                    "warp_id": warp_id,
                })
                # Mark warp on grid (if within bounds and not already marked)
                if 0 <= wx < step_w and 0 <= wy < step_h:
                    grid[wy][wx] = "W"

        # --- Read bg_events (signs) and overlay on grid ---
        num_signs = _read_byte(emu_thread, WRAM_NUM_SIGNS)
        bg_events = []
        for i in range(min(num_signs, 16)):
            ey = _read_byte(emu_thread, WRAM_SIGN_COORDS + i * 2)
            ex = _read_byte(emu_thread, WRAM_SIGN_COORDS + i * 2 + 1)
            text_id = _read_byte(emu_thread, WRAM_SIGN_TEXT_IDS + i)
            bg_events.append({"x": ex, "y": ey, "text_id": text_id})
            if 0 <= ey < step_h and 0 <= ex < step_w:
                cur = grid[ey][ex]
                if cur in ("#", "."):
                    grid[ey][ex] = "!"

        # --- Read sprites ---
        num_sprites = _read_byte(emu_thread, WRAM_NUM_SPRITES)
        sprites = []
        for i in range(1, min(num_sprites + 1, 16)):
            # Picture ID from SpriteStateData1
            pic_id = _read_byte(emu_thread, WRAM_SPRITE_DATA_1 + i * 16)
            if pic_id == 0:
                continue
            # Map coordinates from SpriteStateData2.
            # C2xx coords use a +4 bias (map origin is at 4,4).
            s2_base = WRAM_SPRITE_DATA_2 + i * 16
            npc_y = _read_byte(emu_thread, s2_base + 0x04) - 4
            npc_x = _read_byte(emu_thread, s2_base + 0x05) - 4
            if npc_x < 0 and npc_y < 0:
                continue

            if pic_id == ITEM_BALL_SPRITE_ID:
                stype = "item"
                char = "I"
            elif pic_id in TRAINER_SPRITE_IDS:
                stype = "trainer"
                char = "T"
            else:
                stype = "npc"
                char = "N"

            sprites.append({
                "x": npc_x, "y": npc_y,
                "type": stype,
                "picture_id": pic_id,
            })
            if 0 <= npc_x < step_w and 0 <= npc_y < step_h:
                grid[npc_y][npc_x] = char

        # --- Mark player ---
        if 0 <= player_x < step_w and 0 <= player_y < step_h:
            grid[player_y][player_x] = "@"

        # --- Build ASCII string ---
        # Column header
        col_digits = max(len(str(step_w - 1)), 1)
        header_lines = []
        for digit_pos in range(col_digits):
            divisor = 10 ** (col_digits - 1 - digit_pos)
            hdr = "   "  # row label width
            for c in range(step_w):
                hdr += str((c // divisor) % 10)
            header_lines.append(hdr)

        row_lines = []
        for y in range(step_h):
            label = f"{y:>2}:"
            row_lines.append(label + "".join(grid[y]))

        ascii_str = "\n".join(header_lines + row_lines)

        result = {
            "map_id": map_id,
            "map_name": map_name,
            "tileset": tileset_name,
            "tileset_id": tileset_id,
            "dimensions": {
                "width_blocks": width_blocks,
                "height_blocks": height_blocks,
                "width_steps": step_w,
                "height_steps": step_h,
            },
            "player": {"x": player_x, "y": player_y},
            "ascii": ascii_str,
            "warps": warps,
            "bg_events": bg_events,
            "sprites": sprites,
        }
        if include_legend:
            result["legend"] = (
                ". walkable  # blocked  C pc  B bookshelf  "
                "! interactable  G grass  W warp  "
                "@ player  N npc  T trainer  I item"
            )
        return result

    # ----------------------------------------------------------
    # press_and_read — composite tool: press key + wait + read screen
    # ----------------------------------------------------------
    @server.tool()
    async def press_and_read(
        key: str,
        frames: int = 16,
        wait: int = 60,
    ) -> dict:
        """
        Press a button, wait for the game to respond, then read screen text.

        Combines press_key + run_frames + decode_screen_text into a single call.
        Use this as your PRIMARY interaction tool — it's 3x more efficient than
        calling the three tools separately.

        Args:
            key: Button to press (a, b, up, down, left, right, start, select)
            frames: Frames to hold the button (default 16 — enough for movement/interaction)
            wait: Frames to wait after releasing for animations/text to render (default 60)

        Returns:
            Screen text after the action, plus confirmation of what was pressed
        """
        if err := _require_rom(emu_thread):
            return err

        valid_keys = {"a", "b", "start", "select", "up", "down", "left", "right"}
        k = key.lower()
        if k not in valid_keys:
            return {"error": f"Invalid key: {key}. Valid: {', '.join(sorted(valid_keys))}"}

        frames = max(1, min(frames, 600))
        wait = max(0, min(wait, 600))

        # Press the key
        emu_thread.send_command(CommandType.PRESS_KEY, {"key": k, "frames": frames})

        # Wait for animations/text
        if wait > 0:
            for _ in range(wait):
                emu_thread.send_command(CommandType.STEP_FRAME)

        # Read screen text
        total = 20 * 18
        all_bytes = _read_bytes(emu_thread, WRAM_TILE_MAP, total)
        rows = []
        for y in range(18):
            row_start = y * 20
            row_tiles = all_bytes[row_start:row_start + 20]
            row_text = "".join(_decode_tile(t) for t in row_tiles)
            rows.append(row_text)
        text_lines = _extract_text_lines(rows)

        return {
            "key": k,
            "frames": frames,
            "wait": wait,
            "text_lines": text_lines,
            "rows": rows,
        }

    # ----------------------------------------------------------
    # wait_and_read — composite tool: wait + read screen
    # ----------------------------------------------------------
    @server.tool()
    async def wait_and_read(
        wait: int = 60,
    ) -> dict:
        """
        Wait for animations/dialog to render, then read screen text.

        Use this after an action when you need to wait for the game to update
        without pressing any button. Good for: waiting for dialog to finish
        printing, menu animations, or battle animations.

        Args:
            wait: Frames to wait (default 60, ~1 second)

        Returns:
            Screen text after waiting
        """
        if err := _require_rom(emu_thread):
            return err

        wait = max(1, min(wait, 3600))

        for _ in range(wait):
            emu_thread.send_command(CommandType.STEP_FRAME)

        # Read screen text
        total = 20 * 18
        all_bytes = _read_bytes(emu_thread, WRAM_TILE_MAP, total)
        rows = []
        for y in range(18):
            row_start = y * 20
            row_tiles = all_bytes[row_start:row_start + 20]
            row_text = "".join(_decode_tile(t) for t in row_tiles)
            rows.append(row_text)
        text_lines = _extract_text_lines(rows)

        return {
            "text_lines": text_lines,
            "rows": rows,
        }

    # ----------------------------------------------------------
    # read_inventory — read bag and/or PC item storage
    # ----------------------------------------------------------
    @server.tool()
    async def read_inventory(storage: str = "bag") -> dict:
        """
        Read the player's item inventory.

        Args:
            storage: Which storage to read — "bag", "pc", or "both"

        Returns:
            List of items with id, name, and quantity
        """
        if err := _require_rom(emu_thread):
            return err
        from .pokemon_data import ITEM_NAMES

        result = {}

        if storage in ("bag", "both"):
            count = _read_byte(emu_thread, WRAM_NUM_BAG_ITEMS)
            items = []
            for i in range(min(count, 20)):
                item_id = _read_byte(emu_thread, WRAM_BAG_ITEMS + i * 2)
                qty = _read_byte(emu_thread, WRAM_BAG_ITEMS + i * 2 + 1)
                if item_id == 0xFF:
                    break
                items.append({
                    "id": item_id,
                    "name": ITEM_NAMES.get(item_id, f"Item_0x{item_id:02X}"),
                    "quantity": qty,
                })
            result["bag"] = items

        if storage in ("pc", "both"):
            count = _read_byte(emu_thread, WRAM_NUM_BOX_ITEMS)
            items = []
            for i in range(min(count, 50)):
                item_id = _read_byte(emu_thread, WRAM_BOX_ITEMS + i * 2)
                qty = _read_byte(emu_thread, WRAM_BOX_ITEMS + i * 2 + 1)
                if item_id == 0xFF:
                    break
                items.append({
                    "id": item_id,
                    "name": ITEM_NAMES.get(item_id, f"Item_0x{item_id:02X}"),
                    "quantity": qty,
                })
            result["pc"] = items

        return result

    # ----------------------------------------------------------
    # set_inventory — write items to bag or PC
    # ----------------------------------------------------------
    @server.tool()
    async def set_inventory(
        storage: str = "bag",
        items: str = "",
    ) -> dict:
        """
        Set the player's item inventory. Replaces all items in the chosen storage.

        Args:
            storage: Which storage to write — "bag" or "pc"
            items: Comma-separated "id:qty" pairs, e.g. "20:5,11:3" (decimal item IDs).
                   Use read_inventory to see current IDs. Max 20 for bag, 50 for PC.

        Returns:
            Confirmation with written items
        """
        if err := _require_rom(emu_thread):
            return err
        from .pokemon_data import ITEM_NAMES

        if storage == "bag":
            count_addr = WRAM_NUM_BAG_ITEMS
            items_addr = WRAM_BAG_ITEMS
            max_slots = 20
        elif storage == "pc":
            count_addr = WRAM_NUM_BOX_ITEMS
            items_addr = WRAM_BOX_ITEMS
            max_slots = 50
        else:
            return {"error": f"Invalid storage: {storage}. Use 'bag' or 'pc'."}

        # Parse items string
        parsed = []
        if items.strip():
            for part in items.split(","):
                part = part.strip()
                if ":" not in part:
                    return {"error": f"Invalid format '{part}'. Use 'id:qty' (e.g. '20:5')."}
                try:
                    item_id, qty = part.split(":", 1)
                    item_id = int(item_id)
                    qty = int(qty)
                except ValueError:
                    return {"error": f"Invalid number in '{part}'."}
                if not (1 <= item_id <= 0xFF) or not (1 <= qty <= 99):
                    return {"error": f"Item ID must be 1-255, qty must be 1-99. Got {item_id}:{qty}."}
                parsed.append((item_id, qty))

        if len(parsed) > max_slots:
            return {"error": f"Too many items ({len(parsed)}). Max {max_slots} for {storage}."}

        # Write items
        for i, (item_id, qty) in enumerate(parsed):
            _write_byte(emu_thread, items_addr + i * 2, item_id)
            _write_byte(emu_thread, items_addr + i * 2 + 1, qty)

        # Write terminator
        _write_byte(emu_thread, items_addr + len(parsed) * 2, 0xFF)

        # Write count
        _write_byte(emu_thread, count_addr, len(parsed))

        written = [
            {"id": iid, "name": ITEM_NAMES.get(iid, f"Item_0x{iid:02X}"), "quantity": q}
            for iid, q in parsed
        ]
        return {"storage": storage, "count": len(parsed), "items": written}

    # ----------------------------------------------------------
    # read_money — read player's current money
    # ----------------------------------------------------------
    @server.tool()
    async def read_money() -> dict:
        """
        Read the player's money (stored as 3-byte BCD at 0xD346).

        Returns:
            Money amount as integer and formatted string
        """
        if err := _require_rom(emu_thread):
            return err

        b0 = _read_byte(emu_thread, WRAM_MONEY)
        b1 = _read_byte(emu_thread, WRAM_MONEY + 1)
        b2 = _read_byte(emu_thread, WRAM_MONEY + 2)

        def bcd_decode(b):
            return (b >> 4) * 10 + (b & 0x0F)

        amount = bcd_decode(b0) * 10000 + bcd_decode(b1) * 100 + bcd_decode(b2)
        return {"money": amount, "formatted": f"¥{amount:,}"}

    # ----------------------------------------------------------
    # set_money — set player's money
    # ----------------------------------------------------------
    @server.tool()
    async def set_money(amount: int) -> dict:
        """
        Set the player's money.

        Args:
            amount: Money amount (0-999999)

        Returns:
            Confirmation with new amount
        """
        if err := _require_rom(emu_thread):
            return err

        if not (0 <= amount <= 999999):
            return {"error": f"Amount must be 0-999999. Got {amount}."}

        def bcd_encode(n):
            return ((n // 10) << 4) | (n % 10)

        b0 = bcd_encode((amount // 10000) % 100)
        b1 = bcd_encode((amount // 100) % 100)
        b2 = bcd_encode(amount % 100)

        _write_byte(emu_thread, WRAM_MONEY, b0)
        _write_byte(emu_thread, WRAM_MONEY + 1, b1)
        _write_byte(emu_thread, WRAM_MONEY + 2, b2)

        return {"money": amount, "formatted": f"¥{amount:,}"}

    logger.info("Pokemon Yellow plugin: registered decode_screen_text, "
                "read_screen_tiles, render_ascii_map, press_and_read, wait_and_read, "
                "read_inventory, set_inventory, read_money, set_money")
