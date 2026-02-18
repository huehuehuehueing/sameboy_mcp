#!/usr/bin/env python3
"""Debug coordinate system and warp mechanism."""

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

            await call_tool("enable_live_display", {"scale": 2})
            await call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

            # Load saved state
            result = await call_tool("import_state", {"file_path": state_path})
            state_id = result.get("state_id")
            await call_tool("load_state", {"state_id": state_id})
            await call_tool("run_frames", {"count": 30})

            print("=== Coordinate and Warp Debug ===\n")

            # Read all relevant addresses
            player_x = await read_byte(mem.WRAM_X_COORD)
            player_y = await read_byte(mem.WRAM_Y_COORD)
            cur_map = await read_byte(mem.WRAM_CUR_MAP)
            last_map = await read_byte(mem.WRAM_LAST_MAP)
            map_width = await read_byte(mem.WRAM_CUR_MAP_WIDTH)
            map_height = await read_byte(mem.WRAM_CUR_MAP_HEIGHT)
            warp_dest = await read_byte(mem.WRAM_WARP_DESTINATION)
            dest_map_hram = await read_byte(0xFF8B)  # HRAM destination

            print(f"Player position (from WRAM):")
            print(f"  X: {player_x} (0xD361 = {player_x:#04x})")
            print(f"  Y: {player_y} (0xD360 = {player_y:#04x})")
            print(f"  Current map: {cur_map}")
            print(f"  Last map: {last_map}")
            print(f"  Map size: {map_width}x{map_height}")

            print(f"\nWarp registers:")
            print(f"  WRAM_WARP_DESTINATION (D42F): {warp_dest:#04x}")
            print(f"  HRAM dest map (FF8B): {dest_map_hram:#04x}")

            # Read raw warp entries
            num_warps = await read_byte(mem.WRAM_NUM_WARPS)
            print(f"\nWarp entries ({num_warps}):")
            for i in range(num_warps):
                base = mem.WRAM_WARP_ENTRIES + (i * 4)
                data = await read_bytes(base, 4)
                print(f"  Warp {i} @ {base:#06x}: y={data[0]} x={data[1]} warp_id={data[2]} dest_map={data[3]}")

                # Check if player is on this warp
                if data[0] == player_y and data[1] == player_x:
                    print(f"    ^ PLAYER IS ON THIS WARP!")

            # Read sprite data (sprite 0 is player)
            print(f"\nSprite 0 (player) data:")
            sprite_data = await read_bytes(mem.WRAM_SPRITE_DATA, 16)
            print(f"  Raw: {' '.join(f'{b:02x}' for b in sprite_data)}")
            print(f"  Picture ID: {sprite_data[0]}")
            print(f"  Map Y (offset 4): {sprite_data[4]}")
            print(f"  Map X (offset 6): {sprite_data[6]}")
            print(f"  Direction (offset 9): {sprite_data[9]:#04x}")

            # Walk to the warp and check again
            print("\n=== After walking down ===")
            await call_tool("press_key", {"key": "down", "frames": 16})
            await call_tool("run_frames", {"count": 40})

            player_x = await read_byte(mem.WRAM_X_COORD)
            player_y = await read_byte(mem.WRAM_Y_COORD)
            cur_map = await read_byte(mem.WRAM_CUR_MAP)

            print(f"Player position: ({player_x}, {player_y}) on map {cur_map}")

            if cur_map != 38:
                print("WARP TRIGGERED!")
            else:
                # Check if on warp now
                for i in range(num_warps):
                    base = mem.WRAM_WARP_ENTRIES + (i * 4)
                    data = await read_bytes(base, 4)
                    if data[0] == player_y and data[1] == player_x:
                        print(f"Player is now on warp {i}: ({data[1]},{data[0]}) -> map {data[3]}")

            # Check warp flags
            print(f"\nAdditional warp-related values:")
            d736 = await read_byte(0xD736)  # wPlayerMovingDirection
            d730 = await read_byte(0xD730)  # wd730 - contains warp flags
            print(f"  D736 (player moving direction): {d736:#04x}")
            print(f"  D730 (flags): {d730:#04x}")


if __name__ == "__main__":
    asyncio.run(main())
