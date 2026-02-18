#!/usr/bin/env python3
"""Test walking to the ROM-defined warp position (7,1)."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

from examples.pokemon_agent.game_state import GameStateReader
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

            async def read_byte(addr):
                r = await call_tool("read_memory", {"address": addr, "length": 1})
                return r.get("bytes", [0])[0] if isinstance(r, dict) else 0

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=True)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(30)

            state = await state_reader.read_state()
            print(f"Initial: map={state.map_id} pos=({state.player_x},{state.player_y})", flush=True)

            # ROM says warp is at x=7, y=1
            # Try to walk there
            target_x, target_y = 7, 1
            print(f"\n=== Trying to walk to ROM warp position ({target_x},{target_y}) ===", flush=True)

            before_map = state.map_id

            # Navigate to target
            for step in range(20):
                state = await state_reader.read_state()
                if state.map_id != before_map:
                    print(f"\nWARPED! Now on map {state.map_id} at ({state.player_x},{state.player_y})", flush=True)
                    return

                dx = target_x - state.player_x
                dy = target_y - state.player_y

                if dx == 0 and dy == 0:
                    print(f"\nReached ({target_x},{target_y})!", flush=True)
                    # Try to trigger warp
                    print("Trying all directions to trigger warp...", flush=True)
                    for direction in ["down", "up", "left", "right"]:
                        await routines.trigger_warp(direction)
                        new_state = await state_reader.read_state()
                        if new_state.map_id != before_map:
                            print(f"WARPED with {direction}! Now on map {new_state.map_id}", flush=True)
                            return
                    print("Warp didn't trigger at ROM position either!", flush=True)
                    break

                # Choose direction
                if abs(dy) > abs(dx):
                    direction = "down" if dy > 0 else "up"
                else:
                    direction = "right" if dx > 0 else "left"

                print(f"Step {step}: ({state.player_x},{state.player_y}) -> {direction} (target: ({target_x},{target_y}))", flush=True)
                success = await routines.walk(direction, 1)

                if not success:
                    # Try perpendicular direction
                    if direction in ["up", "down"]:
                        alt = "right" if dx > 0 else "left"
                    else:
                        alt = "down" if dy > 0 else "up"
                    print(f"  blocked, trying {alt}...", flush=True)
                    await routines.walk(alt, 1)

                await routines.wait_frames(5)

            # Final state
            state = await state_reader.read_state()
            print(f"\nFinal: map={state.map_id} pos=({state.player_x},{state.player_y})", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
