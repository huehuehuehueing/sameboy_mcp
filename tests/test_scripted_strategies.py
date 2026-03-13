"""Tests for scripted strategy routines."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from examples.pokemon_agent.scripted_strategies import (
    heal_at_pokecenter, buy_items, use_pc_withdraw, use_pc_deposit, fly_to,
)


@pytest.mark.asyncio
async def test_heal_rejects_non_pokecenter():
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 0  # Pallet Town, not a pokecenter
    routines.read_state = AsyncMock(return_value=state)
    assert await heal_at_pokecenter(routines) is False


@pytest.mark.asyncio
async def test_heal_on_pokecenter_attempts_interaction():
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 41  # Viridian Pokecenter
    routines.read_state = AsyncMock(return_value=state)
    routines.navigate_to_target = AsyncMock(return_value=True)
    routines.navigate_to = AsyncMock(return_value=True)
    routines.face_direction = AsyncMock()
    routines.press = AsyncMock()
    routines.advance_text = AsyncMock()
    routines.ensure_overworld = AsyncMock()
    routines._call = AsyncMock(return_value={"text_lines": []})
    result = await heal_at_pokecenter(routines)
    assert result is True


@pytest.mark.asyncio
async def test_fly_rejects_unknown_destination():
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 0
    routines.read_state = AsyncMock(return_value=state)
    assert await fly_to(routines, "Narnia") is False


@pytest.mark.asyncio
async def test_fly_rejects_indoor_map():
    routines = MagicMock()
    state = MagicMock()
    state.map_id = 37  # Player House 1F (indoor)
    routines.read_state = AsyncMock(return_value=state)
    result = await fly_to(routines, "Viridian City")
    assert result is False


@pytest.mark.asyncio
async def test_buy_items_rejects_empty_list():
    routines = MagicMock()
    result = await buy_items(routines, [])
    assert result is False


@pytest.mark.asyncio
async def test_use_pc_withdraw_handles_missing_item():
    routines = MagicMock()
    # Simulate PC interaction: never find WITHDRAW option
    routines._call = AsyncMock(return_value={"text_lines": ["some other text"]})
    routines.advance_text = AsyncMock()
    routines.ensure_overworld = AsyncMock()
    result = await use_pc_withdraw(routines, "RARE CANDY", qty=1)
    assert result is False


@pytest.mark.asyncio
async def test_use_pc_deposit_handles_missing_item():
    routines = MagicMock()
    routines._call = AsyncMock(return_value={"text_lines": ["some other text"]})
    routines.advance_text = AsyncMock()
    routines.ensure_overworld = AsyncMock()
    result = await use_pc_deposit(routines, "RARE CANDY", qty=1)
    assert result is False
