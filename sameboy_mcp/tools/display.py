# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""Display-related MCP tools."""

import base64
import io

from mcp.server import FastMCP

from ..emulator.thread import EmulatorThread, CommandType
from .utils import require_rom


def register_display_tools(server: FastMCP, emu_thread: EmulatorThread) -> None:
    """Register display-related tools with the MCP server."""

    @server.tool()
    async def capture_screen(format: str = "png", scale: int = 1) -> dict:
        """
        Capture the current screen.

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

        # Convert to PNG using PIL
        try:
            from PIL import Image

            # SameBoy outputs ARGB, need to convert to RGBA for PIL
            # Format: 0xAARRGGBB in memory
            img_data = bytearray(width * height * 4)

            for i in range(width * height):
                offset = i * 4
                # Read as ARGB (little-endian: BGRA in memory)
                b = pixels[offset]
                g = pixels[offset + 1]
                r = pixels[offset + 2]
                a = pixels[offset + 3]

                # Write as RGBA
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

            buf = io.BytesIO()
            img.save(buf, format="PNG")

            return {
                "width": width * scale,
                "height": height * scale,
                "format": "png",
                "data_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
            }

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
