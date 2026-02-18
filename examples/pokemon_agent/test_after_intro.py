#!/usr/bin/env python3
"""Test that after loading saved state, agent doesn't say 'Intro script running'."""

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

            async def read_byte(addr):
                r = await call_tool("read_memory", {"address": addr, "length": 1})
                return r.get("bytes", [0])[0] if isinstance(r, dict) else 0

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=False)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            print("Loading saved state (after intro)...", flush=True)
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await routines.wait_frames(30)

            print("\nTesting if agent correctly handles post-intro state:", flush=True)
            print("=" * 60, flush=True)

            # Simulate what main.py does
            _initial_spawn_handled = False

            for step in range(1, 21):
                state = await state_reader.read_state()
                ignore = await read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)

                print(f"[{step:2d}] Mode={state.mode.name:15s} Pos=({state.player_x},{state.player_y}) ignore={ignore:#04x}", flush=True)

                # This is the logic from main.py
                if not _initial_spawn_handled and state.map_id == 38 and state.party_count == 0:
                    if state.player_x == 3 and state.player_y == 6 and ignore > 10:
                        print("      -> Intro script running, pressing A...", flush=True)
                        await routines.press("a", 8)
                        await routines.wait_frames(30)
                        continue

                    if state.player_x != 3 or state.player_y != 6 or ignore <= 10:
                        print("      -> Spawn complete! Skipping intro check from now on.", flush=True)
                        _initial_spawn_handled = True

                # Normal overworld handling - try to walk
                if state.mode == GameMode.OVERWORLD:
                    print(f"      -> Normal OVERWORLD, finding exit...", flush=True)
                    before_x, before_y = state.player_x, state.player_y

                    # Try walking
                    for d in ["down", "left", "right", "up"]:
                        await routines.walk(d, 1)
                        await routines.wait_frames(20)
                        after = await state_reader.read_state()
                        if after.player_x != before_x or after.player_y != before_y:
                            print(f"      -> Walked {d} to ({after.player_x},{after.player_y})", flush=True)
                            break

            print("\n" + "=" * 60, flush=True)
            print("Test complete. If no 'Intro script running' messages appeared,", flush=True)
            print("the fix is working correctly!", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
