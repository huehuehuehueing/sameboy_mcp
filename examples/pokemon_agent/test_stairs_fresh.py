#!/usr/bin/env python3
"""Test stairs from a fresh game start to see if they work naturally."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

import examples.pokemon_agent.memory_map as mem
from examples.pokemon_agent.game_state import GameStateReader, GameMode
from examples.pokemon_agent.routines import Routines


async def main():
    rom_path = "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc"
    lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"

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
            routines = Routines(call_tool, state_reader, verbose=False)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            print("Running through intro from fresh start...")
            print("=" * 60)

            can_walk = False
            for step in range(500):
                state = await state_reader.read_state()
                ignore = await read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)

                if step % 40 == 0 or (state.mode == GameMode.OVERWORLD and not can_walk):
                    print(f"[{step:3d}] Mode={state.mode.name:15s} Map={state.map_id} Pos=({state.player_x},{state.player_y}) ignore={ignore:#04x}", flush=True)

                # Handle based on mode
                if state.mode == GameMode.TITLE_SCREEN:
                    await routines.press("start", 8)
                    await routines.wait_frames(60)

                elif state.mode == GameMode.MAIN_MENU:
                    await routines.press("a", 8)
                    await routines.wait_frames(60)

                elif state.mode == GameMode.NAME_ENTRY:
                    text = state.screen_text.full_text.upper() if state.screen_text else ""
                    if "RIVAL" in text or "HIS NAME" in text:
                        await routines.enter_name("GARY")
                    else:
                        await routines.enter_name("ASH")
                    await routines.wait_frames(30)

                elif state.mode == GameMode.INTRO or state.mode == GameMode.DIALOG:
                    await routines.press("a", 6)
                    await routines.wait_frames(30)

                elif state.mode == GameMode.OVERWORLD:
                    if ignore > 10:
                        await routines.press("a", 6)
                        await routines.wait_frames(30)
                    else:
                        if not can_walk:
                            # First time we can walk - test it
                            before_x, before_y = state.player_x, state.player_y
                            for d in ["down", "left", "right", "up"]:
                                await routines.walk(d, 1)
                                await routines.wait_frames(20)
                                after = await state_reader.read_state()
                                if after.player_x != before_x or after.player_y != before_y:
                                    can_walk = True
                                    print(f"\n>>> Player can walk! Walked {d} from ({before_x},{before_y}) to ({after.player_x},{after.player_y})")
                                    break

                        if can_walk:
                            # Now try to get to the stairs and use them
                            state = await state_reader.read_state()
                            before_map = state.map_id

                            # Check warps
                            num_warps = await read_byte(mem.WRAM_NUM_WARPS)
                            print(f"\n>>> At ({state.player_x},{state.player_y}) on map {state.map_id}, {num_warps} warps:", flush=True)

                            for i in range(num_warps):
                                base = mem.WRAM_WARP_ENTRIES + (i * 4)
                                data = await read_bytes(base, 4)
                                print(f"    Warp {i}: ({data[1]},{data[0]}) -> map {data[3]} (warp_id={data[2]})", flush=True)

                            # Walk to stairs position (2,7)
                            print("\n>>> Walking to stairs...", flush=True)
                            while state.player_y < 7:
                                await routines.walk("down", 1)
                                await routines.wait_frames(20)
                                state = await state_reader.read_state()
                                print(f"    Now at ({state.player_x},{state.player_y})", flush=True)
                                if state.map_id != before_map:
                                    print(f">>> WARPED! Now on map {state.map_id}!", flush=True)
                                    return

                            # If still on same map, try to trigger warp
                            if state.player_y == 7:
                                print("\n>>> At stairs position, trying to trigger warp...", flush=True)
                                for attempt in range(3):
                                    await routines.press("down", 64)
                                    await routines.wait_frames(60)
                                    state = await state_reader.read_state()
                                    if state.map_id != before_map:
                                        print(f">>> WARPED! Now on map {state.map_id}!", flush=True)
                                        return
                                    print(f"    Attempt {attempt+1}: still on map {state.map_id}", flush=True)

                            print(f"\n>>> Could not trigger warp. Final map: {state.map_id}", flush=True)
                            return

                        await routines.wait_frames(30)
                else:
                    await routines.press("b", 6)
                    await routines.wait_frames(30)

            print("\nTest ended after 500 steps")


if __name__ == "__main__":
    asyncio.run(main())
