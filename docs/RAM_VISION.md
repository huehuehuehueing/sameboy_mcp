# RAM Vision: Reading Game Screens from Memory

## Overview

Traditional game-playing AI agents rely on **screenshot-based vision** -- capturing rendered frames and processing them with OCR or vision-language models. This is slow, error-prone, and requires expensive inference.

RAM Vision is an alternative: read the screen tile map directly from the Game Boy's working RAM. The game engine already stores every on-screen character as a structured tile ID in a known memory region. By mapping these IDs back to characters, we get **instant, deterministic, pixel-perfect text decoding** with zero inference cost.

```
Screenshot Vision:     Screen → PNG → Vision Model → "WITHDRAW ITEM"  (~500ms, lossy)
RAM Vision:            0xC3A0 → [0xED,0x96,0x88,...] → "▶WITHDRAW ITEM"  (~1ms, exact)
```

## How It Works

### The Game Boy Tile Map

The Game Boy renders screens using an 8x8 pixel tile system. The hardware displays a 160x144 pixel screen, which is a 20x18 grid of tiles. Each tile is referenced by an ID byte (0x00-0xFF).

Pokemon Red/Blue/Yellow maintains a **shadow tile map** in WRAM at address `0xC3A0` (`wTileMap`). This is a flat 360-byte array (20 columns x 18 rows) containing the tile ID for every visible screen position. The game engine writes to this buffer, and the VBlank interrupt copies it to VRAM for rendering.

```
Memory layout at 0xC3A0:

Offset  0   1   2   3   4   5   6  ... 19     ← Column
  +0   [79][7A][7A][7A][7A][7A][7A]...[7B]    ← Row 0  (┌──────...──┐)
 +20   [7C][7F][7F][7F][7F][7F][7F]...[7C]    ← Row 1  (│           │)
 +40   [7C][ED][96][88][93][87][83]...[7C]    ← Row 2  (│▶WITHDRAW.│)
  ...
+340   [7D][7A][7A][7A][7A][7A][7A]...[7E]    ← Row 17 (└──────...──┘)
```

### Gen 1 Character Encoding

Game Boy games use custom character encodings, not ASCII. Pokemon Gen 1 (Red/Blue/Yellow) uses this mapping, defined in [pret/pokeyellow charmap.asm](https://github.com/pret/pokeyellow/blob/master/constants/charmap.asm):

| Tile Range | Characters | Example |
|-----------|-----------|---------|
| `0x80`-`0x99` | A-Z | `0x80`=A, `0x81`=B, ..., `0x99`=Z |
| `0xA0`-`0xB9` | a-z | `0xA0`=a, `0xA1`=b, ..., `0xB9`=z |
| `0xF6`-`0xFF` | 0-9 | `0xF6`=0, `0xF7`=1, ..., `0xFF`=9 |
| `0xBA` | é | Used in "POKéMON" |
| `0xBB`-`0xBF` | Contractions | `'d`, `'l`, `'s`, `'t`, `'v` |
| `0xE0` | `'` | Apostrophe |
| `0xE3` | `-` | Hyphen |
| `0xE4`-`0xE5` | Contractions | `'r` (Mr.), `'m` (I'm) |
| `0xE6`-`0xE8` | `?` `!` `.` | Punctuation |
| `0xED` | ▶ | Menu cursor |
| `0xEE` | ▼ | "More text" indicator |
| `0xF3`-`0xF4` | `/` `,` | Punctuation |
| `0x79`-`0x7E` | `┌─┐│└┘` | Text box borders |
| `0x7F`, `0x00` | (space) | Blank tiles |
| `0x50` | (terminator) | End of string |

A single tile ID can map to multiple characters (e.g., `0xBB` = `'d`, `0xE1` = `PK`). These are single-byte encodings for common multi-character sequences, not multi-byte encodings.

### Decoding Pipeline

```
1. Read 360 bytes from 0xC3A0 (WRAM tile map)
         │
         ▼
2. Split into 18 rows of 20 tile IDs
         │
         ▼
3. Map each tile ID → character via GEN1_CHAR_ENCODING
   - Space tiles (0x00, 0x7F, 0x10) → " "
   - Box tiles (0x79-0x7E) → ┌─┐│└┘
   - Letters, numbers, punctuation → their characters
   - Unknown tiles → ""
         │
         ▼
4. Extract text lines (strip box borders + whitespace)
         │
         ▼
5. Return structured result:
   - rows: all 18 decoded rows (preserving layout)
   - text_lines: clean text content only
```

## MCP Tools

### `decode_screen_text`

Reads the tile map and decodes it to human-readable text.

```
Parameters:
  address  (int, default 0xC3A0)  RAM address of the tile map
  width    (int, default 20)      Screen width in tiles
  height   (int, default 18)      Screen height in tiles
```

Example output:
```json
{
  "rows": [
    "┌──────────────┐    ",
    "│              │    ",
    "│▶WITHDRAW ITEM│    ",
    "│ DEPOSIT ITEM │    ",
    "│ TOSS ITEM    │    ",
    "│ LOG OFF      │    ",
    "└──────────────┘    ",
    "┌──────────────────┐",
    "│What do you want  │",
    "│to do?            │",
    "└──────────────────┘"
  ],
  "text_lines": [
    "▶WITHDRAW ITEM",
    "DEPOSIT ITEM",
    "TOSS ITEM",
    "LOG OFF",
    "What do you want",
    "to do?"
  ]
}
```

The `rows` field preserves the full screen layout including borders. The `text_lines` field strips box drawing characters and whitespace, returning only meaningful text content.

### `read_screen_tiles`

Returns raw tile IDs without character decoding. Useful for pattern analysis, detecting non-text elements, or working with games that use different character encodings.

```json
{
  "tile_grid": [
    ["0x79", "0x7A", "0x7A", "0x7A", "0x7B"],
    ["0x7C", "0xED", "0x96", "0x88", "0x7C"],
    ...
  ]
}
```

## Agent Integration

### Game State Detection

The Pokemon agent uses RAM vision for mode detection without any vision model:

```python
# In game_state.py - _detect_mode()
screen_text = self._read_screen_text()

if "PRESS START" in screen_text.full_text:
    return GameMode.TITLE_SCREEN

if "NEW GAME" in screen_text.full_text:
    return GameMode.MAIN_MENU

if "YOUR NAME" in screen_text.full_text:
    return GameMode.NAME_ENTRY
```

### Menu Navigation

Screen text tells the agent exactly what menu options are available and which is selected (indicated by the ▶ cursor at `0xED`):

```python
# Read screen, find cursor position, determine selected item
lines = decode_screen_text()["text_lines"]
for line in lines:
    if line.startswith("▶"):
        current_selection = line[1:]  # Strip cursor
```

### Dialog Reading

When NPCs speak or the game displays messages, the text appears in bordered boxes. RAM vision reads these instantly:

```
┌──────────────────┐
│OAK: Now, RED,    │
│which POKéMON do  │
│you want?         │
└──────────────────┘
```

The `text_lines` extraction strips the borders and returns:
```
["OAK: Now, RED,", "which POKéMON do", "you want?"]
```

## RAM Vision vs Screenshot Vision

| | RAM Vision | Screenshot Vision |
|---|---|---|
| **Speed** | ~1ms (memory read) | ~500ms+ (capture + inference) |
| **Cost** | Zero | Vision model API call |
| **Accuracy** | Perfect (deterministic) | Varies (OCR/model errors) |
| **Offline** | Yes | Requires model endpoint |
| **Data size** | 360 bytes | 10-50 KB PNG |
| **Layout info** | Exact tile positions | Pixel-level (approximate) |
| **Non-text content** | Tile IDs only (no rendering) | Full visual context |
| **Unknown games** | Needs encoding table | Works with any game |

### When to Use Each

**RAM Vision is best for:**
- Reading dialog text and menu options
- Detecting game mode (title, menu, battle, overworld)
- Tracking menu cursor position
- Any text-based decision making

**Screenshot Vision is best for:**
- Identifying visual obstacles not represented in tile data
- Analyzing sprite positions and animations in context
- When the agent is stuck and needs spatial reasoning
- Games with unknown or undocumented character encodings

### Hybrid Approach

The Pokemon agent uses both. RAM vision is the primary input for all text-based decisions. Screenshot vision is reserved for when the agent is stuck and needs to visually analyze the environment for obstacles or paths not captured in memory:

```
Normal operation:  RAM vision only (fast, deterministic)
                   ↓
Agent gets stuck:  Capture screenshot → Vision model analysis
                   ↓
Resume:            Back to RAM vision
```

## Extending to Other Games

The MCP tools accept a configurable `address` parameter. To use RAM vision with a different Game Boy game:

1. **Find the tile map address** -- Use memory monitoring tools to watch VRAM writes, or consult a disassembly. Many games use the hardware BG tile map at `0x9800` (VRAM) rather than a WRAM shadow.

2. **Build a character encoding table** -- Capture known screens and correlate tile IDs with visible characters. The pret disassembly projects ([pokered](https://github.com/pret/pokered), [pokecrystal](https://github.com/pret/pokecrystal), etc.) contain authoritative `charmap.asm` files for Pokemon games.

3. **Call the tool** -- Pass the address to `decode_screen_text` or `read_screen_tiles`. The Gen 1 encoding is built into the MCP server; for other encodings, use `read_screen_tiles` and decode client-side.

## Implementation Files

| File | Role |
|------|------|
| `examples/pokemon_agent/mcp_plugin.py` | MCP tools: `decode_screen_text`, `read_screen_tiles`, `render_ascii_map`, `GEN1_CHAR_ENCODING` table |
| `examples/pokemon_agent/memory_map.py` | Agent-side: `CHAR_ENCODING`, `decode_text()`, `encode_text()`, `WRAM_TILE_MAP` address |
| `examples/pokemon_agent/game_state.py` | `GameStateReader._read_screen_text()`, mode detection using screen text |
| `examples/pokemon_agent/area_analyzer.py` | Hybrid approach: memory-based sprite analysis + optional vision enhancement |

---

# ASCII Map Rendering

## Overview

Beyond reading screen text, an AI agent navigating Pokemon Yellow needs a **spatial map** of the current area — where walls are, where doors lead, where NPCs stand, and which tiles are interactable. The `render_ascii_map` MCP tool reads map data, blockset tiles, collision tables, warp entries, sprite positions, and interactable objects directly from Game Boy memory and ROM to produce a complete top-down ASCII grid.

```
   0123456789
 0:##########
 1:#C.B..B.##
 2:#........#
 3:#..@.....#
 4:#........#
 5:##N.....N#
 6:####WW####

Legend: . walkable  # blocked  C pc  B bookshelf  ! interactable
        G grass  W warp  @ player  N npc  T trainer  I item
```

Each cell in the grid represents one **movement step** (16x16 pixels = 2x2 graphical tiles). This matches the coordinate system used by `wXCoord` / `wYCoord` and the warp table.

## Map Data Hierarchy

```
Graphical Tile   8x8 px      Atomic rendering unit (stored in VRAM)
Block            32x32 px    4x4 graphical tiles = 16 bytes in ROM blockset
Movement Step    16x16 px    2x2 graphical tiles = 1 quadrant of a block
Map              NxM blocks  The walkable area; N*2 x M*2 movement steps
```

### wOverworldMap Buffer (0xC6E8)

The game stores the current map's block IDs in `wOverworldMap` at 0xC6E8. This buffer includes a **3-block border** on all sides for seamless map connections. The actual map blocks are embedded with:

```
stride = width_blocks + 6
offset = 3 * stride + 3
block[row][col] = memory[0xC6E8 + offset + row * stride + col]
```

Reading directly from 0xC6E8 gives border padding, not the actual map.

### Blockset Data (ROM)

Each block ID indexes into a blockset stored in ROM. The blockset address comes from WRAM:

| Address  | Field               | Description                     |
|----------|---------------------|---------------------------------|
| 0xD52A   | wTilesetBank        | ROM bank containing blockset    |
| 0xD52B   | wTilesetBlocksPtr   | 2-byte LE pointer to blockset   |

ROM offset for block N: `bank * 0x4000 + (ptr & 0x3FFF) + N * 16`

Each block is 16 bytes — a 4x4 grid of tile IDs:

```
Byte layout:         Movement quadrants:
[0] [1] [2] [3]     ┌─────┬─────┐
[4] [5] [6] [7]     │(0,0)│(1,0)│  Top-left, Top-right
[8] [9] [10][11]    ├─────┼─────┤
[12][13][14][15]    │(0,1)│(1,1)│  Bottom-left, Bottom-right
                     └─────┴─────┘
```

The **representative tile** for collision is the top-left of each 2x2 quadrant: bytes [0], [2], [8], [10]. The game checks this tile against the tileset's collision list to determine passability.

## Tile Classification

The renderer classifies each movement step using a priority chain:

```
1. Warp tile?      → W    (doors, stairs, cave entrances)
2. Grass tile?     → G    (tall grass, encounter zones)
3. Walkable tile?  → .    (passable floor, path, etc.)
4. PC tile?        → C    (computer terminals)
5. Bookshelf tile? → B    (bookshelves, shelves, elevator buttons)
6. Otherwise       → #    (wall, obstacle, furniture)
```

### Collision (Walkable) Tiles

Each of the 25 tilesets defines a list of passable tile IDs in `pokeyellow/data/tilesets/collision_tile_ids.asm`. Tiles NOT in this list are impassable. The renderer uses hardcoded copies of these tables rather than reading them from ROM, because the collision list and blockset may live in different ROM banks.

### Warp Tiles

Per-tileset warp tile IDs from `pokeyellow/data/tilesets/warp_tile_ids.asm`. When the player steps on a warp tile, the game looks up the destination in the warp table.

### Grass Tiles

From tileset headers — only three tilesets have grass encounters:
- Overworld: tile 0x52
- Forest: tile 0x20
- Plateau: tile 0x45

## Interactable Tile Detection

Pokemon Yellow has three separate systems for A-button interactions, each detected differently by the renderer.

### 1. Bookshelf Tiles (Tile-ID Based → `B`)

Certain tile IDs per tileset trigger a text script when the player faces them and presses A. Defined in `pokeyellow/data/tilesets/bookshelf_tile_ids.asm`:

| Tileset      | Tile IDs    | Objects                        |
|-------------|-------------|--------------------------------|
| House (8)   | 0x3D, 0x1E  | Town map, bookshelf            |
| RedsHouse1  | 0x32        | Bookshelf                      |
| Mansion     | 0x32        | Bookshelf                      |
| Lab         | 0x28        | Bookshelf                      |
| Gym/Dojo    | 0x1D        | Bookshelf                      |
| Lobby       | 0x16, 0x50, 0x52 | Elevator, pokemon merchandise |
| Mart/Center | 0x54, 0x55  | Pokemon merchandise shelves    |
| Gate        | 0x22        | Bookshelf                      |
| Ship        | 0x36        | Bookshelf                      |
| Plateau     | 0x30        | Statues                        |

**Quadrant check**: Bookshelf tiles often appear at non-representative positions within a 2x2 tile quadrant. For example, a bookshelf in the House tileset uses tile 0x1E at position `(0,1)` (bottom-left), not the top-left representative tile. The renderer checks **all 4 tiles** in the quadrant:

```python
quad_tiles = {block_tiles[row*4+col], block_tiles[row*4+col+1],
              block_tiles[(row+1)*4+col], block_tiles[(row+1)*4+col+1]}
if quad_tiles & bookshelf_set:
    grid[y][x] = "B"
```

### 2. PC / Computer Tiles (Tile-ID Based → `C`)

PCs are a special case of blocked interactable tiles. They're detected by tile ID per tileset, determined empirically from blockset data at known PC positions:

| Tileset         | Tile ID | Location                |
|-----------------|---------|-------------------------|
| RedsHouse1 (1)  | 0x42    | Player's house 1F       |
| RedsHouse2 (4)  | 0x42    | Player's house 2F       |
| Mart (2)        | 0x42    | Poke Mart               |
| Pokecenter (6)  | 0x42    | Pokemon Center           |
| Lab (20)        | 0x02    | Oak's Lab, Cinnabar Lab |

Like bookshelves, the PC tile may not be the representative (top-left) tile, so all 4 quadrant tiles are checked. PC detection takes priority over bookshelf detection.

### 3. BG Events / Signs (WRAM Coordinate-Based → `!`)

Signs, posters, and other coordinate-triggered interactions are stored in WRAM as part of the current map's object data:

| Address  | Field            | Description                          |
|----------|------------------|--------------------------------------|
| 0xD4AF   | wNumSigns        | Count of bg_events (max 16)          |
| 0xD4B0   | wSignCoords      | Y,X pairs (2 bytes each)             |
| 0xD4D0   | wSignTextIDs     | Text script ID per event (1 byte)    |

The renderer reads these entries and overlays `!` on the grid at each sign's coordinates, regardless of whether the tile is walkable or blocked.

**Note on hidden events**: PCs, gym statues, and hidden items use a separate ROM-based system (`data/events/hidden_events.asm`) that is NOT stored in WRAM. These are detected via tile IDs (PCs) rather than coordinate lookups.

## Coordinate Systems

### Map Coordinates (wXCoord / wYCoord)

The player's position in `wXCoord` (0xD361) and `wYCoord` (0xD360) uses the movement step grid where (0,0) is the top-left walkable position of the map.

### Sprite Coordinates (C2xx + 4 Bias)

Sprite map positions in `wSpriteStateData2` (0xC200) use an offset coordinate system where map origin (0,0) corresponds to C2xx value (4,4). The renderer subtracts 4 from both X and Y:

```python
npc_y = memory[0xC200 + sprite_index * 16 + 0x04] - 4
npc_x = memory[0xC200 + sprite_index * 16 + 0x05] - 4
```

This was verified empirically: Prof. Oak's C2xx coordinates (Y=8, X=14) minus 4 give (Y=4, X=10), which matches his definition in `PalletTown.asm`: `object_event 10, 4, ...`.

### Warp Coordinates (Direct)

Warp entries at 0xD3AE use direct map coordinates (no offset). Each entry is 4 bytes: `[Y, X, warp_id, dest_map]`. Count at 0xD3AD.

### Sign Coordinates (Direct)

Sign entries at 0xD4B0 use direct map coordinates. Each entry is 2 bytes: `[Y, X]`.

## MCP Tool: `render_ascii_map`

### Parameters

| Parameter       | Type | Default | Description                    |
|----------------|------|---------|--------------------------------|
| include_legend | bool | true    | Include legend in response     |

### Return Value

```json
{
  "map_id": 0,
  "map_name": "Pallet Town",
  "tileset": "Overworld",
  "tileset_id": 0,
  "dimensions": {
    "width_blocks": 10, "height_blocks": 9,
    "width_steps": 20, "height_steps": 18
  },
  "player": {"x": 5, "y": 6},
  "ascii": "   01234567...\n 0:##########...\n 1:...",
  "warps": [
    {"x": 5, "y": 5, "dest_map": 37, "dest_name": "Reds House 1F", "warp_id": 0}
  ],
  "bg_events": [
    {"x": 6, "y": 11, "text_id": 4}
  ],
  "sprites": [
    {"x": 10, "y": 4, "type": "npc", "picture_id": 1}
  ],
  "legend": ". walkable  # blocked  C pc  B bookshelf  ..."
}
```

### Rendering Pipeline

```
1. Read map metadata (map_id, tileset, dimensions, player pos)
           │
           ▼
2. Read map blocks from wOverworldMap (with 3-block border offset)
           │
           ▼
3. Get ROM blockset data (bank + pointer from WRAM)
           │
           ▼
4. For each block → for each 2x2 quadrant:
   - Read representative tile (top-left of quadrant)
   - Read all 4 quadrant tiles for interactable checks
   - Classify: W > G > . > C > B > #
           │
           ▼
5. Overlay warp entries from WRAM (mark W)
           │
           ▼
6. Overlay bg_events/signs from WRAM (mark !)
           │
           ▼
7. Overlay sprites from C1xx/C2xx (mark N/T/I, with -4 offset)
           │
           ▼
8. Mark player position (@)
           │
           ▼
9. Format as numbered ASCII grid with column/row headers
```

## Examples

### Player House 2F (Map 38, Tileset: RedsHouse2)

```
   01234567
 0:########
 1:C#....##
 2:##......#
 3:#......#
 4:#......#
 5:#......#
 6:#..@...#
 7:#W######
```

- `C` at (0,1): Player's PC
- `W` at (1,7): Stairs to 1F
- `@` at (3,6): Player position

### Player House 1F (Map 37, Tileset: RedsHouse1)

```
   01234567
 0:########
 1:#B.....#
 2:##.....#
 3:#......#
 4:#..N...#
 5:#......#
 6:####WW##
```

- `B` at (1,1): Bookshelf
- `N` at (3,4): Mom NPC
- `WW` at row 6: Front door (two warp tiles)

### Pallet Town (Map 0, Tileset: Overworld)

```
   01234567890123456789
 0:####################
 1:#.........#........#
 2:#.........#........#
 3:#..######.#.######.#
 4:#..#....#.#N#....#.#
 5:#..#..WW#.#.#..WW#.#
 6:#..######...######..
 7:....................
 8:....!...............
 9:....................
10:..GG..GG..GG..GG...
11:..GG..GG..GG..GG.!.
...
```

- `W` tiles: Doors to buildings
- `!` tiles: Signs (from bg_events)
- `G` tiles: Tall grass patches
- `N`: NPCs (Prof. Oak, rival, etc.)

## Agent Integration

### Pathfinding

The ASCII map feeds directly into BFS pathfinding. The agent converts the grid to a walkability matrix:

```python
walkable = {'.', 'G', 'W', '!', '@'}  # Tiles the player can step on
blocked  = {'#', 'C', 'B', 'N', 'T'}  # Impassable tiles
```

### Interactable Detection

When the agent needs to use a PC or read a sign:
1. Call `render_ascii_map` to get the grid and entity lists
2. Find `C` tiles (PCs) or `!` tiles (signs) in the grid
3. Pathfind to an adjacent walkable tile
4. Face the interactable and press A

### Map Change Detection

When `map_id` changes after a warp, the agent calls `render_ascii_map` to survey the new area before making navigation decisions.

## Implementation Files

| File | Role |
|------|------|
| `examples/pokemon_agent/mcp_plugin.py` | `render_ascii_map` tool with collision, interactable, and sprite rendering |
| `examples/pokemon_agent/pokemon_data.py` | `MAP_NAMES`, `TILESET_NAMES` lookup tables |
| `examples/pokemon_agent/pathfinding.py` | BFS pathfinding using the ASCII grid |
| `docs/THE_NRO_OF_POKEMON.md` | Detailed reference for the tile/block/map hierarchy |
