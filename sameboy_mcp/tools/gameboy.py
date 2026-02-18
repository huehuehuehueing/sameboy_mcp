# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Game Boy game-specific MCP tools.

Higher-level tools for reading screen text and game data.
Includes Gen 1 Pokemon character encoding (from pret/pokeyellow charmap.asm).
"""

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType


# ============================================================
# Gen 1 Pokemon Character Encoding
# ============================================================
# From pret/pokeyellow constants/charmap.asm
# The Game Boy uses a custom character encoding, not ASCII.

GEN1_CHAR_ENCODING = {
    # Uppercase letters
    0x80: "A", 0x81: "B", 0x82: "C", 0x83: "D", 0x84: "E",
    0x85: "F", 0x86: "G", 0x87: "H", 0x88: "I", 0x89: "J",
    0x8A: "K", 0x8B: "L", 0x8C: "M", 0x8D: "N", 0x8E: "O",
    0x8F: "P", 0x90: "Q", 0x91: "R", 0x92: "S", 0x93: "T",
    0x94: "U", 0x95: "V", 0x96: "W", 0x97: "X", 0x98: "Y",
    0x99: "Z",
    # Special Pokemon symbols
    0x9A: "(", 0x9B: ")", 0x9C: ":", 0x9D: ";", 0x9E: "[", 0x9F: "]",
    # Lowercase letters
    0xA0: "a", 0xA1: "b", 0xA2: "c", 0xA3: "d", 0xA4: "e",
    0xA5: "f", 0xA6: "g", 0xA7: "h", 0xA8: "i", 0xA9: "j",
    0xAA: "k", 0xAB: "l", 0xAC: "m", 0xAD: "n", 0xAE: "o",
    0xAF: "p", 0xB0: "q", 0xB1: "r", 0xB2: "s", 0xB3: "t",
    0xB4: "u", 0xB5: "v", 0xB6: "w", 0xB7: "x", 0xB8: "y",
    0xB9: "z",
    # Accented characters and contractions
    0xBA: "é",
    0xBB: "'d", 0xBC: "'l", 0xBD: "'s", 0xBE: "'t", 0xBF: "'v",
    # Punctuation and symbols
    0xE0: "'",
    0xE1: "PK", 0xE2: "MN",
    0xE3: "-",
    0xE4: "'r", 0xE5: "'m",
    0xE6: "?", 0xE7: "!", 0xE8: ".",
    0xEC: "▷", 0xED: "▶", 0xEE: "▼",
    0xEF: "♂",
    0xF0: "¥", 0xF1: "×",
    0xF3: "/", 0xF4: ",",
    0xF5: "♀",
    # Numbers
    0xF6: "0", 0xF7: "1", 0xF8: "2", 0xF9: "3", 0xFA: "4",
    0xFB: "5", 0xFC: "6", 0xFD: "7", 0xFE: "8", 0xFF: "9",
    # Control characters
    0x50: "@",  # String terminator
    0x4F: "\n",  # Line break
    0x51: "*",  # End of page
}

# Space-like tiles
_SPACE_TILES = {0x00, 0x01, 0x7F, 0x10, 0x11, 0x12, 0x13}

# Box drawing tiles
_BOX_TILES = {
    0x79: "┌", 0x7A: "─", 0x7B: "┐",
    0x7C: "│", 0x7D: "└", 0x7E: "┘",
}


def _decode_tile(tile_id: int) -> str:
    """Decode a single tile ID to its character representation."""
    if tile_id in _SPACE_TILES:
        return " "
    if tile_id in _BOX_TILES:
        return _BOX_TILES[tile_id]
    return GEN1_CHAR_ENCODING.get(tile_id, "")


def _extract_text_lines(rows: list[str]) -> list[str]:
    """Extract non-empty text lines, stripping box borders and whitespace."""
    lines = []
    for row in rows:
        # Strip box drawing chars and whitespace
        text = row.replace("┌", "").replace("─", "").replace("┐", "")
        text = text.replace("│", "").replace("└", "").replace("┘", "")
        text = text.strip()
        if text:
            lines.append(text)
    return lines


def register_gameboy_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register Game Boy game-specific tools with the MCP server."""

    @server.tool()
    async def decode_screen_text(
        address: int = 0xC3A0,
        width: int = 20,
        height: int = 18,
    ) -> dict:
        """
        Read the screen tile map from RAM and decode it to text.

        Reads tile data and decodes using Gen 1 Pokemon character encoding.
        Default address 0xC3A0 is the wTileMap for Pokemon Red/Blue/Yellow.

        Args:
            address: RAM address of the tile map (default: 0xC3A0 for Pokemon)
            width: Screen width in tiles (default: 20)
            height: Screen height in tiles (default: 18)

        Returns:
            Decoded text rows, extracted text lines, and raw tile grid
        """
        total = width * height
        if total > 1024:
            return {"error": f"Tile map too large: {total} tiles (max 1024)"}

        # Read tile data (may need multiple reads since max is 256)
        all_bytes = []
        remaining = total
        offset = 0
        while remaining > 0:
            chunk = min(remaining, 256)
            result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
                "start": (address + offset) & 0xFFFF,
                "length": chunk,
            })
            data = result.get("data", b"")
            all_bytes.extend(data)
            offset += chunk
            remaining -= chunk

        if len(all_bytes) < total:
            return {"error": f"Read only {len(all_bytes)} of {total} bytes"}

        # Decode each row
        rows = []
        tile_grid = []
        for y in range(height):
            row_start = y * width
            row_tiles = all_bytes[row_start:row_start + width]
            tile_grid.append([f"0x{t:02X}" for t in row_tiles])
            row_text = "".join(_decode_tile(t) for t in row_tiles)
            rows.append(row_text)

        # Extract meaningful text lines
        text_lines = _extract_text_lines(rows)

        return {
            "address": f"0x{address:04X}",
            "width": width,
            "height": height,
            "rows": rows,
            "text_lines": text_lines,
        }

    @server.tool()
    async def read_screen_tiles(
        address: int = 0xC3A0,
        width: int = 20,
        height: int = 18,
    ) -> dict:
        """
        Read raw tile IDs from the screen tile map in RAM.

        Returns the tile map as a grid of hex tile IDs without decoding.
        Useful for analyzing tile patterns or non-text screens.

        Args:
            address: RAM address of the tile map (default: 0xC3A0 for Pokemon)
            width: Screen width in tiles (default: 20)
            height: Screen height in tiles (default: 18)

        Returns:
            Grid of tile IDs (hex strings) organized by row
        """
        total = width * height
        if total > 1024:
            return {"error": f"Tile map too large: {total} tiles (max 1024)"}

        all_bytes = []
        remaining = total
        offset = 0
        while remaining > 0:
            chunk = min(remaining, 256)
            result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
                "start": (address + offset) & 0xFFFF,
                "length": chunk,
            })
            data = result.get("data", b"")
            all_bytes.extend(data)
            offset += chunk
            remaining -= chunk

        if len(all_bytes) < total:
            return {"error": f"Read only {len(all_bytes)} of {total} bytes"}

        tile_grid = []
        for y in range(height):
            row_start = y * width
            row_tiles = all_bytes[row_start:row_start + width]
            tile_grid.append([f"0x{t:02X}" for t in row_tiles])

        return {
            "address": f"0x{address:04X}",
            "width": width,
            "height": height,
            "tile_grid": tile_grid,
        }
