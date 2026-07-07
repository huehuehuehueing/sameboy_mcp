#!/usr/bin/env python3
"""Integration tests for LLM prompt quality.

Runs real GPT-4.1 calls against known game states to measure:
- Turns to report_result (fewer = better)
- Whether the LLM delegates to routines (find_exit, explore) vs manual press_key
- Total API cost per decision
- Whether the task actually completes (map change, position change)

Usage:
    # Against running SSE server
    python -m examples.pokemon_agent.test_prompt_quality \
        --server-url http://localhost:8765/sse \
        --provider openai --api-key $OPENAI_API_KEY

    # Standalone (starts its own server)
    python -m examples.pokemon_agent.test_prompt_quality \
        --provider openai --api-key $OPENAI_API_KEY
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

try:
    from mcp.client.sse import sse_client
except ImportError:
    sse_client = None

from examples.pokemon_agent.config import AgentConfig, PROVIDERS
from examples.pokemon_agent.game_state import GameStateReader
from examples.pokemon_agent.llm_agent import (
    LLMToolAgent,
    STRATEGY_SYSTEM_PROMPT,
    BATTLE_SYSTEM_PROMPT,
    mcp_tools_to_openai,
)
from examples.pokemon_agent.cost_tracker import CostTracker


# The OLD prompt (before optimization) — kept here for A/B comparison
OLD_STRATEGY_SYSTEM_PROMPT = """You are a Pokemon game AI. You have access to all emulator and game tools.

You have plenty of turns. Use them to COMPLETE the task — do not stop early.

TOOLS:
- decode_screen_text — read on-screen text (dialog, menus, signs). Use FIRST and after EVERY action.
- render_ascii_map — area layout. Legend: . walkable, # wall, @ player, W warp/door, G grass, N NPC, T trainer, I item, C PC, B bookshelf, ! sign.
- press_key — press a button (a, b, up, down, left, right, start, select). Use frames=8 for normal presses.
- run_frames — advance the game without input (use count=30 to let animations/text render).
- read_memory — check specific memory addresses.
- report_result — REQUIRED as your FINAL call to hand control back to the agent.

MULTI-STEP INTERACTIONS (PC, NPCs, menus):
When interacting with objects like PCs or NPCs, you must drive the ENTIRE interaction:
1. press_key a (frames=8) → run_frames 30 → decode_screen_text (read what changed)
2. Repeat: press_key to advance dialog / navigate menus, then ALWAYS decode_screen_text
3. Continue until the screen text CONFIRMS the goal (e.g. "withdrew POTION")
4. THEN call report_result

VERIFICATION — NEVER assume or hallucinate results:
- After EVERY press_key, call run_frames then decode_screen_text to see what ACTUALLY happened.
- If decode_screen_text shows blank/unchanged text, the action had no effect — try again or adjust.
- In your report_result reasoning, QUOTE the actual screen text that confirms completion.
- If you cannot confirm the goal was achieved from screen text, say so honestly.
- NEVER claim "item obtained" or "interaction complete" without screen text evidence.

When an operator instruction is present, follow it until the goal is verified on screen.

report_result actions (call this as your LAST tool call):
- "explore" with direction (up/down/left/right) and steps (1-5)
- "interact" — single A press (only for simple interactions)
- "find_exit" — auto-navigate to nearest exit/warp
- "collect_item" — pick up nearest item
- "heal" — go to Pokecenter
- "wait" with frames — use after completing a multi-step interaction"""


@dataclass
class TestResult:
    """Result of a single prompt quality test."""
    name: str
    passed: bool
    turns_used: int
    cost: float
    action_chosen: str
    used_report_result: bool
    used_press_key: bool  # True if LLM tried manual navigation
    map_changed: bool
    initial_map: int
    final_map: int
    initial_pos: tuple[int, int] = (0, 0)
    final_pos: tuple[int, int] = (0, 0)
    duration_seconds: float = 0.0
    tool_calls: list[str] = field(default_factory=list)
    error: str | None = None


def print_result(r: TestResult):
    """Print a test result with pass/fail indicator."""
    status = "PASS" if r.passed else "FAIL"
    print(f"\n{'='*60}")
    print(f"[{status}] {r.name}")
    print(f"{'='*60}")
    print(f"  Turns:          {r.turns_used}")
    print(f"  Cost:           ${r.cost:.4f}")
    print(f"  Action:         {r.action_chosen}")
    print(f"  report_result:  {'yes' if r.used_report_result else 'NO  <-- problem'}")
    print(f"  press_key used: {'YES <-- should delegate' if r.used_press_key else 'no (good)'}")
    print(f"  Map changed:    {r.initial_map} -> {r.final_map} ({'yes' if r.map_changed else 'no'})")
    print(f"  Position:       {r.initial_pos} -> {r.final_pos}")
    print(f"  Duration:       {r.duration_seconds:.1f}s")
    if r.tool_calls:
        print(f"  Tool calls:     {', '.join(r.tool_calls[:10])}")
    if r.error:
        print(f"  Error:          {r.error}")


class PromptQualityTester:
    """Runs prompt quality tests against a live MCP server."""

    def __init__(self, session: ClientSession, config: AgentConfig):
        self._session = session
        self._config = config
        self._state_reader = GameStateReader(self.call_tool)

    async def call_tool(self, name: str, args: dict):
        result = await self._session.call_tool(name, args)
        if result.content:
            for item in result.content:
                if hasattr(item, "text"):
                    try:
                        return json.loads(item.text)
                    except json.JSONDecodeError:
                        return item.text
        return None

    async def _load_state(self, state_path: str):
        """Load a saved state file."""
        result = await self.call_tool("import_state", {"file_path": state_path})
        if isinstance(result, dict) and "state_id" in result:
            await self.call_tool("load_state", {"state_id": result["state_id"]})
            await self.call_tool("run_frames", {"count": 30})
            return True
        return False

    async def _create_llm_agent(self) -> LLMToolAgent:
        """Create a fresh LLM agent with tools."""
        cost_tracker = CostTracker()
        agent = LLMToolAgent(self._config, self.call_tool, cost_tracker=cost_tracker)
        agent.check_connection()

        tools_result = await self._session.list_tools()
        openai_tools = mcp_tools_to_openai(tools_result.tools)
        agent.set_tools(openai_tools)

        return agent

    async def run_test(
        self,
        name: str,
        state_path: str,
        instruction: str,
        system_prompt: str,
        max_turns: int = 60,
        expect_action: str | None = None,
        expect_map_change: bool = False,
        max_acceptable_turns: int = 10,
    ) -> TestResult:
        """Run a single prompt quality test.

        Args:
            name: Test name
            state_path: Path to saved state
            instruction: User instruction to give the LLM
            system_prompt: System prompt to use
            max_turns: Max turns for LLM
            expect_action: Expected report_result action (e.g. "find_exit")
            expect_map_change: Whether the test expects map to change
            max_acceptable_turns: Turns threshold for pass/fail
        """
        # Load state
        if not await self._load_state(state_path):
            return TestResult(
                name=name, passed=False, turns_used=0, cost=0,
                action_chosen="", used_report_result=False,
                used_press_key=False, map_changed=False,
                initial_map=0, final_map=0,
                error="Failed to load state",
            )

        # Read initial state
        initial_state = await self._state_reader.read_state()
        initial_map = initial_state.map_id
        initial_pos = (initial_state.player_x, initial_state.player_y)

        # Create agent and track tool calls
        agent = await self._create_llm_agent()
        tool_calls_log = []
        original_execute = agent._execute_tool

        async def tracking_execute(tool_name, args):
            tool_calls_log.append(tool_name)
            return await original_execute(tool_name, args)

        agent._execute_tool = tracking_execute

        # Build context like main.py does
        context = f"""[OPERATOR INSTRUCTION: {instruction}]
Follow this instruction. Use decode_screen_text and render_ascii_map to understand the current state.

Overworld state:
Map: {initial_state.map_name} (ID: {initial_state.map_id})
Position: ({initial_state.player_x}, {initial_state.player_y})
Party size: {initial_state.party_count}
Badges: {initial_state.badge_count}/8

Use tools to analyze the situation, then call report_result with your action."""

        # Run LLM
        start_time = time.time()
        decision = await agent.run_with_tools(system_prompt, context, max_turns=max_turns)
        duration = time.time() - start_time

        # Read final state
        final_state = await self._state_reader.read_state()
        final_map = final_state.map_id
        final_pos = (final_state.player_x, final_state.player_y)

        # Analyze results
        action_chosen = decision.get("action", "unknown")
        used_report_result = "report_result" in tool_calls_log
        used_press_key = "press_key" in tool_calls_log
        map_changed = final_map != initial_map
        turns_used = len([t for t in tool_calls_log if t != "report_result"])
        cost = agent.cost_tracker.total_cost

        # Determine pass/fail
        passed = True
        if not used_report_result:
            passed = False  # Must call report_result
        if turns_used > max_acceptable_turns:
            passed = False  # Too many turns
        if expect_action and action_chosen != expect_action:
            passed = False  # Wrong action
        if used_press_key:
            passed = False  # Should delegate, not manually press

        return TestResult(
            name=name,
            passed=passed,
            turns_used=turns_used,
            cost=cost,
            action_chosen=action_chosen,
            used_report_result=used_report_result,
            used_press_key=used_press_key,
            map_changed=map_changed,
            initial_map=initial_map,
            final_map=final_map,
            initial_pos=initial_pos,
            final_pos=final_pos,
            duration_seconds=duration,
            tool_calls=tool_calls_log,
        )


# ── Test scenarios ───────────────────────────────────────────

SAVED_STATES_DIR = Path(__file__).parent / "saved_states"


async def run_all_tests(session: ClientSession, config: AgentConfig):
    """Run all prompt quality tests."""
    tester = PromptQualityTester(session, config)
    results: list[TestResult] = []

    after_intro = str(SAVED_STATES_DIR / "after_intro.sav")

    # Test 1: Exit building — should use find_exit in few turns
    results.append(await tester.run_test(
        name="Exit building (Player House 2F)",
        state_path=after_intro,
        instruction="Sal de la casa",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        expect_action="find_exit",
        max_acceptable_turns=8,
    ))

    # Test 2: Explore direction — should use explore, not press_key
    results.append(await tester.run_test(
        name="Explore south (Player House 2F)",
        state_path=after_intro,
        instruction="Muevete hacia abajo 3 pasos",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        expect_action="explore",
        max_acceptable_turns=6,
    ))

    # Test 3: Interact with object — should delegate to interact
    results.append(await tester.run_test(
        name="Interact with nearby object (Player House 2F)",
        state_path=after_intro,
        instruction="Revisa la computadora que tienes cerca",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        expect_action="interact",
        max_acceptable_turns=8,
    ))

    # Test 4: No instruction, just explore — should pick a direction quickly
    results.append(await tester.run_test(
        name="Free exploration (no specific goal)",
        state_path=after_intro,
        instruction="Explora el area",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        max_acceptable_turns=6,
    ))

    viridian_pokecenter = str(SAVED_STATES_DIR / "viridian_pokecenter.sav")

    # Test 5: Heal at Pokemon Center — multi-step dialog with nurse
    results.append(await tester.run_test(
        name="Heal Pokemon at Viridian Pokemon Center",
        state_path=viridian_pokecenter,
        instruction="Heal your Pokemon at the Pokemon Center",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        expect_action="heal",
        max_acceptable_turns=35,
    ))

    # Test 6: Exit Pokemon Center — navigate to warp and leave
    results.append(await tester.run_test(
        name="Exit Viridian Pokemon Center",
        state_path=viridian_pokecenter,
        instruction="Exit this building",
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        expect_action="find_exit",
        max_acceptable_turns=8,
    ))

    # Print results
    print("\n" + "=" * 60)
    print("PROMPT QUALITY TEST RESULTS")
    print("=" * 60)

    for r in results:
        print_result(r)

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_cost = sum(r.cost for r in results)
    avg_turns = sum(r.turns_used for r in results) / total if total else 0
    press_key_count = sum(1 for r in results if r.used_press_key)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} passed")
    print(f"  Avg turns per decision:  {avg_turns:.1f}")
    print(f"  Total cost:              ${total_cost:.4f}")
    print(f"  Tests using press_key:   {press_key_count}/{total} (should be 0)")
    print(f"{'='*60}")

    return results


# ── Main ─────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Test LLM prompt quality")
    parser.add_argument("--server-url", help="SSE server URL")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: --api-key or OPENAI_API_KEY required")
        sys.exit(1)

    config = AgentConfig(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        server_url=args.server_url,
        verbose=True,
    )

    if args.server_url:
        if sse_client is None:
            print("Error: mcp[sse] not installed")
            sys.exit(1)
        async with sse_client(args.server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await run_all_tests(session, config)
    else:
        rom_path = "roms/pokeyellow/Pokemon - Yellow Version (USA, Europe).gbc"
        lib_path = "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "sameboy_mcp.server", "--lib", lib_path, "--rom", rom_path,
                  "--model", "CGB_E", "--plugin", "examples.pokemon_agent.mcp_plugin"],
            cwd=str(Path(__file__).parent.parent.parent),
            env=os.environ.copy(),
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await run_all_tests(session, config)


if __name__ == "__main__":
    asyncio.run(main())
