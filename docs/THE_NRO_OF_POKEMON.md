# THE NRO OF POKEMON: Maps, Tiles, Collision, and the ASCII Renderer

How Pokemon Yellow's map system works under the hood, and how the
`render_ascii_map` MCP tool turns raw memory into a faithful ASCII grid.

---

## 1. The Tile / Block / Map Hierarchy

The Game Boy's 160x144 pixel screen is built from three nested layers:

```
Graphical Tile   8x8 pixels     The atomic unit. Stored in VRAM.
Block            32x32 pixels   4x4 graphical tiles (16 bytes). Also called "metatile".
Map              NxM blocks     The overworld area the player walks around in.
```

### Graphical Tiles (8x8)

Each tile is an 8x8 bitmap, 2 bits per pixel (4 shades).
Tiles are identified by an 8-bit ID (0x00-0xFF).
The tileset defines what each tile ID looks like visually.

### Blocks / Metatiles (4x4 tiles = 32x32 pixels)

A block is a 4x4 arrangement of graphical tile IDs, stored as **16 bytes**
in the blockset data in ROM. Example for an indoor floor block:

```
block_data[0..15]:
  tile[0]  tile[1]  tile[2]  tile[3]      row 0
  tile[4]  tile[5]  tile[6]  tile[7]      row 1
  tile[8]  tile[9]  tile[10] tile[11]     row 2
  tile[12] tile[13] tile[14] tile[15]     row 3
```

### Maps (NxM blocks)

A map is a 2D grid of block IDs. Pallet Town is 10x9 blocks (= 20x18 movement
steps = 80x72 graphical tiles = 320x288 pixels).

Map block data lives in `wOverworldMap` (0xC6E8), but this buffer includes a
**3-block border** on all sides for map connections. The actual map data is
embedded with stride `width_blocks + 6`:

```
buffer_stride = width_blocks + 6
first_block_offset = 3 * buffer_stride + 3
block[row][col] = wOverworldMap[first_block_offset + row * buffer_stride + col]
```

For a 4x4 block map (e.g., Player House 2F): stride=10, first block at offset 33
(0xC6E8 + 33 = 0xC709). Reading directly from 0xC6E8 gives border padding blocks,
not the actual map.

---

## 2. Movement Grid and Collision

The player sprite is 16x16 pixels (2x2 graphical tiles). Each movement step
moves the player by 16 pixels. So within each 4x4-tile block, there are
**2x2 movement positions**.

### Collision Check Algorithm

When the player tries to step onto a tile, the game:

1. Determines which **block** the target position falls in.
2. Reads the block's 16-byte tile data from the blockset in ROM.
3. Picks the **representative tile** for the movement quadrant:
   - Quadrant (0,0): `block_data[0]`  (top-left 2x2)
   - Quadrant (1,0): `block_data[2]`  (top-right 2x2)
   - Quadrant (0,1): `block_data[8]`  (bottom-left 2x2)
   - Quadrant (1,1): `block_data[10]` (bottom-right 2x2)
4. Looks up the tile ID in the tileset's **collision list** — a list of tile IDs
   that are passable. If the tile is in the list, movement is allowed.
5. Additionally checks **tile-pair collisions** (elevation differences).

### Collision Tile Lists

Each of the 25 tilesets has its own list of passable tile IDs, defined in
`pokeyellow/data/tilesets/collision_tile_ids.asm`. For example, the Overworld
tileset allows these tile IDs:

```
0x00, 0x10, 0x1B, 0x20, 0x21, 0x23, 0x2C, 0x2D, 0x2E,
0x30, 0x31, 0x33, 0x39, 0x3C, 0x3E, 0x52, 0x54, 0x58, 0x5B
```

Any tile NOT in this list is impassable (walls, water, trees, etc.).

### Tileset WRAM Metadata

When the game loads a map, it copies tileset info into WRAM:

| Address  | Name                   | Description                          |
|----------|------------------------|--------------------------------------|
| `0xD366` | `wCurMapTileset`       | Tileset ID (0-24)                    |
| `0xD52A` | `wTilesetBank`         | ROM bank containing blockset         |
| `0xD52B` | `wTilesetBlocksPtr`    | 2-byte LE pointer to blockset in ROM |
| `0xD52F` | `wTilesetCollisionPtr` | 2-byte LE pointer to collision list  |
| `0xD534` | `wGrassTile`           | Tile ID that triggers grass encounters |

To read blockset data for block N:
```
rom_offset = bank * 0x4000 + (blocks_ptr & 0x3FFF) + block_id * 16
```

To read the collision list:
```
rom_offset = bank * 0x4000 + (coll_ptr & 0x3FFF)
# Read bytes until 0xFF terminator
```

---

## 3. The 25 Tilesets

From `pokeyellow/data/tilesets/tileset_headers.asm`:

| ID | Name       | Grass Tile | Notes                              |
|----|------------|------------|------------------------------------|
| 0  | Overworld  | 0x52       | Towns, routes, outdoor areas       |
| 1  | RedsHouse1 | -          | Player's house ground floor        |
| 2  | Mart       | -          | Poke Marts                         |
| 3  | Forest     | 0x20       | Viridian Forest, Safari Zone       |
| 4  | RedsHouse2 | -          | Player's house 2nd floor           |
| 5  | Dojo       | -          | Fighting Dojo                      |
| 6  | Pokecenter | -          | Pokemon Centers                    |
| 7  | Gym        | -          | Gyms                               |
| 8  | House      | -          | Generic NPC houses                 |
| 9  | ForestGate | -          | Gate buildings between areas        |
| 10 | Museum     | -          | Pewter Museum                      |
| 11 | Underground| -          | Underground paths                  |
| 12 | Gate       | -          | Route gates                        |
| 13 | Ship       | -          | SS Anne                            |
| 14 | ShipPort   | -          | Vermilion Dock                     |
| 15 | Cemetery   | -          | Pokemon Tower                      |
| 16 | Interior   | -          | Silph Co., Game Corner             |
| 17 | Cavern     | -          | Mt. Moon, Rock Tunnel, caves       |
| 18 | Lobby      | -          | Pokemon League lobby               |
| 19 | Mansion    | -          | Pokemon Mansion                    |
| 20 | Lab        | -          | Oak's Lab, Cinnabar Lab            |
| 21 | Club       | -          | Pokemon Fan Club                   |
| 22 | Facility   | -          | Rocket Hideout, Silph Co. elevator |
| 23 | Plateau    | 0x45       | Indigo Plateau                     |
| 24 | BeachHouse | -          | Summer Beach House (Yellow-only)   |

---

## 4. Warp Detection

### Warp Tiles

Each tileset defines which tile IDs trigger warps (doors, stairs, ladders).
From `pokeyellow/data/tilesets/warp_tile_ids.asm`. Key examples:

- Overworld: `0x1B` (door), `0x58` (cave entrance)
- RedsHouse1/2: `0x1A` (stairs up), `0x1C` (stairs down)
- Cavern: `0x18`, `0x1A` (ladders), `0x22` (holes)

### Warp Table in WRAM

The game stores warp entries at `0xD3AF`, count at `0xD3AE`.
Each entry is 4 bytes:

```
byte 0: Y coordinate (step grid)
byte 1: X coordinate (step grid)
byte 2: Warp ID at destination (0-indexed)
byte 3: Destination map ID
```

**Caveat**: Warp entries in WRAM can be corrupted in save states
(particularly `dest_map = 0` for stairs). The `render_ascii_map` tool
marks warp positions on the grid using both the warp table and warp tile
detection from blockset data.

---

## 5. Sprite Positions

### wSpriteStateData1 (0xC100)

16 bytes per sprite, indexed 0-15 (sprite 0 = player). Key fields:
- Offset 0x00: Picture ID (sprite image)
- Offset 0x04: Y pixel position on screen
- Offset 0x06: X pixel position on screen

### wSpriteStateData2 (0xC200)

16 bytes per sprite. **Canonical map coordinates**:
- Offset 0x04: Map Y (step coordinate)
- Offset 0x05: Map X (step coordinate)

**Important**: Always use `wSpriteStateData2` offsets 0x04/0x05 for map
coordinates. The `wSpriteStateData1` Y/X fields are screen-relative pixel
positions, not map coordinates.

### Sprite Classification

The picture ID from SpriteStateData1 identifies what the sprite looks like:

| Picture ID | Type    | Examples                     |
|------------|---------|------------------------------|
| 0x02-0x15  | Trainer | Bug Catcher, Lass, Youngster |
| 0x22-0x26  | NPC     | Prof Oak, Nurse, Officer     |
| 0x29       | Item    | Pokeball item on ground      |
| Others     | NPC     | Generic townspeople          |

---

## 6. The ASCII Rendering Pipeline

The `render_ascii_map` MCP tool performs these steps:

### Step 1: Read Map Metadata
```
map_id       <- 0xD35D
tileset_id   <- 0xD366
width_blocks <- 0xD368
height_blocks<- 0xD367
player_x     <- 0xD361
player_y     <- 0xD360
```

### Step 2: Read Map Block Data
```
map_data[0..width*height-1] <- 0xC6E8
```

### Step 3: Get ROM and Tileset Pointers
```
rom_data    <- GET_DIRECT_ACCESS("rom")
bank        <- 0xD52A
blocks_ptr  <- 0xD52B (2 bytes LE)
coll_ptr    <- 0xD52F (2 bytes LE)
grass_tile  <- 0xD534
```

### Step 4: Build Collision Grid

For each block in the map:
1. Compute ROM offset: `bank * 0x4000 + (blocks_ptr & 0x3FFF) + block_id * 16`
2. Read 16 bytes of tile data
3. For each of the 4 movement quadrants, check the representative tile:
   - In warp tile set? -> `W`
   - Matches grass tile? -> `G`
   - In collision (walkable) set? -> `.`
   - Otherwise -> `#`

### Step 5: Overlay Entities

Read and mark on the grid:
- Warp entries from 0xD3AF (mark `W`)
- Sprites from 0xC100/0xC200 (mark `N`, `T`, or `I`)
- Player position (mark `@`)

### Step 6: Format Output

```
   0123456789...
 0:##WW########
 1:#..........#
 2:#....N.....#
 3:#..........#
 4:#....@.....#
 5:####WW######
```

---

## 7. Example: Player House 2F (Map 38)

Tileset: REDS_HOUSE_2 (ID 4)
Dimensions: 4x4 blocks = 8x8 steps

```
   01234567
 0:########
 1:#......#
 2:#......#
 3:#..N...#
 4:#......#
 5:#......#
 6:#..@...#
 7:#W######
```

- `@` at (3,6): Player spawn point after intro
- `W` at (1,7): Stairs down to 1F
- `N`: Mom NPC (or empty after leaving)

---

## 8. Plugin System Architecture

The `render_ascii_map` tool lives in a **plugin**, not in the core SameBoy MCP
server. This separation keeps game-specific logic out of the generic emulator
tools.

### How Plugins Work

```
sameboy_mcp/server.py          Core server: memory, CPU, display, etc.
examples/pokemon_agent/         Game-specific agent code
  mcp_plugin.py                 Plugin: register_tools(server, emu_thread)
    -> decode_screen_text       Gen 1 text decoder
    -> read_screen_tiles        Raw tile reader
    -> render_ascii_map         ASCII map renderer
```

### Loading a Plugin

```bash
python -m sameboy_mcp.server \
    --lib /path/to/libsameboy.so \
    --rom /path/to/pokemon_yellow.gb \
    --plugin examples.pokemon_agent.mcp_plugin
```

The `--plugin` flag accepts a Python module path. The module must export
`register_tools(server: FastMCP, emu_thread: EmulatorThread)`.

Multiple plugins can be loaded:
```bash
--plugin examples.pokemon_agent.mcp_plugin \
--plugin examples.tetris_agent.mcp_plugin
```

### Writing a Plugin

```python
from mcp.server import FastMCP
from sameboy_mcp.emulator.thread import EmulatorThread, CommandType

def register_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    @server.tool()
    async def my_custom_tool() -> dict:
        result = emu_thread.send_command(CommandType.READ_MEMORY, {"address": 0xC000})
        return {"value": result.get("value", 0)}
```

The plugin has full access to:
- `server` — register new MCP tools via `@server.tool()`
- `emu_thread` — send commands to the emulator (read/write memory, get screen, etc.)
