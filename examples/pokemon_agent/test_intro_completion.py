#!/usr/bin/env python3
"""Test that the intro completes and player can walk.

This test:
1. Runs through the intro sequence (title, name entry, Oak's speech)
2. Verifies the player reaches OVERWORLD mode
3. Tests that the player can actually walk
4. Saves a state after intro completion for future testing
"""

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
    # Find ROM
    rom_path = None
    rom_patterns = [
        "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc",
        "roms/Pokemon - Yellow Version (USA, Europe).gbc",
        "~/Downloads/Pokemon*.gbc",
    ]
    for pattern in rom_patterns:
        expanded = Path(pattern).expanduser()
        if expanded.exists():
            rom_path = str(expanded)
            break
        # Try glob
        for match in Path(".").glob(pattern):
            rom_path = str(match)
            break

    if not rom_path:
        print("ERROR: ROM not found. Place Pokemon Yellow ROM in roms/pokeyellow/")
        return

    # Find lib
    lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
    if not Path(lib_path).exists():
        print(f"ERROR: libsameboy.so not found at {lib_path}")
        return

    # Connect to MCP server
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
                    text = result.content[0].text
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
                return None

            state_reader = GameStateReader(call_tool)
            routines = Routines(call_tool, state_reader, verbose=True)

            # Enable display
            print("Enabling live display...")
            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_user_input", {"enabled": False})

            # Enable turbo
            print("Enabling turbo mode...")
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Let game initialize
            await call_tool("run_frames", {"count": 60})

            status = await call_tool("get_status", {})
            print(f"ROM: {status.get('rom_title', 'Unknown')}")

            max_steps = 100
            intro_complete = False
            player_walked = False
            saved_state_id = None

            print("\n" + "=" * 60)
            print("Testing Intro Completion + Save State")
            print("=" * 60 + "\n")

            for step in range(1, max_steps + 1):
                state = await state_reader.read_state()

                # Read debug values
                ignore_input = await call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                joypad_sim = await call_tool("read_memory", {"address": mem.WRAM_SIM_JOYPAD_STATES_INDEX, "length": 1})
                ignore_val = ignore_input.get("bytes", [0])[0] if isinstance(ignore_input, dict) else 0
                joypad_val = joypad_sim.get("bytes", [0])[0] if isinstance(joypad_sim, dict) else 0

                print(f"\n--- Step {step} ---")
                print(f"Mode: {state.mode.name} | Map: {state.map_id} ({state.map_name}) | Pos: ({state.player_x},{state.player_y})")
                print(f"Party: {state.party_count} | Badges: {state.badge_count} | ignore={ignore_val:#x} | joypad_sim={joypad_val:#x}")

                if state.screen_text and state.screen_text.has_text:
                    text_lines = [l.strip() for l in state.screen_text.lines if l.strip()]
                    if text_lines:
                        print(f"Screen: {' | '.join(text_lines[:2])[:60]}")

                # Handle based on mode
                if state.mode == GameMode.TITLE_SCREEN:
                    print("  -> Pressing Start...")
                    await routines.handle_title_screen()

                elif state.mode == GameMode.MAIN_MENU:
                    print("  -> Selecting New Game...")
                    await routines.handle_main_menu(select_new_game=True)

                elif state.mode == GameMode.INTRO:
                    print("  -> Advancing intro...")
                    await routines.handle_intro()

                elif state.mode == GameMode.NAME_ENTRY:
                    # Determine type from screen
                    text = state.screen_text.full_text.upper() if state.screen_text else ""
                    if "RIVAL" in text or "HIS NAME" in text:
                        print("  -> Entering rival name: GARY")
                        await routines.enter_name("GARY")
                    else:
                        print("  -> Entering player name: ASH")
                        await routines.enter_name("ASH")

                elif state.mode == GameMode.DIALOG:
                    # If we're in a real map with warps, this might be initial dialog
                    if state.map_id > 0 and state.map_info and state.map_info.warps:
                        print("  -> In map with warps, advancing dialog...")
                        for _ in range(5):
                            await routines.press("a", 6)
                            await routines.wait_frames(15)
                    else:
                        print("  -> Advancing dialog...")
                        await routines.advance_text_once()

                elif state.mode == GameMode.OVERWORLD:
                    print("  -> OVERWORLD mode reached!")
                    intro_complete = True

                    # Check if ignore_input is still high
                    if ignore_val > 10:
                        print(f"  -> ignore_input still high ({ignore_val}), pressing A to clear...")
                        for _ in range(10):
                            await routines.press("a", 6)
                            await routines.wait_frames(20)
                        continue

                    # Try to walk
                    before_x, before_y = state.player_x, state.player_y
                    print(f"  -> Testing walk from ({before_x},{before_y})...")

                    # Try each direction
                    for direction in ["down", "left", "right", "up"]:
                        await routines.walk(direction, 1)
                        await routines.wait_frames(30)

                        after_state = await state_reader.read_state()
                        if after_state.player_x != before_x or after_state.player_y != before_y:
                            print(f"  -> SUCCESS! Walked {direction} to ({after_state.player_x},{after_state.player_y})")
                            player_walked = True
                            break

                    if player_walked:
                        # Save state for future testing
                        print("\n  -> Saving state for future testing...")
                        result = await call_tool("save_state", {"name": "after_intro"})
                        if isinstance(result, dict) and "state_id" in result:
                            saved_state_id = result["state_id"]
                            print(f"  -> State saved: {saved_state_id}")

                            # Also export to file for persistence
                            export_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")
                            Path(export_path).parent.mkdir(parents=True, exist_ok=True)
                            export_result = await call_tool("export_state", {
                                "state_id": saved_state_id,
                                "file_path": export_path,
                            })
                            if isinstance(export_result, dict) and export_result.get("success"):
                                print(f"  -> State exported to: {export_path}")
                        break

                else:
                    print(f"  -> Unknown mode, pressing B...")
                    await routines.press("b", 8)

                # Small delay between steps
                await routines.wait_frames(15)

            # Summary
            print("\n" + "=" * 60)
            print("Test Results")
            print("=" * 60)
            print(f"Intro completed:  {'YES' if intro_complete else 'NO'}")
            print(f"Player can walk:  {'YES' if player_walked else 'NO'}")
            print(f"State saved:      {saved_state_id or 'NO'}")

            if not intro_complete:
                print("\nFAILED: Agent never reached OVERWORLD mode")
            elif not player_walked:
                print("\nFAILED: Player could not walk even in OVERWORLD mode")
            else:
                print("\nSUCCESS: Intro completed and player can walk!")


if __name__ == "__main__":
    asyncio.run(main())
