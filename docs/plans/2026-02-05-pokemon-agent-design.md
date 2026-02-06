# Pokemon Yellow Autonomous Agent — Design

## Overview

A hybrid autonomous agent that plays Pokemon Yellow using the SameBoy MCP server.
Coded Python routines handle frame-by-frame execution. An LLM (any OpenAI-compatible
API: Ollama, Groq, OpenRouter) is called only for strategic decisions, with aggressive
caching to minimize API calls.

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│  Layer 3: LLM Strategy Engine (cached)                    │
│  Called for: battle move choice, route planning,           │
│  next objective, party management                          │
│  Providers: Ollama (free/local), Groq (free tier),         │
│  OpenRouter, Anthropic, any OpenAI-compat API              │
├───────────────────────────────────────────────────────────┤
│  Layer 2: Coded Routines                                   │
│  walk_to(), navigate_menu(), advance_text(),               │
│  execute_battle_move(), use_pokecenter(), buy_items()       │
├───────────────────────────────────────────────────────────┤
│  Layer 1: Game State Reader                                │
│  Reads memory → builds GameState every cycle               │
│  Detects: overworld, battle, menu, dialog, title screen    │
├───────────────────────────────────────────────────────────┤
│  SameBoy MCP Server (existing)                             │
│  read_memory, press_key, capture_screen, run_frames,       │
│  breakpoints, disassemble_rom, monitor_memory              │
└───────────────────────────────────────────────────────────┘
```

## File Structure

```
examples/pokemon_agent/
├── __init__.py
├── main.py             # Entry point, CLI args, main loop
├── game_state.py       # Layer 1: Memory reader, state detection
├── routines.py         # Layer 2: Navigation, menus, text, battle execution
├── strategy.py         # Layer 3: LLM decision engine with caching
├── memory_map.py       # Pokemon Yellow RAM addresses (from pokeyellow disasm)
├── pokemon_data.py     # Species, moves, types, items (static ROM data)
├── cache.py            # Decision cache (disk-persisted JSON)
└── config.py           # LLM provider config, agent settings
```

## Layer 1: Game State Reader (`game_state.py`)

Reads key memory addresses every cycle and returns a structured `GameState`:

```python
@dataclass
class GameState:
    # Mode detection
    mode: GameMode  # TITLE, OVERWORLD, BATTLE, MENU, DIALOG, POKECENTER, SHOP

    # Position
    map_id: int
    map_name: str
    player_x: int
    player_y: int
    facing: Direction

    # Party
    party: list[Pokemon]  # species, level, hp, max_hp, moves, status
    party_count: int

    # Battle (when in battle)
    battle: BattleState | None  # my_mon, enemy_mon, is_wild, turn info

    # Progress
    badges: int  # bitfield
    badge_count: int
    money: int

    # UI state
    menu_cursor: int
    text_active: bool
    pikachu_happiness: int
```

### Key Memory Addresses (Pokemon Yellow US)

| What | Address | Size |
|------|---------|------|
| In battle? | `$D056` | 1 (0=no, 1=wild, 2=trainer) |
| Map ID | `$D35D` | 1 |
| Player Y | `$D360` | 1 |
| Player X | `$D361` | 1 |
| Party count | `$D162` | 1 |
| Party mon 1 species | `$D16A` | 1 |
| Party mon 1 HP | `$D16B` | 2 (big-endian) |
| Party mon 1 level | `$D18B` | 1 |
| Party mon 1 moves | `$D172` | 4 |
| Badges | `$D355` | 1 bitfield |
| Money | `$D346` | 3 BCD |
| Enemy species | `$CFE4` | 1 |
| Enemy HP | `$CFE5` | 2 |
| Enemy level | `$CFF2` | 1 |
| Menu cursor | `$CC26` | 1 |
| Pikachu happiness | `$D46F` | 1 |
| Walk counter | `$CFC4` | 1 |
| Tile ahead | `$CFC5` | 1 |
| Joypad pressed | `$FFB3` | 1 |
| Joypad held | `$FFB4` | 1 |
| Buttons to ignore | `$CD6B` | 1 |
| Frame counter | `$FFD5` | 1 |

### State Detection Logic

```
if read($D056) != 0 → BATTLE
elif text_box_active() → DIALOG
elif menu_is_open() → MENU
elif at_title_screen() → TITLE
else → OVERWORLD
```

## Layer 2: Coded Routines (`routines.py`)

State machines that execute actions via MCP tools without LLM calls:

### `advance_text()`
- Detect text box on screen
- Press A repeatedly until text clears
- Handle YES/NO prompts based on strategy directive

### `navigate_menu(target_index)`
- Read current menu cursor position
- Press UP/DOWN to reach target
- Press A to select

### `walk_direction(direction, steps)`
- Press directional key
- Wait for walk animation to complete (watch `$CFC4`)
- Verify position changed

### `execute_battle_move(move_index)`
- Navigate battle menu: FIGHT → select move by index
- Wait for battle animation to complete
- Return result (hit, miss, KO, etc.)

### `use_pokecenter()`
- Walk to nurse → talk → advance dialog → exit

### `run_from_battle()`
- Select RUN from battle menu

### `switch_pokemon(party_index)`
- Navigate: POKEMON → select mon → SWITCH

## Layer 3: LLM Strategy Engine (`strategy.py`)

Called ONLY when a decision is needed. Results are cached.

### Decision Points

1. **Battle: which move?**
   - Input: my_pokemon, my_moves, enemy_pokemon, enemy_type, hp_ratios
   - Output: move_index (0-3) or "run" or "switch:N"
   - Cache key: `(my_species, my_level_bucket, enemy_species, enemy_level_bucket, hp_bucket)`

2. **Overworld: what next?**
   - Input: map_id, badges, party_summary, objective
   - Output: action plan (go to X, fight trainer, enter building)
   - Cache key: `(map_id, badge_count, objective_hash)`

3. **Party management**
   - Input: party composition, new Pokemon available
   - Output: catch/release/teach TM decisions

### Cache Strategy

```python
class DecisionCache:
    """Disk-persisted LLM decision cache."""

    def __init__(self, cache_dir: str):
        self.cache_file = os.path.join(cache_dir, "decisions.json")
        self.cache: dict[str, CachedDecision] = self._load()

    def get(self, key: str) -> str | None:
        entry = self.cache.get(key)
        if entry and entry.uses < entry.max_uses:
            entry.uses += 1
            return entry.decision
        return None

    def put(self, key: str, decision: str, max_uses: int = 10):
        self.cache[key] = CachedDecision(decision=decision, max_uses=max_uses)
        self._save()
```

Cache bucketing reduces cardinality:
- HP: 0-25% → "critical", 25-50% → "low", 50-75% → "mid", 75-100% → "high"
- Level: buckets of 5 (1-5, 6-10, 11-15, ...)
- This means similar battles produce cache hits

### LLM Provider Support

```python
# Ollama (free, local)
python main.py --provider ollama --model llama3.2

# Groq (free tier)
python main.py --provider groq --api-key $GROQ_API_KEY --model llama-3.3-70b-versatile

# OpenRouter (free models)
python main.py --provider openrouter --api-key $OR_KEY --model meta-llama/llama-3.3-70b

# Anthropic
python main.py --provider anthropic --api-key $ANTHROPIC_API_KEY --model claude-sonnet-4-20250514
```

All providers use OpenAI-compatible API format (the existing agent already supports this).

## Disassembly Integration

At startup, the agent uses MCP disassembly tools to:

1. **Verify ROM**: `get_rom_header()` → confirm Pokemon Yellow
2. **Set breakpoints** on key routines for state transition detection:
   - Battle start entry
   - Map transition
   - Text engine entry
3. **Read ROM data tables** for Pokemon species/moves (via `read_memory` at known ROM addresses)

## Main Loop

```python
async def run():
    state = await read_game_state()

    match state.mode:
        case TITLE:
            await routines.press_start()

        case DIALOG:
            await routines.advance_text()

        case BATTLE:
            if needs_decision(state):
                move = await strategy.choose_battle_action(state)  # LLM (cached)
                await routines.execute_battle_action(move)

        case OVERWORLD:
            if not current_plan or plan_complete:
                plan = await strategy.decide_next_objective(state)  # LLM (cached)
            await routines.execute_plan_step(plan)

        case MENU:
            await routines.handle_menu(state)
```

## Implementation Order

1. `memory_map.py` + `pokemon_data.py` — Static data
2. `game_state.py` — Memory reader
3. `config.py` + `cache.py` — LLM config and caching
4. `routines.py` — Coded routines (start with text advance, battle execution)
5. `strategy.py` — LLM integration
6. `main.py` — Main loop tying it all together
