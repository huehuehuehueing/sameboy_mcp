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
| `sameboy_mcp/tools/gameboy.py` | MCP tools: `decode_screen_text`, `read_screen_tiles`, `GEN1_CHAR_ENCODING` table |
| `examples/pokemon_agent/memory_map.py` | Agent-side: `CHAR_ENCODING`, `decode_text()`, `encode_text()`, `WRAM_TILE_MAP` address |
| `examples/pokemon_agent/game_state.py` | `GameStateReader._read_screen_text()`, mode detection using screen text |
| `examples/pokemon_agent/area_analyzer.py` | Hybrid approach: memory-based sprite analysis + optional vision enhancement |
