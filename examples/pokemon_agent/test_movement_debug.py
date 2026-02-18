#!/usr/bin/env python3
"""Debug why player cannot move."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

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

            async def read_byte(addr):
                r = await call_tool("read_memory", {"address": addr, "length": 1})
                return r.get("bytes", [0])[0] if isinstance(r, dict) else 0

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Get through title/intro quickly
            print("Getting through title screen...", flush=True)
            for _ in range(100):
                await call_tool("press_key", {"key": "a", "frames": 4})
                await call_tool("run_frames", {"count": 8})

            print("\nDebug memory state:", flush=True)
            print("=" * 60, flush=True)

            # Read all relevant memory addresses
            addresses = {
                "map_id": mem.WRAM_CUR_MAP,
                "x_coord": mem.WRAM_X_COORD,
                "y_coord": mem.WRAM_Y_COORD,
                "walk_counter": mem.WRAM_WALK_COUNTER,
                "ignore_input": mem.WRAM_IGNORE_INPUT_COUNTER,
                "sim_joypad_idx": mem.WRAM_SIM_JOYPAD_STATES_INDEX,
                "text_box_id": mem.WRAM_TEXT_BOX_ID,
                "party_count": mem.WRAM_PARTY_COUNT,
                "player_direction": mem.WRAM_PLAYER_DIRECTION,
                "tile_in_front": mem.WRAM_TILE_IN_FRONT,
            }

            # Check known addresses that control movement
            extra_addresses = {
                "wJoyIgnore": 0xCFBE,
                "wFlags_D733": 0xD733,  # Bit 1 = Start menu text box skip
                "wStatusFlags5": 0xD7F9,  # Bit 0 = received Pikachu
                "wPlayerSprite": 0xC100,  # Player sprite data
                "wWalkCounter2": 0xCFC5,  # Another walk counter?
                "wJoypadHeld": 0xFFB3,  # HRAM joypad held
                "wJoypadPressed": 0xFFB5,  # HRAM joypad pressed
                "wOverworldDelay": 0xCFB3,  # Overworld delay counter
                "wPlayerStepCounter": 0xD13B,  # Step counter
            }

            for name, addr in addresses.items():
                val = await read_byte(addr)
                print(f"  {name:20s} (0x{addr:04X}) = 0x{val:02X} ({val})", flush=True)

            print("\nExtra debug addresses:", flush=True)
            for name, addr in extra_addresses.items():
                val = await read_byte(addr)
                print(f"  {name:20s} (0x{addr:04X}) = 0x{val:02X} ({val})", flush=True)

            # Try to walk down directly using press_key
            print("\n\nTrying direct walk down...", flush=True)

            # Read position before
            x_before = await read_byte(mem.WRAM_X_COORD)
            y_before = await read_byte(mem.WRAM_Y_COORD)
            print(f"Before: ({x_before}, {y_before})", flush=True)

            # Press down for many frames
            print("Pressing down for 60 frames...", flush=True)
            await call_tool("press_key", {"key": "down", "frames": 60})
            await call_tool("run_frames", {"count": 30})

            # Read position after
            x_after = await read_byte(mem.WRAM_X_COORD)
            y_after = await read_byte(mem.WRAM_Y_COORD)
            walk = await read_byte(mem.WRAM_WALK_COUNTER)
            print(f"After: ({x_after}, {y_after}), walk_counter={walk}", flush=True)

            if x_after != x_before or y_after != y_before:
                print("SUCCESS: Player moved!", flush=True)
            else:
                print("FAILED: Player did not move", flush=True)

                # Check why - read all blocking flags
                print("\nBlocking check:", flush=True)
                ignore = await read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)
                sim_idx = await read_byte(mem.WRAM_SIM_JOYPAD_STATES_INDEX)
                textbox = await read_byte(mem.WRAM_TEXT_BOX_ID)
                walk = await read_byte(mem.WRAM_WALK_COUNTER)
                print(f"  ignore_input={ignore:#x}, sim_joypad={sim_idx:#x}, textbox={textbox:#x}, walk={walk:#x}", flush=True)

                # Try pressing B to cancel any dialog
                print("\nTrying B to cancel dialog...", flush=True)
                for _ in range(20):
                    await call_tool("press_key", {"key": "b", "frames": 4})
                    await call_tool("run_frames", {"count": 10})

                # Try walk again
                print("Trying walk again...", flush=True)
                await call_tool("press_key", {"key": "down", "frames": 60})
                await call_tool("run_frames", {"count": 30})

                x_after2 = await read_byte(mem.WRAM_X_COORD)
                y_after2 = await read_byte(mem.WRAM_Y_COORD)
                print(f"After B+walk: ({x_after2}, {y_after2})", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
