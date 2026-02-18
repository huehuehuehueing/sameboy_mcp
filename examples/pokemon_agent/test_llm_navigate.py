#!/usr/bin/env python3
"""Test smart navigation from saved state."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

from examples.pokemon_agent.config import AgentConfig
from examples.pokemon_agent.game_state import GameStateReader
from examples.pokemon_agent.routines import Routines


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

            # Initialize components (no LLM - pure coded pathfinding)
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

            # Read initial state
            state = await state_reader.read_state()
            print(f"\nInitial: map={state.map_id} ({state.map_name}) pos=({state.player_x},{state.player_y})", flush=True)

            # Build ASCII map for display
            map_ascii = await routines._build_map_ascii(state)
            print(f"\nMap layout:\n{map_ascii}", flush=True)

            # Test smart navigation (coded BFS pathfinding)
            print("\n=== Testing smart navigation (coded BFS) ===", flush=True)
            initial_map = state.map_id

            success = await routines.smart_navigate(
                target_type="exit",
                max_steps=20,
                use_vision=False,  # No vision model needed
            )

            # Final state
            final_state = await state_reader.read_state()
            print(f"\nFinal: map={final_state.map_id} pos=({final_state.player_x},{final_state.player_y})", flush=True)

            if final_state.map_id != initial_map:
                print(f"SUCCESS! Navigated from map {initial_map} to map {final_state.map_id}", flush=True)
            elif success:
                print(f"Navigation completed but didn't change maps", flush=True)
            else:
                print(f"Navigation did not reach target", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
