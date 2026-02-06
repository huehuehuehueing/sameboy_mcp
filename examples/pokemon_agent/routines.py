"""Layer 2: Coded Routines.

State-machine routines that execute game actions via MCP tools.
No LLM calls — pure Python logic using memory state.
"""

import asyncio
from typing import Any

from . import memory_map as mem
from .game_state import GameState, GameMode, Direction, GameStateReader


class Routines:
    """Coded routines for game interaction."""

    def __init__(self, call_tool, state_reader: GameStateReader, verbose: bool = False):
        """
        Args:
            call_tool: async callable(name, args) → result for MCP tools
            state_reader: GameStateReader instance
            verbose: Print debug info
        """
        self._call = call_tool
        self._reader = state_reader
        self._verbose = verbose

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

    # ============================================================
    # Title Screen
    # ============================================================

    async def handle_title_screen(self) -> bool:
        """Navigate past title screen. Returns True if successful."""
        self._log("handling title screen")
        # Press Start on title screen
        await self.press("start", 8)
        await self.wait_frames(60)

        # Press A to confirm / continue
        await self.press("a", 8)
        await self.wait_frames(60)

        state = await self.read_state()
        return state.mode != GameMode.TITLE_SCREEN

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
        Returns True if movement completed.
        """
        self._log(f"walking {direction} x{steps}")
        for _ in range(steps):
            before = await self.read_state()

            # Press direction and wait for walk animation
            await self.press(direction, 8)
            await self.wait_frames(12)

            # Verify position changed
            after = await self.read_state()
            if before.player_x == after.player_x and before.player_y == after.player_y:
                self._log(f"blocked! couldn't move {direction}")
                return False

            # Check if we entered a battle
            if after.mode == GameMode.BATTLE:
                self._log("encountered battle while walking!")
                return False

        return True

    async def face_direction(self, direction: str):
        """Turn to face a direction without walking (tap briefly)."""
        await self.press(direction, 2)
        await self.wait_frames(4)

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
