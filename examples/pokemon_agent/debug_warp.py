#!/usr/bin/env python3
"""Debug warp mechanism in Pokemon Yellow."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

from examples.pokemon_agent.game_state import GameStateReader, GameMode
from examples.pokemon_agent.routines import Routines
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

            async def read_bytes(addr, length):
                r = await call_tool("read_memory", {"address": addr, "length": length})
                return r.get("bytes", []) if isinstance(r, dict) else []

            async def read_byte(addr):
                r = await read_bytes(addr, 1)
                return r[0] if r else 0

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=False)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            print("Loading saved state...", flush=True)
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(30)

            # Walk to warp position (2,7)
            await routines.walk("down", 1)
            await routines.wait_frames(10)

            # Read detailed state
            state = await state_reader.read_state()
            print(f"\nPlayer at: ({state.player_x},{state.player_y}) on map {state.map_id}", flush=True)
            print(f"Facing: {state.facing}, Tile ahead: {state.tile_ahead:#04x}", flush=True)

            # Read raw warp data
            num_warps = await read_byte(mem.WRAM_NUM_WARPS)
            print(f"\nRaw warp data ({num_warps} warps):", flush=True)

            for i in range(num_warps):
                base = mem.WRAM_WARP_ENTRIES + (i * 4)
                data = await read_bytes(base, 4)
                print(f"  Warp {i} @ {base:#06x}: y={data[0]}, x={data[1]}, warp_id={data[2]}, dest={data[3]}", flush=True)

            # Read map info
            map_width = await read_byte(mem.WRAM_CUR_MAP_WIDTH)
            map_height = await read_byte(mem.WRAM_CUR_MAP_HEIGHT)
            print(f"\nMap dimensions: {map_width}x{map_height}", flush=True)

            # Check tile ahead
            tile_ahead = await read_byte(mem.WRAM_TILE_IN_FRONT)
            print(f"Tile ahead: {tile_ahead:#04x}", flush=True)

            # Face down first
            print("\n=== Facing DOWN first, then trying warp ===", flush=True)
            await routines.press("down", 4)  # Just face, don't walk
            await routines.wait_frames(10)

            state = await state_reader.read_state()
            print(f"Now facing: {state.facing}, tile ahead: {state.tile_ahead:#04x}", flush=True)

            # Try different approaches
            print("\n=== Method 1: Walk away and back ===", flush=True)
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(10)

            # Walk to warp position first
            before_map = (await state_reader.read_state()).map_id
            await routines.walk("down", 1)
            await routines.wait_frames(10)

            state = await state_reader.read_state()
            print(f"At warp: ({state.player_x},{state.player_y}) map={state.map_id}", flush=True)

            # Now walk UP (away from warp)
            await routines.walk("up", 1)
            await routines.wait_frames(10)
            state = await state_reader.read_state()
            print(f"Stepped back: ({state.player_x},{state.player_y})", flush=True)

            # Now walk DOWN onto the warp again
            await routines.walk("down", 1)
            await routines.wait_frames(60)  # Wait for warp
            state = await state_reader.read_state()

            if state.map_id != before_map:
                print(f"Warp triggered! Now on map {state.map_id}", flush=True)
            else:
                print(f"No warp (map={state.map_id})", flush=True)

                # Check if we need to walk DOWN again while on the warp
                print("\n=== Method 2: Continue walking down on warp ===", flush=True)
                await routines.press("down", 64)
                await routines.wait_frames(120)
                state = await state_reader.read_state()

                if state.map_id != before_map:
                    print(f"Warp triggered! Now on map {state.map_id}", flush=True)
                else:
                    print(f"Still no warp (map={state.map_id})", flush=True)

                    # Maybe the stairs are a special tile that needs continuous walking?
                    print("\n=== Method 3: Multiple walk steps ===", flush=True)
                    for i in range(5):
                        await routines.walk("down", 1)
                        await routines.wait_frames(30)
                        state = await state_reader.read_state()
                        print(f"  Step {i+1}: map={state.map_id} pos=({state.player_x},{state.player_y})", flush=True)
                        if state.map_id != before_map:
                            print(f"Warp triggered!", flush=True)
                            break

            # Also try going from a different direction
            print("\n=== Method 4: Approach from left ===", flush=True)
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(10)

            before_map = (await state_reader.read_state()).map_id
            # From saved state at (2,6), go left then down then right onto warp
            await routines.walk("left", 1)
            await routines.wait_frames(10)
            await routines.walk("down", 1)
            await routines.wait_frames(10)
            await routines.walk("right", 1)  # This should land on the warp
            await routines.wait_frames(60)

            state = await state_reader.read_state()
            print(f"After approach from left: map={state.map_id} pos=({state.player_x},{state.player_y})", flush=True)

            if state.map_id != before_map:
                print(f"Warp triggered from side approach!", flush=True)

            # Final state
            state = await state_reader.read_state()
            print(f"\nFinal: map {state.map_id} at ({state.player_x},{state.player_y})", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
