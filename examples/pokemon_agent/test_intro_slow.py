#!/usr/bin/env python3
"""Run through intro slowly to understand what's needed."""

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

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=True)

            await call_tool("enable_live_display", {"scale": 2})
            # NO turbo - run at normal speed to see what's happening
            await call_tool("set_turbo", {"enabled": False})

            print("Running intro at normal speed...", flush=True)
            print("=" * 60, flush=True)

            for step in range(100):
                state = await state_reader.read_state()
                ignore = await read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)

                print(f"\n[{step:3d}] Mode={state.mode.name:15s} Map={state.map_id} Pos=({state.player_x},{state.player_y}) ignore={ignore:#04x}", flush=True)

                if state.screen_text and state.screen_text.has_text:
                    lines = [l.strip() for l in state.screen_text.lines if l.strip()]
                    if lines:
                        print(f"      Text: {' | '.join(lines[:2])[:60]}", flush=True)

                # Handle based on mode
                if state.mode == GameMode.TITLE_SCREEN:
                    print("      -> Press Start", flush=True)
                    await routines.press("start", 8)
                    await routines.wait_frames(120)

                elif state.mode == GameMode.MAIN_MENU:
                    print("      -> Select New Game", flush=True)
                    await routines.press("a", 8)
                    await routines.wait_frames(120)

                elif state.mode == GameMode.NAME_ENTRY:
                    text = state.screen_text.full_text.upper() if state.screen_text else ""
                    if "RIVAL" in text or "HIS NAME" in text:
                        print("      -> Enter rival name: GARY", flush=True)
                        await routines.enter_name("GARY")
                    else:
                        print("      -> Enter player name: ASH", flush=True)
                        await routines.enter_name("ASH")
                    await routines.wait_frames(60)

                elif state.mode == GameMode.INTRO:
                    print("      -> Press A to skip intro", flush=True)
                    await routines.press("a", 8)
                    await routines.wait_frames(60)

                elif state.mode == GameMode.DIALOG:
                    print("      -> Press A to advance dialog", flush=True)
                    await routines.press("a", 8)
                    await routines.wait_frames(60)

                elif state.mode == GameMode.OVERWORLD:
                    if ignore > 10:
                        print(f"      -> In overworld but ignore={ignore:#x}, waiting/pressing A", flush=True)
                        await routines.press("a", 8)
                        await routines.wait_frames(60)
                    else:
                        print(f"      -> In overworld with ignore={ignore:#x}, trying to walk!", flush=True)
                        before_x, before_y = state.player_x, state.player_y

                        for d in ["down", "left", "right", "up"]:
                            await routines.walk(d, 1)
                            await routines.wait_frames(60)
                            after = await state_reader.read_state()
                            if after.player_x != before_x or after.player_y != before_y:
                                print(f"      -> SUCCESS! Walked {d} to ({after.player_x},{after.player_y})", flush=True)
                                print("\n\nPlayer can walk! Saving state...", flush=True)

                                # Save state
                                result = await call_tool("save_state", {"name": "after_intro"})
                                if isinstance(result, dict) and "state_id" in result:
                                    print(f"State saved: {result['state_id']}", flush=True)
                                return

                        print(f"      -> Could not walk from ({before_x},{before_y})", flush=True)

                else:
                    print(f"      -> Unknown mode, pressing B", flush=True)
                    await routines.press("b", 8)
                    await routines.wait_frames(60)

            print("\n\nTest ended without successful walk", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
