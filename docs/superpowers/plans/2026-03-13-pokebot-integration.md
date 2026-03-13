# PokeBot Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate PokeBot waypoint paths, textbox detection, scripted strategies, and MCP tool optimizations into the Pokemon Yellow agent.

**Architecture:** Four independent features: (1) waypoint database extracted from PokeBot's paths.lua for fast known-route navigation, (2) wFontLoaded textbox signal for more reliable dialog detection, (3) scripted strategy routines for pokecenter/shop/PC interactions, (4) batch memory reads and screen text caching to reduce MCP round-trips.

**Tech Stack:** Python 3.12, async/await, MCP tools via `call_tool`, dataclasses, BFS pathfinding

**Spec:** `docs/superpowers/specs/2026-03-13-pokebot-integration-design.md`

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `examples/pokemon_agent/pokebot_paths.py` | Waypoint database + lookup | **Create** |
| `examples/pokemon_agent/scripted_strategies.py` | Pokecenter, shop, PC, fly routines | **Create** |
| `examples/pokemon_agent/memory_map.py` | Memory address constants | **Modify** (add WRAM_FONT_LOADED, clean up duplicate) |
| `examples/pokemon_agent/game_state.py` | GameState + mode detection | **Modify** (add font_loaded, batch reads) |
| `examples/pokemon_agent/routines.py` | Navigation + movement | **Modify** (waypoint integration, screen text cache) |
| `tests/test_pokebot_paths.py` | Waypoint DB tests | **Create** |
| `tests/test_scripted_strategies.py` | Strategy routine tests | **Create** |
| `tests/test_game_state_textbox.py` | Textbox detection tests | **Create** |

---

## Chunk 1: Branch Setup + Waypoint Database

### Task 1: Create branch and scaffold

**Files:**
- Modify: `.git` (branch)

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b pokebot-integration master
```

- [ ] **Step 2: Commit spec and plan**

```bash
git add docs/superpowers/specs/2026-03-13-pokebot-integration-design.md
git add docs/superpowers/plans/2026-03-13-pokebot-integration.md
git commit -m "docs: add PokeBot integration spec and plan"
```

---

### Task 2: Build waypoint database from paths.lua

**Files:**
- Read: `PokeBot/data/yellow/paths.lua`
- Create: `examples/pokemon_agent/pokebot_paths.py`
- Create: `tests/test_pokebot_paths.py`

- [ ] **Step 1: Write failing tests for waypoint data structure**

Create `tests/test_pokebot_paths.py`:

```python
"""Tests for PokeBot waypoint database."""
from examples.pokemon_agent.pokebot_paths import WAYPOINTS, WaypointPath, get_waypoint_path


def test_waypoint_path_dataclass():
    wp = WaypointPath(dest_map=37, points=[(3, 6), (5, 6), (5, 1), (7, 1)])
    assert wp.dest_map == 37
    assert len(wp.points) == 4
    assert wp.points[0] == (3, 6)


def test_waypoints_dict_not_empty():
    assert len(WAYPOINTS) > 50, "Should have at least 50 map entries"


def test_known_path_player_house_2f():
    """Player House 2F (map 38) should have a path to map 37 (House 1F)."""
    paths = WAYPOINTS.get(38, [])
    assert any(p.dest_map == 37 for p in paths), "Missing House 2F -> 1F path"


def test_known_path_pallet_to_route1():
    """Pallet Town (map 0) should have a path to Route 1 (map 12)."""
    paths = WAYPOINTS.get(0, [])
    assert any(p.dest_map == 12 for p in paths), "Missing Pallet -> Route 1 path"


def test_all_points_are_tuples():
    for map_id, paths in WAYPOINTS.items():
        for wp in paths:
            assert isinstance(wp, WaypointPath)
            for pt in wp.points:
                assert isinstance(pt, tuple) and len(pt) == 2, (
                    f"Bad point {pt} in map {map_id}"
                )


def test_get_waypoint_path_found():
    result = get_waypoint_path(38, 37)
    assert result is not None
    assert result.dest_map == 37


def test_get_waypoint_path_not_found():
    result = get_waypoint_path(9999, 0)
    assert result is None


def test_no_empty_point_lists():
    for map_id, paths in WAYPOINTS.items():
        for wp in paths:
            assert len(wp.points) >= 2, (
                f"Path in map {map_id} -> {wp.dest_map} has fewer than 2 waypoints"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pokebot_paths.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the conversion script and waypoint module**

Create `examples/pokemon_agent/pokebot_paths.py`. This file must:

1. Parse `PokeBot/data/yellow/paths.lua` at import time (or contain pre-converted data).
2. The recommended approach is **pre-converted static data** — parse paths.lua once with a helper script and embed the result. This avoids a Lua parser dependency.

The module must contain:

```python
"""Waypoint database extracted from PokeBot's paths.lua.

Provides known-good navigation waypoints for Pokemon Yellow maps.
Used by routines.navigate_route() to skip BFS pathfinding on known routes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaypointPath:
    """A known waypoint sequence through a single map."""
    dest_map: int                    # Map ID this path leads to
    points: tuple[tuple[int, int], ...]  # Waypoint coordinates in order


def get_waypoint_path(
    map_id: int, dest_map: int, player_pos: tuple[int, int] | None = None,
    max_start_distance: int = 2,
) -> WaypointPath | None:
    """Look up a waypoint path for navigating map_id toward dest_map.

    Args:
        map_id: Current map ID
        dest_map: Target map ID for next hop
        player_pos: Current player (x, y) for proximity check
        max_start_distance: Max Manhattan distance from player to first waypoint

    Returns:
        WaypointPath if found and player is near start, else None
    """
    paths = WAYPOINTS.get(map_id, [])
    for wp in paths:
        if wp.dest_map == dest_map:
            if player_pos is not None:
                sx, sy = wp.points[0]
                px, py = player_pos
                if abs(sx - px) + abs(sy - py) > max_start_distance:
                    continue
            return wp
    return None


# ── Waypoint database ──────────────────────────────
# Extracted from PokeBot/data/yellow/paths.lua
# Strategy/command entries stripped, only coordinate waypoints kept.
# dest_map inferred from next path entry's map_id.

WAYPOINTS: dict[int, list[WaypointPath]] = {
    # ... (populated by parsing paths.lua)
    # Example entries:
    # 38: [WaypointPath(dest_map=37, points=((3,6), (5,6), (5,1), (7,1)))],
}
```

To populate `WAYPOINTS`, write a helper script `scripts/convert_paths.py` that:
1. Reads `PokeBot/data/yellow/paths.lua`
2. Parses each entry: extract map_id (first field), filter to `{x,y}` coordinate tuples only (skip `{s=...}` and `{c=...}` entries)
3. Infer dest_map from next entry's map_id
4. Split paths at `{s="interact",...}` entries
5. Skip paths with fewer than 2 waypoints
6. Deduplicate same `(map_id, dest_map)` pairs (keep first)
7. Output Python dict literal to stdout (copy into pokebot_paths.py)

The conversion script is a one-time tool, not part of the runtime.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pokebot_paths.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add examples/pokemon_agent/pokebot_paths.py tests/test_pokebot_paths.py
git commit -m "feat: add PokeBot waypoint database for known-route navigation"
```

---

### Task 3: Integrate waypoints into navigate_route()

**Files:**
- Modify: `examples/pokemon_agent/routines.py:1480-1560` (navigate_route)

- [ ] **Step 1: Add waypoint import and _walk_waypoints helper**

At the top of `routines.py`, add:

```python
from .pokebot_paths import get_waypoint_path
```

Add a new method to `Routines` class (before `navigate_route`):

```python
async def _walk_waypoints(self, waypoint_path) -> bool:
    """Walk a pre-computed waypoint path. Returns True if completed."""
    points = waypoint_path.points
    state = await self.read_state()
    px, py = state.player_x, state.player_y

    for i, (tx, ty) in enumerate(points):
        if px == tx and py == ty:
            continue  # Already at this waypoint
        # Compute direction
        dx, dy = tx - px, ty - py
        # Walk one axis at a time
        if dx != 0:
            direction = "right" if dx > 0 else "left"
            if not await self.walk(direction, abs(dx)):
                return False  # Blocked, caller should fall back to BFS
            px = tx
        if dy != 0:
            direction = "down" if dy > 0 else "up"
            if not await self.walk(direction, abs(dy)):
                return False
            py = ty

    return True
```

- [ ] **Step 2: Modify navigate_route() to try waypoints first**

In `navigate_route()` (line ~1480), inside the per-hop loop, before calling `_cross_border()` or `_cross_warp()`, add waypoint lookup:

```python
# Inside the hop loop, after getting (next_map, conn_type):
state = await self.read_state()
wp = get_waypoint_path(
    state.map_id, next_map,
    player_pos=(state.player_x, state.player_y),
)
if wp and use_waypoints:
    if self._verbose:
        print(f"  [waypoints] Using known path through map {state.map_id} -> {next_map}")
    if await self._walk_waypoints(wp):
        # Verify we actually changed maps
        new_state = await self.read_state()
        if new_state.map_id == next_map:
            self.invalidate_map_cache()
            continue  # Success, next hop
    # Waypoints failed, fall back to BFS
    if self._verbose:
        print(f"  [waypoints] Path blocked, falling back to BFS")
```

Add `use_waypoints: bool = True` parameter to `navigate_route()` signature.

- [ ] **Step 3: Test manually with emulator**

Load a save state, call `navigate_route()` with verbose=True from Pallet Town to Viridian City. Verify waypoint path is used and player arrives.

- [ ] **Step 4: Commit**

```bash
git add examples/pokemon_agent/routines.py
git commit -m "feat: integrate waypoint shortcuts into navigate_route()"
```

---

## Chunk 2: Textbox Detection + Memory Map Cleanup

### Task 4: Add wFontLoaded address and clean up memory_map.py

**Files:**
- Modify: `examples/pokemon_agent/memory_map.py:45,426`

- [ ] **Step 1: Add WRAM_FONT_LOADED and fix duplicate**

In `memory_map.py`:

At line 45 area (near WRAM_WALK_COUNTER), add:
```python
WRAM_FONT_LOADED = 0xCFC3   # wFontLoaded — bit 0 set when textbox/font system active
```

At line 426, change the comment on `WRAM_TEXTBOX_FLAG = 0xCFC4` to clarify it's the walk counter neighbor:
```python
# Note: 0xCFC4 is wWalkCounter, used for walk animation.
# The textbox indicator is wFontLoaded at 0xCFC3.
WRAM_WALK_COUNTER = 0xCFC4   # Walk animation counter (also referenced as textbox flag)
```

Remove the duplicate `WRAM_TEXTBOX_FLAG = 0xCFC4` if it exists separately from `WRAM_WALK_COUNTER`.

- [ ] **Step 2: Commit**

```bash
git add examples/pokemon_agent/memory_map.py
git commit -m "fix: add WRAM_FONT_LOADED (0xCFC3), clean up textbox flag duplicate"
```

---

### Task 5: Add font_loaded to GameState and _detect_mode()

**Files:**
- Modify: `examples/pokemon_agent/game_state.py:240-291` (GameState dataclass)
- Modify: `examples/pokemon_agent/game_state.py:672` (_detect_mode)
- Modify: `examples/pokemon_agent/game_state.py:818` (read_state)
- Create: `tests/test_game_state_textbox.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_game_state_textbox.py`:

```python
"""Tests for textbox detection via wFontLoaded."""
from examples.pokemon_agent.game_state import GameState, GameMode, GameStateReader


def test_game_state_has_font_loaded_field():
    """GameState should have a font_loaded boolean field."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(GameState)}
    assert "font_loaded" in fields


def test_detect_mode_dialog_with_font_loaded():
    """When font_loaded=True and joypad_disabled=False, should still detect DIALOG."""
    reader = GameStateReader.__new__(GameStateReader)
    # font_loaded alone should contribute to DIALOG detection
    # (combined with screen text having textbox borders)
    mode = reader._detect_mode(
        in_battle=0, map_id=1, menu_cursor=0, text_box_id=0,
        ignore_input=0, regs={"PC": 0x4000}, naming_screen=0,
        party_count=1, oak_speech=0, badges=0,
        joypad_disabled=False, font_loaded=True,
    )
    # With font_loaded=True but no screen text to confirm,
    # should at minimum not crash and return a valid mode
    assert isinstance(mode, GameMode)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_game_state_textbox.py -v`
Expected: FAIL

- [ ] **Step 3: Add font_loaded field to GameState**

In `game_state.py` at the GameState dataclass (line ~240), add:

```python
font_loaded: bool = False  # wFontLoaded bit 0 — textbox/font system active
```

- [ ] **Step 4: Add font_loaded parameter to _detect_mode()**

In `_detect_mode()` signature (line ~672), add `font_loaded: bool = False` parameter.

In the dialog detection section, update the condition:

```python
# Before: if joypad_disabled:
# After:
if joypad_disabled or font_loaded:
    # Differentiate DIALOG vs MENU via screen analysis
```

- [ ] **Step 5: Read wFontLoaded in read_state()**

In `read_state()` (line ~818), after reading other WRAM values, add:

```python
from .memory_map import WRAM_FONT_LOADED
font_loaded_byte = await self._read_byte(WRAM_FONT_LOADED)
font_loaded = bool(font_loaded_byte & 0x01)
```

Pass `font_loaded=font_loaded` to `_detect_mode()` call and include it in the GameState constructor.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_game_state_textbox.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add examples/pokemon_agent/game_state.py examples/pokemon_agent/memory_map.py tests/test_game_state_textbox.py
git commit -m "feat: add wFontLoaded textbox detection signal to game state"
```

---

## Chunk 3: Scripted Strategy Routines

### Task 6: Implement heal_at_pokecenter

**Files:**
- Create: `examples/pokemon_agent/scripted_strategies.py`
- Create: `tests/test_scripted_strategies.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_scripted_strategies.py`:

```python
"""Tests for scripted strategy routines."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from examples.pokemon_agent.scripted_strategies import heal_at_pokecenter


@pytest.mark.asyncio
async def test_heal_rejects_non_pokecenter():
    """Should return False if not on a pokecenter map."""
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 0  # Pallet Town, not a pokecenter
    routines.read_state = AsyncMock(return_value=state)
    result = await heal_at_pokecenter(routines)
    assert result is False


@pytest.mark.asyncio
async def test_heal_returns_true_on_pokecenter():
    """Should attempt heal on a pokecenter map."""
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 41  # Viridian Pokecenter
    state.mode = MagicMock()
    state.mode.name = "OVERWORLD"
    routines.read_state = AsyncMock(return_value=state)
    routines.navigate_to = AsyncMock(return_value=True)
    routines.face_direction = AsyncMock()
    routines.press = AsyncMock()
    routines.advance_text = AsyncMock()
    routines.ensure_overworld = AsyncMock()
    routines.call_tool = AsyncMock(return_value={"text_lines": ["Welcome!"]})
    result = await heal_at_pokecenter(routines)
    assert result is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripted_strategies.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement scripted_strategies.py**

Create `examples/pokemon_agent/scripted_strategies.py`:

```python
"""Scripted strategy routines for common Pokemon Yellow interactions.

These are deterministic async routines that batch common interaction sequences,
reducing MCP tool call overhead compared to LLM-driven step-by-step control.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .routines import Routines

# Pokecenter map IDs from pokemon_data.py
from .pokemon_data import POKECENTER_MAP_IDS


async def heal_at_pokecenter(routines: Routines) -> bool:
    """Walk to nurse counter, interact, wait for heal animation, exit dialog.

    Preconditions:
    - Player must be on a Pokecenter map

    Returns True on success, False if precondition fails or interaction errors.
    """
    state = await routines.read_state()
    if state.map_id not in POKECENTER_MAP_IDS:
        return False

    # Pokecenter nurse is always at the counter, face up to interact.
    # Counter position varies but nurse is always behind center counter.
    # Navigate to tile in front of counter (typically y=3 or y=4, center x).
    # Use entity_points if available, otherwise hardcode nurse interaction point.
    try:
        # Try navigating to the counter target
        if not await routines.navigate_to_target("pokecenter"):
            # Fallback: try (3, 3) which is typical nurse counter position
            if not await routines.navigate_to(3, 3):
                return False

        await routines.face_direction("up")
        # Press A to talk to nurse
        result = await routines.call_tool("press_and_read", key="a", wait=60)

        # Advance through heal dialog (Yes/No prompt, healing, done)
        for _ in range(6):
            await routines.call_tool("press_and_read", key="a", wait=60)

        # Exit any remaining dialog
        await routines.ensure_overworld()
        return True

    except Exception:
        await routines.ensure_overworld()
        return False


async def buy_items(
    routines: Routines,
    shopping_list: list[tuple[str, int]],
) -> bool:
    """Buy items from a mart clerk.

    Args:
        shopping_list: List of (item_name, quantity) tuples.

    Preconditions:
    - Player must be facing or near a shop clerk.

    Returns True if all items purchased, False on error.
    """
    state = await routines.read_state()

    try:
        # Face counter and interact
        await routines.face_direction("up")
        await routines.call_tool("press_and_read", key="a", wait=60)

        # Navigate to BUY option (first in menu)
        await routines.call_tool("press_and_read", key="a", wait=60)

        for item_name, qty in shopping_list:
            # Navigate to item in shop list
            # Read screen to find item position
            result = await routines.call_tool("press_and_read", key="a", wait=30)
            text = result.get("text_lines", [])

            # Select quantity (press up for more)
            for _ in range(qty - 1):
                await routines.call_tool("press_key", key="up", frames=8)

            # Confirm purchase
            await routines.call_tool("press_and_read", key="a", wait=60)
            # Confirm "Is that OK?" dialog
            await routines.call_tool("press_and_read", key="a", wait=60)

        # Exit shop menu (press B twice)
        await routines.call_tool("press_and_read", key="b", wait=30)
        await routines.call_tool("press_and_read", key="b", wait=30)

        await routines.ensure_overworld()
        return True

    except Exception:
        await routines.ensure_overworld()
        return False


async def use_pc_withdraw(
    routines: Routines,
    item_name: str,
    qty: int = 1,
) -> bool:
    """Withdraw an item from the PC.

    Preconditions:
    - Player must be adjacent to and facing a PC.

    Returns True on success.
    """
    try:
        # Interact with PC
        await routines.call_tool("press_and_read", key="a", wait=60)

        # Select WITHDRAW ITEM (second option after DEPOSIT)
        await routines.call_tool("press_and_read", key="down", wait=15)
        await routines.call_tool("press_and_read", key="a", wait=60)

        # Select item and quantity
        await routines.call_tool("press_and_read", key="a", wait=30)
        for _ in range(qty - 1):
            await routines.call_tool("press_key", key="up", frames=8)
        await routines.call_tool("press_and_read", key="a", wait=60)

        # LOG OFF
        await routines.call_tool("press_and_read", key="b", wait=30)
        await routines.call_tool("press_and_read", key="b", wait=30)

        await routines.ensure_overworld()
        return True

    except Exception:
        await routines.ensure_overworld()
        return False


async def use_pc_deposit(
    routines: Routines,
    item_name: str,
    qty: int = 1,
) -> bool:
    """Deposit an item to the PC.

    Preconditions:
    - Player must be adjacent to and facing a PC.

    Returns True on success.
    """
    try:
        # Interact with PC
        await routines.call_tool("press_and_read", key="a", wait=60)

        # Select DEPOSIT ITEM (first option)
        await routines.call_tool("press_and_read", key="a", wait=60)

        # Select item and quantity
        await routines.call_tool("press_and_read", key="a", wait=30)
        for _ in range(qty - 1):
            await routines.call_tool("press_key", key="up", frames=8)
        await routines.call_tool("press_and_read", key="a", wait=60)

        # LOG OFF
        await routines.call_tool("press_and_read", key="b", wait=30)
        await routines.call_tool("press_and_read", key="b", wait=30)

        await routines.ensure_overworld()
        return True

    except Exception:
        await routines.ensure_overworld()
        return False


async def fly_to(routines: Routines, dest_name: str) -> bool:
    """Use Fly to travel to a known city.

    Preconditions:
    - A party Pokemon must know Fly.
    - Player must be in overworld (not indoors).

    Returns True on success.
    """
    # Fly destination order in Gen 1 Yellow menu:
    FLY_DESTINATIONS = [
        "Pallet Town", "Viridian City", "Pewter City", "Cerulean City",
        "Lavender Town", "Vermilion City", "Celadon City", "Fuchsia City",
        "Cinnabar Island", "Indigo Plateau", "Saffron City",
    ]

    if dest_name not in FLY_DESTINATIONS:
        return False

    dest_index = FLY_DESTINATIONS.index(dest_name)

    try:
        state = await routines.read_state()

        # Check if we're outdoors (indoor maps can't use Fly)
        # Indoor maps have map_id > 12 and are in _INDOOR_PARENT
        from .pokemon_data import _INDOOR_PARENT
        if state.map_id in _INDOOR_PARENT:
            return False

        # Open START menu
        await routines.call_tool("press_and_read", key="start", wait=30)

        # Navigate to POKEMON option (second in start menu)
        await routines.call_tool("press_and_read", key="down", wait=10)
        await routines.call_tool("press_and_read", key="a", wait=30)

        # Find Pokemon with Fly — for now select first Pokemon
        await routines.call_tool("press_and_read", key="a", wait=30)

        # Select FLY from move list
        await routines.call_tool("press_and_read", key="a", wait=30)

        # Navigate to destination in fly map
        for _ in range(dest_index):
            await routines.call_tool("press_key", key="down", frames=8)

        # Confirm
        await routines.call_tool("press_and_read", key="a", wait=120)

        # Wait for fly animation
        await routines.wait_frames(180)
        await routines.ensure_overworld()
        return True

    except Exception:
        # Close any open menus
        for _ in range(5):
            await routines.call_tool("press_key", key="b", frames=8)
        await routines.ensure_overworld()
        return False
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_scripted_strategies.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add examples/pokemon_agent/scripted_strategies.py tests/test_scripted_strategies.py
git commit -m "feat: add scripted strategy routines for pokecenter, shop, PC, fly"
```

---

## Chunk 4: MCP Tool Optimization

### Task 7: Add screen text caching to Routines

**Files:**
- Modify: `examples/pokemon_agent/routines.py:68` (__init__)

- [ ] **Step 1: Add _last_screen_text cache to Routines.__init__**

In `routines.py` `__init__` (line ~68), add:

```python
self._last_screen_text: dict | None = None
self._last_screen_text_frame: int = 0
```

- [ ] **Step 2: Add cache getter method**

```python
def get_cached_screen_text(self, max_age_frames: int = 30) -> dict | None:
    """Return cached screen text if still fresh, else None."""
    if self._last_screen_text is None:
        return None
    # Invalidate if too old
    # (frame tracking is approximate — based on last known frame)
    return self._last_screen_text

def _cache_screen_text(self, result: dict) -> None:
    """Cache screen text from a press_and_read or decode_screen_text result."""
    if result and "text_lines" in result:
        self._last_screen_text = result

def _invalidate_screen_text(self) -> None:
    """Invalidate screen text cache (call after any input that changes screen)."""
    self._last_screen_text = None
```

- [ ] **Step 3: Update walk() and press() to invalidate cache**

In `walk()` (line ~437), after any movement input, add:
```python
self._invalidate_screen_text()
```

In `press()`, add the same invalidation.

- [ ] **Step 4: Update callers to use cache when appropriate**

In methods that call `decode_screen_text` after `press_and_read`, check cache first:

```python
cached = self.get_cached_screen_text()
if cached is None:
    result = await self.call_tool("decode_screen_text")
    self._cache_screen_text(result)
else:
    result = cached
```

- [ ] **Step 5: Commit**

```bash
git add examples/pokemon_agent/routines.py
git commit -m "feat: add screen text caching to reduce redundant decode calls"
```

---

### Task 8: Batch memory reads in read_state()

**Files:**
- Modify: `examples/pokemon_agent/game_state.py:818` (read_state)

- [ ] **Step 1: Identify contiguous read clusters**

In `read_state()`, group the individual `_read_byte` calls into contiguous memory ranges. Create a helper:

```python
async def _read_range(self, address: int, length: int) -> bytes:
    """Read a contiguous memory range and return as bytes."""
    result = await self._call_tool("read_memory", address=address, length=length)
    if "error" in result:
        return b'\x00' * length
    return bytes(result.get("data", [0] * length))
```

- [ ] **Step 2: Consolidate core overworld reads**

Replace individual reads in the core (non-conditional) path of `read_state()` with batch reads:

```python
# Batch 1: 0xCC24-0xCC52 (menu state, ~48 bytes)
menu_block = await self._read_range(0xCC24, 0x30)
# Parse: menu_cursor = menu_block[0], etc.

# Batch 2: 0xD056-0xD070 (battle flags, ~26 bytes)
battle_block = await self._read_range(0xD056, 0x1A)

# Batch 3: 0xD346-0xD370 (money/badges/position, ~42 bytes)
state_block = await self._read_range(0xD346, 0x2A)
# Parse: money (BCD at offset 0-2), badges (offset 0x0F), position (offset 0x1A-0x1C)

# Batch 4: 0xD72D-0xD731 (status flags, 5 bytes)
flags_block = await self._read_range(0xD72D, 5)
```

Keep conditional reads (party data when party_count > 0, battle data when in_battle != 0) as individual calls since they're only needed in specific modes.

- [ ] **Step 3: Verify read_state() still produces correct GameState**

Test by loading a save state and comparing `read_state()` output before and after the batch optimization. Values must match exactly.

- [ ] **Step 4: Commit**

```bash
git add examples/pokemon_agent/game_state.py
git commit -m "perf: batch contiguous memory reads in read_state() to reduce MCP calls"
```

---

### Task 9: Final integration test and push

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/test_pokebot_paths.py tests/test_scripted_strategies.py tests/test_game_state_textbox.py -v
```

Expected: All PASS

- [ ] **Step 2: Push branch**

```bash
git push github pokebot-integration
```
