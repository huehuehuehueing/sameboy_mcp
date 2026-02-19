#!/usr/bin/env python3
"""Pokemon Yellow Autonomous Agent.

Hybrid architecture: coded routines + LLM tool agent using MCP.
The LLM uses function calling to invoke MCP tools directly.

Usage:
    # Connect to existing MCP server with local vLLM
    python -m examples.pokemon_agent.main --server-url http://localhost:8769/sse \
        --provider vllm-mlx --turbo --verbose --log-state

    # Load a saved state on startup
    python -m examples.pokemon_agent.main --server-url http://localhost:8769/sse \
        --provider vllm-mlx --turbo --state examples/pokemon_agent/saved_states/after_intro.sav

    # Start new server with ROM
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc \
        --provider vllm-mlx --turbo

    # With OpenAI (supports function calling)
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc \
        --provider openai --api-key $OPENAI_API_KEY

    # Save state on exit
    python -m examples.pokemon_agent.main --server-url http://localhost:8769/sse \
        --provider vllm-mlx --save-state my_state.sav
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

try:
    from mcp.client.sse import sse_client
except ImportError:
    sse_client = None

from examples.pokemon_agent.config import AgentConfig, PROVIDERS
from examples.pokemon_agent.game_state import GameStateReader, GameMode
from examples.pokemon_agent.game_analysis import GameAnalyzer
from examples.pokemon_agent.routines import Routines
from examples.pokemon_agent.strategy import StrategyEngine
from examples.pokemon_agent.llm_agent import LLMToolAgent, BATTLE_SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT, mcp_tools_to_openai
from examples.pokemon_agent.area_analyzer import AreaAnalyzer, AreaData
from examples.pokemon_agent.cost_tracker import CostTracker


class PokemonAgent:
    """Autonomous Pokemon Yellow agent."""

    def __init__(self, config: AgentConfig, event_sink=None):
        self.config = config
        self._session: ClientSession | None = None
        self._client_ctx = None
        self._session_ctx = None
        self._step_count = 0
        self._start_time = 0.0
        self._event_sink = event_sink

        # Cost tracking (shared across all LLM components)
        self._cost_tracker = CostTracker()

        # Initialized after MCP connect
        self._state_reader: GameStateReader | None = None
        self._routines: Routines | None = None
        self._strategy: StrategyEngine | None = None
        self._analyzer: GameAnalyzer | None = None
        self._llm_agent: LLMToolAgent | None = None
        self._area_analyzer: AreaAnalyzer | None = None

        # Area analysis tracking
        self._last_analyzed_map_id: int = -1
        self._area_data: AreaData | None = None

        # Navigation state
        self._interacted_objects: set[tuple[int, int, int]] = set()  # (map_id, x, y)
        self._last_position: tuple[int, int, int] = (0, 0, 0)  # (map_id, x, y)
        self._stuck_counter = 0  # Counts steps without movement
        self._movement_history: list[tuple[int, int, int, str]] = []  # (map_id, x, y, direction) for backtracking
        self._max_history = 50  # Keep last N movements

        # Autopilot: when True, LLM runs every cycle autonomously.
        # When False, LLM only runs for one-shot prompt injections.
        # Resume/Stop buttons toggle this.
        self._autopilot = False
        # Active instruction: persists across cycles as operator context until
        # the user explicitly stops or sends a new instruction.  This lets
        # multi-step goals ("grab the potion from the PC") run to completion.
        self._active_instruction: str | None = None

    def _log_action(self, msg: str):
        """Print a compact action line to console and emit to dashboard."""
        print(msg)
        if self._event_sink:
            self._event_sink.emit_llm_message("agent", msg)

    async def call_tool(self, name: str, args: dict):
        """Call an MCP tool and return result."""
        if not self._session:
            raise RuntimeError("Not connected")
        result = await self._session.call_tool(name, args)
        if result.content:
            # Find the first TextContent item (skip ImageContent, etc.)
            for item in result.content:
                if hasattr(item, "text"):
                    try:
                        return json.loads(item.text)
                    except json.JSONDecodeError:
                        return item.text
            # No text content — return metadata about non-text items
            item = result.content[0]
            return {"type": type(item).__name__}
        return None

    async def connect(self):
        """Connect to the MCP server."""
        if self.config.server_url:
            if sse_client is None:
                raise RuntimeError("mcp[sse] not installed. pip install mcp[sse]")
            self._client_ctx = sse_client(self.config.server_url)
            read, write = await self._client_ctx.__aenter__()
            self._session_ctx = ClientSession(read, write)
        else:
            if not self.config.lib_path:
                # Try default path
                default = Path(__file__).parent.parent.parent / "sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so"
                if default.exists():
                    self.config.lib_path = str(default)
                else:
                    raise RuntimeError("libsameboy.so not found. Use --lib to specify path.")

            args = [
                '-m', 'sameboy_mcp.server',
                '--lib', self.config.lib_path,
                '--model', self.config.gb_model,
                '--plugin', 'examples.pokemon_agent.mcp_plugin',
            ]
            if self.config.rom_path:
                args.extend(['--rom', self.config.rom_path])

            server_params = StdioServerParameters(
                command='python',
                args=args,
                cwd=str(Path(__file__).parent.parent.parent),
                env=os.environ.copy(),
            )
            self._client_ctx = stdio_client(server_params)
            read, write = await self._client_ctx.__aenter__()
            self._session_ctx = ClientSession(read, write)

        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

        # Initialize agent components
        self._state_reader = GameStateReader(self.call_tool)
        self._analyzer = GameAnalyzer(
            self.call_tool,
            verbose=self.config.verbose,
        )
        self._strategy = StrategyEngine(self.config, self._analyzer)

        # Initialize LLM tool agent for MCP-based decisions
        self._llm_agent = LLMToolAgent(self.config, self.call_tool,
                                       cost_tracker=self._cost_tracker,
                                       event_sink=self._event_sink)

        # Initialize area analyzer for map change detection
        self._area_analyzer = AreaAnalyzer(self.call_tool)

        # Initialize routines with strategy engine for LLM-assisted navigation
        self._routines = Routines(
            self.call_tool,
            self._state_reader,
            verbose=self.config.verbose,
            strategy=self._strategy,
        )

    async def disconnect(self):
        """Disconnect from MCP server."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
        self._session = None

    async def setup(self):
        """Post-connection setup: display, turbo, initial state."""
        # Enable live display
        if self.config.display:
            print(f"Enabling live display (scale: {self.config.display_scale}x)...")
            await self.call_tool("enable_live_display", {"scale": self.config.display_scale})
            # Disable user input so agent has full control
            await self.call_tool("set_user_input", {"enabled": False})

        # Enable turbo mode
        if self.config.turbo:
            print("Enabling turbo mode...")
            await self.call_tool("set_turbo", {"enabled": True, "no_frame_skip": False})

        # Verify ROM is loaded
        status = await self.call_tool("get_status", {})
        if isinstance(status, dict):
            print(f"ROM: {status.get('rom_title', 'Unknown')}")
            print(f"Model: CGB_E | Frame: {status.get('frame_count', 0)}")

        # Discover all MCP tools and expose them to the LLM agent
        tools_result = await self._session.list_tools()
        tool_names = {t.name for t in tools_result.tools}
        if "render_ascii_map" not in tool_names:
            print("ERROR: render_ascii_map tool not found!")
            print("  The Pokemon plugin must be loaded on the MCP server.")
            print("  If using --server-url, start the server with:")
            print("    --plugin examples.pokemon_agent.mcp_plugin")
            raise RuntimeError("Required MCP plugin not loaded: examples.pokemon_agent.mcp_plugin")

        openai_tools = mcp_tools_to_openai(tools_result.tools)
        self._llm_agent.set_tools(openai_tools)
        print(f"  MCP tools: {len(tools_result.tools)} discovered → {len(openai_tools)} exposed to LLM")

        # Load saved state if provided
        if self.config.state_path:
            print(f"Loading saved state: {self.config.state_path}")
            result = await self.call_tool("import_state", {"file_path": self.config.state_path})
            if isinstance(result, dict) and "state_id" in result:
                state_id = result["state_id"]
                await self.call_tool("load_state", {"state_id": state_id})
                print(f"  State loaded (ID: {state_id})")
            else:
                print(f"  Warning: Failed to load state: {result}")

        # Check LLM connectivity
        print("Checking LLM connection...")
        if self._llm_agent.check_connection():
            print(f"  LLM: OK ({self._llm_agent._model})")
        else:
            print(f"  LLM: UNREACHABLE — use dashboard action buttons to control manually")

        # Register dashboard action buttons
        if self._event_sink:
            self._event_sink.emit_action_registry([
                {"id": "resume",        "label": "Autopilot ON",  "group": "control"},
                {"id": "stop",          "label": "Autopilot OFF", "group": "control"},
                {"id": "find_exit",     "label": "Find Exit",  "group": "navigation"},
                {"id": "explore_up",    "label": "\u2191",     "group": "explore"},
                {"id": "explore_down",  "label": "\u2193",     "group": "explore"},
                {"id": "explore_left",  "label": "\u2190",     "group": "explore"},
                {"id": "explore_right", "label": "\u2192",     "group": "explore"},
                {"id": "interact",      "label": "Interact",   "group": "action"},
                {"id": "press_a",       "label": "A",          "group": "action"},
                {"id": "press_b",       "label": "B",          "group": "action"},
            ])

        # Run startup ROM analysis
        print("Analyzing ROM...")
        analysis = await self._analyzer.startup_analysis()
        print(f"ROM analysis: {analysis.get('rom_title', '?')} | "
              f"{len(analysis.get('landmarks', []))} landmarks | "
              f"{analysis.get('trainer_classes', 0)} trainer classes")

        # Let the game run a bit to initialize
        await self.call_tool("run_frames", {"count": 60})

    async def get_screenshot_b64(self) -> str | None:
        """Capture screenshot and return base64 data, or None."""
        if not self.config.screenshot_on_decision:
            return None
        result = await self.call_tool("capture_screen", {"format": "png"})
        if isinstance(result, dict) and "data_base64" in result:
            return result["data_base64"]
        return None

    async def _analyze_new_area(self, state):
        """
        Analyze a new area when map changes.

        Uses MCP tools for:
        - Screenshot/visual analysis
        - Memory inspection for sprites/NPCs
        - CPU registers and disassembly context
        """
        self._log_action(f"=== AREA CHANGE: {state.map_name} (map {state.map_id}) ===")

        try:
            # Analyze area using render_ascii_map MCP tool
            self._area_data = await self._area_analyzer.analyze_area(state)

            # Invalidate pathfinding cache so next find_exit() re-reads the map
            self._routines.invalidate_map_cache()

            # Record the warp tile we arrived on so pathfinding doesn't walk back into it
            self._routines.set_arrival_warp(state.map_id, state.player_x, state.player_y)

            # Update tracking
            self._last_analyzed_map_id = state.map_id

            # Print summary
            print(self._area_data.summary())

            # Print ASCII map to console for verification
            try:
                map_result = await self.call_tool("render_ascii_map", {})
                if isinstance(map_result, dict) and "ascii" in map_result:
                    print(map_result["ascii"])
                else:
                    print(f"  (render_ascii_map returned: {type(map_result).__name__})")
            except Exception as e:
                print(f"  (render_ascii_map error: {e})")

            # Log any important findings
            if self._area_data.npcs:
                trainers = [n for n in self._area_data.npcs if n.can_battle]
                if trainers:
                    print(f"  WARNING: {len(trainers)} potential trainer(s) detected!")

            if self._area_data.items:
                uncollected = [i for i in self._area_data.items if not i.collected]
                if uncollected:
                    print(f"  ITEMS: {len(uncollected)} item(s) available to collect")

            print(f"{'='*50}\n")

        except Exception as e:
            print(f"  Area analysis error: {e}")
            self._last_analyzed_map_id = state.map_id  # Still update to avoid retrying

    async def _execute_overworld_decision(self, decision: dict, state) -> None:
        """Execute an LLM overworld decision."""
        action = decision.get("action", "explore")
        pos = f"({state.player_x},{state.player_y})"
        current_pos = (state.map_id, state.player_x, state.player_y)

        if action == "explore":
            direction = decision.get("direction", "up")
            steps = decision.get("steps", 1)
            steps = min(steps, 5)

            walkable = await self._routines.get_walkable_directions()
            if direction not in walkable and walkable:
                alt_direction = walkable[0]
                self._log_action(
                    f"[{self._step_count}] {state.map_name} {pos}"
                    f" → {direction} blocked, walk {alt_direction} x{steps}"
                )
                direction = alt_direction
            else:
                self._log_action(
                    f"[{self._step_count}] {state.map_name} {pos}"
                    f" → walk {direction} x{steps}"
                )

            success = await self._routines.walk(direction, steps)
            if not success and walkable:
                self._log_action(f"  blocked — exploring around")
                await self._routines.explore_area(max_steps=3)

        elif action == "heal":
            self._log_action(f"[{self._step_count}] {state.map_name} {pos} → heal")
            await self._routines.use_pokecenter()

        elif action == "interact":
            if current_pos not in self._interacted_objects:
                self._log_action(f"[{self._step_count}] {state.map_name} {pos} → interact")
                self._interacted_objects.add(current_pos)
                await self._routines.interact()

                if self._area_analyzer:
                    items_here = self._area_analyzer.get_items_at(
                        state.map_id, state.player_x, state.player_y
                    )
                    for item in items_here:
                        if not item.collected:
                            self._log_action(f"  collected {item.item_name or 'item'}")
                            self._area_analyzer.mark_item_collected(
                                state.map_id, item.x, item.y
                            )
            else:
                self._log_action(f"[{self._step_count}] {state.map_name} {pos} → already interacted, moving on")
                walkable = await self._routines.get_walkable_directions()
                if walkable:
                    await self._routines.walk(walkable[0], 1)

        elif action == "collect_item":
            if self._area_analyzer:
                nearest = self._area_analyzer.get_nearest_item(
                    state.map_id, state.player_x, state.player_y
                )
                if nearest:
                    item, dist = nearest
                    self._log_action(
                        f"[{self._step_count}] {state.map_name} {pos}"
                        f" → collect {item.item_name or 'item'} at ({item.x},{item.y})"
                    )
                    dx = item.x - state.player_x
                    dy = item.y - state.player_y
                    if abs(dx) > abs(dy):
                        await self._routines.walk("right" if dx > 0 else "left", 1)
                    elif abs(dy) > 0:
                        await self._routines.walk("down" if dy > 0 else "up", 1)
                    else:
                        await self._routines.interact()
                        self._area_analyzer.mark_item_collected(state.map_id, item.x, item.y)
                        self._log_action(f"  collected {item.item_name or 'item'}")
                else:
                    self._log_action(f"[{self._step_count}] {state.map_name} {pos} → no items nearby")
                    walkable = await self._routines.get_walkable_directions()
                    if walkable:
                        await self._routines.walk(walkable[0], 1)

        elif action == "wait":
            frames = decision.get("frames", 60)
            self._log_action(f"[{self._step_count}] {state.map_name} {pos} → wait {frames}f")
            await self._routines.wait_frames(min(frames, 120))

        elif action == "find_exit":
            self._log_action(f"[{self._step_count}] {state.map_name} {pos} → find_exit")
            changed = await self._routines.navigate_to_exit()
            if changed:
                self._log_action(f"  exited map")
            else:
                self._log_action(f"  navigate_to_exit failed")

        else:
            walkable = await self._routines.get_walkable_directions()
            if walkable:
                direction = walkable[self._step_count % len(walkable)]
                self._log_action(f"[{self._step_count}] {state.map_name} {pos} → walk {direction} (fallback)")
                await self._routines.walk(direction, 1)
            else:
                await self._routines.wait_frames(30)

    async def _handle_dashboard_action(self, action_id: str, state) -> bool:
        """Handle an action triggered from the dashboard. Returns True if handled."""
        pos = f"({state.player_x},{state.player_y})"
        match action_id:
            case "find_exit":
                self._log_action(f"[dash] {state.map_name} {pos} → find_exit")
                changed = await self._routines.navigate_to_exit()
                if changed:
                    self._log_action(f"  exited map")
                else:
                    self._log_action(f"  navigate_to_exit failed")
            case "explore_up":
                self._log_action(f"[dash] {state.map_name} {pos} → walk up")
                await self._routines.walk("up", 1)
            case "explore_down":
                self._log_action(f"[dash] {state.map_name} {pos} → walk down")
                await self._routines.walk("down", 1)
            case "explore_left":
                self._log_action(f"[dash] {state.map_name} {pos} → walk left")
                await self._routines.walk("left", 1)
            case "explore_right":
                self._log_action(f"[dash] {state.map_name} {pos} → walk right")
                await self._routines.walk("right", 1)
            case "interact":
                self._log_action(f"[dash] {state.map_name} {pos} → interact")
                await self._routines.interact()
            case "press_a":
                self._log_action(f"[dash] {state.map_name} {pos} → press A")
                await self._routines.press("a", 8)
            case "press_b":
                self._log_action(f"[dash] {state.map_name} {pos} → press B")
                await self._routines.press("b", 8)
            case _:
                return False
        return True

    async def run_cycle(self) -> bool:
        """
        Run one agent decision cycle.
        Returns False to stop the agent.
        """
        self._step_count += 1

        # Read game state
        state = await self._state_reader.read_state()

        # Emit game state to dashboard
        if self._event_sink:
            self._event_sink.emit_state({
                "mode": state.mode.name if state.mode else "UNKNOWN",
                "map_name": state.map_name,
                "map_id": state.map_id,
                "player_x": state.player_x,
                "player_y": state.player_y,
                "party_count": state.party_count,
                "badge_count": state.badge_count,
                "step": self._step_count,
            })

        # Detect map change and trigger area analysis
        if state.map_id != self._last_analyzed_map_id and state.map_id > 0:
            await self._analyze_new_area(state)

        if self.config.log_state:
            print(f"\n--- Step {self._step_count} ---")
            print(state.summary(verbose=self.config.verbose))

            # In verbose mode, show detected warps/exits
            if self.config.verbose and state.map_info and state.map_info.warps:
                for warp in state.map_info.warps:
                    dist_x = abs(warp.x - state.player_x)
                    dist_y = abs(warp.y - state.player_y)
                    print(f"  [warp] ({warp.x},{warp.y}) -> map {warp.dest_map} (dist: {dist_x + dist_y})")

        # Check for pending dashboard actions (always take priority)
        if self._event_sink:
            pending = self._event_sink.get_pending_actions()
            if pending:
                action_id = pending[0].get("action_id", "")
                if action_id == "resume":
                    self._autopilot = True
                    self._log_action(f"[{self._step_count}] Autopilot ON")
                    # Fall through so the LLM runs this cycle
                elif action_id == "stop":
                    self._autopilot = False
                    self._active_instruction = None
                    self._log_action(f"[{self._step_count}] Autopilot OFF — waiting for prompts or dashboard actions")
                    await self._routines.wait_frames(self.config.cycle_frames)
                    return True
                else:
                    handled = await self._handle_dashboard_action(action_id, state)
                    if handled:
                        await self._routines.wait_frames(self.config.cycle_frames)
                        return True

            # Prompt injection → set as active instruction and enable autopilot
            # so the LLM keeps working on this goal across multiple cycles.
            injections = self._event_sink.get_pending_injections()
            if injections:
                self._active_instruction = " | ".join(injections)
                self._autopilot = True
                self._log_action(f"[{self._step_count}] Instruction: {self._active_instruction}")
                # Fall through to LLM execution below

        # When not on autopilot and no active instruction, wait
        if not self._autopilot and not self._active_instruction:
            if self._step_count % 30 == 0:
                self._log_action(
                    f"[{self._step_count}] {state.map_name} — waiting (send a prompt or click Resume for autopilot)"
                )
            await self._routines.wait_frames(60)
            return True

        if self._llm_agent and not self._llm_agent.is_available:
            if self._step_count % 30 == 0:
                self._log_action(
                    f"[{self._step_count}] {state.map_name} — LLM unavailable, use dashboard actions"
                )
            await self._routines.wait_frames(60)
            return True

        # Act based on game mode
        match state.mode:
            case GameMode.BATTLE:
                my_name = state.battle.my_pokemon.species_name if state.battle and state.battle.my_pokemon else "???"
                enemy_name = state.battle.enemy_pokemon.species_name if state.battle and state.battle.enemy_pokemon else "???"

                # Build battle context for LLM
                battle_context = f"""Battle state:
Your Pokemon: {my_name} Lv{state.battle.my_pokemon.level if state.battle and state.battle.my_pokemon else '?'}
Enemy: {enemy_name} Lv{state.battle.enemy_pokemon.level if state.battle and state.battle.enemy_pokemon else '?'}
Battle type: {'Wild' if state.battle and state.battle.is_wild else 'Trainer'}

Use read_memory to check HP and stats, then call report_result with your battle decision."""

                # Use LLM tool agent for battle decisions
                decision = await self._llm_agent.run_with_tools(
                    BATTLE_SYSTEM_PROMPT,
                    battle_context,
                    max_turns=60,
                )

                action = decision.get("action", "move")
                index = decision.get("index", 0)

                if action == "move":
                    move_name = "???"
                    if state.battle and state.battle.my_pokemon:
                        names = state.battle.my_pokemon.move_names
                        if 0 <= index < len(names):
                            move_name = names[index]
                    self._log_action(f"[{self._step_count}] Battle: {my_name} vs {enemy_name} → {move_name}")
                    await self._routines.execute_battle_move(index)

                elif action == "run":
                    self._log_action(f"[{self._step_count}] Battle: {my_name} vs {enemy_name} → RUN!")
                    escaped = await self._routines.run_from_battle()
                    if not escaped:
                        await self._routines.execute_battle_move(0)

                elif action == "switch":
                    self._log_action(f"[{self._step_count}] Battle: switch to party #{index}")
                    await self._routines.switch_pokemon(index)

                elif action == "item":
                    self._log_action(f"[{self._step_count}] Battle: use item #{index}")
                    await self._routines.use_item_in_battle(index)

                else:
                    self._log_action(f"[{self._step_count}] Battle: fallback → move 0")
                    await self._routines.execute_battle_move(0)

            case GameMode.OVERWORLD:
                # Track position for stuck detection
                current_pos = (state.map_id, state.player_x, state.player_y)
                if current_pos == self._last_position:
                    self._stuck_counter += 1
                else:
                    self._stuck_counter = 0
                    self._last_position = current_pos

                # Log screen text if available (for debugging)
                if self.config.verbose and state.screen_text and state.screen_text.has_text:
                    text_preview = state.screen_text.full_text[:100].replace("\n", " | ")
                    print(f"  [screen] {text_preview}")

                # All overworld decisions go through the LLM tool agent
                # Include area context from analyzer
                area_context = ""
                if self._area_analyzer:
                    area_context = self._area_analyzer.get_area_context_for_llm(
                        state.map_id, state.player_x, state.player_y
                    )

                # Build stuck warning if position hasn't changed
                stuck_warning = ""
                if self._stuck_counter >= 3:
                    stuck_warning = (
                        f"\n\n*** STUCK at ({state.player_x},{state.player_y}) "
                        f"for {self._stuck_counter} turns. Try a DIFFERENT direction "
                        f"to navigate around the obstacle. ***"
                    )

                # Prepend active instruction (persists across cycles)
                operator_instruction = ""
                if self._active_instruction:
                    operator_instruction = f"[OPERATOR INSTRUCTION: {self._active_instruction}]\nFollow this instruction. Use decode_screen_text and render_ascii_map to understand the current state.\n\n"

                strategy_context = f"""{operator_instruction}Overworld state:
Map: {state.map_name} (ID: {state.map_id})
Position: ({state.player_x}, {state.player_y})
Party size: {state.party_count}
Badges: {state.badge_count}/8
Progress: {state.game_progress}

Area Analysis:
{area_context}{stuck_warning}

Use tools to analyze the situation, then call report_result with your action."""

                decision = await self._llm_agent.run_with_tools(
                    STRATEGY_SYSTEM_PROMPT,
                    strategy_context,
                    max_turns=60,
                )

                # When LLM is unavailable, wait for dashboard actions
                if decision.get("_no_llm"):
                    self._log_action(
                        f"[{self._step_count}] {state.map_name} — LLM unavailable, use dashboard actions"
                    )
                    await self._routines.wait_frames(60)
                    return True

                await self._execute_overworld_decision(decision, state)

            case _:
                # Non-battle/overworld modes (dialog, name entry, intro, etc.)
                # are handled via dashboard actions only
                await self._routines.wait_frames(self.config.cycle_frames)

        # Run some frames between decisions
        await self._routines.wait_frames(self.config.cycle_frames)

        # Check step limit
        if self.config.max_steps > 0 and self._step_count >= self.config.max_steps:
            print(f"\nReached max steps ({self.config.max_steps})")
            return False

        return True

    async def run(self):
        """Main agent loop."""
        self._start_time = time.time()
        print("\n" + "=" * 60)
        print("Pokemon Yellow Autonomous Agent")
        print("=" * 60)

        llm_cfg = self.config.get_llm_config()
        print(f"Text LLM: {self.config.provider} ({llm_cfg['model']})")
        if self.config.has_vision:
            vis_cfg = self.config.get_vision_config()
            vp = self.config.vision_provider or self.config.provider
            print(f"Vision:   {vp} ({vis_cfg['model']})")
        else:
            print("Vision:   disabled")
        print(f"Cache:    {'enabled' if self.config.cache_enabled else 'disabled'} ({self.config.cache_dir})")
        print(f"Turbo:    {'ON' if self.config.turbo else 'OFF'}")
        print("=" * 60)
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                should_continue = await self.run_cycle()
                if not should_continue:
                    break
        except KeyboardInterrupt:
            print("\n\nStopped by user.")
        finally:
            # Save state on exit if requested
            if self.config.save_state_path:
                print(f"\nSaving state to: {self.config.save_state_path}")
                try:
                    result = await self.call_tool("save_state", {"name": "exit_state"})
                    if isinstance(result, dict) and "state_id" in result:
                        state_id = result["state_id"]
                        export_result = await self.call_tool("export_state", {
                            "state_id": state_id,
                            "file_path": self.config.save_state_path,
                        })
                        if isinstance(export_result, dict) and export_result.get("success"):
                            print(f"  State saved successfully")
                        else:
                            print(f"  Warning: Export failed: {export_result}")
                except Exception as e:
                    print(f"  Warning: Failed to save state: {e}")

            elapsed = time.time() - self._start_time
            print(f"\n--- Session Summary ---")
            print(f"Steps: {self._step_count}")
            print(f"Time: {elapsed:.1f}s")
            print(f"Cache stats: {self._strategy.cache_stats}")

            # Cost tracking
            print(f"\n--- LLM Cost ---")
            print(self._cost_tracker.summary())

            # Area analysis stats
            if self._area_analyzer:
                areas = self._area_analyzer.get_all_areas()
                total_npcs = sum(len(a.npcs) for a in areas.values())
                total_items = sum(len(a.items) for a in areas.values())
                collected_items = sum(1 for a in areas.values() for i in a.items if i.collected)
                print(f"Areas analyzed: {len(areas)}")
                print(f"NPCs catalogued: {total_npcs}")
                print(f"Items found: {total_items} ({collected_items} collected)")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pokemon Yellow Autonomous Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # MCP connection
    conn = parser.add_argument_group("MCP Server Connection")
    conn.add_argument("--server-url", help="URL of existing MCP server (SSE)")
    conn.add_argument("--lib", help="Path to libsameboy.so")
    conn.add_argument("--rom", "-r", help="Path to Pokemon Yellow ROM (.gbc)")
    conn.add_argument("--gb-model", default="CGB_E", help="Game Boy model (default: CGB_E)")

    # LLM providers
    llm = parser.add_argument_group("LLM Configuration")
    llm.add_argument(
        "--provider", "-p",
        default="ollama",
        choices=list(PROVIDERS.keys()),
        help="LLM provider for text decisions (default: ollama)",
    )
    llm.add_argument("--model", help="Override LLM model name")
    llm.add_argument("--api-key", help="API key (or use env vars: OPENAI_API_KEY, GROQ_API_KEY)")
    llm.add_argument("--base-url", help="Override LLM base URL")

    # Vision
    vis = parser.add_argument_group("Vision Model (screenshot analysis)")
    vis.add_argument(
        "--vision-provider",
        choices=list(PROVIDERS.keys()),
        help="Vision model provider (default: same as --provider)",
    )
    vis.add_argument("--vision-model", help="Override vision model name")
    vis.add_argument("--vision-base-url", help="Override vision base URL")
    vis.add_argument("--vision-api-key", help="Vision API key")
    vis.add_argument("--no-vision", action="store_true", help="Disable vision even if provider supports it")

    # Agent behavior
    agent = parser.add_argument_group("Agent Behavior")
    agent.add_argument("--turbo", action="store_true", help="Run emulator in turbo mode (fast)")
    agent.add_argument("--no-display", action="store_true", help="Disable live display window")
    agent.add_argument("--display-scale", type=int, default=2, choices=[1, 2, 3, 4])
    agent.add_argument("--max-steps", type=int, default=0, help="Stop after N steps (0=unlimited)")
    agent.add_argument("--cycle-frames", type=int, default=30, help="Frames between decisions")
    agent.add_argument("--no-cache", action="store_true", help="Disable decision caching")
    agent.add_argument("--cache-dir", default=".pokemon_agent_cache")
    agent.add_argument("--max-history", type=int, default=60,
                       help="Summarize LLM history after N messages (default: 60)")
    agent.add_argument("-v", "--verbose", action="store_true")
    agent.add_argument("--log-state", action="store_true", help="Print game state each cycle")

    # Saved state
    state = parser.add_argument_group("Saved State")
    state.add_argument("--state", "-s", help="Path to saved state file to load on startup")
    state.add_argument("--save-state", help="Path to save state on exit")

    # Dashboard
    dash = parser.add_argument_group("Dashboard")
    dash.add_argument("--dashboard-url", help="Dashboard WebSocket URL (e.g. ws://localhost:8765/dashboard/ws)")

    return parser.parse_args()


async def main():
    args = parse_args()

    # Resolve API key from args or environment
    api_key = args.api_key
    if not api_key:
        if args.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        elif args.provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY")
        elif args.provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        elif args.provider == "openrouter":
            api_key = os.environ.get("OPENROUTER_API_KEY")

    # Build config
    config = AgentConfig(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        base_url=args.base_url,
        vision_provider=args.vision_provider if not args.no_vision else None,
        vision_model=args.vision_model,
        vision_base_url=args.vision_base_url,
        vision_api_key=args.vision_api_key or api_key,
        server_url=args.server_url,
        lib_path=args.lib,
        rom_path=args.rom,
        gb_model=args.gb_model,
        turbo=args.turbo,
        display=not args.no_display,
        display_scale=args.display_scale,
        max_steps=args.max_steps,
        cycle_frames=args.cycle_frames,
        cache_dir=args.cache_dir,
        cache_enabled=not args.no_cache,
        verbose=args.verbose,
        log_state=args.log_state,
        screenshot_on_decision=not args.no_vision,
        state_path=args.state,
        save_state_path=args.save_state,
        max_history=args.max_history,
    )

    # Validate
    if not config.server_url and not config.rom_path:
        print("Error: --rom is required (or use --server-url for existing server)")
        sys.exit(1)

    if not config.server_url and config.rom_path and not Path(config.rom_path).exists():
        print(f"Error: ROM not found: {config.rom_path}")
        sys.exit(1)

    # Set up dashboard event sink if requested
    event_sink = None
    if args.dashboard_url:
        try:
            from sameboy_mcp.dashboard.events import RemoteDashboardEventSink
            event_sink = RemoteDashboardEventSink(args.dashboard_url)
            if await event_sink.connect():
                print(f"Dashboard: connected to {args.dashboard_url}")
            else:
                print(f"Dashboard: failed to connect (continuing without)")
                event_sink = None
        except ImportError:
            print("Dashboard: websockets package not installed (continuing without)")

    # Run agent
    agent = PokemonAgent(config, event_sink=event_sink)
    try:
        print("Connecting to SameBoy MCP server...")
        await agent.connect()
        print("Connected!")

        await agent.setup()
        await agent.run()
    finally:
        print("Disconnecting...")
        await agent.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
