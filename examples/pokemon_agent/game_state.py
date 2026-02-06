"""Layer 1: Game State Reader.

Reads Pokemon Yellow memory via MCP and builds a structured GameState.
This runs every cycle and is the agent's "eyes" into the game.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from . import memory_map as mem


class GameMode(Enum):
    """Current game mode detected from memory."""
    UNKNOWN = auto()
    TITLE_SCREEN = auto()
    OVERWORLD = auto()
    BATTLE = auto()
    DIALOG = auto()
    MENU = auto()
    BATTLE_MENU = auto()     # In battle, selecting action
    WHITEOUT = auto()        # Blacked out / lost battle


class Direction(Enum):
    DOWN = 0x00
    UP = 0x04
    LEFT = 0x08
    RIGHT = 0x0C


@dataclass
class Pokemon:
    """A Pokemon in the party or battle."""
    species: int         # Internal species index
    species_name: str
    level: int
    hp: int
    max_hp: int
    moves: list[int]     # Move indices (up to 4)
    move_names: list[str]
    pp: list[int]        # PP for each move
    status: int          # Status condition byte
    type1: int
    type2: int
    attack: int
    defense: int
    speed: int
    special: int

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def hp_fraction(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0

    @property
    def status_name(self) -> str:
        if self.status == 0:
            return "OK"
        if self.status & mem.STATUS_PARALYSIS:
            return "PAR"
        if self.status & mem.STATUS_BURN:
            return "BRN"
        if self.status & mem.STATUS_FREEZE:
            return "FRZ"
        if self.status & mem.STATUS_POISON:
            return "PSN"
        if self.status & mem.STATUS_SLEEP_MASK:
            return "SLP"
        return "???"


@dataclass
class StatModifiers:
    """Battle stat stage modifiers (1-13, 7=neutral)."""
    attack: int = 7
    defense: int = 7
    speed: int = 7
    special: int = 7

    def describe(self, prefix: str = "") -> str:
        """Return human-readable string of non-neutral modifiers."""
        parts = []
        for name, val in [("ATK", self.attack), ("DEF", self.defense),
                          ("SPD", self.speed), ("SPC", self.special)]:
            if val != 7:
                sign = "+" if val > 7 else ""
                parts.append(f"{name}{sign}{val - 7}")
        if not parts:
            return f"{prefix}no modifiers" if prefix else "no modifiers"
        return f"{prefix}{', '.join(parts)}"


@dataclass
class BattleState:
    """Current battle information."""
    is_wild: bool                # True=wild, False=trainer
    my_pokemon: Pokemon | None
    enemy_pokemon: Pokemon | None
    turn_number: int = 0

    # Enemy details
    enemy_party_count: int = 0   # Number of Pokemon on enemy trainer's team
    trainer_class: int = 0       # Trainer class ID (0 for wild)
    catch_rate: int = 0          # Enemy's catch rate (wild only)

    # Stat modifiers for active battle mons
    my_stat_mods: StatModifiers = field(default_factory=StatModifiers)
    enemy_stat_mods: StatModifiers = field(default_factory=StatModifiers)

    # Battle status flags (raw bytes)
    my_battle_status: tuple[int, int, int] = (0, 0, 0)
    enemy_battle_status: tuple[int, int, int] = (0, 0, 0)

    def _describe_battle_status(self, status: tuple[int, int, int]) -> list[str]:
        """Decode battle status flag bytes into human-readable effects."""
        s1, s2, s3 = status
        effects = []
        if s1 & mem.BSTATUS1_SUBSTITUTE:
            effects.append("Substitute")
        if s1 & mem.BSTATUS1_RECHARGING:
            effects.append("Recharging")
        if s1 & mem.BSTATUS1_RAGE:
            effects.append("Rage")
        if s1 & mem.BSTATUS1_FLINCH:
            effects.append("Flinch")
        if s1 & mem.BSTATUS1_CHARGING:
            effects.append("Charging")
        if s1 & mem.BSTATUS1_BIDE:
            effects.append("Bide")
        if s2 & mem.BSTATUS2_CONFUSED:
            effects.append("Confused")
        if s2 & mem.BSTATUS2_FOCUS_ENERGY:
            effects.append("FocusEnergy")
        if s2 & mem.BSTATUS2_X_ACCURACY:
            effects.append("XAccuracy")
        if s3 & mem.BSTATUS3_REFLECT:
            effects.append("Reflect")
        if s3 & mem.BSTATUS3_LIGHT_SCREEN:
            effects.append("LightScreen")
        if s3 & mem.BSTATUS3_TRANSFORMED:
            effects.append("Transformed")
        return effects

    @property
    def my_battle_effects(self) -> list[str]:
        return self._describe_battle_status(self.my_battle_status)

    @property
    def enemy_battle_effects(self) -> list[str]:
        return self._describe_battle_status(self.enemy_battle_status)

    @property
    def summary(self) -> str:
        if not self.my_pokemon or not self.enemy_pokemon:
            return "battle (no data)"
        parts = [
            f"{'Wild' if self.is_wild else 'Trainer'} battle: "
            f"{self.my_pokemon.species_name} Lv{self.my_pokemon.level} "
            f"({self.my_pokemon.hp}/{self.my_pokemon.max_hp}) vs "
            f"{self.enemy_pokemon.species_name} Lv{self.enemy_pokemon.level} "
            f"({self.enemy_pokemon.hp}/{self.enemy_pokemon.max_hp})"
        ]
        if not self.is_wild:
            parts.append(f"  Trainer class: {self.trainer_class}, enemy party: {self.enemy_party_count}")
        if self.is_wild and self.catch_rate > 0:
            parts.append(f"  Catch rate: {self.catch_rate}/255")
        my_effects = self.my_battle_effects
        enemy_effects = self.enemy_battle_effects
        if my_effects:
            parts.append(f"  My effects: {', '.join(my_effects)}")
        if enemy_effects:
            parts.append(f"  Enemy effects: {', '.join(enemy_effects)}")
        return "\n".join(parts)


@dataclass
class GameState:
    """Complete snapshot of the game state."""
    mode: GameMode
    frame: int

    # Position
    map_id: int = 0
    map_name: str = ""
    player_x: int = 0
    player_y: int = 0
    facing: Direction = Direction.DOWN
    walk_counter: int = 0
    tile_ahead: int = 0

    # Party
    party: list[Pokemon] = field(default_factory=list)
    party_count: int = 0

    # Battle
    battle: BattleState | None = None

    # Progress
    badges: int = 0
    badge_count: int = 0
    money: int = 0

    # UI
    menu_cursor: int = 0
    menu_max: int = 0
    text_active: bool = False
    pikachu_happiness: int = 0

    # Raw
    joypad_pressed: int = 0
    joypad_held: int = 0

    @property
    def alive_party_count(self) -> int:
        return sum(1 for p in self.party if p.is_alive)

    @property
    def party_avg_level(self) -> int:
        if not self.party:
            return 0
        return sum(p.level for p in self.party) // len(self.party)

    @property
    def party_species(self) -> list[int]:
        return [p.species for p in self.party]

    def summary(self) -> str:
        lines = [
            f"Mode: {self.mode.name} | Frame: {self.frame}",
            f"Map: {self.map_name} ({self.map_id}) | Pos: ({self.player_x}, {self.player_y})",
            f"Party: {self.party_count} ({self.alive_party_count} alive) | Badges: {self.badge_count} | Money: ${self.money}",
        ]
        if self.party:
            lead = self.party[0]
            lines.append(
                f"Lead: {lead.species_name} Lv{lead.level} "
                f"HP:{lead.hp}/{lead.max_hp} [{lead.status_name}]"
            )
        if self.battle:
            lines.append(self.battle.summary)
        return "\n".join(lines)


class GameStateReader:
    """Reads game state from memory via MCP tool calls."""

    def __init__(self, call_tool):
        """
        Args:
            call_tool: async callable(name, args) → result
                       Wraps MCP tool invocation.
        """
        self._call = call_tool
        # Lazy imports to avoid circular deps
        self._species_names: dict[int, str] = {}
        self._move_names: dict[int, str] = {}
        self._map_names: dict[int, str] = {}
        self._data_loaded = False

    def _ensure_data(self):
        """Load static data tables on first use."""
        if self._data_loaded:
            return
        try:
            from . import pokemon_data as data
            self._species_names = {idx: info["name"] for idx, info in data.SPECIES.items()}
            self._move_names = {idx: info["name"] for idx, info in data.MOVES.items()}
            self._map_names = data.MAP_NAMES
        except ImportError:
            pass
        self._data_loaded = True

    def _species_name(self, idx: int) -> str:
        self._ensure_data()
        return self._species_names.get(idx, f"???({idx:#04x})")

    def _move_name(self, idx: int) -> str:
        self._ensure_data()
        if idx == 0:
            return "---"
        return self._move_names.get(idx, f"move_{idx}")

    def _map_name(self, idx: int) -> str:
        self._ensure_data()
        return self._map_names.get(idx, f"map_{idx}")

    async def _read(self, address: int, length: int = 1) -> list[int]:
        """Read bytes from memory. Returns list of int values."""
        result = await self._call("read_memory", {
            "address": address,
            "length": length,
        })
        if isinstance(result, dict) and "bytes" in result:
            return result["bytes"]
        if isinstance(result, dict) and "error" in result:
            return [0] * length
        return [0] * length

    async def _read_byte(self, address: int) -> int:
        vals = await self._read(address, 1)
        return vals[0] if vals else 0

    async def _read_word(self, address: int) -> int:
        """Read 2-byte big-endian value (as Pokemon uses)."""
        vals = await self._read(address, 2)
        if len(vals) >= 2:
            return (vals[0] << 8) | vals[1]
        return 0

    async def _read_bcd(self, address: int, length: int) -> int:
        """Read BCD-encoded value."""
        vals = await self._read(address, length)
        result = 0
        for b in vals:
            result = result * 100 + ((b >> 4) * 10) + (b & 0x0F)
        return result

    async def _read_pokemon(self, base_addr: int) -> Pokemon:
        """Read a Pokemon structure from memory."""
        data = await self._read(base_addr, mem.PARTY_MON_SIZE)
        if len(data) < mem.PARTY_MON_SIZE:
            data.extend([0] * (mem.PARTY_MON_SIZE - len(data)))

        species = data[mem.MON_SPECIES]
        hp = (data[mem.MON_HP] << 8) | data[mem.MON_HP + 1]
        max_hp = (data[mem.MON_MAX_HP] << 8) | data[mem.MON_MAX_HP + 1]
        level = data[mem.MON_LEVEL]
        status = data[mem.MON_STATUS]
        type1 = data[mem.MON_TYPE1]
        type2 = data[mem.MON_TYPE2]
        moves = [data[mem.MON_MOVES + i] for i in range(4)]
        pp = [data[mem.MON_PP + i] for i in range(4)]
        attack = (data[mem.MON_ATTACK] << 8) | data[mem.MON_ATTACK + 1]
        defense = (data[mem.MON_DEFENSE] << 8) | data[mem.MON_DEFENSE + 1]
        speed = (data[mem.MON_SPEED] << 8) | data[mem.MON_SPEED + 1]
        special = (data[mem.MON_SPECIAL] << 8) | data[mem.MON_SPECIAL + 1]

        return Pokemon(
            species=species,
            species_name=self._species_name(species),
            level=level,
            hp=hp,
            max_hp=max_hp,
            moves=moves,
            move_names=[self._move_name(m) for m in moves],
            pp=pp,
            status=status,
            type1=type1,
            type2=type2,
            attack=attack,
            defense=defense,
            speed=speed,
            special=special,
        )

    async def _read_battle_pokemon(self, is_enemy: bool) -> Pokemon:
        """Read the active battle Pokemon (player or enemy)."""
        if is_enemy:
            species = await self._read_byte(mem.WRAM_ENEMY_MON_SPECIES)
            hp = await self._read_word(mem.WRAM_ENEMY_MON_HP)
            max_hp = await self._read_word(mem.WRAM_ENEMY_MON_MAX_HP)
            level = await self._read_byte(mem.WRAM_ENEMY_MON_LEVEL)
            status = await self._read_byte(mem.WRAM_ENEMY_MON_STATUS)
            type1 = await self._read_byte(mem.WRAM_ENEMY_MON_TYPE1)
            type2 = await self._read_byte(mem.WRAM_ENEMY_MON_TYPE2)
            move_data = await self._read(mem.WRAM_ENEMY_MON_MOVES, 4)
            pp_data = await self._read(mem.WRAM_ENEMY_MON_PP, 4)
            attack = await self._read_word(mem.WRAM_ENEMY_MON_ATTACK)
            defense = await self._read_word(mem.WRAM_ENEMY_MON_DEFENSE)
            speed = await self._read_word(mem.WRAM_ENEMY_MON_SPEED)
            special = await self._read_word(mem.WRAM_ENEMY_MON_SPECIAL)
        else:
            species = await self._read_byte(mem.WRAM_BATTLE_MON_SPECIES)
            hp = await self._read_word(mem.WRAM_BATTLE_MON_HP)
            max_hp = await self._read_word(mem.WRAM_BATTLE_MON_MAX_HP)
            level = await self._read_byte(mem.WRAM_BATTLE_MON_LEVEL)
            status = await self._read_byte(mem.WRAM_BATTLE_MON_STATUS)
            type1 = await self._read_byte(mem.WRAM_BATTLE_MON_TYPE1)
            type2 = await self._read_byte(mem.WRAM_BATTLE_MON_TYPE2)
            move_data = await self._read(mem.WRAM_BATTLE_MON_MOVES, 4)
            pp_data = await self._read(mem.WRAM_BATTLE_MON_PP, 4)
            attack = await self._read_word(mem.WRAM_BATTLE_MON_ATTACK)
            defense = await self._read_word(mem.WRAM_BATTLE_MON_DEFENSE)
            speed = await self._read_word(mem.WRAM_BATTLE_MON_SPEED)
            special = await self._read_word(mem.WRAM_BATTLE_MON_SPECIAL)

        moves = list(move_data) if move_data else [0, 0, 0, 0]
        pp = list(pp_data) if pp_data else [0, 0, 0, 0]

        return Pokemon(
            species=species,
            species_name=self._species_name(species),
            level=level,
            hp=hp,
            max_hp=max_hp,
            moves=moves,
            move_names=[self._move_name(m) for m in moves],
            pp=pp,
            status=status,
            type1=type1,
            type2=type2,
            attack=attack,
            defense=defense,
            speed=speed,
            special=special,
        )

    def _detect_mode(
        self,
        in_battle: int,
        map_id: int,
        menu_cursor: int,
        text_box_id: int,
        ignore_input: int,
        pc: int,
    ) -> GameMode:
        """Detect current game mode from memory values."""
        # Lost battle
        if in_battle == 0xFF:
            return GameMode.WHITEOUT

        # In battle
        if in_battle in (1, 2):
            return GameMode.BATTLE

        # Title screen detection: map_id 0 with specific PC ranges
        # or before the game has properly initialized
        if map_id == 0 and pc < 0x4000:
            return GameMode.TITLE_SCREEN

        # Text/dialog active
        if text_box_id != 0 or ignore_input > 0:
            return GameMode.DIALOG

        # Overworld (default)
        return GameMode.OVERWORLD

    async def read_state(self) -> GameState:
        """Read complete game state from memory."""
        self._ensure_data()

        # Read core state bytes in bulk where possible
        in_battle = await self._read_byte(mem.WRAM_IS_IN_BATTLE)
        map_id = await self._read_byte(mem.WRAM_CUR_MAP)
        player_x = await self._read_byte(mem.WRAM_X_COORD)
        player_y = await self._read_byte(mem.WRAM_Y_COORD)
        facing_raw = await self._read_byte(mem.WRAM_PLAYER_DIRECTION)
        walk_counter = await self._read_byte(mem.WRAM_WALK_COUNTER)
        tile_ahead = await self._read_byte(mem.WRAM_TILE_IN_FRONT)
        party_count = await self._read_byte(mem.WRAM_PARTY_COUNT)
        badges = await self._read_byte(mem.WRAM_BADGES)
        money = await self._read_bcd(mem.WRAM_MONEY, 3)
        menu_cursor = await self._read_byte(mem.WRAM_CURRENT_MENU_ITEM)
        menu_max = await self._read_byte(mem.WRAM_MAX_MENU_ITEM)
        text_box_id = await self._read_byte(mem.WRAM_TEXT_BOX_ID)
        ignore_input = await self._read_byte(mem.WRAM_IGNORE_INPUT_COUNTER)
        pikachu = await self._read_byte(mem.WRAM_PIKACHU_HAPPINESS)
        joy_pressed = await self._read_byte(mem.HRAM_JOY_PRESSED)
        joy_held = await self._read_byte(mem.HRAM_JOY_HELD)
        frame = await self._read_byte(mem.HRAM_FRAME_COUNTER)

        # Get CPU PC for title screen detection
        regs = await self._call("get_registers", {})
        pc = regs.get("PC", 0) if isinstance(regs, dict) else 0

        # Parse direction
        try:
            facing = Direction(facing_raw & 0x0C)
        except ValueError:
            facing = Direction.DOWN

        # Detect mode
        mode = self._detect_mode(in_battle, map_id, menu_cursor, text_box_id, ignore_input, pc)

        # Read party Pokemon
        party = []
        count = min(party_count, 6)
        for i in range(count):
            mon = await self._read_pokemon(mem.PARTY_MON_ADDRESSES[i])
            party.append(mon)

        # Read battle state if in battle
        battle = None
        if mode == GameMode.BATTLE:
            my_mon = await self._read_battle_pokemon(is_enemy=False)
            enemy_mon = await self._read_battle_pokemon(is_enemy=True)

            # Read stat modifiers (1-13, 7=neutral)
            my_stat_mods = StatModifiers(
                attack=await self._read_byte(mem.WRAM_PLAYER_ATK_MOD),
                defense=await self._read_byte(mem.WRAM_PLAYER_DEF_MOD),
                speed=await self._read_byte(mem.WRAM_PLAYER_SPD_MOD),
                special=await self._read_byte(mem.WRAM_PLAYER_SPC_MOD),
            )
            enemy_stat_mods = StatModifiers(
                attack=await self._read_byte(mem.WRAM_ENEMY_ATK_MOD),
                defense=await self._read_byte(mem.WRAM_ENEMY_DEF_MOD),
                speed=await self._read_byte(mem.WRAM_ENEMY_SPD_MOD),
                special=await self._read_byte(mem.WRAM_ENEMY_SPC_MOD),
            )

            # Read battle status flags
            my_bs1 = await self._read_byte(mem.WRAM_PLAYER_BATTLE_STATUS1)
            my_bs2 = await self._read_byte(mem.WRAM_PLAYER_BATTLE_STATUS2)
            my_bs3 = await self._read_byte(mem.WRAM_PLAYER_BATTLE_STATUS3)
            en_bs1 = await self._read_byte(mem.WRAM_ENEMY_BATTLE_STATUS1)
            en_bs2 = await self._read_byte(mem.WRAM_ENEMY_BATTLE_STATUS2)
            en_bs3 = await self._read_byte(mem.WRAM_ENEMY_BATTLE_STATUS3)

            # Trainer/catch info
            trainer_class = await self._read_byte(mem.WRAM_TRAINER_CLASS)
            enemy_party_count = await self._read_byte(mem.WRAM_ENEMY_PARTY_COUNT)
            catch_rate = await self._read_byte(mem.WRAM_ENEMY_MON_CATCH_RATE)

            battle = BattleState(
                is_wild=(in_battle == 1),
                my_pokemon=my_mon,
                enemy_pokemon=enemy_mon,
                enemy_party_count=enemy_party_count,
                trainer_class=trainer_class,
                catch_rate=catch_rate,
                my_stat_mods=my_stat_mods,
                enemy_stat_mods=enemy_stat_mods,
                my_battle_status=(my_bs1, my_bs2, my_bs3),
                enemy_battle_status=(en_bs1, en_bs2, en_bs3),
            )

        return GameState(
            mode=mode,
            frame=frame,
            map_id=map_id,
            map_name=self._map_name(map_id),
            player_x=player_x,
            player_y=player_y,
            facing=facing,
            walk_counter=walk_counter,
            tile_ahead=tile_ahead,
            party=party,
            party_count=count,
            battle=battle,
            badges=badges,
            badge_count=bin(badges).count("1"),
            money=money,
            menu_cursor=menu_cursor,
            menu_max=menu_max,
            text_active=(text_box_id != 0 or ignore_input > 0),
            pikachu_happiness=pikachu,
            joypad_pressed=joy_pressed,
            joypad_held=joy_held,
        )
