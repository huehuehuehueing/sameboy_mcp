# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Shared utilities for MCP tools."""

from typing import Union


def parse_address(address: Union[int, str]) -> int:
    """Parse an address that may be an int or a hex string like '0xC3A0'.

    Accepts:
      - int: used directly (masked to 16-bit)
      - str: parsed with int(s, 0) so "0xC3A0", "0xc3a0", "50080" all work
    """
    if isinstance(address, str):
        return int(address, 0) & 0xFFFF
    return address & 0xFFFF
