#!/usr/bin/env python3
"""Test loading the saved state and verifying player can walk."""

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


async def main():
    rom_path = "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc"
    lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
    state_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")

    if not Path(state_path).exists():
        print(f"ERROR: State file not found at {state_path}")
        print("Run create_after_intro_state.py first")
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

            print("Loading saved state...")
            result = await call_tool("import_state", {"file_path": state_path})
            if isinstance(result, dict) and "error" in result:
                print(f"ERROR: {result['error']}")
                return

            state_id = result.get("state_id")
            print(f"State imported with ID: {state_id}")

            # Load the state into the emulator
            load_result = await call_tool("load_state", {"state_id": state_id})
            if isinstance(load_result, dict) and "error" in load_result:
                print(f"ERROR loading state: {load_result['error']}")
                return

            print(f"State loaded successfully!")

            # Wait a bit for the state to stabilize
            await routines.wait_frames(30)

            # Read current state
            state = await state_reader.read_state()
            print(f"\nCurrent state:")
            print(f"  Mode: {state.mode.name}")
            print(f"  Map: {state.map_id} ({state.map_name})")
            print(f"  Position: ({state.player_x}, {state.player_y})")
            print(f"  Party count: {state.party_count}")

            # Try to walk
            print(f"\nTesting movement...")
            before_x, before_y = state.player_x, state.player_y

            for d in ["down", "right", "up", "left"]:
                print(f"  Trying {d}...")
                await routines.walk(d, 1)
                await routines.wait_frames(30)
                after = await state_reader.read_state()
                if after.player_x != before_x or after.player_y != before_y:
                    print(f"\n  SUCCESS! Walked {d} from ({before_x},{before_y}) to ({after.player_x},{after.player_y})")
                    print("\nState load test PASSED - player can walk!")
                    return

            print(f"\nFAILED: Could not walk from ({before_x},{before_y})")


if __name__ == "__main__":
    asyncio.run(main())
