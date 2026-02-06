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
from examples.pokemon_agent.llm_agent import LLMToolAgent, BATTLE_SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT
from examples.pokemon_agent.area_analyzer import AreaAnalyzer, AreaData


class PokemonAgent:
    """Autonomous Pokemon Yellow agent."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._client_ctx = None
        self._session_ctx = None
        self._step_count = 0
        self._start_time = 0.0

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
        self._dialog_counter = 0  # Counts consecutive dialog steps
        self._last_position: tuple[int, int, int] = (0, 0, 0)  # (map_id, x, y)
        self._stuck_counter = 0  # Counts steps without movement
        self._last_screen_text = ""  # For detecting changing dialogue
        self._movement_history: list[tuple[int, int, int, str]] = []  # (map_id, x, y, direction) for backtracking
        self._max_history = 50  # Keep last N movements
        self._initial_spawn_handled = False  # Track if initial spawn sequence was handled

    async def call_tool(self, name: str, args: dict):
        """Call an MCP tool and return result."""
        if not self._session:
            raise RuntimeError("Not connected")
        result = await self._session.call_tool(name, args)
        if result.content:
            text = result.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
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
        self._llm_agent = LLMToolAgent(self.config, self.call_tool)

        # Initialize area analyzer for map change detection
        self._area_analyzer = AreaAnalyzer(self.config, self.call_tool)

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

        # Load saved state if provided
        if self.config.state_path:
            print(f"Loading saved state: {self.config.state_path}")
            result = await self.call_tool("import_state", {"file_path": self.config.state_path})
            if isinstance(result, dict) and "state_id" in result:
                state_id = result["state_id"]
                await self.call_tool("load_state", {"state_id": state_id})
                print(f"  State loaded (ID: {state_id})")
                # Mark initial spawn as handled since we're loading a state
                self._initial_spawn_handled = True
            else:
                print(f"  Warning: Failed to load state: {result}")

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
        print(f"\n{'='*50}")
        print(f"AREA CHANGE: Entering {state.map_name} (map {state.map_id})")
        print(f"{'='*50}")

        try:
            # Always use memory-only analysis first (fast, reliable)
            self._area_data = await self._area_analyzer.analyze_area(state)

            # Optionally enhance with LLM vision analysis if available
            if self.config.has_vision and self._area_analyzer._client:
                if self.config.verbose:
                    print("  Enhancing with vision analysis...")
                await self._area_analyzer._do_vision_analysis(self._area_data, state)

            # Update tracking
            self._last_analyzed_map_id = state.map_id

            # Print summary
            print(self._area_data.summary())

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

    async def run_cycle(self) -> bool:
        """
        Run one agent decision cycle.
        Returns False to stop the agent.
        """
        self._step_count += 1

        # Read game state
        state = await self._state_reader.read_state()

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

        # Act based on game mode
        match state.mode:
            case GameMode.TITLE_SCREEN:
                print(f"[{self._step_count}] Title screen — pressing Start...")
                await self._routines.handle_title_screen()

            case GameMode.INTRO:
                print(f"[{self._step_count}] Intro sequence — skipping...")
                await self._routines.handle_intro()

            case GameMode.MAIN_MENU:
                # Check screen text to see options
                menu_text = ""
                if state.screen_text and state.screen_text.has_text:
                    menu_text = state.screen_text.full_text[:50]
                print(f"[{self._step_count}] Main menu — selecting New Game... ({menu_text})")
                await self._routines.handle_main_menu(select_new_game=True)

            case GameMode.NAME_ENTRY:
                # Determine if naming player or rival from screen text
                name_type = "player"  # Default
                if state.screen_text and state.screen_text.has_text:
                    text = state.screen_text.full_text.upper()
                    if "RIVAL" in text or "HIS NAME" in text:
                        name_type = "rival"
                    elif "NICKNAME" in text:
                        name_type = "pokemon"

                print(f"[{self._step_count}] Name entry ({name_type}) — entering name...")
                # Use default names
                if name_type == "player":
                    await self._routines.enter_name("ASH")
                elif name_type == "rival":
                    await self._routines.enter_name("GARY")
                else:
                    await self._routines.enter_name("BUDDY")

            case GameMode.DIALOG:
                self._dialog_counter += 1

                # Get current screen text for comparison
                current_text = ""
                if state.screen_text and state.screen_text.has_text:
                    current_text = state.screen_text.full_text

                # Check if text is changing (legitimate dialogue) or stuck (repeating)
                text_is_changing = current_text != self._last_screen_text
                self._last_screen_text = current_text

                # Check if we're stuck in a dialog loop (same position + same text)
                current_pos = (state.map_id, state.player_x, state.player_y)
                if current_pos == self._last_position and not text_is_changing:
                    self._stuck_counter += 1
                else:
                    self._stuck_counter = 0
                    self._last_position = current_pos

                # Check if we're on a warp - try to use it (simple check)
                if state.map_info and state.map_info.warps and self._stuck_counter > 10:
                    for warp in state.map_info.warps:
                        dist = abs(warp.x - state.player_x) + abs(warp.y - state.player_y)
                        if dist == 0:  # On the warp
                            print(f"[{self._step_count}] On warp at ({warp.x},{warp.y}) - pressing B then down...")
                            await self._routines.press("b", 6)
                            await self._routines.wait_frames(10)
                            await self._routines.press("down", 16)
                            await self._routines.wait_frames(30)
                            break

                # Only consider "stuck" if text isn't changing AND we're in actual gameplay area
                if self._stuck_counter > 15 and state.map_id > 0:
                    # Likely stuck interacting with an object - mark it and move away
                    self._interacted_objects.add(current_pos)
                    print(f"[{self._step_count}] Stuck on same dialog at ({state.player_x},{state.player_y}) — escaping...")

                    # Press B multiple times to exit any menu/dialog
                    for _ in range(3):
                        await self._routines.press_b_cancel()
                        await self._routines.wait_frames(8)

                    # Record position before movement attempt
                    before_x, before_y = state.player_x, state.player_y

                    # Try backtracking first if we have movement history
                    moved = False
                    if self._movement_history:
                        # Get last movement and reverse it
                        last_map, last_x, last_y, last_dir = self._movement_history[-1]
                        if last_map == state.map_id:
                            reverse_dir = {"up": "down", "down": "up", "left": "right", "right": "left"}.get(last_dir, "down")
                            print(f"  backtracking: {reverse_dir}")
                            await self._routines.walk(reverse_dir, 1)

                            # Verify movement
                            after_state = await self._state_reader.read_state()
                            if after_state.player_x != before_x or after_state.player_y != before_y:
                                moved = True
                                self._movement_history.pop()  # Remove the move we reversed
                                print(f"  moved to ({after_state.player_x},{after_state.player_y})")

                    # If backtracking didn't work, try other directions
                    if not moved:
                        walkable = await self._routines.get_walkable_directions()
                        for direction in walkable:
                            print(f"  trying: {direction}")
                            await self._routines.walk(direction, 1)

                            # Verify movement
                            after_state = await self._state_reader.read_state()
                            if after_state.player_x != before_x or after_state.player_y != before_y:
                                moved = True
                                # Record successful movement
                                self._movement_history.append((state.map_id, before_x, before_y, direction))
                                if len(self._movement_history) > self._max_history:
                                    self._movement_history.pop(0)
                                print(f"  moved to ({after_state.player_x},{after_state.player_y})")
                                break

                    if not moved:
                        print(f"  WARNING: could not move from ({before_x},{before_y}), using escape routine")
                        escaped = await self._routines.escape_stuck_state(self._movement_history)
                        if escaped:
                            print(f"  escaped successfully!")
                        else:
                            print(f"  escape failed - may be truly stuck")

                    self._stuck_counter = 0
                    self._dialog_counter = 0
                else:
                    if self.config.verbose:
                        print(f"[{self._step_count}] Dialog — advancing text...")
                    await self._routines.advance_text_once()

            case GameMode.WHITEOUT:
                print(f"[{self._step_count}] Whiteout — advancing through text...")
                await self._routines.handle_whiteout()

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
                    max_turns=3,
                )

                action = decision.get("action", "move")
                index = decision.get("index", 0)

                if action == "move":
                    move_name = "???"
                    if state.battle and state.battle.my_pokemon:
                        names = state.battle.my_pokemon.move_names
                        if 0 <= index < len(names):
                            move_name = names[index]
                    print(f"[{self._step_count}] Battle: {my_name} vs {enemy_name} → {move_name}")
                    await self._routines.execute_battle_move(index)

                elif action == "run":
                    print(f"[{self._step_count}] Battle: {my_name} vs {enemy_name} → RUN!")
                    escaped = await self._routines.run_from_battle()
                    if not escaped:
                        # If can't escape, just fight
                        await self._routines.execute_battle_move(0)

                elif action == "switch":
                    print(f"[{self._step_count}] Battle: switching to party mon {index}")
                    await self._routines.switch_pokemon(index)

                elif action == "item":
                    print(f"[{self._step_count}] Battle: using item {index}")
                    await self._routines.use_item_in_battle(index)

                else:
                    # Fallback: just use first move
                    print(f"[{self._step_count}] Battle: fallback → move 0")
                    await self._routines.execute_battle_move(0)

            case GameMode.OVERWORLD:
                # Reset dialog counter when in overworld
                self._dialog_counter = 0

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

                # Handle initial spawn sequence in Player House 2F
                # The intro script keeps ignore_input high until fully complete.
                # Only check this while at the spawn point (3,6) and before first movement.
                if not self._initial_spawn_handled and state.map_id == 38 and state.party_count == 0:
                    # Check if intro script is still running
                    import examples.pokemon_agent.memory_map as mem
                    ignore_result = await self.call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                    ignore_input = ignore_result.get("bytes", [0])[0] if isinstance(ignore_result, dict) else 0

                    # If still at spawn point with high ignore_input, intro is still running
                    if state.player_x == 3 and state.player_y == 6 and ignore_input > 10:
                        if self.config.verbose or (self._step_count % 10 == 0):
                            print(f"[{self._step_count}] Intro script running (ignore={ignore_input:#x}), pressing A...")
                        await self._routines.press("a", 8)
                        await self._routines.wait_frames(30)
                        return True  # Continue to next cycle

                    # Player moved from spawn or ignore_input is low - intro complete!
                    if state.player_x != 3 or state.player_y != 6 or ignore_input <= 10:
                        print(f"[{self._step_count}] Initial spawn complete - player can move freely")
                        self._initial_spawn_handled = True

                # Early game: prioritize finding exits until we have Pokemon
                if state.party_count == 0:
                    before_x, before_y = state.player_x, state.player_y
                    before_map = state.map_id
                    moved = False

                    # First check: are we standing on a warp tile? If so, trigger it
                    if state.map_info and state.map_info.warps:
                        for warp in state.map_info.warps:
                            if warp.x == state.player_x and warp.y == state.player_y:
                                print(f"[{self._step_count}] Standing on warp at ({warp.x},{warp.y}) → triggering stairs")
                                warped = await self._routines.trigger_warp("down")
                                if warped:
                                    print(f"  warped to new map!")
                                    return True
                                else:
                                    print(f"  warp didn't trigger, trying other directions...")
                                    # Try other directions for non-standard warps
                                    for direction in ["up", "left", "right"]:
                                        warped = await self._routines.trigger_warp(direction)
                                        if warped:
                                            print(f"  warped via {direction}!")
                                            return True
                                break

                    # Use smart navigation if stuck for a while
                    if self._stuck_counter > 5:
                        print(f"[{self._step_count}] Stuck at ({state.player_x},{state.player_y}) - using smart navigation...")
                        success = await self._routines.smart_navigate(
                            target_type="exit",
                            max_steps=10,
                            use_vision=self.config.has_vision,
                        )
                        if success:
                            print(f"  Smart navigation succeeded!")
                            return True
                        print(f"  Smart navigation didn't reach exit, continuing...")

                    # Look for exit first (stairs, doors)
                    exit_dir = await self._routines.find_exit()
                    if exit_dir:
                        print(f"[{self._step_count}] {state.map_name} ({state.player_x},{state.player_y}) "
                              f"→ found exit: {exit_dir}")
                        success = await self._routines.walk(exit_dir, 1)

                        # Verify movement (position change OR map change)
                        after_state = await self._state_reader.read_state()
                        if after_state.map_id != before_map:
                            # Warped to new map!
                            print(f"  warped to map {after_state.map_id}!")
                            return True
                        if after_state.player_x != before_x or after_state.player_y != before_y:
                            moved = True
                            self._movement_history.append((state.map_id, before_x, before_y, exit_dir))
                            if len(self._movement_history) > self._max_history:
                                self._movement_history.pop(0)
                        elif not success:
                            # Exit direction was blocked, try alternative route
                            print(f"  blocked! trying alternative directions...")
                            walkable = await self._routines.get_walkable_directions()
                            # Remove the direction that was just blocked
                            if exit_dir in walkable:
                                walkable.remove(exit_dir)
                            for alt_dir in walkable:
                                await self._routines.walk(alt_dir, 1)
                                new_state = await self._state_reader.read_state()
                                if new_state.player_x != before_x or new_state.player_y != before_y:
                                    moved = True
                                    self._movement_history.append((state.map_id, before_x, before_y, alt_dir))
                                    if len(self._movement_history) > self._max_history:
                                        self._movement_history.pop(0)
                                    print(f"  moved {alt_dir} to ({new_state.player_x},{new_state.player_y})")
                                    break

                            # If still no movement, try clearing invisible state
                            if not moved:
                                # Read raw memory to debug why movement blocked
                                if self.config.verbose:
                                    import examples.pokemon_agent.memory_map as mem
                                    textbox = await self.call_tool("read_memory", {"address": mem.WRAM_TEXTBOX_OPEN, "length": 1})
                                    script = await self.call_tool("read_memory", {"address": mem.WRAM_SCRIPT_RUNNING, "length": 1})
                                    ignore = await self.call_tool("read_memory", {"address": mem.WRAM_IGNORE_INPUT_COUNTER, "length": 1})
                                    joypad = await self.call_tool("read_memory", {"address": mem.WRAM_JOYPAD_SIM_ACTIVE, "length": 1})
                                    textbox_val = textbox.get("bytes", [0])[0] if isinstance(textbox, dict) else 0
                                    script_val = script.get("bytes", [0])[0] if isinstance(script, dict) else 0
                                    ignore_val = ignore.get("bytes", [0])[0] if isinstance(ignore, dict) else 0
                                    joypad_val = joypad.get("bytes", [0])[0] if isinstance(joypad, dict) else 0
                                    print(f"  DEBUG: textbox={textbox_val:#x} script={script_val:#x} ignore={ignore_val:#x} joypad={joypad_val:#x}")
                                print(f"  all directions blocked - clearing potential hidden state...")
                                for _ in range(3):
                                    await self._routines.press("a", 6)
                                    await self._routines.wait_frames(15)
                                for _ in range(3):
                                    await self._routines.press("b", 6)
                                    await self._routines.wait_frames(15)
                                # Reset stuck counter since we're actively trying to fix it
                                self._stuck_counter = 0

                    if not moved and not exit_dir:
                        # Explore to find exit
                        walkable = await self._routines.get_walkable_directions()
                        if walkable:
                            # Prefer directions we haven't tried recently
                            direction = walkable[self._step_count % len(walkable)]
                            print(f"[{self._step_count}] {state.map_name} ({state.player_x},{state.player_y}) "
                                  f"→ exploring {direction}")
                            await self._routines.walk(direction, 1)

                            # Verify and record movement
                            after_state = await self._state_reader.read_state()
                            if after_state.player_x != before_x or after_state.player_y != before_y:
                                self._movement_history.append((state.map_id, before_x, before_y, direction))
                                if len(self._movement_history) > self._max_history:
                                    self._movement_history.pop(0)
                        else:
                            print(f"[{self._step_count}] {state.map_name} — no walkable directions, waiting...")
                            await self._routines.wait_frames(30)
                else:
                    # Normal gameplay with party - use LLM tool agent
                    # Include area context from analyzer
                    area_context = ""
                    if self._area_analyzer:
                        area_context = self._area_analyzer.get_area_context_for_llm(
                            state.map_id, state.player_x, state.player_y
                        )

                    strategy_context = f"""Overworld state:
Map: {state.map_name} (ID: {state.map_id})
Position: ({state.player_x}, {state.player_y})
Party size: {state.party_count}
Badges: {state.badge_count}/8

Area Analysis:
{area_context}

Use tools to analyze the situation, then call report_result with your action."""

                    decision = await self._llm_agent.run_with_tools(
                        STRATEGY_SYSTEM_PROMPT,
                        strategy_context,
                        max_turns=3,
                    )
                    action = decision.get("action", "explore")

                    if action == "explore":
                        direction = decision.get("direction", "up")
                        steps = decision.get("steps", 1)
                        steps = min(steps, 5)  # Safety limit

                        # Check if direction is walkable first
                        walkable = await self._routines.get_walkable_directions()
                        if direction not in walkable and walkable:
                            # Use an alternative walkable direction
                            alt_direction = walkable[0]
                            print(f"[{self._step_count}] {state.map_name} ({state.player_x},{state.player_y}) "
                                  f"→ {direction} blocked, trying {alt_direction}")
                            direction = alt_direction

                        print(f"[{self._step_count}] {state.map_name} ({state.player_x},{state.player_y}) → walk {direction} x{steps}")
                        success = await self._routines.walk(direction, steps)

                        if not success and walkable:
                            # Try to explore in available directions
                            print(f"  blocked! trying to explore...")
                            await self._routines.explore_area(max_steps=3)

                    elif action == "heal":
                        print(f"[{self._step_count}] Heading to Pokecenter to heal...")
                        await self._routines.use_pokecenter()

                    elif action == "interact":
                        # Check if we've already interacted with this position
                        if current_pos not in self._interacted_objects:
                            print(f"[{self._step_count}] Interacting...")
                            self._interacted_objects.add(current_pos)
                            await self._routines.interact()

                            # Check if we collected an item
                            if self._area_analyzer:
                                items_here = self._area_analyzer.get_items_at(
                                    state.map_id, state.player_x, state.player_y
                                )
                                for item in items_here:
                                    if not item.collected:
                                        print(f"  Collected: {item.item_name or 'item'}")
                                        self._area_analyzer.mark_item_collected(
                                            state.map_id, item.x, item.y
                                        )
                        else:
                            print(f"[{self._step_count}] Already interacted here, moving on...")
                            walkable = await self._routines.get_walkable_directions()
                            if walkable:
                                await self._routines.walk(walkable[0], 1)

                    elif action == "collect_item":
                        # Navigate to and collect a nearby item
                        if self._area_analyzer:
                            nearest = self._area_analyzer.get_nearest_item(
                                state.map_id, state.player_x, state.player_y
                            )
                            if nearest:
                                item, dist = nearest
                                print(f"[{self._step_count}] Going to collect {item.item_name or 'item'} at ({item.x},{item.y})")
                                # Simple navigation towards item
                                dx = item.x - state.player_x
                                dy = item.y - state.player_y
                                if abs(dx) > abs(dy):
                                    await self._routines.walk("right" if dx > 0 else "left", 1)
                                elif abs(dy) > 0:
                                    await self._routines.walk("down" if dy > 0 else "up", 1)
                                else:
                                    # At item position - interact
                                    await self._routines.interact()
                                    self._area_analyzer.mark_item_collected(state.map_id, item.x, item.y)
                                    print(f"  Collected: {item.item_name or 'item'}")
                            else:
                                print(f"[{self._step_count}] No items nearby to collect")
                                walkable = await self._routines.get_walkable_directions()
                                if walkable:
                                    await self._routines.walk(walkable[0], 1)

                    elif action == "wait":
                        frames = decision.get("frames", 60)
                        await self._routines.wait_frames(min(frames, 120))

                    elif action == "find_exit":
                        print(f"[{self._step_count}] Looking for exit...")
                        exit_dir = await self._routines.find_exit()
                        if exit_dir:
                            print(f"  found exit: {exit_dir}")
                            await self._routines.walk(exit_dir, 1)
                        else:
                            await self._routines.explore_area(max_steps=5)

                    else:
                        # Default: explore the area
                        walkable = await self._routines.get_walkable_directions()
                        if walkable:
                            direction = walkable[self._step_count % len(walkable)]
                            await self._routines.walk(direction, 1)
                        else:
                            await self._routines.wait_frames(30)

            case _:
                # Unknown mode, press B to try to exit, then wait
                await self._routines.press_b_cancel()
                await self._routines.wait_frames(30)

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
    agent.add_argument("-v", "--verbose", action="store_true")
    agent.add_argument("--log-state", action="store_true", help="Print game state each cycle")

    # Saved state
    state = parser.add_argument_group("Saved State")
    state.add_argument("--state", "-s", help="Path to saved state file to load on startup")
    state.add_argument("--save-state", help="Path to save state on exit")

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
    )

    # Validate
    if not config.server_url and not config.rom_path:
        print("Error: --rom is required (or use --server-url for existing server)")
        sys.exit(1)

    if not config.server_url and config.rom_path and not Path(config.rom_path).exists():
        print(f"Error: ROM not found: {config.rom_path}")
        sys.exit(1)

    # Run agent
    agent = PokemonAgent(config)
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
