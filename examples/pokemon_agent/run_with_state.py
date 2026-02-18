#!/usr/bin/env python3
"""Run the Pokemon agent with a saved state to skip the intro."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

from examples.pokemon_agent.config import AgentConfig
from examples.pokemon_agent.game_state import GameStateReader, GameMode
from examples.pokemon_agent.routines import Routines
from examples.pokemon_agent.main import PokemonAgent


async def main():
    rom_path = "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc"
    lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
    state_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")

    if not Path(state_path).exists():
        print("ERROR: No saved state found. Run create_after_intro_state.py first")
        return

    config = AgentConfig(
        provider="ollama",
        rom_path=rom_path,
        lib_path=lib_path,
        turbo=True,
        display=True,
        display_scale=2,
        max_steps=50,
        cycle_frames=30,
        verbose=True,
        log_state=True,
    )

    agent = PokemonAgent(config)

    try:
        print("Connecting to SameBoy MCP server...")
        await agent.connect()
        print("Connected!")

        await agent.setup()

        # Load saved state
        print(f"\nLoading saved state: {state_path}")
        result = await agent.call_tool("import_state", {"file_path": state_path})
        if isinstance(result, dict) and "error" in result:
            print(f"ERROR: {result['error']}")
            return

        state_id = result.get("state_id")
        print(f"State imported: {state_id}")

        load_result = await agent.call_tool("load_state", {"state_id": state_id})
        if isinstance(load_result, dict) and "error" in load_result:
            print(f"ERROR: {load_result['error']}")
            return

        print("State loaded! Starting agent from post-intro position...\n")

        # Mark initial spawn as handled since we're loading a post-intro state
        agent._initial_spawn_handled = True

        # Run the agent
        await agent.run()

    finally:
        print("Disconnecting...")
        await agent.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
