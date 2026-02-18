# Where Am I Bro: Navigating and Reading Signs

A walkthrough of using MCP tools to determine the player's location, navigate to a sign, and read it -- all from memory.

## Starting State

The player just exited the PC in Player House 2F, walked downstairs, and left the house. They're now standing in Pallet Town.

## Step 1: Read Player Position

Three WRAM addresses give us the player's exact location:

```
read_memory(address=0xD35D, length=1)   → map_id = 0 (Pallet Town)
read_memory(address=0xD360, length=1)   → y = 6
read_memory(address=0xD361, length=1)   → x = 3
```

Player is at tile **(3, 6)** on map 0 (Pallet Town).

## Step 2: Find the Sign Location

The pret/pokeyellow disassembly defines all background events (signs, bookshelves, etc.) per map. From `pokeyellow/data/maps/objects/PalletTown.asm`:

```asm
def_bg_events
bg_event 13, 13, TEXT_PALLETTOWN_OAKSLAB_SIGN
bg_event  7,  9, TEXT_PALLETTOWN_SIGN
bg_event  3,  5, TEXT_PALLETTOWN_PLAYERSHOUSE_SIGN
bg_event 11,  5, TEXT_PALLETTOWN_RIVALSHOUSE_SIGN
```

The player's house sign is at **(3, 5)**. The player is at **(3, 6)** -- directly below the sign. No movement needed, just face up and interact.

### Pallet Town Sign Layout

```
     x=3       x=7      x=11     x=13
      │         │         │         │
y=5 ──┤ HOUSE   │         ┤ RIVAL   │
      │ SIGN    │         │ SIGN    │
      │         │         │         │
y=9 ──┤         ┤ TOWN    │         │
      │         │ SIGN    │         │
      │         │         │         │
y=11──┤         │         │         │
      │         │         │         │
y=13──┤         │         │         ┤ LAB
      │         │         │         │ SIGN
```

## Step 3: Face the Sign and Press A

```
press_key(key="up", frames=5)    # Face up toward the sign
run_frames(count=10)             # Let animation settle
press_key(key="a", frames=10)    # Interact
run_frames(count=60)             # Wait for text box to appear
```

## Step 4: Read the Sign Text

```
decode_screen_text()
```

```json
{
  "rows": [
    "...",
    "┌──────────────────┐",
    "│                  │",
    "│ASH's house       │",
    "│                  │",
    "│                  │",
    "└──────────────────┘"
  ],
  "text_lines": [
    "ASH's house"
  ]
}
```

The sign reads **"ASH's house"** (ASH being the player's chosen name).

The contraction "'s" is a single tile (`0xBD`) in the Gen 1 character encoding, decoded correctly by the `GEN1_CHAR_ENCODING` table in the MCP server.

## Step 5: Dismiss and Re-enable Input

```
press_key(key="a", frames=10)    # Dismiss text box
run_frames(count=30)
set_user_input(enabled=true)     # Give control back to the user
```

## Key Addresses Used

| Address | Name | Value | Meaning |
|---------|------|-------|---------|
| `0xD35D` | `WRAM_CUR_MAP` | `0x00` | Pallet Town |
| `0xD360` | `WRAM_Y_COORD` | `0x06` | Player Y position |
| `0xD361` | `WRAM_X_COORD` | `0x03` | Player X position |
| `0xC3A0` | `WRAM_TILE_MAP` | 360 bytes | Screen tile map for text decoding |

## Finding Signs Programmatically

Signs are `bg_event` entries in the ROM's map object data. To find them at runtime:

1. **Read the map ID** from `0xD35D`
2. **Look up the map's object data** in the pret disassembly (`data/maps/objects/<MapName>.asm`)
3. **Find `bg_event` entries** -- format is `bg_event X, Y, TEXT_ID`
4. **Navigate to (X, Y±1)** -- stand adjacent to the sign tile
5. **Face the sign and press A**
6. **Read the result** with `decode_screen_text()`

All four Pallet Town signs:

| Position | Text ID | Content |
|----------|---------|---------|
| (3, 5) | `TEXT_PALLETTOWN_PLAYERSHOUSE_SIGN` | "ASH's house" |
| (11, 5) | `TEXT_PALLETTOWN_RIVALSHOUSE_SIGN` | "GARY's house" |
| (7, 9) | `TEXT_PALLETTOWN_SIGN` | "PALLET TOWN - Shades of your journey await!" |
| (13, 13) | `TEXT_PALLETTOWN_OAKSLAB_SIGN` | "OAK POKéMON RESEARCH LAB" |
