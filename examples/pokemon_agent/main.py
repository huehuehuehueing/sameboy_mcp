#!/usr/bin/env python3
"""Pokemon Yellow Autonomous Agent.

Hybrid architecture: coded routines + LLM strategy with caching.
Supports vision models via vllm-mlx for screenshot analysis.

Usage:
    # With local Ollama (text only)
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc --provider ollama

    # With vllm-mlx vision (start server first: vllm-mlx serve mlx-community/Qwen3-VL-4B-Instruct-3bit)
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc \
        --provider ollama --vision-provider vllm-mlx

    # With OpenAI (text + vision)
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc \
        --provider openai --api-key $OPENAI_API_KEY

    # With Groq (text) + vllm-mlx (vision)
    python -m examples.pokemon_agent.main --rom ~/Downloads/Pokemon*.gbc \
        --provider groq --api-key $GROQ_API_KEY --vision-provider vllm-mlx

    # Connect to existing MCP server
    python -m examples.pokemon_agent.main --server-url http://localhost:8765/sse \
        --provider vllm-mlx
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
from examples.pokemon_agent.routines import Routines
from examples.pokemon_agent.strategy import StrategyEngine


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
        self._routines = Routines(
            self.call_tool,
            self._state_reader,
            verbose=self.config.verbose,
        )
        self._strategy = StrategyEngine(self.config)

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

    async def run_cycle(self) -> bool:
        """
        Run one agent decision cycle.
        Returns False to stop the agent.
        """
        self._step_count += 1

        # Read game state
        state = await self._state_reader.read_state()

        if self.config.log_state:
            print(f"\n--- Step {self._step_count} ---")
            print(state.summary())

        # Act based on game mode
        match state.mode:
            case GameMode.TITLE_SCREEN:
                print(f"[{self._step_count}] Title screen — pressing Start...")
                await self._routines.handle_title_screen()

            case GameMode.DIALOG:
                if self.config.verbose:
                    print(f"[{self._step_count}] Dialog — advancing text...")
                await self._routines.advance_text_once()

            case GameMode.WHITEOUT:
                print(f"[{self._step_count}] Whiteout — advancing through text...")
                await self._routines.handle_whiteout()

            case GameMode.BATTLE:
                # Get screenshot for vision if available
                screenshot = await self.get_screenshot_b64() if self.config.has_vision else None

                # Ask LLM for battle decision
                decision = self._strategy.choose_battle_action(state, screenshot)
                action = decision.get("action", "move")
                index = decision.get("index", 0)

                my_name = state.battle.my_pokemon.species_name if state.battle and state.battle.my_pokemon else "???"
                enemy_name = state.battle.enemy_pokemon.species_name if state.battle and state.battle.enemy_pokemon else "???"

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
                # Get screenshot for vision
                screenshot = await self.get_screenshot_b64() if self.config.has_vision else None

                # Ask LLM for overworld decision
                decision = self._strategy.decide_next_action(state, screenshot)
                action = decision.get("action", "explore")

                if action == "explore":
                    direction = decision.get("direction", "up")
                    steps = decision.get("steps", 1)
                    steps = min(steps, 5)  # Safety limit
                    print(f"[{self._step_count}] {state.map_name} ({state.player_x},{state.player_y}) → walk {direction} x{steps}")
                    await self._routines.walk(direction, steps)

                elif action == "heal":
                    print(f"[{self._step_count}] Heading to Pokecenter to heal...")
                    await self._routines.use_pokecenter()

                elif action == "interact":
                    print(f"[{self._step_count}] Interacting...")
                    await self._routines.interact()

                elif action == "wait":
                    frames = decision.get("frames", 60)
                    await self._routines.wait_frames(min(frames, 120))

                else:
                    # Default: walk in a random-ish direction
                    await self._routines.walk("right", 1)

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
            elapsed = time.time() - self._start_time
            print(f"\n--- Session Summary ---")
            print(f"Steps: {self._step_count}")
            print(f"Time: {elapsed:.1f}s")
            print(f"Cache stats: {self._strategy.cache_stats}")


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
