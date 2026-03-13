# PokeBot Integration Design

**Date**: 2026-03-13
**Status**: Draft
**Branch**: `pokebot-integration`

## Overview

Port useful patterns from PokeBot (a Lua-based Pokemon Yellow speedrunner for BizHawk) into the SameBoy MCP Pokemon Yellow agent. Three features plus an MCP tool optimization pass to reduce redundant round-trips.

## Feature 1: Waypoint Route Database

### Problem

`navigate_route()` does map-level BFS via `MAP_GRAPH`, then per-map BFS pathfinding via `render_ascii_map` + collision maps. Each map hop requires: render ASCII map, parse collision map, BFS, walk step-by-step with state reads. For well-known routes (e.g., Pallet Town to Viridian City), this is wasteful — the same path is recomputed every time.

### Solution

New module `examples/pokemon_agent/pokebot_paths.py` containing waypoint data extracted from PokeBot's `data/yellow/paths.lua` (439 entries).

**Data structure:**

```python
# map_id -> list of known waypoint sequences
# Each sequence: [(x1,y1), (x2,y2), ...] from start to exit
WAYPOINTS: dict[int, list[WaypointPath]] = {
    38: [WaypointPath(dest_map=37, points=[(3,6), (5,6), (5,1), (7,1)])],  # House 2F -> stairs
    39: [WaypointPath(dest_map=0, points=[(7,1), (7,6), (3,6), (3,8)])],   # House 1F -> outside
    0:  [WaypointPath(dest_map=12, points=[(5,6), (10,6), (10,0)])],        # Pallet -> Route 1
    ...
}

@dataclass
class WaypointPath:
    dest_map: int           # Target map ID this path leads to
    points: list[tuple[int, int]]  # Waypoint coordinates in order
```

**Conversion details:**

The `paths.lua` file contains 439 entries with interleaved strategy commands (`{s="fightBrock"}`, `{c="a",a="Route 3"}`) alongside coordinate waypoints (`{x, y}`). During conversion:

1. **Strip non-coordinate entries**: Filter out `{s=...}` strategy and `{c=...}` control entries, keeping only `{x, y}` tuples.
2. **Split on interactions**: Paths containing mid-path interactions (`{s="interact",dir="Up"}`) are split into separate `WaypointPath` segments at each interaction point. The segment before the interaction and the segment after become independent waypoint paths.
3. **Infer `dest_map`**: For each path entry at index `i`, `dest_map` is the `map_id` of entry `i+1`. The last entry's `dest_map` is set to the Hall of Fame map (or omitted).
4. **Deduplicate**: When the same `(map_id, dest_map)` pair appears multiple times (e.g., Pallet Town map 0 is visited at different progression points), keep only the first pure-navigation path. Strategy-dependent paths (those that were split due to interactions) are excluded from the default database.
5. **Validate starting coordinate**: On first use of a waypoint path, verify the player's current position is within 2 tiles of the path's first waypoint. If not, fall back to BFS.

Estimated ~200-250 of the 439 entries survive filtering as pure navigation waypoints.

**Integration into `routines.py`:**

`navigate_route()` gains `use_waypoints=True`. Before doing BFS within a map, check `WAYPOINTS[current_map_id]` for a path whose `dest_map` matches the next hop. If found, walk the waypoints directly — skip `render_ascii_map`, skip collision map parsing, skip BFS. If a waypoint is blocked (walk returns False), invalidate and fall back to existing BFS.

### MCP Tool Savings

- **Eliminates per-hop**: `render_ascii_map` (expensive — reads ROM blockset, builds grid) + `read_memory` calls for collision data
- **Reduces to**: Direct `walk()` calls using cached waypoints
- For a 5-map route, saves ~10-15 MCP tool calls

## Feature 2: Textbox Detection Signal (wFontLoaded)

### Problem

Dialog detection uses `wStatusFlags5` bit 5 (0xD72F) as primary signal, with screen tile analysis as fallback. PokeBot uses `wFontLoaded` at `0xCFC3` — bit 0 is set when the text/font system is loaded (textbox active). Adding this gives a second independent signal for more reliable detection.

### Address derivation

PokeBot's `memory.lua` reads address `0x0FC4` (BizHawk WRAM offset), but applies a Yellow-specific adjustment of `-1` for addresses in the `0x0F12-0x1F00` range, making the actual BizHawk read `0x0FC3`. The absolute Game Boy address is `0xC000 + 0x0FC3 = 0xCFC3`, which corresponds to `wFontLoaded` in the pret/pokeyellow disassembly.

**Note**: `memory_map.py` currently has a duplicate definition `WRAM_TEXTBOX_FLAG = 0xCFC4` / `WRAM_WALK_COUNTER = 0xCFC4` at the neighboring byte. This should be cleaned up.

### Solution

**In `memory_map.py`:**

```python
WRAM_FONT_LOADED = 0xCFC3   # wFontLoaded — bit 0 set when textbox/font system active
# Clean up: remove or rename the duplicate WRAM_TEXTBOX_FLAG = 0xCFC4
```

**In `game_state.py`:**

Add `font_loaded: bool` to `GameState` dataclass. Read bit 0 of `0xCFC3` in `read_state()` alongside existing reads. Use it in `_detect_mode()`:

```python
# Current: only wStatusFlags5 bit 5
# New: font_loaded OR joypad_disabled -> DIALOG candidate
if font_loaded or joypad_disabled:
    # Then differentiate DIALOG vs MENU via screen analysis
```

This is a single `read_memory` call bundled with the existing batch reads — no extra MCP round-trip.

### MCP Tool Savings

- **Zero additional calls** — piggyback on existing `read_memory` batch
- **Reduces false negatives** in dialog detection, preventing wasted recovery attempts

## Feature 3: Scripted Strategy Routines

### Problem

Common game interactions (healing at Pokecenter, buying items, using PC) require many MCP tool calls when driven by LLM decision-making: read screen text, navigate menu, press A, read again, navigate again, etc. Each step is a separate tool call the LLM orchestrates.

### Solution

New module `examples/pokemon_agent/scripted_strategies.py` with deterministic async routines that batch common interaction sequences. These compose `Routines` methods internally.

**Routines:**

```python
async def heal_at_pokecenter(routines: Routines) -> bool:
    """Walk to nurse counter, interact, wait for heal, exit dialog.

    Preconditions:
    - Player must be on a Pokecenter map (verified via POKECENTER_MAP_IDS)
    - If not on a Pokecenter map, returns False immediately

    Error handling:
    - Wild encounter during navigation: wait for battle to end, retry
    - Dialog stuck: press B up to 10 times to force exit
    """
    # 1. Verify on pokecenter map
    # 2. Navigate to nurse counter tile (hardcoded per-pokecenter or entity_points["C"])
    # 3. Face up, press A
    # 4. Advance text (press A x3-4 for heal dialog)
    # 5. Wait ~120 frames for heal jingle
    # 6. Press B to exit dialog
    # Returns True on success

async def buy_items(routines: Routines, shopping_list: list[tuple[str, int]]) -> bool:
    """Buy items from mart clerk.

    Preconditions:
    - Player must be on a Mart map or facing a shop clerk
    - shopping_list: list of (item_name, quantity) tuples

    Error handling:
    - Item not in stock: skip and continue with remaining items
    - Insufficient funds: abort remaining purchases, return False
    """
    # 1. Navigate to counter, face up, press A
    # 2. Select BUY
    # 3. For each (item_name, qty): navigate to item, set quantity, confirm
    # 4. Exit shop menu
    # Returns True on success

async def use_pc_withdraw(routines: Routines, item_name: str, qty: int = 1) -> bool:
    """Withdraw item from PC.

    Preconditions:
    - Player must be adjacent to and facing a PC
    """
    # 1. Press A to interact with PC
    # 2. Select WITHDRAW ITEM
    # 3. Navigate to item, set quantity, confirm
    # 4. LOG OFF

async def use_pc_deposit(routines: Routines, item_name: str, qty: int = 1) -> bool:
    """Deposit item to PC."""
    # Same pattern as withdraw but DEPOSIT ITEM

async def fly_to(routines: Routines, dest_name: str) -> bool:
    """Use Fly to travel to a known city.

    Preconditions:
    - A party Pokemon must know Fly
    - Player must be in overworld (not indoors)

    Error handling:
    - No Pokemon knows Fly: return False
    - Indoors: return False
    """
    # 1. Open START menu
    # 2. Navigate to POKEMON
    # 3. Select Pokemon with Fly
    # 4. Select FLY
    # 5. Navigate to destination city
    # 6. Confirm
```

**Key design principles:**

- Each routine **checks preconditions** before proceeding and returns False if unmet
- Uses `press_and_read` (combined press+wait+decode) instead of separate press/wait/decode calls
- Reads state only when needed (after expected transitions), not every step
- Returns bool success/failure so caller can decide on fallback
- No LLM involvement — pure coded logic

### MCP Tool Savings

A pokecenter heal via LLM typically takes 8-12 tool calls (navigate, read, press A, read, press A, read, press B, read...). The scripted routine does it in 4-5 calls by:
- Using `press_and_read` (1 call = press + wait + decode, vs 3 separate)
- Skipping redundant state reads between known-deterministic menu steps
- Batching navigation via waypoints when available

## Feature 4: MCP Tool Call Optimization

### Problem

The current flow makes many redundant MCP calls:
1. `render_ascii_map` called on every pathfinding attempt (even if map hasn't changed)
2. `decode_screen_text` called separately from `press_and_read` (which already decodes)
3. `read_memory` called for individual addresses when batch reads are possible
4. State reads repeated between sequential operations that don't change game state

### Solution

**4a. Collision map cache with TTL:**

`_get_collision_map()` already caches by map_id. Strengthen this:
- Cache remains valid until `map_id` changes OR a warp/border crossing occurs
- Add `_cache_frame` tracking — skip re-render if within 60 frames and no movement
- Waypoint paths (Feature 1) bypass this entirely

**4b. Batch memory reads in `read_state()`:**

Current `read_state()` makes 25+ separate `read_memory` calls (92 total `_read` calls in game_state.py, many conditional). The addresses span non-contiguous ranges from 0xC100 to 0xFFD5. Consolidate into ~6 reads of contiguous clusters:

```python
# Cluster 1: Menu state (0xCC24-0xCC52, ~0x30 bytes)
# Cluster 2: Battle flags (0xD056-0xD06F, ~0x20 bytes)
# Cluster 3: Game state (0xD119-0xD16B, ~0x50 bytes)
# Cluster 4: Money/badges/position (0xD346-0xD36F, ~0x30 bytes)
# Cluster 5: Direction/tileset (0xD529-0xD534, ~0x0C bytes)
# Cluster 6: Status flags (0xD72D-0xD731, 5 bytes)
```

Then parse individual values from the byte arrays. Realistic savings: ~6 reads instead of 25+ for the core overworld path. Conditional reads (party data, battle data) remain separate since they're only needed in specific modes.

**4c. `press_and_read` as primary interaction tool:**

Audit all places where `press_key` + `run_frames` + `decode_screen_text` are called separately. Replace with single `press_and_read` call. Already partially done but not consistent.

**4d. Skip redundant `decode_screen_text` after `press_and_read`:**

`press_and_read` returns decoded text. Store it on `Routines` as `_last_screen_text` with a frame counter. Invalidate on any input (press, walk, run_frames) or when frame counter advances beyond a threshold (30 frames). Subsequent checks use cached text if still valid.

## File Changes Summary

| File | Change |
|------|--------|
| `examples/pokemon_agent/pokebot_paths.py` | **New** — Waypoint database from paths.lua |
| `examples/pokemon_agent/scripted_strategies.py` | **New** — Pokecenter, shop, PC, fly routines |
| `examples/pokemon_agent/routines.py` | Waypoint lookup in `navigate_route()`, cache optimization, `_last_screen_text` |
| `examples/pokemon_agent/game_state.py` | `font_loaded` field, `0xCFC3` read, batch memory reads |
| `examples/pokemon_agent/memory_map.py` | `WRAM_FONT_LOADED = 0xCFC3`, clean up duplicate `WRAM_TEXTBOX_FLAG` |
| `examples/pokemon_agent/pokemon_data.py` | No changes (MAP_GRAPH stays as-is) |
| `examples/pokemon_agent/pathfinding.py` | No changes |
| `examples/pokemon_agent/mcp_plugin.py` | No changes |

## Testing

- **Waypoint validation**: Load `after_pokedex_pallet_town.sav` state, run `navigate_route()` from Pallet Town to Viridian City with `use_waypoints=True`. Verify player arrives. Compare MCP tool call count with waypoints off vs on.
- **Textbox detection**: Load `find_my_daddy.sav` (pokecenter dialog), verify `font_loaded=True`. Load `after_pokedex_pallet_town.sav` (overworld), verify `font_loaded=False`. Test transitions between states.
- **Scripted strategies**: Load `viridian_pokecenter.sav`, run `heal_at_pokecenter()`, verify party HP restored. Load a mart save state (or navigate to one), run `buy_items()`.
- **Batch reads**: Measure `read_memory` call count in `read_state()` before and after optimization. Target: 6-8 calls down from 25+.

## Out of Scope

- PokeBot's combat AI (damage calculation, move selection) — our agent uses LLM for battle decisions
- PokeBot's DSum manipulation and RNG control
- PokeBot's streaming/Twitch integration
- Full speedrun route automation
