"""Scripted strategy routines for common Pokemon Yellow interactions.

Each function takes a Routines instance and returns bool (success/failure).
Functions are self-contained with no shared state between them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .routines import Routines

from .pokemon_data import POKECENTER_MAP_IDS, MAP_NAME_TO_ID, MAP_NAMES

logger = logging.getLogger(__name__)

# Fly destinations: name -> map_id for towns/cities reachable by Fly.
# Order matches the in-game Fly destination list (top to bottom).
FLY_DESTINATIONS = {
    "Pallet Town": 0,
    "Viridian City": 1,
    "Pewter City": 2,
    "Cerulean City": 3,
    "Lavender Town": 4,
    "Vermilion City": 5,
    "Celadon City": 6,
    "Fuchsia City": 7,
    "Cinnabar Island": 8,
    "Indigo Plateau": 9,
    "Saffron City": 10,
}

# Map IDs that are outdoors (towns, cities, routes) where Fly can be used.
OUTDOOR_MAP_IDS = set(range(0, 37))  # 0-10 = towns/cities, 12-36 = routes

# Fly destination list order (top to bottom in the game's Fly menu).
FLY_DEST_ORDER = [
    "Pallet Town",
    "Viridian City",
    "Pewter City",
    "Cerulean City",
    "Lavender Town",
    "Vermilion City",
    "Celadon City",
    "Fuchsia City",
    "Cinnabar Island",
    "Indigo Plateau",
    "Saffron City",
]


async def _press_and_read(routines: Routines, key: str, frames: int = 16, wait: int = 60) -> dict:
    """Press a key, wait, and read screen text. Returns dict with 'text_lines'."""
    return await routines._call("press_and_read", {
        "key": key,
        "frames": frames,
        "wait": wait,
    })


def _screen_contains(result: dict, *keywords: str) -> bool:
    """Check if press_and_read result text contains any of the keywords (case-insensitive)."""
    lines = result.get("text_lines", [])
    text = " ".join(lines).upper()
    return any(kw.upper() in text for kw in keywords)


# ============================================================
# 1. Heal at Pokemon Center
# ============================================================

async def heal_at_pokecenter(routines: Routines) -> bool:
    """Heal party at a Pokemon Center.

    Precondition: player must be on a Pokecenter map.
    Walks to the counter, interacts with the nurse, and advances
    through the heal dialog until back in overworld.

    Returns:
        True if healing completed successfully, False otherwise.
    """
    state = await routines.read_state()
    if state.map_id not in POKECENTER_MAP_IDS:
        logger.warning(f"Not on a Pokecenter map (map_id={state.map_id})")
        return False

    try:
        # Navigate to the counter area (nurse is behind counter at y=1-2).
        # Stand in front of counter: typical Pokecenter counter is at (3, 3).
        nav_ok = await routines.navigate_to(3, 3)
        if not nav_ok:
            # Try alternate position
            nav_ok = await routines.navigate_to(4, 3)

        # Face up toward the nurse
        await routines.face_direction("up")

        # Talk to the nurse
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through the heal dialog:
        # "Welcome to our POKEMON CENTER"
        # "We heal your POKEMON back to perfect health"
        # "OK I'll take your POKEMON for a few seconds"
        # <healing animation>
        # "We hope to see you again"
        for _ in range(15):
            result = await _press_and_read(routines, "a", frames=16, wait=60)
            # Check if we're back to overworld (no dialog text)
            if not _screen_contains(result, "POKEMON", "CENTER", "HEAL", "HOPE", "WELCOME"):
                break

        # Extra presses to clear any remaining dialog
        await routines.advance_text(max_presses=5)
        await routines.ensure_overworld()
        return True

    except Exception as e:
        logger.error(f"heal_at_pokecenter failed: {e}")
        await routines.ensure_overworld()
        return False


# ============================================================
# 2. Buy items at a Mart
# ============================================================

async def buy_items(routines: Routines, shopping_list: list[tuple[str, int]]) -> bool:
    """Buy items from a Poke Mart.

    Precondition: player should be inside a mart and near the counter.

    Args:
        shopping_list: List of (item_name, quantity) tuples.

    Returns:
        True if purchase completed, False otherwise.
    """
    if not shopping_list:
        return False

    state = await routines.read_state()

    try:
        # Face the shopkeeper (up toward counter)
        await routines.face_direction("up")

        # Talk to shopkeeper
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through greeting dialog until we see buy/sell menu
        for _ in range(5):
            if _screen_contains(result, "BUY", "SELL", "QUIT"):
                break
            result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Select BUY (should be first option)
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # For each item in shopping list
        for item_name, quantity in shopping_list:
            # Navigate to the item in the buy menu.
            # Scroll through the item list looking for our item.
            found = False
            for scroll in range(20):
                result = await _press_and_read(routines, "a" if scroll == 0 else "down",
                                               frames=8, wait=40)
                if _screen_contains(result, item_name):
                    found = True
                    break

            if not found:
                logger.warning(f"Item '{item_name}' not found in shop")
                continue

            # Select the item
            result = await _press_and_read(routines, "a", frames=16, wait=60)

            # Set quantity (default is 1, press up for more)
            for _ in range(quantity - 1):
                await _press_and_read(routines, "up", frames=8, wait=20)

            # Confirm purchase
            result = await _press_and_read(routines, "a", frames=16, wait=60)

            # Confirm "Is that OK?" prompt - select YES
            if _screen_contains(result, "OK", "YES", "NO"):
                result = await _press_and_read(routines, "a", frames=16, wait=60)

            # Advance through "Here you are!" text
            await routines.advance_text(max_presses=3)

        # Exit the shop menu - press B to cancel, then advance
        for _ in range(3):
            await _press_and_read(routines, "b", frames=16, wait=40)

        await routines.advance_text(max_presses=5)
        await routines.ensure_overworld()
        return True

    except Exception as e:
        logger.error(f"buy_items failed: {e}")
        await routines.ensure_overworld()
        return False


# ============================================================
# 3. PC Withdraw Item
# ============================================================

async def use_pc_withdraw(routines: Routines, item_name: str, qty: int = 1) -> bool:
    """Withdraw an item from the PC.

    Precondition: player should be near/facing a PC in a Pokemon Center.

    Args:
        item_name: Name of the item to withdraw.
        qty: Number to withdraw (default 1).

    Returns:
        True if withdrawal completed, False otherwise.
    """
    try:
        # Interact with PC
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through "turned on the PC" text
        for _ in range(3):
            result = await _press_and_read(routines, "a", frames=16, wait=60)
            if _screen_contains(result, "WITHDRAW", "DEPOSIT", "LOG OFF"):
                break

        # Select WITHDRAW ITEM
        # Navigate menu: WITHDRAW is typically first or second option
        found_withdraw = False
        for _ in range(4):
            if _screen_contains(result, "WITHDRAW"):
                result = await _press_and_read(routines, "a", frames=16, wait=60)
                found_withdraw = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=40)

        if not found_withdraw:
            logger.warning("Could not find WITHDRAW option in PC menu")
            await _exit_pc(routines)
            return False

        # Find the item in the withdraw list
        found_item = False
        for _ in range(20):
            if _screen_contains(result, item_name):
                found_item = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=40)

        if not found_item:
            logger.warning(f"Item '{item_name}' not found in PC storage")
            await _exit_pc(routines)
            return False

        # Select the item
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Set quantity
        for _ in range(qty - 1):
            await _press_and_read(routines, "up", frames=8, wait=20)

        # Confirm withdrawal
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through confirmation text
        await routines.advance_text(max_presses=3)

        # Exit PC
        await _exit_pc(routines)
        return True

    except Exception as e:
        logger.error(f"use_pc_withdraw failed: {e}")
        await routines.ensure_overworld()
        return False


# ============================================================
# 4. PC Deposit Item
# ============================================================

async def use_pc_deposit(routines: Routines, item_name: str, qty: int = 1) -> bool:
    """Deposit an item into the PC.

    Precondition: player should be near/facing a PC in a Pokemon Center.

    Args:
        item_name: Name of the item to deposit.
        qty: Number to deposit (default 1).

    Returns:
        True if deposit completed, False otherwise.
    """
    try:
        # Interact with PC
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through "turned on the PC" text
        for _ in range(3):
            result = await _press_and_read(routines, "a", frames=16, wait=60)
            if _screen_contains(result, "WITHDRAW", "DEPOSIT", "LOG OFF"):
                break

        # Select DEPOSIT ITEM
        found_deposit = False
        for _ in range(4):
            if _screen_contains(result, "DEPOSIT"):
                result = await _press_and_read(routines, "a", frames=16, wait=60)
                found_deposit = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=40)

        if not found_deposit:
            logger.warning("Could not find DEPOSIT option in PC menu")
            await _exit_pc(routines)
            return False

        # Find the item in inventory list
        found_item = False
        for _ in range(20):
            if _screen_contains(result, item_name):
                found_item = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=40)

        if not found_item:
            logger.warning(f"Item '{item_name}' not found in inventory")
            await _exit_pc(routines)
            return False

        # Select the item
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Set quantity
        for _ in range(qty - 1):
            await _press_and_read(routines, "up", frames=8, wait=20)

        # Confirm deposit
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Advance through confirmation text
        await routines.advance_text(max_presses=3)

        # Exit PC
        await _exit_pc(routines)
        return True

    except Exception as e:
        logger.error(f"use_pc_deposit failed: {e}")
        await routines.ensure_overworld()
        return False


async def _exit_pc(routines: Routines) -> None:
    """Exit the PC menu by pressing B and selecting LOG OFF."""
    for _ in range(5):
        result = await _press_and_read(routines, "b", frames=16, wait=40)
        if _screen_contains(result, "LOG OFF"):
            await _press_and_read(routines, "a", frames=16, wait=60)
            break
    await routines.advance_text(max_presses=3)
    await routines.ensure_overworld()


# ============================================================
# 5. Fly to destination
# ============================================================

async def fly_to(routines: Routines, dest_name: str) -> bool:
    """Use Fly to travel to a destination city/town.

    Precondition: player must be outdoors (not in a building/cave).
    A party Pokemon must know Fly.

    Args:
        dest_name: Destination name (e.g. "Viridian City").

    Returns:
        True if Fly completed successfully, False otherwise.
    """
    # Validate destination
    dest_key = None
    for name in FLY_DESTINATIONS:
        if name.upper() == dest_name.upper():
            dest_key = name
            break
    if dest_key is None:
        logger.warning(f"Unknown Fly destination: '{dest_name}'")
        return False

    # Check we're outdoors
    state = await routines.read_state()
    if state.map_id not in OUTDOOR_MAP_IDS:
        logger.warning(f"Cannot Fly from indoor map (map_id={state.map_id})")
        return False

    try:
        # Open START menu
        result = await _press_and_read(routines, "start", frames=16, wait=60)

        # Navigate to POKEMON option
        found_pokemon = False
        for _ in range(6):
            if _screen_contains(result, "POK", "POKEMON"):
                found_pokemon = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=30)

        if not found_pokemon:
            logger.warning("Could not find POKEMON in START menu")
            await _press_and_read(routines, "b", frames=16, wait=40)
            await routines.ensure_overworld()
            return False

        # Select POKEMON
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Find the Pokemon that knows Fly in the party list.
        # We need to check each party member's moves.
        fly_mon_index = None
        for i, mon in enumerate(state.party):
            if "FLY" in [m.upper() for m in mon.move_names]:
                fly_mon_index = i
                break

        if fly_mon_index is None:
            logger.warning("No party Pokemon knows Fly")
            await _press_and_read(routines, "b", frames=16, wait=40)
            await _press_and_read(routines, "b", frames=16, wait=40)
            await routines.ensure_overworld()
            return False

        # Navigate to the flyer in party list
        for _ in range(fly_mon_index):
            await _press_and_read(routines, "down", frames=8, wait=30)

        # Select the Pokemon
        result = await _press_and_read(routines, "a", frames=16, wait=60)

        # Select FLY from the move/action list
        found_fly = False
        for _ in range(6):
            if _screen_contains(result, "FLY"):
                result = await _press_and_read(routines, "a", frames=16, wait=60)
                found_fly = True
                break
            result = await _press_and_read(routines, "down", frames=8, wait=30)

        if not found_fly:
            logger.warning("Could not find FLY in Pokemon's action menu")
            for _ in range(3):
                await _press_and_read(routines, "b", frames=16, wait=40)
            await routines.ensure_overworld()
            return False

        # Now on the Fly destination map.
        # Navigate to the destination. The cursor starts at the top (Pallet Town).
        dest_index = FLY_DEST_ORDER.index(dest_key)
        for _ in range(dest_index):
            await _press_and_read(routines, "down", frames=8, wait=30)

        # Confirm destination
        result = await _press_and_read(routines, "a", frames=16, wait=120)

        # Wait for fly animation to complete
        await routines.wait_frames(120)

        # Ensure we're back in overworld after landing
        await routines.ensure_overworld()
        return True

    except Exception as e:
        logger.error(f"fly_to failed: {e}")
        await routines.ensure_overworld()
        return False
