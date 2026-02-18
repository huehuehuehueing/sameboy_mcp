#!/usr/bin/env python3
"""Quick diagnostic test for mode detection."""

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

    if not Path(rom_path).exists() or not Path(lib_path).exists():
        print("ERROR: ROM or lib not found")
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
            routines = Routines(call_tool, state_reader, verbose=False)

            # Enable display and turbo
            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})
            await call_tool("run_frames", {"count": 60})

            print("Testing mode detection for 50 steps...", flush=True)
            print("=" * 60, flush=True)

            for step in range(1, 51):
                state = await state_reader.read_state()

                # Debug values
                ignore_input = await call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                joypad_sim = await call_tool("read_memory", {"address": mem.WRAM_SIM_JOYPAD_STATES_INDEX, "length": 1})
                ignore_val = ignore_input.get("bytes", [0])[0] if isinstance(ignore_input, dict) else 0
                joypad_val = joypad_sim.get("bytes", [0])[0] if isinstance(joypad_sim, dict) else 0

                print(f"[{step:2d}] Mode={state.mode.name:15s} Map={state.map_id:2d} Pos=({state.player_x},{state.player_y}) "
                      f"ignore={ignore_val:#04x} joypad={joypad_val:#04x}", flush=True)

                # Handle each mode
                if state.mode == GameMode.TITLE_SCREEN:
                    await routines.handle_title_screen()
                elif state.mode == GameMode.MAIN_MENU:
                    await routines.handle_main_menu(select_new_game=True)
                elif state.mode == GameMode.INTRO:
                    await routines.handle_intro()
                elif state.mode == GameMode.NAME_ENTRY:
                    text = state.screen_text.full_text.upper() if state.screen_text else ""
                    if "RIVAL" in text or "HIS NAME" in text:
                        await routines.enter_name("GARY")
                    else:
                        await routines.enter_name("ASH")
                elif state.mode == GameMode.DIALOG:
                    await routines.advance_text_once()
                elif state.mode == GameMode.OVERWORLD:
                    # If ignore_input is high, game is still in scripted mode
                    if ignore_val > 5:
                        print(f"    -> OVERWORLD but ignore_input={ignore_val:#x}, pressing A to advance script...", flush=True)
                        for _ in range(5):
                            await routines.press("a", 6)
                            await routines.wait_frames(20)
                        continue

                    print(f"    -> OVERWORLD! ignore_input={ignore_val:#x}, testing walk...", flush=True)
                    before_x, before_y = state.player_x, state.player_y
                    for d in ["down", "left", "right", "up"]:
                        await routines.walk(d, 1)
                        await routines.wait_frames(20)
                        after = await state_reader.read_state()
                        if after.player_x != before_x or after.player_y != before_y:
                            print(f"    -> SUCCESS: walked {d} to ({after.player_x},{after.player_y})", flush=True)
                            print("\nPlayer can walk! Test complete.", flush=True)
                            return
                    print(f"    -> Could not walk from ({before_x},{before_y})", flush=True)
                else:
                    await routines.press("b", 8)

                await routines.wait_frames(10)

            print("\nTest ended after 50 steps without successful walk")


if __name__ == "__main__":
    asyncio.run(main())
