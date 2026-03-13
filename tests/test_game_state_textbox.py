"""Tests for textbox detection via wFontLoaded."""
import dataclasses
from examples.pokemon_agent.game_state import GameState


def test_game_state_has_font_loaded_field():
    fields = {f.name for f in dataclasses.fields(GameState)}
    assert "font_loaded" in fields


def test_font_loaded_default_false():
    # GameState has many required fields - just check the field exists with default
    fields = {f.name: f for f in dataclasses.fields(GameState)}
    assert fields["font_loaded"].default is False
