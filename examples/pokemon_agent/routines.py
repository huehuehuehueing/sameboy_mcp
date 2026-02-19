"""Layer 2: Coded Routines.

State-machine routines that execute game actions via MCP tools.
No LLM calls — pure Python logic using memory state.
"""

import asyncio
from collections import deque
from typing import Any

from . import memory_map as mem
from .game_state import GameState, GameMode, Direction, GameStateReader, ScreenText
from .pokemon_data import MAP_GRAPH, MAP_NAMES, MAP_NAME_TO_ID


# ============================================================
# Multi-map route planning (BFS over MAP_GRAPH)
# ============================================================

def plan_route(
    current_map_id: int,
    dest_map_id: int,
    max_depth: int = 30,
) -> list[tuple[int, str]] | None:
    """BFS over MAP_GRAPH to find shortest map-level path.

    Args:
        current_map_id: Starting map ID.
        dest_map_id: Destination map ID.
        max_depth: Maximum BFS depth.

    Returns:
        List of (map_id, connection_type) hops from current to dest,
        e.g. [(1, "warp"), (12, "border_south"), (0, "border_south")]
        meaning: warp to map 1, walk south to map 12, walk south to map 0.
        Returns empty list if already on dest_map.
        Returns None if no route found.
    """
    if current_map_id == dest_map_id:
        return []

    # BFS
    queue: deque[tuple[int, list[tuple[int, str]]]] = deque()
    queue.append((current_map_id, []))
    visited: set[int] = {current_map_id}

    while queue:
        map_id, path = queue.popleft()

        if len(path) >= max_depth:
            continue

        for dest_id, conn_type in MAP_GRAPH.get(map_id, []):
            if dest_id in visited:
                continue
            new_path = path + [(dest_id, conn_type)]
            if dest_id == dest_map_id:
                return new_path
            visited.add(dest_id)
            queue.append((dest_id, new_path))

    return None


class Routines:
    """Coded routines for game interaction."""

    def __init__(self, call_tool, state_reader: GameStateReader, verbose: bool = False, strategy=None):
        """
        Args:
            call_tool: async callable(name, args) → result for MCP tools
            state_reader: GameStateReader instance
            verbose: Print debug info
            strategy: Optional StrategyEngine for LLM-assisted navigation
        """
        self._call = call_tool
        self._reader = state_reader
        self._verbose = verbose
        self._strategy = strategy
        self._blocked_tiles: set[tuple[int, int, int]] = set()  # (map_id, x, y)
        # ASCII map cache for pathfinding
        self._cached_map_id: int = -1
        self._cached_collision_map = None  # CollisionMap
        self._cached_warp_points: list = []  # list[Point]
        self._cached_entity_points: dict = {}  # dict[str, list[Point]]
        self._cached_warps_data: list = []  # raw warps data from render_ascii_map
        # Warp we arrived from — excluded from pathfinding targets to avoid loops
        self._arrival_warp: tuple[int, int, int] | None = None  # (map_id, x, y)

    def _log(self, msg: str):
        if self._verbose:
            print(f"  [routine] {msg}")

    # ============================================================
    # Low-level helpers
    # ============================================================

    async def press(self, key: str, frames: int = 4):
        """Press a button for N frames."""
        self._log(f"press {key} ({frames}f)")
        await self._call("press_key", {"key": key, "frames": frames})

    async def press_combo(self, keys: list[str], frames: int = 4):
        """Press multiple buttons simultaneously."""
        self._log(f"press {'+'.join(keys)} ({frames}f)")
        await self._call("press_keys", {"keys": keys, "frames": frames})

    async def wait_frames(self, count: int = 30):
        """Run emulator for N frames without input."""
        await self._call("run_frames", {"count": count})

    async def read_state(self) -> GameState:
        """Read current game state."""
        return await self._reader.read_state()

    async def screenshot(self) -> dict:
        """Capture current screen as base64 PNG."""
        return await self._call("capture_screen", {"format": "png"})

    async def ensure_overworld(self, max_attempts: int = 20) -> bool:
        """Clear any active dialog/menu so the player can move.

        Uses the deterministic BIT_DISABLE_JOYPAD flag (wStatusFlags5 bit 5
        at 0xD72F) — the same flag the game's joypad handler checks.
        Presses B repeatedly to dismiss dialogs and close menus.
        Returns True when joypad input is enabled.
        """
        for attempt in range(max_attempts):
            state = await self.read_state()
            if not state.joypad_disabled and state.mode in (GameMode.OVERWORLD, GameMode.MENU):
                if attempt > 0:
                    print(f"  [ensure_overworld] input enabled after {attempt} B presses")
                return True
            # Press B to dismiss dialog / close menu, then wait for animation
            await self.press("b", 6)
            await self.wait_frames(12)
        state = await self.read_state()
        print(f"  [ensure_overworld] FAILED after {max_attempts} attempts, "
              f"mode={state.mode}, joypad_disabled={state.joypad_disabled}")
        return not state.joypad_disabled

    # ============================================================
    # Title Screen and Intro
    # ============================================================

    async def handle_title_screen(self) -> bool:
        """Navigate past title screen. Returns True if successful."""
        self._log("handling title screen - pressing Start")
        await self.press("start", 8)
        await self.wait_frames(60)

        state = await self.read_state()
        # Verify: screen text should now show NEW GAME/CONTINUE (main menu)
        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            if "NEW GAME" in text:
                self._log("confirmed: main menu visible")
        return state.mode != GameMode.TITLE_SCREEN

    async def advance_intro(self) -> str:
        """
        Advance one step of the Oak intro sequence.

        Reads screen text to decide what to do:
        - If preset name list visible ("NEW NAME"): press A to select it (opens keyboard)
        - If ▼ prompt visible: press A to advance dialog
        - If text visible without ▼: press A to speed up or dismiss
        - If no text: press A to advance through animation

        Always presses A — safe during the intro phase.
        Returns a short description of what happened.
        """
        state = await self.read_state()

        # If game is running a scripted sequence (joypad simulation active),
        # don't press anything — our input interferes with the cutscene
        # (e.g. bedroom "ASH is playing the SNES!" sequence loops if we press A).
        if state.joypad_sim != 0:
            await self.wait_frames(60)
            return "waiting (scripted sequence)"

        text = ""
        lines = []
        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            lines = state.screen_text.lines

        # Detect preset name list — select "NEW NAME" (index 0) to open keyboard
        if "NEW NAME" in text:
            self._log("preset name list detected — selecting NEW NAME to open keyboard")
            await self.press("a", 6)
            await self.wait_frames(120)  # Wait for keyboard to render
            return "selected NEW NAME (keyboard)"

        # Check for ▼ prompt — press A to advance
        has_prompt = any("\u25bc" in l for l in lines)
        if has_prompt:
            await self.press("a", 4)
            await self.wait_frames(30)
            return "pressed A at prompt"

        # Text visible but no ▼ — press A to speed up printing or dismiss
        if text:
            await self.press("a", 4)
            await self.wait_frames(30)
            return "pressed A (text visible)"

        # No text on screen (animation/transition) — press A to advance
        await self.press("a", 4)
        await self.wait_frames(60)
        return "pressed A (no text)"

    async def handle_main_menu(self, select_new_game: bool = True) -> bool:
        """
        Navigate the main menu (Continue/New Game/Options).

        Args:
            select_new_game: If True, select New Game. If False, select Continue.

        Returns True if we successfully left the main menu.
        """
        self._log(f"handling main menu - select_new_game={select_new_game}")
        state = await self.read_state()

        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            has_continue = "CONTINUE" in text
            has_new_game = "NEW GAME" in text

            # Verify we actually see menu options
            if not has_new_game:
                self._log("WARNING: 'NEW GAME' not found on screen")
                await self.press("a", 8)
                await self.wait_frames(60)
                return False

            if select_new_game:
                if has_continue:
                    # NEW GAME is below CONTINUE — press down
                    self._log("CONTINUE detected, pressing down to NEW GAME")
                    await self.press("down", 4)
                    await self.wait_frames(8)
                    state = await self.read_state()
                    self._log(f"cursor now at index {state.menu_cursor}")
            else:
                if not has_continue:
                    self._log("no save game found - selecting New Game instead")

        await self.press("a", 8)
        await self.wait_frames(60)

        # Post-action verification
        state = await self.read_state()
        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            if "NEW GAME" not in text and "OPTION" not in text:
                self._log("confirmed: left main menu")
            else:
                self._log("WARNING: may still be on main menu")
        return state.mode != GameMode.MAIN_MENU

    async def enter_name(self, name: str = "ASH") -> bool:
        """Type a name on the on-screen keyboard.

        Assumes the keyboard grid is already visible (cursor at 'A' = row 0, col 0).
        Navigates to each letter and presses A, then submits with START.

        Args:
            name: The name to type (max 7 chars)

        Returns True when name entry is complete.
        """
        name = name.upper()[:7]
        self._log(f"typing name on keyboard: {name}")

        # Verify keyboard is visible
        state = await self.read_state()
        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            self._log(f"keyboard screen: {text[:80]}")
            if "A B C D E F G H I" not in text:
                self._log("WARNING: keyboard grid not visible, waiting")
                await self.wait_frames(60)
                return False

        # Keyboard grid positions (row, col)
        char_positions = {
            'A': (0, 0), 'B': (0, 1), 'C': (0, 2), 'D': (0, 3), 'E': (0, 4),
            'F': (0, 5), 'G': (0, 6), 'H': (0, 7), 'I': (0, 8),
            'J': (1, 0), 'K': (1, 1), 'L': (1, 2), 'M': (1, 3), 'N': (1, 4),
            'O': (1, 5), 'P': (1, 6), 'Q': (1, 7), 'R': (1, 8),
            'S': (2, 0), 'T': (2, 1), 'U': (2, 2), 'V': (2, 3), 'W': (2, 4),
            'X': (2, 5), 'Y': (2, 6), 'Z': (2, 7),
            ' ': (4, 0),
        }

        current_row, current_col = 0, 0  # Initial cursor at 'A'

        for char in name:
            if char not in char_positions:
                char = ' '
            target_row, target_col = char_positions[char]

            # Navigate to target position
            while current_row < target_row:
                await self.press("down", 4)
                await self.wait_frames(2)
                current_row += 1
            while current_row > target_row:
                await self.press("up", 4)
                await self.wait_frames(2)
                current_row -= 1
            while current_col < target_col:
                await self.press("right", 4)
                await self.wait_frames(2)
                current_col += 1
            while current_col > target_col:
                await self.press("left", 4)
                await self.wait_frames(2)
                current_col -= 1

            # Type the character
            await self.press("a", 6)
            await self.wait_frames(8)
            self._log(f"typed '{char}'")

        # Submit name with START
        await self.press("start", 8)
        await self.wait_frames(30)
        self._log("pressed START to submit name")

        # Press A to advance past "Your name is..." confirmation text
        await self.press("a", 6)
        await self.wait_frames(60)

        state = await self.read_state()
        if state.screen_text and state.screen_text.has_text:
            text = state.screen_text.full_text.upper()
            if "A B C D E F G H I" not in text:
                self._log("confirmed: left name entry")
        return state.mode != GameMode.NAME_ENTRY

    async def skip_oak_intro(self) -> bool:
        """
        Skip through Oak's intro speech by pressing A repeatedly.
        Handles the "world of Pokemon" introduction.
        """
        self._log("skipping Oak intro sequence")

        for _ in range(100):  # Safety limit
            state = await self.read_state()

            # Check if we've moved past the intro
            if state.mode == GameMode.NAME_ENTRY:
                self._log("reached name entry")
                return True
            if state.mode == GameMode.OVERWORLD:
                self._log("reached overworld")
                return True
            if state.party_count > 0:
                self._log("player has Pokemon - intro complete")
                return True

            # Press A to advance dialog
            await self.press("a", 6)
            await self.wait_frames(15)

        return False

    # ============================================================
    # Text / Dialog
    # ============================================================

    async def advance_text(self, max_presses: int = 20) -> bool:
        """
        Advance text dialog by pressing A repeatedly.
        Returns True when text is cleared.
        """
        self._log("advancing text")
        for _ in range(max_presses):
            await self.press("a", 6)
            await self.wait_frames(10)

            state = await self.read_state()
            if state.mode != GameMode.DIALOG:
                return True
        return False

    async def advance_text_once(self):
        """Press A once to advance dialog."""
        await self.press("a", 6)
        await self.wait_frames(8)

    async def press_b_cancel(self):
        """Press B to cancel / go back."""
        await self.press("b", 6)
        await self.wait_frames(8)

    # ============================================================
    # Menu Navigation
    # ============================================================

    async def navigate_menu(self, target_index: int, max_items: int | None = None) -> bool:
        """
        Navigate menu cursor to target_index.
        Returns True if cursor is at target.
        """
        self._log(f"navigating menu to index {target_index}")

        for _ in range(20):  # Safety limit
            state = await self.read_state()
            current = state.menu_cursor

            if current == target_index:
                return True

            if current < target_index:
                await self.press("down", 4)
            else:
                await self.press("up", 4)
            await self.wait_frames(6)

        return False

    async def select_menu_item(self, index: int) -> bool:
        """Navigate to menu item and press A."""
        if await self.navigate_menu(index):
            await self.press("a", 6)
            await self.wait_frames(10)
            return True
        return False

    # ============================================================
    # Movement
    # ============================================================

    async def walk(self, direction: str, steps: int = 1) -> bool:
        """
        Walk in a direction for N steps.
        direction: "up", "down", "left", "right"
        Returns True if movement completed (position changed).
        """
        self._log(f"walking {direction} x{steps}")

        for step in range(steps):
            before = await self.read_state()

            # If joypad is disabled (dialog/text active), try to clear it
            if before.joypad_disabled:
                self._log(f"joypad disabled (BIT_DISABLE_JOYPAD set), pressing B")
                await self.press("b", 6)
                await self.wait_frames(8)
                before = await self.read_state()
                if before.joypad_disabled:
                    self._log(f"joypad still disabled, cannot walk")
                    return False

            # Press direction and wait for walk animation
            # A walk cycle in Pokemon is 16 frames, we need sufficient time
            await self.press(direction, 16)  # Hold for full walk cycle
            await self.wait_frames(24)  # Wait longer after releasing

            # Verify movement occurred
            after = await self.read_state()

            # Check if we changed maps (warp) FIRST - position might not change during warp
            if after.map_id != before.map_id:
                self._log(f"warped from map {before.map_id} to {after.map_id}!")
                return True

            # Check if we entered a battle
            if after.mode == GameMode.BATTLE:
                self._log("encountered battle while walking!")
                return False

            # Check if position changed
            if before.player_x == after.player_x and before.player_y == after.player_y:
                self._log(f"blocked at ({before.player_x},{before.player_y})! couldn't move {direction}")
                return False

            self._log(f"moved from ({before.player_x},{before.player_y}) to ({after.player_x},{after.player_y})")

        return True

    async def trigger_warp(self, direction: str = "down") -> bool:
        """
        Trigger a warp/stairs by holding a direction longer.
        Stairs in Pokemon require holding the direction button during the animation.
        Returns True if map changed.
        """
        self._log(f"triggering warp by holding {direction}")
        before = await self.read_state()

        # Hold the direction for longer (stairs need extended input)
        await self.press(direction, 32)  # Double the normal walk time
        await self.wait_frames(60)  # Wait for warp animation

        after = await self.read_state()

        # Check for map change
        if after.map_id != before.map_id:
            self._log(f"warp triggered! {before.map_id} -> {after.map_id}")
            return True

        # If still same map, try again with even more pressure
        await self.press(direction, 48)
        await self.wait_frames(90)

        after = await self.read_state()
        if after.map_id != before.map_id:
            self._log(f"warp triggered (2nd attempt)! {before.map_id} -> {after.map_id}")
            return True

        self._log("warp did not trigger")
        return False

    async def face_direction(self, direction: str):
        """Turn to face a direction without walking (tap briefly)."""
        await self.press(direction, 2)
        await self.wait_frames(4)

    async def get_walkable_directions(self) -> list[str]:
        """
        Check which directions are walkable from current position.
        Returns list of walkable directions in priority order (down first for exits).

        Uses quick tile checks by briefly facing each direction.
        """
        walkable = []
        state = await self.read_state()

        facing_map = {
            Direction.UP: "up",
            Direction.DOWN: "down",
            Direction.LEFT: "left",
            Direction.RIGHT: "right",
        }
        current_facing = facing_map.get(state.facing, "down")

        # Check each direction - prioritize down (exits usually at bottom)
        for direction in ["down", "left", "right", "up"]:
            # Face the direction to read the tile ahead
            if direction != current_facing:
                await self.press(direction, 2)
                await self.wait_frames(3)

            new_state = await self.read_state()
            tile = new_state.tile_ahead

            # Check if walkable (not solid, not 0xFF)
            # Also allow warp tiles since those are valid destinations
            if tile not in mem.SOLID_TILES and tile != 0xFF:
                walkable.append(direction)
            elif tile in mem.WARP_TILES:
                walkable.insert(0, direction)  # Prioritize warps

            current_facing = direction

        self._log(f"walkable directions: {walkable}")
        return walkable

    async def explore_area(self, max_steps: int = 10) -> bool:
        """
        Explore the current area by walking in available directions.
        Returns True if exploration was successful.
        """
        self._log(f"exploring area (max {max_steps} steps)")

        for step in range(max_steps):
            walkable = await self.get_walkable_directions()

            if not walkable:
                self._log("no walkable directions!")
                return False

            # Prefer unexplored directions (simple heuristic: rotate through)
            direction = walkable[step % len(walkable)]

            success = await self.walk(direction, 1)
            if not success:
                # Try another direction
                for alt_dir in walkable:
                    if alt_dir != direction:
                        success = await self.walk(alt_dir, 1)
                        if success:
                            break

            state = await self.read_state()

            # Check if we found something interesting
            if state.mode == GameMode.BATTLE:
                self._log("encountered battle while exploring!")
                return True
            if state.mode == GameMode.DIALOG:
                self._log("found dialog/NPC!")
                return True

        return True

    def invalidate_map_cache(self):
        """Clear the cached ASCII collision map, forcing re-read on next pathfinding call."""
        self._cached_map_id = -1
        self._cached_collision_map = None
        self._cached_warp_points = []
        self._cached_entity_points = {}
        self._cached_warps_data = []

    def set_arrival_warp(self, map_id: int, x: int, y: int):
        """Record which warp tile we arrived on after a map change.

        This warp is excluded from pathfinding targets so we don't
        immediately walk back through it.
        """
        self._arrival_warp = (map_id, x, y)
        self._log(f"arrival warp set: map {map_id} ({x},{y})")

    async def _get_collision_map(self):
        """Build or return cached collision map, warp points, entity points, and player position.

        Returns a *working copy* of the collision map so callers can safely mutate it
        (e.g. marking blocked tiles) without corrupting the cache.

        Returns:
            (collision_map, warp_points, entity_points, warps_data, player_pos, state) or None on failure.
        """
        import copy
        from .pathfinding import collision_map_from_ascii, CollisionMap, Point

        state = await self.read_state()
        player_pos = Point(state.player_x, state.player_y)

        # Use cached collision map if map hasn't changed
        if self._cached_map_id == state.map_id and self._cached_collision_map is not None:
            self._log(f"using cached collision map for map {state.map_id}")
        else:
            # Call render_ascii_map MCP tool
            try:
                result = await self._call("render_ascii_map", {"include_legend": False})
            except Exception as e:
                self._log(f"render_ascii_map call failed: {e}")
                return None

            if not isinstance(result, dict):
                self._log(f"render_ascii_map: expected dict, got {type(result).__name__}: "
                          f"{repr(result)[:300]}")
                return None

            if "ascii" not in result:
                self._log(f"render_ascii_map: 'ascii' key missing, keys={list(result.keys())}")
                if "error" in result:
                    self._log(f"render_ascii_map error: {result['error']}")
                return None

            ascii_grid = result["ascii"]
            warps_data = result.get("warps", [])
            collision_map, warp_points, entity_points = collision_map_from_ascii(ascii_grid, warps_data)

            # Cache the result
            self._cached_map_id = state.map_id
            self._cached_collision_map = collision_map
            self._cached_warp_points = warp_points
            self._cached_entity_points = entity_points
            self._cached_warps_data = warps_data

            self._log(f"built collision map from ASCII: {collision_map.width}x{collision_map.height}, "
                      f"{len(warp_points)} warps")

        # Return a working copy so mutations don't corrupt the cache
        cm = CollisionMap(self._cached_collision_map.width, self._cached_collision_map.height)
        cm._grid = [row[:] for row in self._cached_collision_map._grid]
        cm._npcs = set(self._cached_collision_map._npcs)

        # Apply per-call overlays on the copy
        cm.set_walkable(player_pos.x, player_pos.y)
        for (map_id, bx, by) in self._blocked_tiles:
            if map_id == state.map_id:
                cm.set_blocked(bx, by)

        return cm, self._cached_warp_points, self._cached_entity_points, self._cached_warps_data, player_pos, state

    async def find_path_to_warp(self) -> list[str]:
        """
        Find a path to the nearest warp using the ASCII map from render_ascii_map.

        Uses cached collision data when available.

        Returns:
            List of directions ["down", "left", etc.] to reach the warp,
            or empty list if no path found.
        """
        from .pathfinding import find_path_to_nearest

        result = await self._get_collision_map()
        if result is None:
            return []

        collision_map, warp_points, entity_points, warps_data, player_pos, state = result

        # Filter out the warp we arrived from to avoid walking back through it
        goals = warp_points
        if self._arrival_warp and self._arrival_warp[0] == state.map_id:
            ax, ay = self._arrival_warp[1], self._arrival_warp[2]
            goals = [w for w in warp_points if not (w.x == ax and w.y == ay)]
            if len(goals) < len(warp_points):
                self._log(f"excluding arrival warp ({ax},{ay})")

        if not goals:
            self._log("no warps found (all excluded as arrival warp)")
            return []

        # Log warp locations
        for warp in goals:
            dist = abs(warp.x - player_pos.x) + abs(warp.y - player_pos.y)
            self._log(f"warp at ({warp.x},{warp.y}), dist={dist}")

        # Find path to nearest warp
        path = find_path_to_nearest(collision_map, player_pos, goals)

        if path:
            self._log(f"path found: {len(path.steps)} steps - {path.steps[:5]}...")
            return path.steps
        else:
            self._log("no path to any warp found")
            return []

    async def find_exit(self) -> str | None:
        """
        Try to find a map exit/warp point.
        Returns the direction to walk, or None if no exit found.

        Uses render_ascii_map BFS pathfinding exclusively.
        """
        state = await self.read_state()

        # Check current tile ahead for warp — if we're already facing one, use it
        if state.tile_ahead in mem.WARP_TILES:
            facing_map = {
                Direction.UP: "up",
                Direction.DOWN: "down",
                Direction.LEFT: "left",
                Direction.RIGHT: "right",
            }
            return facing_map.get(state.facing, "down")

        # Use ASCII-map-based pathfinding to nearest warp
        path = await self.find_path_to_warp()
        if path:
            return path[0]  # Return first step of the path

        return None

    async def navigate_to(
        self,
        target_x: int,
        target_y: int,
        interact: bool = False,
        margin: float = 0.2,
    ) -> bool:
        """
        BFS-walk to arbitrary (target_x, target_y) coordinates.

        Args:
            target_x: Target x coordinate (from ASCII map).
            target_y: Target y coordinate (from ASCII map).
            interact: If True, press A when adjacent to the target.
            margin: Safety margin over BFS path length (0.2 = 20%).

        Returns:
            True if player reached the target (or adjacent for interact).
        """
        import math
        from .pathfinding import find_path, find_path_to_nearest, Point

        self._log(f"navigate_to({target_x},{target_y}) interact={interact}")

        result = await self._get_collision_map()
        if result is None:
            self._log("navigate_to: failed to get collision map")
            return False

        collision_map, warp_points, entity_points, warps_data, player_pos, state = result
        initial_map = state.map_id

        target = Point(target_x, target_y)

        # For interact mode, we need to reach an adjacent tile, not the target itself
        if interact and not collision_map.is_walkable(target_x, target_y):
            # Target is blocked (e.g. NPC, PC counter) — find path to nearest adjacent tile
            adjacent = []
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                ax, ay = target_x + dx, target_y + dy
                if collision_map.is_walkable(ax, ay):
                    adjacent.append(Point(ax, ay))
            if not adjacent:
                self._log(f"navigate_to: no walkable tile adjacent to ({target_x},{target_y})")
                return False
            path = find_path_to_nearest(collision_map, player_pos, adjacent)
        else:
            path = find_path(collision_map, player_pos, target)

        if path is None:
            self._log(f"navigate_to: no path found to ({target_x},{target_y})")
            return False

        if path.length == 0:
            self._log(f"navigate_to: already at target")
            if interact:
                await self.interact()
            return True

        # Dynamic max_steps from BFS path length + margin
        max_steps = math.ceil(path.length * (1 + margin)) + 2  # +2 for rounding safety
        self._log(f"navigate_to: path={path.length} steps, budget={max_steps}")

        steps_taken = 0
        step_idx = 0  # Current index into path.steps

        while steps_taken < max_steps:
            # Check for map change (unexpected warp)
            current_state = await self.read_state()
            if current_state.map_id != initial_map:
                self._log(f"navigate_to: map changed {initial_map} -> {current_state.map_id}")
                return False

            # Check for battle
            if current_state.mode == GameMode.BATTLE:
                self._log("navigate_to: entered battle")
                return False

            current_pos = Point(current_state.player_x, current_state.player_y)

            # Check if we reached the target (or adjacent for interact)
            if not interact and current_pos == target:
                self._log(f"navigate_to: reached target ({target_x},{target_y})")
                return True

            if interact:
                dist = abs(current_pos.x - target_x) + abs(current_pos.y - target_y)
                if dist == 0:
                    # Standing on the target tile (walkable target) — just interact
                    self._log(f"navigate_to: standing on target, interacting")
                    await self.interact()
                    return True
                if dist == 1:
                    self._log(f"navigate_to: adjacent to target, interacting")
                    # Face the target direction
                    dx = target_x - current_pos.x
                    dy = target_y - current_pos.y
                    if abs(dx) >= abs(dy):
                        face_dir = "right" if dx > 0 else "left"
                    else:
                        face_dir = "down" if dy > 0 else "up"
                    await self.face_direction(face_dir)
                    await self.interact()
                    return True

            # If we've exhausted the pre-computed path, recompute
            if step_idx >= len(path.steps):
                self._log("navigate_to: recomputing path from current position")
                # Invalidate cache to get fresh map data
                self.invalidate_map_cache()
                result = await self._get_collision_map()
                if result is None:
                    return False
                collision_map, _, _, _, _, _ = result

                if interact and not collision_map.is_walkable(target_x, target_y):
                    adjacent = []
                    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                        ax, ay = target_x + dx, target_y + dy
                        if collision_map.is_walkable(ax, ay):
                            adjacent.append(Point(ax, ay))
                    if not adjacent:
                        return False
                    path = find_path_to_nearest(collision_map, current_pos, adjacent)
                else:
                    path = find_path(collision_map, current_pos, target)

                if path is None or path.length == 0:
                    self._log("navigate_to: recomputed path is empty or None")
                    if interact and abs(current_pos.x - target_x) + abs(current_pos.y - target_y) <= 1:
                        await self.interact()
                        return True
                    return path is not None and path.length == 0
                step_idx = 0
                # Extend budget if recomputed path requires more steps
                needed = steps_taken + math.ceil(path.length * (1 + margin)) + 2
                if needed > max_steps:
                    self._log(f"navigate_to: extending budget {max_steps} -> {needed}")
                    max_steps = needed

            direction = path.steps[step_idx]
            before_state = await self.read_state()
            success = await self.walk(direction, 1)
            steps_taken += 1

            if success:
                step_idx += 1
            else:
                # Retry once — handles transient blockers like the Pikachu follower
                # which moves out of the way after one failed attempt
                success = await self.walk(direction, 1)
                steps_taken += 1
                if success:
                    step_idx += 1
                    continue

                # Permanently blocked — mark tile and recompute
                dx = {"left": -1, "right": 1}.get(direction, 0)
                dy = {"up": -1, "down": 1}.get(direction, 0)
                blocked_x = before_state.player_x + dx
                blocked_y = before_state.player_y + dy
                self._blocked_tiles.add((initial_map, blocked_x, blocked_y))
                self._log(f"navigate_to: blocked at ({blocked_x},{blocked_y}), recomputing")

                # Force recompute on next iteration
                self.invalidate_map_cache()
                result = await self._get_collision_map()
                if result is None:
                    return False
                collision_map, _, _, _, _, _ = result
                collision_map.set_blocked(blocked_x, blocked_y)

                current_pos = Point(before_state.player_x, before_state.player_y)
                if interact and not collision_map.is_walkable(target_x, target_y):
                    adjacent = []
                    for ddx, ddy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                        ax, ay = target_x + ddx, target_y + ddy
                        if collision_map.is_walkable(ax, ay):
                            adjacent.append(Point(ax, ay))
                    if not adjacent:
                        return False
                    path = find_path_to_nearest(collision_map, current_pos, adjacent)
                else:
                    path = find_path(collision_map, current_pos, target)

                if path is None:
                    self._log("navigate_to: no path after recompute")
                    return False
                step_idx = 0
                # Extend budget if detour path requires more steps
                needed = steps_taken + math.ceil(path.length * (1 + margin)) + 2
                if needed > max_steps:
                    self._log(f"navigate_to: extending budget {max_steps} -> {needed}")
                    max_steps = needed

        self._log(f"navigate_to: budget exhausted after {steps_taken} steps")
        return False

    async def navigate_to_target(self, target: str) -> bool:
        """
        Navigate to a named target using BFS pathfinding.

        Args:
            target: Target type — "item", "npc", "trainer", "pc",
                    "warp", "hidden_item", "pokecenter".

        Returns:
            True if target was reached.
        """
        from .pathfinding import find_path_to_nearest, Point

        self._log(f"navigate_to_target({target})")

        if target == "warp":
            # Delegate to existing find_path_to_warp flow
            return await self.navigate_to_exit()

        result = await self._get_collision_map()
        if result is None:
            self._log("navigate_to_target: failed to get collision map")
            return False

        collision_map, warp_points, entity_points, warps_data, player_pos, state = result

        goals: list[Point] = []
        interact = False

        if target == "item":
            goals = entity_points.get("I", [])
            interact = True
        elif target == "npc":
            goals = entity_points.get("N", [])
            interact = True
        elif target == "trainer":
            goals = entity_points.get("T", [])
            interact = True
        elif target == "pc":
            goals = entity_points.get("C", [])
            interact = True
        elif target == "hidden_item":
            # Use get_area_info for hidden items
            try:
                area_info = await self._call("get_area_info", {"include_hidden_items": True})
                if isinstance(area_info, dict):
                    hidden = area_info.get("hidden_items", [])
                    for h in hidden:
                        hx, hy = h.get("x", -1), h.get("y", -1)
                        if hx >= 0 and hy >= 0:
                            goals.append(Point(hx, hy))
            except Exception as e:
                self._log(f"navigate_to_target: get_area_info failed: {e}")
            interact = True
        elif target == "pokecenter":
            from .pokemon_data import POKECENTER_MAP_IDS
            # Find warps whose dest_map is a Pokecenter
            for w in warps_data:
                dest_map = w.get("dest_map", -1)
                if dest_map in POKECENTER_MAP_IDS:
                    wx, wy = w.get("x", -1), w.get("y", -1)
                    if wx >= 0 and wy >= 0:
                        goals.append(Point(wx, wy))
                        self._log(f"pokecenter warp at ({wx},{wy}) -> map {dest_map}")
            interact = False  # Walk onto warp tile, don't press A
        else:
            self._log(f"navigate_to_target: unknown target type '{target}'")
            return False

        if not goals:
            self._log(f"navigate_to_target: no {target} found on current map")
            return False

        # Find nearest goal
        nearest = None
        nearest_dist = float("inf")
        for g in goals:
            dist = abs(g.x - player_pos.x) + abs(g.y - player_pos.y)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = g

        self._log(f"navigate_to_target: nearest {target} at ({nearest.x},{nearest.y}), dist={nearest_dist}")
        return await self.navigate_to(nearest.x, nearest.y, interact=interact)

    async def navigate_to_exit(self, max_attempts: int = 20) -> bool:
        """
        Actively try to navigate to and use a map exit.
        Returns True if we changed maps.
        """
        self._log("navigating to exit")
        initial_map = (await self.read_state()).map_id

        for attempt in range(max_attempts):
            state = await self.read_state()

            # Check if we changed maps
            if state.map_id != initial_map:
                self._log(f"changed maps! {initial_map} -> {state.map_id}")
                return True

            # Find exit direction
            exit_dir = await self.find_exit()
            if exit_dir:
                success = await self.walk(exit_dir, 1)
                if not success:
                    # Blocked, try other directions
                    walkable = await self.get_walkable_directions()
                    if walkable:
                        await self.walk(walkable[0], 1)
            else:
                # No exit found, explore
                walkable = await self.get_walkable_directions()
                if walkable:
                    # Vary direction based on attempt
                    direction = walkable[attempt % len(walkable)]
                    await self.walk(direction, 1)

            await self.wait_frames(8)

        return False

    async def smart_navigate(
        self,
        target_type: str = "exit",
        max_steps: int = 30,
        use_vision: bool = True,
    ) -> bool:
        """
        Navigate to a target using coded BFS pathfinding.

        Uses vision analysis (if available) to detect obstacles not in memory,
        but relies on coded pathfinding for actual movement.

        Args:
            target_type: What to navigate to ("exit", "npc", "item", "pokecenter")
            max_steps: Maximum number of steps before giving up
            use_vision: Whether to use vision for obstacle detection

        Returns:
            True if target was reached (e.g., map changed for exits)
        """
        self._log(f"smart navigation to {target_type} (max {max_steps} steps)")

        state = await self.read_state()
        initial_map = state.map_id
        steps_taken = 0
        consecutive_failures = 0

        while steps_taken < max_steps:
            state = await self.read_state()

            # Check if we changed maps (success for exit targets)
            if target_type == "exit" and state.map_id != initial_map:
                self._log(f"reached exit! map {initial_map} -> {state.map_id}")
                return True

            # Optional: use vision to detect obstacles
            if use_vision and self._strategy and consecutive_failures > 2:
                screen_result = await self.screenshot()
                if isinstance(screen_result, dict) and "image_base64" in screen_result:
                    vision_info = await self._strategy.analyze_for_navigation(
                        state=state,
                        screenshot_b64=screen_result["image_base64"],
                    )
                    if vision_info.get("obstacles"):
                        self._log(f"vision detected obstacles: {vision_info['obstacles']}")

            # Use coded pathfinding
            exit_dir = await self.find_exit()

            if exit_dir:
                self._log(f"coded pathfinding says: {exit_dir}")
                before_state = await self.read_state()
                before_pos = (before_state.player_x, before_state.player_y)

                success = await self.walk(exit_dir, 1)
                steps_taken += 1

                after_state = await self.read_state()

                # Check for map change
                if after_state.map_id != initial_map:
                    self._log(f"reached exit after {steps_taken} steps!")
                    return True

                # Track blocked tiles
                if not success:
                    dx = {"left": -1, "right": 1}.get(exit_dir, 0)
                    dy = {"up": -1, "down": 1}.get(exit_dir, 0)
                    blocked_x = before_pos[0] + dx
                    blocked_y = before_pos[1] + dy
                    self._blocked_tiles.add((state.map_id, blocked_x, blocked_y))
                    self._log(f"marked ({blocked_x},{blocked_y}) as blocked")
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

            else:
                # No exit found, try exploration
                walkable = await self.get_walkable_directions()
                if walkable:
                    direction = walkable[steps_taken % len(walkable)]
                    self._log(f"exploring: {direction}")
                    await self.walk(direction, 1)
                    steps_taken += 1
                else:
                    self._log("no walkable directions, waiting...")
                    await self.wait_frames(30)
                    steps_taken += 1
                    consecutive_failures += 1

            await self.wait_frames(5)

        self._log(f"failed to reach {target_type} after {steps_taken} steps")
        return False

    # XXX: verify this is not producing lossy information vs the expanded ascii map
    async def _build_map_ascii(self, state: GameState) -> str:
        """Build a simple ASCII representation of the current map area."""
        # Get map dimensions
        width = state.map_info.width * 2 if state.map_info else 8
        height = state.map_info.height * 2 if state.map_info else 8

        # Limit size for LLM context
        # XXX: verify this does not cause lossy compression of the map
        width = min(width, 16)
        height = min(height, 16)

        # Initialize grid
        grid = [['.' for _ in range(width)] for _ in range(height)]

        # Mark walls at edges
        for x in range(width):
            if 0 <= 0 < height:
                grid[0][x] = '#'
            if 0 <= height - 1 < height:
                grid[height - 1][x] = '#'
        for y in range(height):
            if 0 <= 0 < width:
                grid[y][0] = '#'
            if 0 <= width - 1 < width:
                grid[y][width - 1] = '#'

        # Mark warps
        if state.map_info and state.map_info.warps:
            for warp in state.map_info.warps:
                if 0 <= warp.y < height and 0 <= warp.x < width:
                    grid[warp.y][warp.x] = 'W'

        # Mark known blocked tiles
        for (map_id, bx, by) in self._blocked_tiles:
            if map_id == state.map_id and 0 <= by < height and 0 <= bx < width:
                grid[by][bx] = '#'

        # Mark player
        px, py = state.player_x, state.player_y
        if 0 <= py < height and 0 <= px < width:
            grid[py][px] = 'P'

        # Build string with coordinates
        lines = ["    " + "".join(str(x % 10) for x in range(width))]
        for y, row in enumerate(grid):
            lines.append(f"{y:2d}: " + "".join(row))

        return "\n".join(lines)

    async def smart_navigate_to_exit(self, max_attempts: int = 30) -> bool:
        """
        Navigate to map exit using coded BFS pathfinding.

        Uses vision analysis for obstacle detection if strategy engine is available.
        """
        return await self.smart_navigate(
            target_type="exit",
            max_steps=max_attempts,
            use_vision=self._strategy is not None,
        )

    # ============================================================
    # Battle Execution
    # ============================================================

    async def execute_battle_move(self, move_index: int) -> bool:
        """
        Execute a battle move by index (0-3).
        Navigates: FIGHT → select move → confirm.
        Returns True if move was executed.
        """
        self._log(f"executing battle move {move_index}")

        # Select FIGHT (first option in battle menu, index 0)
        await self.press("a", 6)
        await self.wait_frames(15)

        # Navigate to the move
        if move_index > 0:
            for _ in range(move_index):
                await self.press("down", 4)
                await self.wait_frames(4)

        # Select the move
        await self.press("a", 6)

        # Wait for battle animation to play
        await self.wait_frames(120)

        return True

    async def run_from_battle(self) -> bool:
        """
        Attempt to run from a wild battle.
        Navigates: RUN (4th option in battle menu).
        """
        self._log("attempting to run from battle")

        # RUN is the 4th battle option (bottom-right)
        # Battle menu layout: FIGHT  BAG
        #                     POKEMON RUN
        await self.press("down", 4)
        await self.wait_frames(4)
        await self.press("right", 4)
        await self.wait_frames(4)
        await self.press("a", 6)
        await self.wait_frames(60)

        state = await self.read_state()
        if state.mode != GameMode.BATTLE:
            self._log("successfully ran away!")
            return True

        self._log("couldn't escape!")
        return False

    async def switch_pokemon(self, party_index: int) -> bool:
        """
        Switch to a different Pokemon in battle.
        party_index: 0-5
        """
        self._log(f"switching to party Pokemon {party_index}")

        # Open POKEMON menu (3rd battle option, bottom-left)
        await self.press("down", 4)
        await self.wait_frames(4)
        await self.press("a", 6)
        await self.wait_frames(20)

        # Navigate to the Pokemon
        for _ in range(party_index):
            await self.press("down", 4)
            await self.wait_frames(4)

        # Select it
        await self.press("a", 6)
        await self.wait_frames(15)

        # Choose SWITCH (should be first option)
        await self.press("a", 6)
        await self.wait_frames(90)

        return True

    async def use_item_in_battle(self, bag_index: int = 0) -> bool:
        """
        Use an item from the bag in battle.
        Navigates: BAG → select item → use.
        """
        self._log(f"using bag item {bag_index}")

        # BAG is top-right in battle menu
        await self.press("right", 4)
        await self.wait_frames(4)
        await self.press("a", 6)
        await self.wait_frames(20)

        # Navigate to item
        for _ in range(bag_index):
            await self.press("down", 4)
            await self.wait_frames(4)

        # Select and use
        await self.press("a", 6)
        await self.wait_frames(15)
        await self.press("a", 6)
        await self.wait_frames(90)

        return True

    # ============================================================
    # Pokecenter Healing
    # ============================================================

    async def use_pokecenter(self) -> bool:
        """
        Interact with Pokecenter nurse to heal party.
        Assumes player is standing in front of the nurse counter.
        """
        self._log("using Pokecenter")

        # Talk to nurse (face up and press A)
        await self.face_direction("up")
        await self.press("a", 6)
        await self.wait_frames(30)

        # Advance through dialog (nurse asks to heal)
        await self.advance_text(max_presses=5)

        # Say YES
        await self.press("a", 6)
        await self.wait_frames(120)  # Healing animation

        # Advance remaining dialog
        await self.advance_text(max_presses=10)

        self._log("healed at Pokecenter!")
        return True

    # ============================================================
    # Overworld Interactions
    # ============================================================

    async def interact(self):
        """Press A to interact with whatever is in front of the player."""
        await self.press("a", 6)
        await self.wait_frames(15)

    async def open_start_menu(self):
        """Open the START menu in the overworld."""
        await self.press("start", 6)
        await self.wait_frames(15)

    async def close_menu(self):
        """Close current menu with B."""
        await self.press("b", 6)
        await self.wait_frames(10)

    async def escape_stuck_state(self, movement_history: list = None) -> bool:
        """
        Attempt to escape from a stuck state (dialog loop, blocked position).
        Uses backtracking if history is provided.
        Returns True if position changed.
        """
        self._log("attempting to escape stuck state")
        state = await self.read_state()
        start_x, start_y, start_map = state.player_x, state.player_y, state.map_id

        # Step 1: Mash B to exit any dialog/menu
        for _ in range(5):
            await self.press("b", 4)
            await self.wait_frames(6)

        # Step 2: Check if we're in a different mode now
        state = await self.read_state()
        if state.mode == GameMode.OVERWORLD:
            self._log("escaped to overworld")

        # Step 3: Try backtracking if we have history
        if movement_history:
            for i in range(min(3, len(movement_history))):
                last_entry = movement_history[-(i+1)]
                last_map, last_x, last_y, last_dir = last_entry

                if last_map != state.map_id:
                    continue  # Different map, skip

                reverse = {"up": "down", "down": "up", "left": "right", "right": "left"}
                rev_dir = reverse.get(last_dir, "down")

                self._log(f"backtrack attempt {i+1}: {rev_dir}")
                await self.press(rev_dir, 10)
                await self.wait_frames(16)

                new_state = await self.read_state()
                if new_state.player_x != start_x or new_state.player_y != start_y:
                    self._log(f"escaped via backtrack to ({new_state.player_x},{new_state.player_y})")
                    return True

        # Step 4: Try all directions
        for direction in ["down", "left", "right", "up"]:
            self._log(f"escape attempt: {direction}")
            await self.press(direction, 10)
            await self.wait_frames(16)

            new_state = await self.read_state()
            if new_state.player_x != start_x or new_state.player_y != start_y:
                self._log(f"escaped via {direction} to ({new_state.player_x},{new_state.player_y})")
                return True

            if new_state.map_id != start_map:
                self._log(f"escaped via map change to {new_state.map_id}")
                return True

        self._log("failed to escape")
        return False

    # ============================================================
    # Composite Actions
    # ============================================================

    async def wait_for_battle_end(self, timeout_frames: int = 600) -> GameState:
        """Wait until battle ends or timeout."""
        frames_waited = 0
        while frames_waited < timeout_frames:
            # Advance any text that appears
            await self.press("a", 4)
            await self.wait_frames(15)
            frames_waited += 19

            state = await self.read_state()
            if state.mode != GameMode.BATTLE:
                return state
        return await self.read_state()

    async def handle_whiteout(self) -> bool:
        """Handle a whiteout (all Pokemon fainted). Just advance text."""
        self._log("handling whiteout")
        return await self.advance_text(max_presses=30)

    # ============================================================
    # Multi-Map Route Navigation
    # ============================================================

    async def navigate_route(self, dest_map_id: int, max_depth: int = 30) -> bool:
        """Execute a multi-map route to reach dest_map_id.

        Plans a route across map borders and warps, then executes each hop.

        Args:
            dest_map_id: Target map ID to reach.
            max_depth: Maximum hops in the route plan.

        Returns:
            True if dest_map_id was reached.
        """
        print(f"  [nav-route] navigate_route() ENTERED: dest_map_id={dest_map_id}")

        # Clear any active dialog/menu before navigating
        in_overworld = await self.ensure_overworld()
        if not in_overworld:
            print(f"  [nav-route] could not clear dialog, aborting")
            return False

        state = await self.read_state()
        current_map = state.map_id
        print(f"  [nav-route] current_map={current_map} ({MAP_NAMES.get(current_map, '?')})")

        if current_map == dest_map_id:
            print(f"  [nav-route] already on destination map, returning True")
            return True

        print(f"  [nav-route] calling plan_route({current_map}, {dest_map_id})")
        route = plan_route(current_map, dest_map_id, max_depth=max_depth)
        if route is None:
            print(f"  [nav-route] plan_route returned None — no route found!")
            return False

        dest_name = MAP_NAMES.get(dest_map_id, f"map_{dest_map_id}")
        hop_summary = " → ".join(
            f"{MAP_NAMES.get(m, str(m))}({c})" for m, c in route
        )
        print(f"  [nav-route] route planned: {len(route)} hops: {hop_summary}")

        for i, (next_map_id, conn_type) in enumerate(route):
            state = await self.read_state()
            current_map = state.map_id
            print(f"  [nav-route] hop {i+1}/{len(route)}: current={current_map} "
                  f"({MAP_NAMES.get(current_map, '?')}), target={next_map_id} "
                  f"({MAP_NAMES.get(next_map_id, '?')}), type={conn_type}")

            if current_map == dest_map_id:
                print(f"  [nav-route] reached destination early at hop {i}")
                return True
            if current_map == next_map_id:
                print(f"  [nav-route] already on hop target, skipping")
                continue

            if conn_type.startswith("border_"):
                direction = conn_type.replace("border_", "")
                print(f"  [nav-route] calling _cross_border('{direction}', {next_map_id})")
                success = await self._cross_border(direction, next_map_id)
            elif conn_type == "warp":
                print(f"  [nav-route] calling _cross_warp({next_map_id})")
                success = await self._cross_warp(next_map_id)
            else:
                print(f"  [nav-route] unknown connection type '{conn_type}'")
                success = False
            print(f"  [nav-route] hop result: success={success}")

            if not success:
                state = await self.read_state()
                if state.map_id == next_map_id:
                    print(f"  [nav-route] hop actually succeeded (map changed despite failure)")
                    continue
                print(f"  [nav-route] hop FAILED, stuck on map {state.map_id}")
                return False

            self.invalidate_map_cache()
            new_state = await self.read_state()
            self.set_arrival_warp(new_state.map_id, new_state.player_x, new_state.player_y)
            print(f"  [nav-route] after hop: now on map {new_state.map_id} "
                  f"({MAP_NAMES.get(new_state.map_id, '?')}) at ({new_state.player_x},{new_state.player_y})")

        state = await self.read_state()
        reached = state.map_id == dest_map_id
        print(f"  [nav-route] FINAL: on map {state.map_id}, wanted {dest_map_id}, reached={reached}")
        return reached

    async def _cross_border(self, direction: str, expected_map_id: int) -> bool:
        """Walk to a map border and cross it.

        Scans the edge of the map for ALL walkable tiles, BFS-finds the
        nearest reachable one, navigates there, and walks off the edge.
        """
        from .pathfinding import find_path_to_nearest, Point

        print(f"  [nav-border] _cross_border('{direction}', expected={expected_map_id})")
        state = await self.read_state()
        initial_map = state.map_id

        result = await self._get_collision_map()
        if result is None:
            print(f"  [nav-border] failed to get collision map")
            return False

        collision_map, _, _, _, player_pos, state = result
        map_w, map_h = collision_map.width, collision_map.height
        print(f"  [nav-border] map dims: {map_w}x{map_h}, player at ({player_pos.x},{player_pos.y})")

        # Find ALL walkable tiles at the border edge
        edge_goals: list[Point] = []
        if direction == "north":
            edge_goals = [Point(x, 0) for x in range(map_w) if collision_map.is_walkable(x, 0)]
        elif direction == "south":
            edge_goals = [Point(x, map_h - 1) for x in range(map_w) if collision_map.is_walkable(x, map_h - 1)]
        elif direction == "west":
            edge_goals = [Point(0, y) for y in range(map_h) if collision_map.is_walkable(0, y)]
        elif direction == "east":
            edge_goals = [Point(map_w - 1, y) for y in range(map_h) if collision_map.is_walkable(map_w - 1, y)]
        else:
            print(f"  [nav-border] unknown direction '{direction}'")
            return False

        print(f"  [nav-border] {len(edge_goals)} walkable edge tiles at {direction} border")
        if not edge_goals:
            print(f"  [nav-border] no walkable edge tiles!")
            return False

        # BFS to nearest reachable edge tile
        path = find_path_to_nearest(collision_map, player_pos, edge_goals)
        if path is None:
            print(f"  [nav-border] BFS found no path to any edge tile")
            return False

        target = path.positions[-1] if path.positions else player_pos
        print(f"  [nav-border] nearest reachable edge tile: ({target.x},{target.y}), "
              f"path={path.length} steps")

        # Navigate to the edge tile
        reached = await self.navigate_to(target.x, target.y)
        state = await self.read_state()
        if state.map_id != initial_map:
            print(f"  [nav-border] map changed during navigation to edge!")
            return True

        print(f"  [nav-border] at ({state.player_x},{state.player_y}), walking {direction} to cross")

        # Walk off the edge to trigger border connection
        for attempt in range(10):
            success = await self.walk(direction, 1)
            state = await self.read_state()
            if state.map_id != initial_map:
                print(f"  [nav-border] CROSSED border to map {state.map_id}!")
                return True
            if state.mode == GameMode.BATTLE:
                print(f"  [nav-border] entered battle during crossing")
                return False

        print(f"  [nav-border] FAILED to cross {direction} border after reaching edge")
        return False

    async def _cross_warp(self, expected_map_id: int) -> bool:
        """Find and use a warp to reach expected_map_id."""
        print(f"  [nav-warp] _cross_warp(expected={expected_map_id})")
        state = await self.read_state()
        initial_map = state.map_id
        print(f"  [nav-warp] initial_map={initial_map}, player at ({state.player_x},{state.player_y})")

        result = await self._get_collision_map()
        if result is not None:
            collision_map, warp_points, entity_points, warps_data, player_pos, state = result
            print(f"  [nav-warp] got collision map, {len(warps_data)} warps found:")
            for w in warps_data:
                print(f"    warp: ({w.get('x')},{w.get('y')}) -> map {w.get('dest_map')}")

            for w in warps_data:
                dest_map = w.get("dest_map", -1)
                if dest_map == expected_map_id:
                    wx, wy = w.get("x", -1), w.get("y", -1)
                    if wx >= 0 and wy >= 0:
                        print(f"  [nav-warp] MATCH: warp at ({wx},{wy}) -> map {dest_map}, navigating")
                        reached = await self.navigate_to(wx, wy)
                        state = await self.read_state()
                        print(f"  [nav-warp] after navigate_to warp: map={state.map_id}, pos=({state.player_x},{state.player_y})")
                        if state.map_id != initial_map:
                            print(f"  [nav-warp] warped! now on map {state.map_id}")
                            return True
                        for d in ["down", "up", "left", "right"]:
                            await self.walk(d, 1)
                            state = await self.read_state()
                            print(f"  [nav-warp] step {d}: map={state.map_id}")
                            if state.map_id != initial_map:
                                print(f"  [nav-warp] warped via step {d}!")
                                return True
                            reverse = {"down": "up", "up": "down", "left": "right", "right": "left"}
                            await self.walk(reverse[d], 1)
        else:
            print(f"  [nav-warp] _get_collision_map returned None")

        print(f"  [nav-warp] no targeted warp found, falling back to navigate_to_exit")
        changed = await self.navigate_to_exit(max_attempts=30)
        if changed:
            state = await self.read_state()
            print(f"  [nav-warp] navigate_to_exit succeeded, now on map {state.map_id}")
        else:
            print(f"  [nav-warp] navigate_to_exit FAILED")
        return changed
