# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Display-related MCP tools."""

import base64
import io
import json
import os

from mcp.server import FastMCP
from mcp.server.fastmcp.utilities.types import Image as McpImage
from mcp.types import TextContent

from ..emulator.thread import EmulatorThread, CommandType
from .utils import require_rom


def _pixels_to_image(pixels: bytes, width: int, height: int, scale: int = 1):
    """Convert raw ARGB pixel data to a PIL Image with optional scaling.

    SameBoy stores pixels as little-endian 0xAARRGGBB (BGRA in memory).
    This converts to RGBA for PIL.

    Args:
        pixels: Raw pixel bytes from the emulator.
        width: Screen width in pixels.
        height: Screen height in pixels.
        scale: Upscale factor (uses nearest-neighbor).

    Returns:
        A PIL Image in RGBA mode.
    """
    from PIL import Image

    img_data = bytearray(width * height * 4)
    for i in range(width * height):
        offset = i * 4
        b = pixels[offset]
        g = pixels[offset + 1]
        r = pixels[offset + 2]
        a = pixels[offset + 3]
        img_data[offset] = r
        img_data[offset + 1] = g
        img_data[offset + 2] = b
        img_data[offset + 3] = a

    img = Image.frombytes("RGBA", (width, height), bytes(img_data))
    if scale > 1:
        img = img.resize(
            (width * scale, height * scale),
            resample=Image.NEAREST,
        )
    return img


def register_display_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register display-related tools with the MCP server."""

    @server.tool()
    async def capture_screen(format: str = "png", scale: int = 1):
        """
        Capture the current screen.

        Note: After loading a save state, you must run at least one frame
        (e.g. run_frames(1)) before the screen buffer contains valid data.

        Args:
            format: Image format ("png" or "raw")
            scale: Upscale factor (1-4, default 1). Uses nearest-neighbor for crisp pixels.

        Returns:
            Screen image data with dimensions
        """
        if err := require_rom(emu_thread):
            return err
        scale = max(1, min(4, scale))
        # Get screen size
        size_result = emu_thread.send_command(CommandType.GET_SCREEN_SIZE)
        if size_result.get("error"):
            return {"error": size_result["error"]}

        width = size_result["width"]
        height = size_result["height"]

        # Get pixel data
        screen_result = emu_thread.send_command(CommandType.GET_SCREEN)
        if screen_result.get("error"):
            return {"error": screen_result["error"]}

        pixels = screen_result["pixels"]

        if format.lower() == "raw":
            return {
                "width": width,
                "height": height,
                "format": "ARGB32",
                "data_base64": base64.b64encode(pixels).decode("ascii"),
            }

        # Convert to PNG and return as MCP ImageContent
        try:
            img = _pixels_to_image(pixels, width, height, scale)

            buf = io.BytesIO()
            img.save(buf, format="PNG")

            return [
                McpImage(data=buf.getvalue(), format="png"),
                TextContent(
                    type="text",
                    text=json.dumps({
                        "width": width * scale,
                        "height": height * scale,
                    }),
                ),
            ]

        except ImportError:
            # PIL not available, return raw
            return {
                "width": width,
                "height": height,
                "format": "ARGB32",
                "note": "PIL not installed, returning raw pixels",
                "data_base64": base64.b64encode(pixels).decode("ascii"),
            }

    @server.tool()
    async def save_screenshot(path: str, scale: int = 1) -> dict:
        """
        Save a screenshot PNG to a filesystem path.

        Note: After loading a save state, you must run at least one frame
        (e.g. run_frames(1)) before the screen buffer contains valid data.

        Args:
            path: Filesystem path to write the PNG file to.
            scale: Upscale factor (1-4, default 2). Uses nearest-neighbor for crisp pixels.

        Returns:
            Success status, path, and image dimensions.
        """
        if err := require_rom(emu_thread):
            return err
        scale = max(1, min(4, scale))

        # Get screen size
        size_result = emu_thread.send_command(CommandType.GET_SCREEN_SIZE)
        if size_result.get("error"):
            return {"error": size_result["error"]}

        width = size_result["width"]
        height = size_result["height"]

        # Get pixel data
        screen_result = emu_thread.send_command(CommandType.GET_SCREEN)
        if screen_result.get("error"):
            return {"error": screen_result["error"]}

        pixels = screen_result["pixels"]

        try:
            img = _pixels_to_image(pixels, width, height, scale)
        except ImportError:
            return {"error": "PIL (Pillow) is required for save_screenshot"}

        # Resolve and create parent directories
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)

        img.save(abs_path, format="PNG")

        return {
            "success": True,
            "path": abs_path,
            "width": width * scale,
            "height": height * scale,
        }

    @server.tool()
    async def get_sprites() -> dict:
        """
        Get information about all sprites (OAM entries).

        Returns:
            List of sprite objects with position, tile, flags
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.GET_OAM)

        if result.get("error"):
            return {"error": result["error"]}

        return {
            "count": len(result.get("sprites", [])),
            "sprites": result.get("sprites", []),
        }

    @server.tool()
    async def get_screen_info() -> dict:
        """
        Get current screen dimensions and frame info.

        Returns:
            Screen dimensions and related information
        """
        if err := require_rom(emu_thread):
            return err
        result = emu_thread.send_command(CommandType.GET_SCREEN_SIZE)

        if result.get("error"):
            return {"error": result["error"]}

        status = emu_thread.send_command(CommandType.GET_STATUS)

        return {
            "width": result["width"],
            "height": result["height"],
            "frame_count": status.get("frame_count", 0),
        }
