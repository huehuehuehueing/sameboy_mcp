#!/usr/bin/env python3
"""Test warp/stairs triggering from saved state."""

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

    if not Path(state_path).exists():
        print("ERROR: No saved state. Run create_after_intro_state.py first")
        return

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

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=True)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            print("Loading saved state (after intro)...", flush=True)
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(30)

            # Read initial position
            state = await state_reader.read_state()
            print(f"\nInitial: map={state.map_id} ({state.map_name}) pos=({state.player_x},{state.player_y})", flush=True)

            # Show warps
            if state.map_info and state.map_info.warps:
                for warp in state.map_info.warps:
                    print(f"  Warp: ({warp.x},{warp.y}) -> map {warp.dest_map}", flush=True)

            # Walk to warp position (2,7)
            print("\n=== Walking to warp position (2,7) ===", flush=True)
            for i in range(15):
                state = await state_reader.read_state()
                before_map = state.map_id

                # Check if on warp
                on_warp = False
                if state.map_info and state.map_info.warps:
                    for warp in state.map_info.warps:
                        if warp.x == state.player_x and warp.y == state.player_y:
                            on_warp = True
                            print(f"\nStep {i}: ON WARP at ({state.player_x},{state.player_y})!", flush=True)

                            # Try to trigger the warp
                            print("Triggering warp with 'down'...", flush=True)
                            warped = await routines.trigger_warp("down")

                            after = await state_reader.read_state()
                            if after.map_id != before_map:
                                print(f"SUCCESS! Warped from map {before_map} to map {after.map_id}", flush=True)
                                print(f"New position: ({after.player_x},{after.player_y})", flush=True)
                                return
                            else:
                                print(f"Down didn't work, trying other directions...", flush=True)
                                for direction in ["up", "left", "right"]:
                                    warped = await routines.trigger_warp(direction)
                                    after = await state_reader.read_state()
                                    if after.map_id != before_map:
                                        print(f"SUCCESS! Warped with {direction} to map {after.map_id}", flush=True)
                                        return
                                print(f"Warp didn't trigger with any direction", flush=True)
                            break

                if not on_warp:
                    # Navigate to warp at (2,7)
                    target_x, target_y = 2, 7
                    dx = target_x - state.player_x
                    dy = target_y - state.player_y

                    if dy > 0:
                        direction = "down"
                    elif dy < 0:
                        direction = "up"
                    elif dx > 0:
                        direction = "right"
                    elif dx < 0:
                        direction = "left"
                    else:
                        print(f"Step {i}: Already at target but not on warp?", flush=True)
                        break

                    print(f"Step {i}: pos=({state.player_x},{state.player_y}) - walking {direction} towards (2,7)...", flush=True)
                    success = await routines.walk(direction, 1)

                    # Check for warp during walk
                    after = await state_reader.read_state()
                    if after.map_id != before_map:
                        print(f"WARPED during walk! Now on map {after.map_id}", flush=True)
                        return

                    await routines.wait_frames(10)

            # Final check
            state = await state_reader.read_state()
            print(f"\nFinal: map={state.map_id} pos=({state.player_x},{state.player_y})", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
