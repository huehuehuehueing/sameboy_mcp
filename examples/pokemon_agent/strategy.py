"""Layer 3: LLM Strategy Engine with caching and vision support.

Calls an LLM only when a strategic decision is needed.
Results are cached to avoid repeated API calls for similar situations.
Supports vision models (vllm-mlx, OpenAI, Anthropic) for screenshot analysis.
"""

import base64
import json
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import AgentConfig
from .cache import (
    DecisionCache,
    bucket_hp,
    bucket_level,
    make_battle_cache_key,
    make_navigation_cache_key,
    make_strategy_cache_key,
)
from .game_state import GameState, BattleState, Pokemon
from .game_analysis import GameAnalyzer
from . import memory_map as mem


BATTLE_SYSTEM_PROMPT = """You are a Pokemon battle strategist for Pokemon Yellow.
Given the current battle state, choose the best action.

RESPOND WITH ONLY a JSON object, no other text:
{"action": "move", "index": 0}        -- Use move at index 0-3
{"action": "run"}                       -- Run from wild battle
{"action": "switch", "index": 2}       -- Switch to party Pokemon at index 0-5
{"action": "item", "index": 0}         -- Use bag item at index

Consider:
- Type effectiveness (super effective = 2x, not very effective = 0.5x, immune = 0x)
- STAB bonus (Same Type Attack Bonus = 1.5x when move type matches Pokemon type)
- HP levels (heal or switch if low)
- PP remaining (don't use moves with 0 PP)
- Status conditions
- Run from wild battles if party is weak and the wild Pokemon isn't valuable
- Enemy's known moves and their type/power — choose moves that resist their attacks
- Stat modifiers: stages above 7 = boosted, below 7 = lowered (Gen 1 scale 1-13)
- Battle effects like Reflect, Light Screen, Substitute change damage calculations
- In trainer battles, consider enemy party size to manage resources"""

STRATEGY_SYSTEM_PROMPT = """You are an autonomous Pokemon Yellow player.
Given the current game state, decide what to do next.

RESPOND WITH ONLY a JSON object:
{"action": "explore", "direction": "up", "steps": 3}  -- Walk in a direction
{"action": "heal"}                                      -- Go to nearest Pokecenter
{"action": "interact"}                                  -- Talk to NPC / interact with object
{"action": "enter_building"}                            -- Enter a building in front
{"action": "wait", "frames": 60}                        -- Wait and observe

Consider:
- If party HP is low, prioritize healing
- If in a new area, explore systematically
- Progress the story: get badges, fight trainers
- Keep Pikachu happy (it's Yellow version!)"""

VISION_PROMPT = """Analyze this Pokemon Yellow Game Boy screenshot.
Describe what you see:
1. What screen/menu is shown? (overworld, battle, dialog, menu, title)
2. Any text visible? What does it say?
3. If overworld: describe the location, any NPCs or obstacles
4. If battle: which Pokemon are fighting, any HP bars visible
5. If menu: what options are shown, which is selected
Be concise and factual."""


class StrategyEngine:
    """LLM-powered decision engine with caching and vision."""

    def __init__(self, config: AgentConfig, analyzer: GameAnalyzer | None = None):
        self.config = config
        self.analyzer = analyzer
        self.cache = DecisionCache(
            config.cache_dir,
            enabled=config.cache_enabled,
        )

        # Initialize text LLM client
        llm_cfg = config.get_llm_config()
        self._text_client = None
        self._text_model = llm_cfg["model"]
        if OpenAI and llm_cfg.get("base_url"):
            self._text_client = OpenAI(
                base_url=llm_cfg["base_url"],
                api_key=llm_cfg.get("api_key") or "not-needed",
            )

        # Initialize vision client (may be same or different)
        self._vision_client = None
        self._vision_model = None
        if config.has_vision:
            vis_cfg = config.get_vision_config()
            self._vision_model = vis_cfg["model"]
            if OpenAI and vis_cfg.get("base_url"):
                self._vision_client = OpenAI(
                    base_url=vis_cfg["base_url"],
                    api_key=vis_cfg.get("api_key") or "not-needed",
                )

        self._verbose = config.verbose

    def _log(self, msg: str):
        if self._verbose:
            print(f"  [strategy] {msg}")

    # ============================================================
    # Text LLM calls
    # ============================================================

    def _ask_llm(self, system: str, user: str, max_tokens: int = 256) -> str:
        """Send a text prompt to the LLM. Returns raw response text."""
        if not self._text_client:
            self._log("no LLM client available, returning default")
            return '{"action": "wait", "frames": 60}'

        self._log(f"calling LLM ({self._text_model})...")
        try:
            response = self._text_client.chat.completions.create(
                model=self._text_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            text = response.choices[0].message.content or ""
            self._log(f"LLM response: {text[:200]}")
            return text
        except Exception as e:
            self._log(f"LLM error: {e}")
            return '{"action": "wait", "frames": 60}'

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        return {"action": "wait", "frames": 60}

    # ============================================================
    # Vision LLM calls
    # ============================================================

    def analyze_screenshot(self, screenshot_b64: str, prompt: str | None = None) -> str:
        """
        Send a screenshot to the vision model for analysis.

        Args:
            screenshot_b64: Base64-encoded PNG image data
            prompt: Custom prompt (uses default if None)

        Returns:
            Description of what's on screen
        """
        if not self._vision_client:
            return "(no vision model available)"

        prompt = prompt or VISION_PROMPT
        self._log(f"analyzing screenshot with vision model ({self._vision_model})...")

        try:
            response = self._vision_client.chat.completions.create(
                model=self._vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}"
                            },
                        },
                    ],
                }],
                max_tokens=512,
                temperature=0.2,
            )
            text = response.choices[0].message.content or ""
            self._log(f"vision response: {text[:200]}")
            return text
        except Exception as e:
            self._log(f"vision error: {e}")
            return f"(vision error: {e})"

    # ============================================================
    # Battle Strategy
    # ============================================================

    async def choose_battle_action(
        self,
        state: GameState,
        screenshot_b64: str | None = None,
    ) -> dict:
        """
        Choose what to do in battle.

        Returns dict: {"action": "move"|"run"|"switch"|"item", ...}
        """
        if not state.battle or not state.battle.my_pokemon or not state.battle.enemy_pokemon:
            return {"action": "move", "index": 0}

        my = state.battle.my_pokemon
        enemy = state.battle.enemy_pokemon

        # Check cache first
        cache_key = make_battle_cache_key(
            my_species=my.species,
            my_level=my.level,
            my_hp=my.hp,
            my_max_hp=my.max_hp,
            my_moves=my.moves,
            enemy_species=enemy.species,
            enemy_level=enemy.level,
            enemy_hp_bucket=bucket_hp(enemy.hp, enemy.max_hp),
        )

        cached = self.cache.get(cache_key)
        if cached:
            self._log(f"cache hit for battle decision: {cached}")
            return self._parse_json_response(cached)

        # Build battle context for LLM
        # Load move data for detailed info
        try:
            from . import pokemon_data as pdata
            move_db = pdata.MOVES
            type_names = pdata.TYPE_NAMES
        except ImportError:
            move_db = {}
            type_names = {}

        def describe_move(move_id, move_name, pp):
            info = move_db.get(move_id, {})
            mtype = info.get("type", "???")
            power = info.get("power", 0)
            acc = info.get("accuracy", 0)
            if power > 0:
                return f"{move_name} ({mtype}, pwr:{power}, acc:{acc}, PP:{pp})"
            elif move_id > 0:
                return f"{move_name} ({mtype}, status, acc:{acc}, PP:{pp})"
            return None

        moves_desc = []
        for i, (move_id, move_name, pp) in enumerate(
            zip(my.moves, my.move_names, my.pp)
        ):
            desc = describe_move(move_id, move_name, pp)
            if desc:
                moves_desc.append(f"  {i}: {desc}")

        # Enemy moves with full details
        enemy_moves_desc = []
        for i, (move_id, move_name, pp) in enumerate(
            zip(enemy.moves, enemy.move_names, enemy.pp)
        ):
            desc = describe_move(move_id, move_name, pp)
            if desc:
                enemy_moves_desc.append(f"  {i}: {desc}")

        alive_party = [
            f"  {i}: {p.species_name} Lv{p.level} HP:{p.hp}/{p.max_hp} [{p.status_name}]"
            for i, p in enumerate(state.party) if p.is_alive
        ]

        # Type names for display
        my_type1 = type_names.get(my.type1, f"type_{my.type1}")
        my_type2 = type_names.get(my.type2, f"type_{my.type2}")
        en_type1 = type_names.get(enemy.type1, f"type_{enemy.type1}")
        en_type2 = type_names.get(enemy.type2, f"type_{enemy.type2}")

        my_types = my_type1 if my_type1 == my_type2 else f"{my_type1}/{my_type2}"
        en_types = en_type1 if en_type1 == en_type2 else f"{en_type1}/{en_type2}"

        # Stat modifiers
        my_mods = state.battle.my_stat_mods.describe("My mods: ")
        en_mods = state.battle.enemy_stat_mods.describe("Enemy mods: ")

        # Battle effects
        my_effects = state.battle.my_battle_effects
        en_effects = state.battle.enemy_battle_effects
        my_effects_str = f"My effects: {', '.join(my_effects)}" if my_effects else ""
        en_effects_str = f"Enemy effects: {', '.join(en_effects)}" if en_effects else ""

        # Stats
        my_stats = f"ATK:{my.attack} DEF:{my.defense} SPD:{my.speed} SPC:{my.special}"
        en_stats = f"ATK:{enemy.attack} DEF:{enemy.defense} SPD:{enemy.speed} SPC:{enemy.special}"

        user_msg = f"""Battle state:
My Pokemon: {my.species_name} Lv{my.level} [{my_types}] HP:{my.hp}/{my.max_hp} [{my.status_name}]
My stats: {my_stats}
{my_mods}
My moves:
{chr(10).join(moves_desc)}

Enemy: {enemy.species_name} Lv{enemy.level} [{en_types}] HP:{enemy.hp}/{enemy.max_hp} [{enemy.status_name}]
Enemy stats: {en_stats}
{en_mods}
Enemy moves (read from memory $CFEC):
{chr(10).join(enemy_moves_desc) if enemy_moves_desc else "  (no moves detected)"}

Battle type: {"Wild" if state.battle.is_wild else "Trainer"}"""

        if not state.battle.is_wild:
            user_msg += f"\nTrainer class: {state.battle.trainer_class}, Enemy party size: {state.battle.enemy_party_count}"
        if state.battle.is_wild and state.battle.catch_rate > 0:
            user_msg += f"\nCatch rate: {state.battle.catch_rate}/255"

        if my_effects_str:
            user_msg += f"\n{my_effects_str}"
        if en_effects_str:
            user_msg += f"\n{en_effects_str}"

        user_msg += f"""

My alive party:
{chr(10).join(alive_party)}

Badges: {state.badge_count}/8

Memory reference: Enemy data at $CFE4-$D006 (species=$CFE4, HP=$CFE5, moves=$CFEC, stats=$CFF5-$CFFB, catch_rate=$D006). Stat mods at $CD2E-$CD31 (7=neutral)."""

        # Add realtime ROM analysis context (cached per trainer class)
        if self.analyzer:
            trainer_class = state.battle.trainer_class if state.battle else 0
            analysis_ctx = await self.analyzer.get_battle_analysis_context(trainer_class)
            trainer_name = self.analyzer.get_trainer_name(trainer_class)
            if not state.battle.is_wild:
                user_msg += f"\nTrainer: {trainer_name}"
            user_msg += f"\n\nGame engine context:\n{analysis_ctx}"

        # Add vision analysis if available
        if screenshot_b64 and self._vision_client:
            vision_desc = self.analyze_screenshot(
                screenshot_b64,
                "Describe this Pokemon battle screenshot briefly. "
                "What Pokemon are shown? Any HP bars or status info visible?"
            )
            user_msg += f"\n\nScreenshot analysis: {vision_desc}"

        response_text = self._ask_llm(BATTLE_SYSTEM_PROMPT, user_msg)
        decision = self._parse_json_response(response_text)

        # Cache the decision
        self.cache.put(
            cache_key,
            json.dumps(decision),
            context=f"{my.species_name} vs {enemy.species_name}",
            max_hits=20,
        )

        return decision

    # ============================================================
    # Overworld Strategy
    # ============================================================

    def decide_next_action(
        self,
        state: GameState,
        screenshot_b64: str | None = None,
    ) -> dict:
        """
        Decide what to do in the overworld.

        Returns dict: {"action": "explore"|"heal"|"interact"|...}
        """
        # Quick coded decisions first (no LLM needed)

        # If party is hurting, heal
        if state.party:
            avg_hp_pct = sum(p.hp_fraction for p in state.party) / len(state.party)
            if avg_hp_pct < 0.3 and state.alive_party_count > 0:
                self._log("party HP low, suggesting heal")
                return {"action": "heal"}

        # Check cache
        cache_key = make_strategy_cache_key(
            map_id=state.map_id,
            badge_count=state.badge_count,
            party_species=state.party_species,
            party_avg_level=state.party_avg_level,
        )

        cached = self.cache.get(cache_key)
        if cached:
            self._log(f"cache hit for strategy: {cached}")
            return self._parse_json_response(cached)

        # Build context for LLM
        party_desc = "\n".join(
            f"  {p.species_name} Lv{p.level} HP:{p.hp}/{p.max_hp} [{p.status_name}] "
            f"Moves: {', '.join(n for n in p.move_names if n != '---')}"
            for p in state.party
        )

        user_msg = f"""Current state:
Map: {state.map_name} (ID: {state.map_id})
Position: ({state.player_x}, {state.player_y})
Facing: {state.facing.name}
Badges: {state.badge_count}/8 (bits: {state.badges:#04x})
Money: ${state.money}
Pikachu happiness: {state.pikachu_happiness}

Party:
{party_desc}"""

        # Add vision if available
        if screenshot_b64 and self._vision_client:
            vision_desc = self.analyze_screenshot(
                screenshot_b64,
                "Describe this Pokemon Yellow overworld screenshot. "
                "What location is shown? Any NPCs, buildings, or paths visible? "
                "Which direction can the player go?"
            )
            user_msg += f"\n\nScreenshot analysis: {vision_desc}"

        response_text = self._ask_llm(STRATEGY_SYSTEM_PROMPT, user_msg)
        decision = self._parse_json_response(response_text)

        # Cache with lower max_hits since overworld state changes more
        self.cache.put(
            cache_key,
            json.dumps(decision),
            context=f"map:{state.map_name} badges:{state.badge_count}",
            max_hits=5,
        )

        return decision

    # ============================================================
    # General vision query
    # ============================================================

    def describe_screen(self, screenshot_b64: str) -> str:
        """Get a description of the current screen using vision model."""
        if not self._vision_client:
            return "(vision not available)"
        return self.analyze_screenshot(screenshot_b64)

    # ============================================================
    # Stats
    # ============================================================

    @property
    def cache_stats(self) -> dict:
        return self.cache.stats
