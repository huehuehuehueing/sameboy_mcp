# Adventure Time: An AI Agent's Pokemon Yellow Odyssey

## How an LLM Hacked, Warped, and Conquered a 1998 Game Boy Game Through MCP Tools

> *A chronicle of the SameBoy MCP Server's capabilities, demonstrated through
> a live session where an AI agent went from zero to Pokemon Master in under
> an hour, armed with nothing but memory reads, memory writes, and an
> unreasonable amount of ambition.*

---

## Prologue: The Setup

The stage was set: a Game Boy Color emulator (SameBoy) wrapped as an MCP
server, a copy of Pokemon Yellow (1998), and a Claude agent connected via
the Model Context Protocol. The emulator exposed over 50 tools -- memory
read/write, screen capture, joypad input, save states, breakpoints, ASCII
map rendering, and more.

A saved state (`after_intro.sav`) placed the player in **Player House 2F**
(map 38), freshly awoken by Pikachu, with the whole Kanto region ahead.

The question: *How much havoc can an AI agent cause through direct memory
manipulation of a 27-year-old game?*

The answer: **A lot.**

---

## Act I: The Great Potion Heist

**Objective:** Withdraw the Potion from the bedroom PC.

The agent navigated the player character to the PC at coordinates (0,1),
confirmed its location via the `render_ascii_map` tool (which showed it as
`C` for computer), and initiated interaction. Through a sequence of
precisely-timed `press_key` commands, the agent navigated:

```
Turn on PC → WITHDRAW ITEM → Select POTION → Quantity: 1 → Confirm → LOG OFF
```

Each menu transition required reading the screen text via `decode_screen_text`
to verify the correct option was highlighted before pressing A. The Potion
was successfully withdrawn.

**Tools used:** `press_key`, `run_frames`, `decode_screen_text`, `render_ascii_map`

---

## Act II: The Inventory Hack

### 99 Potions

**Objective:** Turn 1 Potion into 99.

The agent located the bag data structure in WRAM:

| Address  | Field          | Value |
|----------|----------------|-------|
| `0xD31C` | Number of item types | 1     |
| `0xD31D` | Item ID (Potion)     | `0x14` |
| `0xD31E` | Quantity             | 1     |
| `0xD31F` | Terminator           | `0xFF` |

One `write_memory` call changed `0xD31E` from `1` to `99` (`0x63`).
Verified by opening the bag menu: **POTION x99**. Done.

### 99 Master Balls

**Objective:** Add 99 Master Balls to inventory.

The agent extended the bag data structure by:

1. Incrementing item count at `0xD31C` to `2`
2. Writing Master Ball ID (`0x01`) at `0xD31F`
3. Writing quantity `99` at `0xD320`
4. Moving the terminator (`0xFF`) to `0xD321`

Verified in the bag menu: **MASTER BALL x99**. The world was now at our mercy.

**Tools used:** `read_memory`, `write_memory`, `press_key`, `decode_screen_text`

---

## Act III: The Pokemon Injection

### A Level 100 Magikarp

**Objective:** Inject a fully-formed Level 100 Magikarp into the party.

This was the most technically demanding operation. The agent constructed the
**entire 44-byte Gen 1 party Pokemon data structure from scratch**, writing
to three separate memory regions:

**Party metadata** (at `0xD162`):
- Party count = 1
- Species list = `[0x85, 0xFF]` (Magikarp + terminator)

**Mon data** (44 bytes at `0xD16A`):

| Offset | Field       | Value                        |
|--------|-------------|------------------------------|
| +0x00  | Species     | `0x85` (Magikarp)            |
| +0x01  | Current HP  | 244 (big-endian)             |
| +0x03  | Level (box) | 100                          |
| +0x05  | Type 1/2    | Water/Water (`0x15/0x15`)    |
| +0x07  | Catch rate  | 255                          |
| +0x08  | Move 1      | Splash (`0x96`)              |
| +0x09  | Move 2      | Tackle (`0x21`)              |
| +0x0C  | OT ID       | `0x3BC0`                     |
| +0x0E  | Experience  | 1,000,000 (Slow growth)      |
| +0x11  | EVs         | All maxed (`0xFFFF` x5)      |
| +0x1B  | IVs         | All maxed (`0xFFFF`)         |
| +0x21  | Level (party)| 100                         |
| +0x22  | Max HP      | 244                          |
| +0x24  | Stats       | Calculated with max EVs/IVs  |

Stats were computed using the Gen 1 stat formula:
```
Stat = floor(((Base + IV + floor(sqrt(EV)/8)) * Level / 50) + 5)
HP   = floor(((Base + IV + floor(sqrt(EV)/8)) * Level / 50) + Level + 10)
```

With Magikarp's pitiful base stats (20/10/55/80/20), even maxed out at
Level 100, the result was: **HP 244 / Atk 119 / Def 209 / Spd 259 / Spc 139**.

**OT Name** "ASH" written at `0xD272` in Gen 1 character encoding
(A=`0x80`, S=`0x92`, H=`0x87`).

**Nickname** "MAGIKARP" written at `0xD2B8`.

Verified in the Pokemon stats screen. A legitimate (if tragic) Level 100
Magikarp, ready to Splash its way to defeat.

### Transformation: Magikarp Becomes Mew

**Objective:** Transform the Magikarp into a competitive Level 100 Mew.

The agent performed a species transplant, updating every relevant field:

| Change              | Old (Magikarp) | New (Mew)                    |
|---------------------|----------------|------------------------------|
| Species             | `0x85`         | `0x15`                       |
| Types               | Water/Water    | Psychic/Psychic (`0x18`)     |
| Catch rate          | 255            | 45                           |
| Moves               | Splash, Tackle | Psychic, Thunderbolt, Ice Beam, Earthquake |
| Experience          | 1,000,000      | 1,059,860 (Medium Slow)      |
| HP                  | 244            | **404**                      |
| Atk/Def/Spd/Spc    | Various        | **299/299/299/299**          |
| Nickname            | MAGIKARP       | MEW                          |

Mew's base stats are a uniform 100 across the board. With max EVs and IVs
at Level 100, every stat hit **299**, with HP at **404**. The moveset was
chosen for maximum coverage:

- **Psychic** (STAB, 90 power)
- **Thunderbolt** (95 power, Electric coverage)
- **Ice Beam** (95 power, Ice coverage)
- **Earthquake** (100 power, Ground coverage)

Pokemon #151, the mythical Mew -- now sitting in the party, ready to
obliterate everything in Kanto. Verified in the stats screen: Level 100,
HP 404/404, all stats 299.

**Tools used:** `read_memory`, `write_memory` (dozens of calls), `press_key`, `capture_screen`

---

## Act IV: The Great Warp Heist

### Max Money

**Objective:** Set money to the maximum $999,999.

Pokemon Gen 1 stores money in **Binary-Coded Decimal** (BCD) format across
3 bytes at `0xD347`:

```
$999,999 = 0x99 0x99 0x99
```

Three `write_memory` calls. Instant millionaire.

### Warp Table Hijacking: Player House to Pokemon Center

**Objective:** Teleport from Player House 2F directly to the Pokemon Center.

This was the crown jewel of memory manipulation. The agent exploited the
game's warp table stored in WRAM:

- `0xD3AD`: Number of warps on current map
- `0xD3AE`: Warp entries (4 bytes each: Y, X, warp_id, dest_map)

Player House 2F had stairs at position (7,1) leading to Player House 1F
(map 37). The agent **hijacked the warp destination** by overwriting:

| Address  | Original        | Modified                    |
|----------|-----------------|-----------------------------|
| `0xD3B0` | warp_id → 1F    | warp_id → Pokemon Center    |
| `0xD3B1` | dest_map = 37   | dest_map = 58               |

The player walked to the stairs, stepped on them, and was instantly
teleported to the **Pewter Pokemon Center** instead of downstairs.

But there was a catch: the `ignore_input` counter at `0xD139` was still
active from the intro sequence (value: 89), blocking all player movement.
The agent wrote `0` to clear it, and the player was free.

### Meeting Nurse Joy

The agent navigated the player up to Nurse Joy and pressed A. She greeted
us: *"Welcome to our POKEMON CENTER!"*

Then came the punchline.

### Rewriting Reality: Custom Dialog Injection

**Objective:** Replace Nurse Joy's dialog text with a custom message.

The agent wrote **Gen 1 character-encoded glyphs directly to the WRAM tile
map** at `0xC3A0`. The screen is a 20x18 grid of tile IDs, and the text
box occupies rows 14-17. Each character has a unique tile ID in Pokemon's
custom encoding:

```
A=0x80  B=0x81  C=0x82  ...  Z=0x99
a=0xA0  b=0xA1  ...  z=0xB9
Space=0x7F  String terminator=0x50
```

The agent calculated the exact WRAM offsets for the text lines:
- **Row 14, col 1** = `0xC4B9` (line 1)
- **Row 16, col 1** = `0xC4E1` (line 2)

Then wrote 36 bytes of encoded text. Since the Game Boy's VBlank handler
copies the WRAM tile map to VRAM every frame, the custom text rendered
immediately on the next frame. Nurse Joy was now saying exactly what we
wanted.

A screenshot was captured at 4x scale as proof.

**Tools used:** `write_memory`, `decode_screen_text`, `capture_screen`, `run_frames`

---

## Act V: The Homecoming

### Saving the WINNER State

The agent saved the entire emulator state (all of RAM, registers, and
hardware state -- approximately 116KB) with the name **"WINNER"**. This
preserved every hack: the Mew, the Master Balls, the money, the custom
dialog, the Pokemon Center location.

### Warping Home to Pallet Town

**Objective:** Get back to Pallet Town from the Pokemon Center.

The same warp hijacking technique was used again, this time on the Pokemon
Center's exit doors. The two warps at positions (3,7) and (4,7) originally
pointed to `dest_map=255` (a special value meaning "return to previous
map"). The agent overwrote both:

| Address  | Original | Modified       |
|----------|----------|----------------|
| `0xD3B1` | 255      | 0 (Pallet Town)|
| `0xD3B5` | 255      | 0 (Pallet Town)|

The warp IDs were set to 0, targeting Pallet Town's first warp entry at
coordinates (5,5) -- the front door of the player's house. Walk through the
Pokemon Center doors, arrive at mama's doorstep.

**Home sweet home.**

---

## Technical Summary

### Tools Used in This Session

| Category           | Tools                                    | Purpose                          |
|--------------------|------------------------------------------|----------------------------------|
| Memory             | `read_memory`, `write_memory`            | Game state manipulation          |
| Display            | `capture_screen`, `decode_screen_text`   | Visual verification              |
| Map Analysis       | `render_ascii_map`                       | Spatial awareness & navigation   |
| Input              | `press_key`, `run_frames`                | Game interaction                 |
| State Management   | `save_state`, `load_state`, `import_state` | Progress preservation          |
| Live Display       | `enable_live_display`, `set_user_input`  | Real-time visual feedback        |

### Key Memory Addresses Manipulated

| Address    | Name              | Purpose                              |
|------------|-------------------|--------------------------------------|
| `0xC3A0`   | wTileMap          | Screen tile data (text injection)    |
| `0xD139`   | wIgnoreInput      | Input blocking counter               |
| `0xD162`   | wPartyCount       | Number of Pokemon in party           |
| `0xD163`   | wPartySpecies     | Species list                         |
| `0xD16A`   | wPartyMon1        | Full Pokemon data (44 bytes)         |
| `0xD272`   | wPartyMonOT       | Original Trainer name                |
| `0xD2B8`   | wPartyMonNicks    | Pokemon nickname                     |
| `0xD31C`   | wNumBagItems      | Inventory item count                 |
| `0xD31D`   | wBagItems         | Item ID/quantity pairs               |
| `0xD347`   | wPlayerMoney      | Money (3 bytes, BCD encoded)         |
| `0xD35E`   | wCurMap           | Current map number                   |
| `0xD361`   | wYCoord/wXCoord   | Player position                      |
| `0xD3AD`   | wNumberOfWarps    | Warp count for current map           |
| `0xD3AE`   | wWarpEntries      | Warp destinations (Y, X, id, map)    |

### Techniques Demonstrated

1. **Inventory Structure Manipulation** -- Extending Gen 1's item list format with proper terminator management
2. **Full Pokemon Data Construction** -- Building a 44-byte party Pokemon from scratch with calculated stats using the Gen 1 formula
3. **Species Transformation** -- Hot-swapping species, types, moves, experience groups, and stats across multiple WRAM regions
4. **BCD Money Encoding** -- Setting max currency using Binary-Coded Decimal
5. **Warp Table Hijacking** -- Redirecting map transitions by overwriting WRAM warp destinations
6. **Direct VRAM Text Injection** -- Writing character-encoded glyphs to the tile map for custom dialog rendering
7. **Input Counter Bypass** -- Clearing the ignore_input counter to enable movement during scripted sequences
8. **ASCII Map Rendering** -- Real-time spatial analysis using blockset data, collision tables, and sprite positions

---

## Epilogue

What started as a test of the ASCII map renderer ended with an AI agent
that had:

- Stolen a Potion from a PC
- Duplicated it 99 times
- Conjured 99 Master Balls from thin air
- Manifested a Level 100 Mew with a perfect moveset
- Become a millionaire
- Teleported across the map by rewriting warp tables
- Put custom words in Nurse Joy's mouth
- Warped home to Pallet Town for a well-deserved rest

All through the Model Context Protocol. All through memory reads and writes.
All in a single session.

The SameBoy MCP Server turns a Game Boy emulator into a programmable
sandbox where AI agents can observe, analyze, and manipulate game state at
the deepest level. It is reverse engineering as a service, game hacking as
a tool call, and an absurdly fun way to demonstrate what happens when you
give an LLM direct access to hardware memory.

**GG.**

---

*Built for COSC 69.16 at Dartmouth College, Winter 2026.*
*Powered by SameBoy, the Model Context Protocol, and sheer audacity.*
