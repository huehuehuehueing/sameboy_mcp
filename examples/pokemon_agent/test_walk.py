#!/usr/bin/env python3
"""Test if player can eventually walk after intro."""

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
            routines = Routines(call_tool, state_reader, verbose=False)

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})
            await call_tool("run_frames", {"count": 60})

            print("Rapid-firing through intro (500 A presses)...", flush=True)

            # Just press A many times to get through all intro/scripts
            for i in range(500):
                await routines.press("a", 4)
                await routines.wait_frames(8)

                if i % 50 == 49:
                    state = await state_reader.read_state()
                    ignore = await call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                    ignore_val = ignore.get("bytes", [0])[0] if isinstance(ignore, dict) else 0
                    print(f"  [{i+1}] Mode={state.mode.name} Map={state.map_id} Pos=({state.player_x},{state.player_y}) ignore={ignore_val:#04x}", flush=True)

            print("\nNow testing walk after 500 A presses...", flush=True)

            for attempt in range(10):
                state = await state_reader.read_state()
                ignore = await call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                ignore_val = ignore.get("bytes", [0])[0] if isinstance(ignore, dict) else 0

                print(f"\nAttempt {attempt+1}: Mode={state.mode.name} Map={state.map_id} Pos=({state.player_x},{state.player_y}) ignore={ignore_val:#04x}", flush=True)

                if state.mode == GameMode.OVERWORLD:
                    before_x, before_y = state.player_x, state.player_y

                    for d in ["down", "left", "right", "up"]:
                        print(f"  Trying {d}...", flush=True)
                        await routines.walk(d, 1)
                        await routines.wait_frames(30)

                        after = await state_reader.read_state()
                        if after.player_x != before_x or after.player_y != before_y:
                            print(f"  SUCCESS! Walked {d} from ({before_x},{before_y}) to ({after.player_x},{after.player_y})", flush=True)

                            # Save state
                            print("\nSaving state for future testing...", flush=True)
                            result = await call_tool("save_state", {"name": "after_intro"})
                            if isinstance(result, dict) and "state_id" in result:
                                state_id = result["state_id"]
                                print(f"State saved: {state_id}", flush=True)

                                # Export to file
                                export_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")
                                Path(export_path).parent.mkdir(parents=True, exist_ok=True)
                                await call_tool("export_state", {"state_id": state_id, "file_path": export_path})
                                print(f"Exported to: {export_path}", flush=True)
                            return

                    print(f"  Could not walk from ({before_x},{before_y})", flush=True)

                    # Press more A buttons
                    print("  Pressing more A buttons...", flush=True)
                    for _ in range(50):
                        await routines.press("a", 4)
                        await routines.wait_frames(8)
                else:
                    # Handle other modes
                    if state.mode == GameMode.NAME_ENTRY:
                        text = state.screen_text.full_text.upper() if state.screen_text else ""
                        if "RIVAL" in text:
                            await routines.enter_name("GARY")
                        else:
                            await routines.enter_name("ASH")
                    else:
                        for _ in range(20):
                            await routines.press("a", 4)
                            await routines.wait_frames(8)

            print("\nFailed to walk after all attempts", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
