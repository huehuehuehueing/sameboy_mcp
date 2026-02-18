# Grab Da Potion: A Complete MCP Workflow Example

This document walks through a real interaction where an AI agent withdraws a Potion from the player's PC in Pokemon Yellow using only MCP tools and RAM vision -- no screenshot analysis, no vision model, just memory reads and button presses.

## Starting State

The player is in Player House 2F (map 38) standing at the PC, which is already open. The PC contains 1 Potion. The bag is empty.

State was loaded from a save file:

```
import_state(file_path="examples/pokemon_agent/saved_states/pc_menu.sav", name="pc_menu")
load_state(state_id="1cd7fd01")
```

## Step 1: Read the Screen

First, confirm what's on screen using `decode_screen_text`:

```
decode_screen_text()
```

```json
{
  "rows": [
    "┌──────────────┐    ",
    "│              │    ",
    "│▶WITHDRAW ITEM│    ",
    "│              │    ",
    "│ DEPOSIT ITEM │  ",
    "│              │  ",
    "│ TOSS ITEM    │    ",
    "│              │    ",
    "│ LOG OFF      │    ",
    "└──────────────┘    ",
    "                    ",
    "                    ",
    "┌──────────────────┐",
    "│                  │",
    "│What do you want  │",
    "│                  │",
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

Two text boxes are visible:
- **Top**: PC menu with 4 options. The `▶` cursor (tile `0xED`) is on WITHDRAW ITEM.
- **Bottom**: Dialog prompt "What do you want to do?"

## Step 2: Disable User Input

Before automating inputs, block the keyboard so the user doesn't interfere:

```
set_user_input(enabled=false)
```

## Step 3: Select WITHDRAW ITEM

The cursor is already on WITHDRAW ITEM. Press A to select it:

```
press_key(key="a", frames=10)
run_frames(count=30)
```

Read the screen to confirm:

```
decode_screen_text()
```

```json
{
  "text_lines": [
    "▷WI",
    "DE▶POTION",
    "× 1",
    "TO CANCEL",
    "LO",
    "What do you want",
    "to withdraw?"
  ]
}
```

A new item list appeared overlaying the PC menu. The `▶` cursor is on **POTION** (× 1). The dialog now reads "What do you want to withdraw?"

Full screen layout shows the overlapping boxes:

```
┌──────────────┐
│▷WI┌──────────────┐
│   │              │
│ DE│▶POTION       │
│   │         × 1  │
│ TO│ CANCEL       │
│   └──────────────┘
└───
┌──────────────────┐
│What do you want  │
│to withdraw?      │
└──────────────────┘
```

Note: The original PC menu is partially visible behind the item list (WI=WITHDRAW, DE=DEPOSIT, TO=TOSS, LO=LOG OFF). The `▷` (tile `0xEC`, hollow triangle) marks the previously selected menu item, while `▶` (tile `0xED`, filled triangle) marks the active cursor.

## Step 4: Select the Potion

Cursor is on POTION. Press A:

```
press_key(key="a", frames=10)
run_frames(count=30)
```

```
decode_screen_text()
```

```json
{
  "text_lines": [
    "▷WI",
    "DE▷POTION",
    "× 1",
    "TO CANCEL",
    "LO",
    "×01",
    "How many?"
  ]
}
```

The game asks "How many?" with a quantity selector showing `×01`. Only 1 Potion is available, so the quantity is already correct.

## Step 5: Confirm Quantity

Press A to confirm withdrawing 1 Potion:

```
press_key(key="a", frames=10)
run_frames(count=60)
```

```
decode_screen_text()
```

```json
{
  "text_lines": [
    "▷WI",
    "DE▷POTION",
    "× 1",
    "TO CANCEL",
    "LO",
    "×01",
    "Withdrew",
    "POTION.          ▼"
  ]
}
```

The dialog now reads **"Withdrew POTION."** with a `▼` indicator (tile `0xEE`) meaning there's more text or the game is waiting for input.

## Step 6: Dismiss the Confirmation

Press A to advance past the message:

```
press_key(key="a", frames=10)
run_frames(count=30)
```

```
decode_screen_text()
```

```json
{
  "text_lines": [
    "DE▶CANCEL",
    "What do you want",
    "to withdraw?"
  ]
}
```

The item list now only shows **CANCEL** -- the Potion is gone from PC storage. It's in the bag now.

## Step 7: Exit the PC

Press B to back out of the withdraw list:

```
press_key(key="b", frames=10)
run_frames(count=30)
```

Back at the main PC menu. Navigate to LOG OFF (3 presses down from WITHDRAW ITEM):

```
press_key(key="down", frames=10)
press_key(key="down", frames=10)
press_key(key="down", frames=10)
run_frames(count=10)
```

Confirm cursor position:

```
decode_screen_text()
```

```json
{
  "text_lines": [
    "WITHDRAW ITEM",
    "DEPOSIT ITEM",
    "TOSS ITEM",
    "▶LOG OFF",
    "What do you want",
    "to do?"
  ]
}
```

Cursor is on LOG OFF. Press A to exit:

```
press_key(key="a", frames=10)
run_frames(count=30)
```

```
decode_screen_text()
```

```json
{
  "text_lines": []
}
```

Empty text lines -- the PC menu is closed. We're back in the overworld.

## Step 8: Re-enable User Input

```
set_user_input(enabled=true)
```

## Summary

The complete sequence was:

| Step | Action | Screen Response |
|------|--------|----------------|
| 1 | Read screen | PC menu, cursor on WITHDRAW ITEM |
| 2 | Disable user input | -- |
| 3 | Press A | Item list appears, cursor on POTION |
| 4 | Press A | "How many?" prompt, ×01 |
| 5 | Press A | "Withdrew POTION." confirmation |
| 6 | Press A | Item list shows only CANCEL |
| 7 | Press B, Down×3, A | LOG OFF selected, PC closes |
| 8 | Re-enable user input | -- |

**Total button presses:** 8 (A×5, B×1, Down×3... wait, that's 9)
**Total frames advanced:** ~230 (~3.8 seconds of game time)
**Vision model calls:** 0
**RAM reads:** 7 (one `decode_screen_text` per decision point)

## Key Observations

1. **RAM vision was sufficient for the entire interaction.** No screenshots or vision models were needed. Every decision was made by reading text from the tile map.

2. **The `▶` cursor tile (`0xED`) is the primary UI signal.** It tells the agent exactly which menu item is selected without pixel-level analysis.

3. **The `▼` indicator (`0xEE`) means "press A to continue."** This is a reliable signal that the game is waiting for input to advance dialog.

4. **Overlapping text boxes are readable.** Even when the item list overlays the PC menu, both are present in the tile map. The partial text from the background menu (WI, DE, TO, LO) is visible alongside the foreground list.

5. **The `▷`/`▶` distinction matters.** Hollow triangle (`0xEC`, `▷`) marks a previously selected item; filled triangle (`0xED`, `▶`) marks the active cursor. This lets the agent distinguish active from inactive selections.

6. **Frame timing is generous.** 10 frames for a button press + 30 frames of wait is more than enough for menu transitions. The Game Boy runs at ~60 fps, so 30 frames is half a second.
