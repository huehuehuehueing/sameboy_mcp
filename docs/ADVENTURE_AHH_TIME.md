# Don't Be a Menace to Pallet Town While Drinking Your Juice in the Hood

## How Ashtray and His Homie Hacked Pokemon Yellow Through MCP Tools

> *A chronicle of the SameBoy MCP Server's capabilities, demonstrated through
> a live session where a man named Ashtray and his AI homie went from mama's
> crib to the Pokemon Center and back, armed with nothing but memory reads,
> memory writes, and an unreasonable amount of audacity.*
>
> *All MCP tool responses shown below are actual, unmodified outputs from the
> live session.*
>
> *"I'm just trying to be a good person in a bad world." -- Ashtray, probably*

---

## Prologue: Message In a Bottle

My name is Ashtray. I was sent to live with my grandmama in Pallet Town,
which was located in a bad part of Kanto. Her house was always full of
old people who watched game shows and waited to die.

But today was different. Today I had a mission. And I had my homie -- an
AI agent connected to mama's Game Boy through something called the
"Model Context Protocol." My homie had access to over 50 tools: memory
read/write, screen capture, joypad input, save states, breakpoints, ASCII
map rendering -- the whole arsenal. Everything a young man needs to make
it in the hood.

We loaded up at mama's crib from a saved state (`newgame_pallettown.sav`),
standing right outside the front door in **Pallet Town** at position (5,6).

My homie surveyed the neighborhood with `render_ascii_map`:

```
render_ascii_map -> {
  "map_id": 0,
  "map_name": "Pallet Town",
  "tileset": "OVERWORLD",
  "player": { "x": 5, "y": 6 },
  "ascii": "   00000000001111111111
   01234567890123456789
 0:...#.....#GG#.....#.
 1:##########GG########
 2:#..................#
 3:#...####....####...#
 4:#...####....####...#
 5:#...#W##....#W##...#
 6:#....@.............#
 7:#..................#
 8:#.........######...#
 9:#...###...######...#
10:#.........######...#
11:#...####..##W###...#
12:#..................#
 ...",
  "warps": [
    { "x": 5, "y": 5, "dest_map": 37, "dest_name": "Player House 1F" },
    { "x": 13, "y": 5, "dest_map": 39, "dest_name": "Rival House" },
    { "x": 12, "y": 11, "dest_map": 40, "dest_name": "Oak's Lab" }
  ]
}
```

There it was. `W` at (5,5) -- mama's front door. The whole hood laid out
in ASCII. Time to go inside.

The question: *How much havoc can a man named Ashtray and his AI homie
cause through direct memory manipulation of a 27-year-old game?*

The answer: **Don't even trip.**

---

## Act I: Mama's Crib

**Objective:** Get upstairs to the bedroom and steal the Potion from the PC.

We walked through the front door into Player House 1F. Mama wasn't home --
probably at bingo. Good. We headed straight for the stairs and climbed up
to Player House 2F. My bedroom.

The agent mapped the room:

```
render_ascii_map -> {
  "map_id": 38,
  "map_name": "Player House 2F",
  "tileset": "REDS_HOUSE_2",
  "player": { "x": 3, "y": 6 },
  "ascii": "   01234567
 0:########
 1:C##....#
 2:........
 3:........
 4:...#....
 5:...#....
 6:#..@..#.
 7:#.W...#.",
  "warps": [{
    "x": 2, "y": 7,
    "dest_map": 37, "dest_name": "Player House 1F", "warp_id": 0
  }]
}
```

`C` at (0,1) -- the PC. That's where mama kept the goods. `W` at (2,7) --
the stairs back down. And `@` at (3,6) -- that's me, Ashtray, standing
in my room about to commit my first crime.

See, mama always kept a Potion in the PC. Said it was "for emergencies."
Well this *was* an emergency. An emergency of ambition.

---

## Act II: The Great Potion Heist

**Objective:** Withdraw the Potion from the bedroom PC.

My homie navigated me to the PC. Had to go the long way around -- the
`##` tiles were blocking the direct path (story of my life). Went down to
row 2, cut left to x=0, then faced up to interact.

The `decode_screen_text` tool verified the menu:

```
decode_screen_text -> {
  "text_lines": [
    "WITHDRAW ITEM",
    "DEPOSIT ITEM",
    "TOSS ITEM",
    "LOG OFF",
    "What do you want",
    "to do?"
  ]
}
```

After selecting WITHDRAW ITEM:

```
decode_screen_text -> {
  "text_lines": [
    "POTION",
    "x 1",
    "CANCEL",
    "What do you want",
    "to withdraw?"
  ]
}
```

Selected the Potion. Confirmed quantity 1. Logged off.

One Potion acquired. Through *legitimate gameplay*. Grandmama would be
proud.

But legitimacy was about to leave the building. Like my daddy.

**Tools used:** `press_key`, `run_frames`, `decode_screen_text`, `render_ascii_map`

---

## Act III: The Inventory Hack

### 99 Potions

**Objective:** Turn 1 Potion into 99. Because in the hood, you always
need backup.

My homie located the bag data structure in WRAM:

```
read_memory(address=0xD31C, length=20) -> {
  "address": "0xD31C",
  "hex": "011401ff00000000000000000000000000000000",
  "bytes": [1, 20, 1, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
}
```

Decoded:

| Address  | Field                | Hex    | Value |
|----------|----------------------|--------|-------|
| `0xD31C` | Number of item types | `0x01` | 1     |
| `0xD31D` | Item ID (Potion)     | `0x14` | 20    |
| `0xD31E` | Quantity             | `0x01` | 1     |
| `0xD31F` | Terminator           | `0xFF` | --    |

One `write_memory` call changed `0xD31E` from `1` to `99` (`0x63`).

```
read_memory(address=0xD31C, length=4) -> {
  "hex": "011463ff",
  "bytes": [1, 20, 99, 255]
}
```

Bag menu confirmation:

```
"text_lines": ["POTION", "x99", "CANCEL"]
```

99 Potions. Like that scene where Loc Dog pulls out an increasingly
ridiculous number of weapons. Except these heal.

### 99 Master Balls

**Objective:** Add 99 Master Balls. Because I told my homie, "Gimme dat
99x MASTER BALL loot too brotha."

Four `write_memory` calls extended the bag:

```
write_memory(address=0xD31C, value=0x02) -> "item count = 2"
write_memory(address=0xD31F, value=0x01) -> "Master Ball item ID"
write_memory(address=0xD320, value=0x63) -> "quantity = 99"
write_memory(address=0xD321, value=0xFF) -> "terminator"
```

Verified:

```
decode_screen_text -> {
  "text_lines": [
    "POTION",
    "x99",
    "MASTER BALL",
    "x99",
    "CANCEL"
  ]
}
```

99 Potions. 99 Master Balls. Ashtray was strapped.

**Tools used:** `read_memory`, `write_memory`, `press_key`, `decode_screen_text`

---

## Act IV: The Bread and the Squad

### Max Money

**Objective:** Get the bread. All of it.

See, in the hood, they say money can't buy happiness. But it *can* buy
99 Hyper Potions at the Celadon Department Store, and that's basically
the same thing.

Pokemon Gen 1 stores money in **Binary-Coded Decimal** (BCD) format across
3 bytes at `0xD347`:

```
$999,999 = 0x99 0x99 0x99
```

Three `write_memory` calls. Instant hood rich.

### Pokemon Injection: Mew and Magikarp

**Objective:** Build a squad. A Level 100 jacked Mew and a fat Magikarp.
Because every crew needs a heavy hitter and a funny guy.

This was the most technically demanding operation. My homie constructed
**two complete 44-byte Gen 1 party Pokemon data structures from scratch**,
writing to multiple memory regions.

**Party setup** (at `0xD162`):
- Party count = 2
- Species list = `[0x15, 0x85, 0xFF]` (Mew, Magikarp, terminator)

**Mew** (44 bytes at `0xD16A`) -- the muscle:

| Field       | Value                                     |
|-------------|-------------------------------------------|
| Species     | `0x15` (Mew)                              |
| Level       | 100                                       |
| HP          | **404**                                   |
| Types       | Psychic/Psychic                           |
| Moves       | Psychic, Thunderbolt, Ice Beam, Earthquake|
| All Stats   | **299**                                   |
| EVs/IVs     | Maxed                                     |

Mew's base stats are a uniform 100. With max EVs and IVs at Level 100,
every stat hits **299**, with HP at **404**. The moveset was chosen for
maximum devastation:

- **Psychic** (STAB, 90 power -- for when they talk sideways)
- **Thunderbolt** (95 power -- shocking, like my life choices)
- **Ice Beam** (95 power -- cold, like mama when I forgot to take out the trash)
- **Earthquake** (100 power -- ground coverage, for keeping it real)

Stats computed using the Gen 1 formula:
```
Stat = floor(((Base + IV + floor(sqrt(EV)/8)) * Level / 50) + 5)
HP   = floor(((Base + IV + floor(sqrt(EV)/8)) * Level / 50) + Level + 10)
```

**Magikarp** (44 bytes at `0xD196`) -- the comic relief:

| Field       | Value                        |
|-------------|------------------------------|
| Species     | `0x85` (Magikarp)            |
| Level       | 100                          |
| HP          | 242                          |
| Types       | Water/Water                  |
| Moves       | Splash, Tackle               |
| All Stats   | Calculated with max EVs/IVs  |

Every crew got that one homie who means well but can't fight. That's
Magikarp. Level 100, fully juiced on EVs and IVs, and his best move is
still Splash. But he's family.

**OT Names** "ASH" written at `0xD272` and `0xD27D` in Gen 1 character
encoding (A=`0x80`, S=`0x92`, H=`0x87`).

**Nicknames** "MEW" at `0xD2B8` and "MAGIKARP" at `0xD2C3`.

**Tools used:** `read_memory`, `write_memory` (dozens of calls), `press_key`, `capture_screen`

---

## Act V: The Great Warp Heist

### Warp Table Hijacking: Bedroom to Pokemon Center

**Objective:** Teleport from my bedroom to the Pewter Pokemon Center.
Because ain't nobody got time for Route 1.

This was the crown jewel. See, the game keeps a warp table in WRAM:

- `0xD3AD`: Number of warps on current map
- `0xD3AE`: Warp entries (4 bytes each: Y, X, warp_id, dest_map)

Player House 2F had stairs at (7,1) leading to Player House 1F (map 37).
My homie **hijacked the warp destination**:

| Address  | Original           | Modified                    |
|----------|--------------------|-----------------------------|
| `0xD3B0` | warp_id -> 1F      | warp_id -> Pokemon Center   |
| `0xD3B1` | dest_map = 37      | dest_map = 58               |

Walked to the stairs. Stepped on them. And instead of going downstairs
to mama's living room, I ended up in the **Pewter Pokemon Center**.

Like that scene in the movie where Ashtray walks through one door and
comes out somewhere completely different. Except this time it was on
purpose.

But there was a catch: the `ignore_input` counter at `0xD139` was still
active (value: 89), blocking all movement. My homie wrote `0` to clear
it.

Free at last.

---

## Act VI: That Fine Baddie Joy

### Arrival at Pewter Pokemon Center

The agent surveyed the new location:

```
render_ascii_map -> {
  "map_id": 58,
  "map_name": "Pewter Pokemon Center",
  "tileset": "POKECENTER",
  "player": { "x": 3, "y": 7 },
  "ascii": "   00000000001111
   01234567890123
 0:##############
 1:###IN#########
 2:###########N##
 3:#N##T########C
 4:##############
 5:##############
 6:##############
 7:###@W######T##",
  "warps": [
    { "x": 3, "y": 7, "dest_map": 255, "warp_id": 6 },
    { "x": 4, "y": 7, "dest_map": 255, "warp_id": 6 }
  ]
}
```

The Pokemon Center. NPCs everywhere. The PC at `C` (13,3). Exit doors
at `W`. And somewhere behind that counter -- Nurse Joy.

### Meeting Nurse Joy

Now, navigating the Pokemon Center was harder than it should've been.
My homie kept talking to the wrong people. First some gentleman going off
about how "POKEMON CENTERS are wonderful!" Then some other fool talking
about "conditions like sleep, burn..." I didn't come here for a TED talk.

I had to step in: "You must go down one spot, left two, one up."

Sometimes even AI needs directions from the hood.

Finally, we reached Joy. Pressed A:

```
decode_screen_text -> {
  "text_lines": [
    "Welcome to our",
    "POKeMON CENTER!  >"
  ]
}
```

*"Welcome to our POKEMON CENTER!"* -- there she was. The baddest nurse
in Kanto. And she had no idea what was about to happen to her dialog.

**Tools used:** `press_key`, `run_frames`, `decode_screen_text`, `render_ascii_map`

---

## Act VII: Rewriting Reality

### Text Injection #1: The Title Drop

**Objective:** Put our movie title in Nurse Joy's mouth.

My homie paused the game and wrote **Gen 1 character-encoded glyphs
directly to the WRAM tile map** at `0xC3A0`. The screen is a 20x18 grid
of tile IDs, and the text box occupies rows 14-17. Each character has a
unique tile ID:

```
A=0x80  B=0x81  C=0x82  ...  Z=0x99
a=0xA0  b=0xA1  ...  z=0xB9
Space=0x7F  String terminator=0x50
```

The agent calculated exact WRAM offsets:
- **Row 14, col 1** = `0xC4B9` (line 1)
- **Row 16, col 1** = `0xC4E1` (line 2)

Then wrote the encoded bytes. Since the Game Boy's VBlank handler copies
the WRAM tile map to VRAM every frame, the custom text rendered
immediately.

Verified:

```json
decode_screen_text() -> {
  "address": "0xC3A0",
  "width": 20,
  "height": 18,
  "rows": [
    "                    ",
    "                    ",
    "    ",
    "    ",
    "      ",
    "      ",
    "  ",
    "  ",
    "         ",
    "         ",
    "         ",
    "         ",
    "┌──────────────────┐",
    "│                  │",
    "│DONT BE A MENACE  │",
    "│                  │",
    "│WHILE DRINKIN OJ ▼│",
    "└──────────────────┘"
  ],
  "text_lines": [
    "DONT BE A MENACE",
    "WHILE DRINKIN OJ ▼"
  ]
}
```

The full 20x18 tile map decoded. Rows 0-11 are the Pokemon Center
interior (mostly blank tiles where sprites render). Rows 12-17 are
the text box: Gen 1 box-drawing characters (`┌─┐│└┘`) framing the
injected text, with the `▼` indicator (tile `0xEE`) signaling
"press A to continue."

Nurse Joy was now delivering the most important message in cinema history.
A screenshot was captured at 4x scale and saved as `ashtray_winner.png`.

State saved as `ASHTRAY_WINNER` and exported to
`examples/pokemon_agent/saved_states/ashtray_winner.sav`.

### Text Injection #2: Ashtray's Quest

**Objective:** Make Joy's next line about the real journey.

See, throughout the whole movie, Ashtray is just trying to find his
daddy. That's the subplot. That's the heart. So when Joy advanced her
dialog to *"We heal your POKeMON back to perfect health!"*, my homie
paused again and dropped the second injection:

```json
decode_screen_text() -> {
  "address": "0xC3A0",
  "width": 20,
  "height": 18,
  "rows": [
    "                    ",
    "                    ",
    "    ",
    "    ",
    "      ",
    "      ",
    "  ",
    "  ",
    "         ",
    "         ",
    "         ",
    "         ",
    "┌──────────────────┐",
    "│                  │",
    "│IM JUST TRYNA     │",
    "│                  │",
    "│FIND MY DADDY     │",
    "└──────────────────┘"
  ],
  "text_lines": [
    "IM JUST TRYNA",
    "FIND MY DADDY"
  ]
}
```

There it was. The emotional core of both the movie and this Pokemon
adventure, encoded in Gen 1 character glyphs and injected directly into
video memory.

State saved as `FIND_MY_DADDY` and exported to
`examples/pokemon_agent/saved_states/find_my_daddy.sav`.

**Tools used:** `write_memory`, `decode_screen_text`, `capture_screen`, `save_state`, `export_state`

---

## Act VIII: Going Home

### Warping Back to Mama's Crib

**Objective:** Get back to Pallet Town. Because at the end of every
adventure movie, you gotta go home.

Same warp hijacking technique, but in reverse. The Pokemon Center's exit
doors at (3,7) and (4,7) originally pointed to `dest_map=255` (a special
value meaning "return to previous map"). My homie overwrote both:

| Address  | Original | Modified        |
|----------|----------|-----------------|
| `0xD3B1` | 255      | 0 (Pallet Town) |
| `0xD3B5` | 255      | 0 (Pallet Town) |

Warp IDs set to 0, targeting Pallet Town's first warp entry -- the front
door of mama's house.

Walked through the Pokemon Center doors. And just like that...

```
render_ascii_map -> {
  "map_id": 0,
  "map_name": "Pallet Town",
  "tileset": "OVERWORLD",
  "player": { "x": 5, "y": 6 },
  "ascii": "   00000000001111111111
   01234567890123456789
 0:...#.....#GG#.....#.
 1:##########GG########
 2:#..................#
 3:#...####....####...#
 4:#...####..T.####...#
 5:#..!#W##...!#W##...#
 6:#....@.............#
 7:#..................#
 8:#....T....######...#
 9:#...###!..######...#
10:#.........######...#
11:#...####..##W###...#
12:#..................#
13:#.........###!##...#
14:#..........N.......#
15:#...####..####.....#
16:#...####...........#
17:##..################",
  "warps": [
    { "x": 5, "y": 5, "dest_map": 37, "dest_name": "Player House 1F" },
    { "x": 13, "y": 5, "dest_map": 39, "dest_name": "Rival House" },
    { "x": 12, "y": 11, "dest_map": 40, "dest_name": "Oak's Lab" }
  ]
}
```

Pallet Town. `@` at (5,6). Standing right outside mama's front door.

**We made it homie.**

---

## Technical Summary

### Tools Used in This Session

| Category           | Tools                                        | Purpose                          |
|--------------------|----------------------------------------------|----------------------------------|
| Memory             | `read_memory`, `write_memory`                | Game state manipulation          |
| Display            | `capture_screen`, `decode_screen_text`       | Visual verification              |
| Map Analysis       | `render_ascii_map`                           | Spatial awareness & navigation   |
| Input              | `press_key`, `run_frames`                    | Game interaction                 |
| State Management   | `save_state`, `load_state`, `import_state`, `export_state` | Progress preservation |
| Live Display       | `enable_live_display`, `disable_live_display`, `set_user_input` | Real-time visual feedback |

### Key Memory Addresses Manipulated

| Address    | Name              | Purpose                              |
|------------|-------------------|--------------------------------------|
| `0xC3A0`   | wTileMap          | Screen tile data (text injection)    |
| `0xD139`   | wIgnoreInput      | Input blocking counter               |
| `0xD162`   | wPartyCount       | Number of Pokemon in party           |
| `0xD163`   | wPartySpecies     | Species list                         |
| `0xD16A`   | wPartyMon1        | Mew data (44 bytes)                  |
| `0xD196`   | wPartyMon2        | Magikarp data (44 bytes)             |
| `0xD272`   | wPartyMonOT       | Original Trainer names               |
| `0xD2B8`   | wPartyMonNicks    | Pokemon nicknames                    |
| `0xD31C`   | wNumBagItems      | Inventory item count                 |
| `0xD31D`   | wBagItems         | Item ID/quantity pairs               |
| `0xD347`   | wPlayerMoney      | Money (3 bytes, BCD encoded)         |
| `0xD3AD`   | wNumberOfWarps    | Warp count for current map           |
| `0xD3AE`   | wWarpEntries      | Warp destinations (Y, X, id, map)    |

### Techniques Demonstrated

1. **Inventory Structure Manipulation** -- Extending Gen 1's item list format with proper terminator management
2. **Full Pokemon Data Construction** -- Building two 44-byte party Pokemon from scratch with calculated stats using the Gen 1 formula
3. **BCD Money Encoding** -- Setting max currency using Binary-Coded Decimal
4. **Warp Table Hijacking** -- Redirecting map transitions by overwriting WRAM warp destinations (used twice: to Pokemon Center, then back home)
5. **Direct VRAM Text Injection** -- Writing character-encoded glyphs to the tile map for custom dialog rendering (two separate injections)
6. **Input Counter Bypass** -- Clearing the ignore_input counter to enable movement during scripted sequences
7. **ASCII Map Rendering** -- Real-time spatial analysis using blockset data, collision tables, and sprite positions
8. **Save State Management** -- Capturing and exporting emulator states at key story moments

---

## Epilogue

What started as a trip to mama's PC ended with Ashtray:

- Stealing a Potion from the bedroom PC (sorry mama)
- Duplicating it 99 times (not sorry)
- Conjuring 99 Master Balls from thin air
- Becoming hood rich with $999,999
- Rolling with a Level 100 Mew packing Psychic, Thunderbolt, Ice Beam, and Earthquake
- Keeping a fat Level 100 Magikarp for emotional support
- Warping from the bedroom to Pewter Pokemon Center by rewriting the game's warp table
- Making Nurse Joy say "DONT BE A MENACE / WHILE DRINKIN OJ"
- Making her follow up with "IM JUST TRYNA / FIND MY DADDY"
- Warping home to Pallet Town through the same trick in reverse
- Standing outside mama's front door like nothing happened

All through the Model Context Protocol. All through memory reads and
writes. All in a single session.

The SameBoy MCP Server turns a Game Boy emulator into a programmable
sandbox where AI agents can observe, analyze, and manipulate game state
at the deepest level. It is reverse engineering as a service, game
hacking as a tool call, and the most fun you can have with 8-bit
hardware memory without catching a case.

**Message.**

---

*Built for COSC 69.16 at Dartmouth College, Winter 2026.*
*Powered by SameBoy, the Model Context Protocol, and sheer audacity.*
*No Magikarp were harmed in the making of this adventure. He knew what he signed up for.*
