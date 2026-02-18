#!/usr/bin/env python3
"""Create and save a state after the intro completes for future testing."""

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

    if not Path(rom_path).exists():
        print(f"ERROR: ROM not found at {rom_path}")
        return
    if not Path(lib_path).exists():
        print(f"ERROR: lib not found at {lib_path}")
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

            print("Running through intro to create save state...")
            print("This may take a while (500+ steps)...")
            print("=" * 60)

            for step in range(600):  # Increased from 200
                state = await state_reader.read_state()
                ignore = await read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)

                if step % 20 == 0:
                    print(f"[{step:3d}] Mode={state.mode.name:15s} Map={state.map_id} Pos=({state.player_x},{state.player_y}) ignore={ignore:#04x}")

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
                        # Try to walk around a bit first to let game fully initialize
                        before_x, before_y = state.player_x, state.player_y
                        walked = False

                        for d in ["down", "left", "right", "up"]:
                            await routines.walk(d, 1)
                            await routines.wait_frames(30)
                            after = await state_reader.read_state()
                            if after.player_x != before_x or after.player_y != before_y:
                                walked = True
                                print(f"\n[{step}] Walked {d} from ({before_x},{before_y}) to ({after.player_x},{after.player_y})")
                                break

                        if walked:
                            # Walk around a bit more to ensure game is fully initialized
                            print("Walking around to ensure game is stable...")
                            for _ in range(5):
                                await routines.wait_frames(60)
                                cur = await state_reader.read_state()
                                for d in ["up", "left", "down", "right"]:
                                    bx, by = cur.player_x, cur.player_y
                                    await routines.walk(d, 1)
                                    await routines.wait_frames(20)
                                    cur = await state_reader.read_state()
                                    if cur.player_x != bx or cur.player_y != by:
                                        break

                            # Wait extra frames for any pending animations
                            await routines.wait_frames(120)

                            # Now save the state
                            final_state = await state_reader.read_state()
                            print(f"Final position: ({final_state.player_x},{final_state.player_y}) on map {final_state.map_id}")

                            print("\nSaving state...")
                            result = await call_tool("save_state", {"name": "after_intro"})
                            if isinstance(result, dict) and "state_id" in result:
                                state_id = result["state_id"]
                                print(f"State saved with ID: {state_id}")

                                # Export to file
                                save_dir = Path(__file__).parent / "saved_states"
                                save_dir.mkdir(parents=True, exist_ok=True)
                                export_path = str(save_dir / "after_intro.sav")

                                export_result = await call_tool("export_state", {
                                    "state_id": state_id,
                                    "file_path": export_path,
                                })
                                if isinstance(export_result, dict) and export_result.get("success"):
                                    print(f"State exported to: {export_path}")
                                    print(f"\nTo use this state in future tests, call:")
                                    print(f'  await call_tool("import_state", {{"file_path": "{export_path}"}})')
                                else:
                                    print(f"Export failed: {export_result}")

                                return

                        print(f"[{step}] Could not walk from ({before_x},{before_y}), continuing...")
                        await routines.press("a", 6)
                        await routines.wait_frames(30)
                else:
                    await routines.press("b", 6)
                    await routines.wait_frames(30)

            print("\nFailed to complete intro after 200 steps")


if __name__ == "__main__":
    asyncio.run(main())
