#!/usr/bin/env python3
"""Debug the map layout and warp positions."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

from examples.pokemon_agent.game_state import GameStateReader
import examples.pokemon_agent.memory_map as mem


async def main():
    rom_path = "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc"
    lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
    state_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")

    server_params = StdioServerParameters(
        command='python',
        args=['-m', 'sameboy_mcp.server', '--lib', lib_path, '--rom', rom_path, '--model', 'CGB_E'],
        cwd=str(Path(__file__).parent.parent.parent),
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call_tool(name, args):
                result = await session.call_tool(name, args)
                if result.content:
                    try:
                        return json.loads(result.content[0].text)
                    except:
                        return result.content[0].text
                return None

            async def read_byte(addr):
                r = await call_tool("read_memory", {"address": addr, "length": 1})
                return r.get("bytes", [0])[0] if isinstance(r, dict) else 0

            async def read_bytes(addr, length):
                r = await call_tool("read_memory", {"address": addr, "length": length})
                return r.get("bytes", []) if isinstance(r, dict) else []

            state_reader = GameStateReader(call_tool)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True})

            # Load saved state
            print("Loading saved state...", flush=True)
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await call_tool("run_frames", {"count": 30})

            # Read map info
            state = await state_reader.read_state()
            print(f"\nCurrent State:", flush=True)
            print(f"  Map: {state.map_id} ({state.map_name})", flush=True)
            print(f"  Player position: ({state.player_x}, {state.player_y})", flush=True)

            # Read map dimensions
            map_width = await read_byte(mem.WRAM_CUR_MAP_WIDTH)
            map_height = await read_byte(mem.WRAM_CUR_MAP_HEIGHT)
            print(f"  Map size: {map_width}x{map_height}", flush=True)

            # Read warp data
            num_warps = await read_byte(mem.WRAM_NUM_WARPS)
            print(f"\nWarps ({num_warps}):", flush=True)

            for i in range(num_warps):
                base = mem.WRAM_WARP_ENTRIES + (i * 4)
                data = await read_bytes(base, 4)
                if len(data) >= 4:
                    y, x, warp_id, dest_map = data[0], data[1], data[2], data[3]
                    print(f"  Warp {i}: ({x}, {y}) -> map {dest_map} (warp_id={warp_id})", flush=True)

            # Read sprite data to see NPCs
            num_sprites = await read_byte(mem.WRAM_NUM_SPRITES)
            print(f"\nSprites ({num_sprites}):", flush=True)

            for i in range(min(num_sprites + 1, 8)):
                base = mem.WRAM_SPRITE_DATA + (i * 16)
                data = await read_bytes(base, 16)
                if len(data) >= 14:
                    picture_id = data[0]
                    map_y = data[4]
                    map_x = data[6]
                    if picture_id != 0 or i == 0:
                        kind = "Player" if i == 0 else f"NPC {i}"
                        print(f"  {kind}: ({map_x}, {map_y}) pic={picture_id}", flush=True)

            # Read the screen tile map to visualize
            print(f"\nScreen Tiles (decoded):", flush=True)
            tile_data = await read_bytes(mem.WRAM_TILE_MAP, 360)

            for row in range(18):
                row_tiles = tile_data[row * 20:(row + 1) * 20]
                line = ""
                for tile in row_tiles:
                    # Simple visualization
                    if tile == 0x7F:  # space
                        line += " "
                    elif 0x80 <= tile <= 0x99:  # A-Z
                        line += chr(tile - 0x80 + ord('A'))
                    elif tile == 0x00:
                        line += "."
                    else:
                        line += "?"
                print(f"  {row:2d}: {line}", flush=True)

            print("\n" + "=" * 60, flush=True)
            print("Check the live display window to see where the stairs are!", flush=True)
            print("The player should walk to the stairs (usually bottom of room)", flush=True)

            # Keep display open for a moment
            await call_tool("run_frames", {"count": 300})


if __name__ == "__main__":
    asyncio.run(main())
