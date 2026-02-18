#!/usr/bin/env python3
"""Fix warp data and test if stairs work."""

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
    state_path = str(Path(__file__).parent / "saved_states" / "after_intro.sav")

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

            async def read_bytes(addr, length):
                r = await call_tool("read_memory", {"address": addr, "length": length})
                return r.get("bytes", []) if isinstance(r, dict) else []

            async def read_byte(addr):
                r = await read_bytes(addr, 1)
                return r[0] if r else 0

            async def write_byte(addr, value):
                await call_tool("write_memory", {"address": addr, "data": [value]})

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await call_tool("run_frames", {"count": 30})

            print("=== Before Fix ===")
            warp_data = await read_bytes(mem.WRAM_WARP_ENTRIES, 4)
            print(f"Warp 0: y={warp_data[0]} x={warp_data[1]} warp_id={warp_data[2]} dest_map={warp_data[3]}")

            # The ROM says the warp should be at (7,1) -> map 37, warp 2
            # warp_event macro stores: db y, x, warp_id-1, dest_map
            # So correct values: y=1, x=7, warp_id=2, dest_map=37
            print("\n=== Fixing warp data ===")
            print("ROM says: warp_event 7, 1, REDS_HOUSE_1F, 3")
            print("Stored as: y=1, x=7, warp_id=2, dest_map=37")

            # Write the correct warp data
            base = mem.WRAM_WARP_ENTRIES
            await write_byte(base + 0, 1)   # y = 1
            await write_byte(base + 1, 7)   # x = 7
            await write_byte(base + 2, 2)   # warp_id = 3-1 = 2
            await write_byte(base + 3, 37)  # dest_map = REDS_HOUSE_1F = 37
            await call_tool("run_frames", {"count": 10})

            warp_data = await read_bytes(mem.WRAM_WARP_ENTRIES, 4)
            print(f"Warp 0 (fixed): y={warp_data[0]} x={warp_data[1]} warp_id={warp_data[2]} dest_map={warp_data[3]}")

            # Also set the last_map to 37 in case that's used
            await write_byte(mem.WRAM_LAST_MAP, 37)

            print("\n=== Testing warp after fix ===")
            player_y = await read_byte(mem.WRAM_Y_COORD)
            player_x = await read_byte(mem.WRAM_X_COORD)
            cur_map = await read_byte(mem.WRAM_CUR_MAP)
            print(f"Player at ({player_x},{player_y}) on map {cur_map}")

            # Walk to warp position if not there
            if player_y < 7:
                print("Walking to stairs...")
                await call_tool("press_key", {"key": "down", "frames": 16})
                await call_tool("run_frames", {"count": 60})

            player_y = await read_byte(mem.WRAM_Y_COORD)
            player_x = await read_byte(mem.WRAM_X_COORD)
            cur_map = await read_byte(mem.WRAM_CUR_MAP)
            print(f"After walk: ({player_x},{player_y}) on map {cur_map}")

            if cur_map != 38:
                print(f"\nWARP WORKED! Now on map {cur_map}")
                return

            # Try pressing down while on stairs
            print("\nTrying to trigger warp by pressing down...")
            for attempt in range(5):
                await call_tool("press_key", {"key": "down", "frames": 32})
                await call_tool("run_frames", {"count": 60})

                new_map = await read_byte(mem.WRAM_CUR_MAP)
                if new_map != 38:
                    print(f"WARP WORKED on attempt {attempt+1}! Now on map {new_map}")
                    return
                print(f"  Attempt {attempt+1}: still on map {new_map}")

            print("\nWarp still not working even after fixing dest_map!")
            print("This suggests the issue is with warp triggering logic, not the warp data.")


if __name__ == "__main__":
    asyncio.run(main())
