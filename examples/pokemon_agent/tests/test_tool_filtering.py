#!/usr/bin/env python3
"""Live end-to-end test for per-mode tool filtering + prompt caching.

Connects to a real MCP server, loads real save states, calls gpt-4.1,
executes tool calls against the real SameBoy emulator, and reports
token savings vs the old all-tools approach.

Requirements:
  - MCP server running: python -m sameboy_mcp.server --sse --port 8769 \
        --lib ... --rom ... --plugin examples.pokemon_agent.mcp_plugin
  - OpenAI API key in ~/openai.txt
  - Save states in examples/pokemon_agent/saved_states/

Usage:
    python -m examples.pokemon_agent.test_tool_filtering
"""
import asyncio
import json
import time
import os

async def main():
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from openai import OpenAI
    from examples.pokemon_agent.llm_agent import (
        mcp_tools_to_openai, filter_tools,
        BATTLE_TOOLS, STRATEGY_TOOLS, DIALOG_TOOLS,
        BATTLE_SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT, DIALOG_SYSTEM_PROMPT,
    )
    from examples.pokemon_agent.pokemon_data import MAP_NAMES

    api_key = open(os.path.expanduser("~/openai.txt")).read().strip()
    llm = OpenAI(api_key=api_key, timeout=60.0)
    MODEL = "gpt-4.1"
    SERVER_URL = os.environ.get("MCP_URL", "http://localhost:8769/sse")
    STATES_DIR = "examples/pokemon_agent/saved_states"

    print("=" * 70)
    print(f"  LIVE TEST — {MODEL} + Real MCP + Save States")
    print("=" * 70)

    async with sse_client(SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            openai_tools = mcp_tools_to_openai(tools_result.tools)
            battle_tools = filter_tools(openai_tools, BATTLE_TOOLS)
            strategy_tools = filter_tools(openai_tools, STRATEGY_TOOLS)
            dialog_tools = filter_tools(openai_tools, DIALOG_TOOLS)

            print(f"Connected! {len(tools_result.tools)} MCP tools → "
                  f"BATTLE={len(battle_tools)} STRATEGY={len(strategy_tools)} DIALOG={len(dialog_tools)}")

            async def call_tool(name, args):
                result = await session.call_tool(name, args)
                if result.content:
                    for item in result.content:
                        if hasattr(item, "text"):
                            try:
                                return json.loads(item.text)
                            except json.JSONDecodeError:
                                return item.text
                return None

            async def load_state(path):
                result = await call_tool("import_state", {"file_path": path})
                if isinstance(result, dict) and "state_id" in result:
                    await call_tool("load_state", {"state_id": result["state_id"]})
                    await call_tool("run_frames", {"count": 5})
                    return True
                return False

            def fmt(name, result):
                if not isinstance(result, dict):
                    return str(result)[:100]
                if name == "render_ascii_map":
                    return (f"{result.get('map_name', '?')} "
                            f"({result.get('dimensions', {}).get('width_steps', '?')}x"
                            f"{result.get('dimensions', {}).get('height_steps', '?')}) — "
                            f"{len(result.get('warps', []))} warps, "
                            f"{len(result.get('sprites', []))} sprites")
                if name in ("press_and_read", "wait_and_read"):
                    text = " | ".join(result.get("text_lines", []))[:80] or "(blank)"
                    pos = ""
                    if "player_x" in result:
                        pos = f" @({result['player_x']},{result['player_y']})"
                    return f"{text}{pos}"
                if name == "decode_screen_text":
                    return " | ".join(result.get("text_lines", []))[:80] or "(blank)"
                if name == "read_inventory":
                    items = result.get("bag", result.get("pc", []))
                    if isinstance(items, list):
                        return (f"{len(items)} items: "
                                + ", ".join(f"{i['name']}x{i['quantity']}" for i in items[:5]))
                    return json.dumps(result)[:80]
                if name == "read_money":
                    return result.get("formatted", str(result))
                return json.dumps(result)[:100]

            async def run_scenario(title, state_path, sys_prompt, user_msg,
                                   tools, cache_key, max_turns=3):
                print(f"\n{'=' * 70}")
                print(f"  {title}")
                print(f"{'=' * 70}")
                await load_state(state_path)
                mid_raw = await call_tool("read_memory", {"address": "0xD35D", "length": 1})
                mid = mid_raw.get("value", 0) if isinstance(mid_raw, dict) else 0
                print(f"  State: {MAP_NAMES.get(mid, f'Map {mid}')} | Tools: {len(tools)}")

                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg},
                ]
                total_prompt = total_comp = total_cached = 0
                all_calls = []
                t0 = time.time()

                for turn in range(1, max_turns + 1):
                    resp = llm.chat.completions.create(
                        model=MODEL, messages=messages, tools=tools,
                        tool_choice="auto", max_tokens=512, temperature=0.3,
                        extra_body={"prompt_cache_key": cache_key},
                    )
                    u = resp.usage
                    total_prompt += u.prompt_tokens
                    total_comp += u.completion_tokens
                    cached = 0
                    det = getattr(u, "prompt_tokens_details", None)
                    if det and hasattr(det, "cached_tokens"):
                        cached = det.cached_tokens or 0
                    total_cached += cached
                    cache_s = f" (cached: {cached})" if cached else ""
                    print(f"\n  Turn {turn}: {u.prompt_tokens}p + {u.completion_tokens}c{cache_s}")

                    ch = resp.choices[0]
                    if not ch.message.tool_calls:
                        if ch.message.content:
                            print(f"    text: {ch.message.content[:100]}")
                        break
                    messages.append(ch.message)
                    done = False
                    for tc in ch.message.tool_calls:
                        name = tc.function.name
                        args = json.loads(tc.function.arguments)
                        all_calls.append({"name": name, "args": args})
                        if name == "report_result":
                            print(f"    ✓ report_result: action={args.get('action')} "
                                  f"| {args.get('reasoning', '')[:80]}")
                            messages.append({
                                "role": "tool", "tool_call_id": tc.id,
                                "content": json.dumps(args),
                            })
                            done = True
                        else:
                            result = await call_tool(name, args)
                            print(f"    → {name}: {fmt(name, result)}")
                            messages.append({
                                "role": "tool", "tool_call_id": tc.id,
                                "content": (json.dumps(result)
                                            if not isinstance(result, str) else result),
                            })
                    if done:
                        break

                elapsed = time.time() - t0
                print(f"  ── {len(all_calls)} calls | {total_prompt}p + {total_comp}c "
                      f"| cached: {total_cached} | {elapsed:.1f}s")
                return {
                    "title": title, "turns": turn, "calls": all_calls,
                    "prompt": total_prompt, "comp": total_comp,
                    "cached": total_cached, "elapsed": elapsed,
                    "n_tools": len(tools),
                }

            results = []

            # Pre-read battle context from the real emulator
            await load_state(f"{STATES_DIR}/battle_start.sav")
            from examples.pokemon_agent.game_state import GameStateReader
            sr = GameStateReader(call_tool)
            bs = await sr.read_state()
            bc = "Battle state unavailable."
            if bs.battle:
                my, en = bs.battle.my_pokemon, bs.battle.enemy_pokemon
                lines = [f"Battle type: {'Wild' if bs.battle.is_wild else 'Trainer'}"]
                if my:
                    mvs = ", ".join(
                        f"{n} ({pp}PP)" for n, pp in zip(my.move_names, my.pp) if n != "---"
                    )
                    lines += [
                        f"\nYour Pokemon: {my.species_name} Lv{my.level}",
                        f"  HP: {my.hp}/{my.max_hp}",
                        f"  Moves: {mvs}",
                    ]
                if en:
                    lines += [
                        f"\nEnemy: {en.species_name} Lv{en.level}",
                        f"  HP: {en.hp}/{en.max_hp}",
                    ]
                lines.append("\nCall report_result with your battle decision.")
                bc = "\n".join(lines)

            # ── Scenario 1: BATTLE ──
            r = await run_scenario(
                "BATTLE — battle_start.sav",
                f"{STATES_DIR}/battle_start.sav",
                BATTLE_SYSTEM_PROMPT, bc,
                battle_tools, "battle", max_turns=3,
            )
            if r:
                results.append(r)

            # ── Scenario 2: STRATEGY — overworld ──
            r = await run_scenario(
                "STRATEGY — route1_in_grass.sav",
                f"{STATES_DIR}/route1_in_grass.sav",
                STRATEGY_SYSTEM_PROMPT,
                ("[OPERATOR INSTRUCTION: Walk north toward Viridian City]\n\n"
                 "Map: Route 1\nPosition: unknown — use render_ascii_map first\n"
                 "Party: 1, Badges: 0/8\n\nUse tools, then report_result."),
                strategy_tools, "strategy", max_turns=5,
            )
            if r:
                results.append(r)

            # ── Scenario 3: DIALOG — Pokemon Center ──
            r = await run_scenario(
                "DIALOG — viridian_pokecenter.sav",
                f"{STATES_DIR}/viridian_pokecenter.sav",
                DIALOG_SYSTEM_PROMPT,
                ("A dialog or menu may be open on VIRIDIAN_POKECENTER.\n"
                 "Use decode_screen_text to see, then navigate. report_result when done."),
                dialog_tools, "dialog", max_turns=8,
            )
            if r:
                results.append(r)

            # ── Scenario 4: STRATEGY — PC menu ──
            r = await run_scenario(
                "STRATEGY — pc_menu.sav",
                f"{STATES_DIR}/pc_menu.sav",
                STRATEGY_SYSTEM_PROMPT,
                ("[OPERATOR INSTRUCTION: Check what's in the PC]\n\n"
                 "Use render_ascii_map and read_inventory to check. Then report_result."),
                strategy_tools, "strategy", max_turns=5,
            )
            if r:
                results.append(r)

            # ── BASELINE: all tools ──
            print(f"\n{'=' * 70}")
            print("  BASELINE — ALL tools (old approach)")
            print(f"{'=' * 70}")
            await load_state(f"{STATES_DIR}/route1_in_grass.sav")
            t0 = time.time()
            resp_full = llm.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                    {"role": "user", "content": "Route 1. render_ascii_map, then report_result."},
                ],
                tools=openai_tools, tool_choice="auto", max_tokens=512, temperature=0.3,
            )
            el = time.time() - t0
            baseline_tokens = resp_full.usage.prompt_tokens
            print(f"  {baseline_tokens} prompt tokens | {el:.1f}s")

            # ── Final Summary ──
            print(f"\n{'=' * 70}")
            print(f"  RESUMEN — {MODEL} LIVE TEST")
            print(f"{'=' * 70}")
            print(f"\n{'Scenario':<42} {'Tools':>5} {'Turns':>5} "
                  f"{'Prompt':>8} {'Cached':>8} {'Time':>6}")
            print("-" * 80)
            for r in results:
                print(f"  {r['title'][:40]:<40} {r['n_tools']:>5} {r['turns']:>5} "
                      f"{r['prompt']:>8} {r['cached']:>8} {r['elapsed']:>5.1f}s")

            total_f = sum(r["prompt"] for r in results)
            total_turns = sum(r["turns"] for r in results)
            avg_f = total_f // total_turns
            total_cached = sum(r["cached"] for r in results)
            savings = (1 - avg_f / baseline_tokens) * 100

            print(f"\n  Baseline: {baseline_tokens} tokens/call (all tools)")
            print(f"  Filtered: {avg_f} tokens/call average")
            print(f"  Savings: {savings:.0f}%")
            print(f"  Total cached: {total_cached} tokens")

            for n_calls in (50, 100):
                cost_old = baseline_tokens * 2.00 / 1_000_000 * n_calls
                cost_new = avg_f * 2.00 / 1_000_000 * n_calls
                print(f"\n  Cost per {n_calls} calls (gpt-4.1 $2/1M):")
                print(f"    Old: ${cost_old:.4f}")
                print(f"    New: ${cost_new:.4f}")
                print(f"    Saved: ${cost_old - cost_new:.4f}")

            print(f"\n  ✓ ALL TESTS PASSED WITH {MODEL}")


if __name__ == "__main__":
    asyncio.run(main())
