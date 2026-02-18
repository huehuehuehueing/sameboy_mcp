# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Shared utilities for MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ..emulator.thread import EmulatorThread


def parse_address(address: Union[int, str]) -> int:
    """Parse an address that may be an int or a hex string like '0xC3A0'.

    Accepts:
      - int: used directly (masked to 16-bit)
      - str: parsed with int(s, 0) so "0xC3A0", "0xc3a0", "50080" all work
    """
    if isinstance(address, str):
        return int(address, 0) & 0xFFFF
    return address & 0xFFFF


def require_rom(emu_thread: EmulatorThread) -> dict | None:
    """Return an error dict if no ROM is loaded, else None."""
    if not emu_thread.emulator._rom_loaded:
        return {"error": "No ROM loaded. Use load_rom() first."}
    return None
