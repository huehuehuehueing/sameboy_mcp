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
    TITLE_SCREEN = auto()    # Press Start screen
    INTRO = auto()           # Oak's intro / copyright screens
    MAIN_MENU = auto()       # Continue / New Game menu
    NAME_ENTRY = auto()      # Entering player or rival name
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
class ScreenText:
    """Text content read from screen memory."""
    lines: list[str] = field(default_factory=list)
    raw_tiles: list[list[int]] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(self.lines)

    @property
    def has_text(self) -> bool:
        return any(line.strip() for line in self.lines)


@dataclass
class WarpPoint:
    """A warp/exit point on the map."""
    x: int
    y: int
    dest_map: int
    warp_id: int

    def __str__(self):
        return f"Warp({self.x},{self.y})->map{self.dest_map}"


@dataclass
class SpriteInfo:
    """Information about a sprite/NPC on the map."""
    index: int
    x: int  # Map X coordinate
    y: int  # Map Y coordinate
    picture_id: int
    facing: int
    is_player: bool = False

    def __str__(self):
        kind = "Player" if self.is_player else f"NPC{self.index}"
        return f"{kind}({self.x},{self.y})"


@dataclass
class MapInfo:
    """Information about the current map."""
    width: int = 0
    height: int = 0
    tileset: int = 0
    connections: int = 0  # NSEW connection flags
    visible_tiles: list[list[int]] = field(default_factory=list)
    collision_map: list[list[bool]] = field(default_factory=list)  # True = walkable
    warps: list[WarpPoint] = field(default_factory=list)
    sprites: list[SpriteInfo] = field(default_factory=list)


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
    badge_names: list[str] = field(default_factory=list)
    money: int = 0
    game_progress: str = ""  # Human-readable story progress phase
    event_flags: dict[str, bool] = field(default_factory=dict)

    # UI
    menu_cursor: int = 0
    menu_max: int = 0
    text_active: bool = False
    pikachu_happiness: int = 0

    # Screen text (decoded from tile map)
    screen_text: ScreenText | None = None

    # Map data for navigation
    map_info: MapInfo | None = None

    # Name entry state
    naming_type: int = 0       # 0=player, 1=rival, 2=pokemon
    letters_entered: int = 0   # Number of chars entered so far

    # Input control
    ignore_input: int = 0   # Frames remaining where game ignores joypad
    joypad_sim: int = 0     # Non-zero when game is simulating joypad (scripted sequences)
    joypad_disabled: bool = False  # BIT_DISABLE_JOYPAD (bit 5 of wStatusFlags5 @ 0xD72F) — definitive input block
    font_loaded: bool = False  # wFontLoaded (0xCFC3) bit 0 — textbox/font system active
    names_set: bool = False  # True when both player and rival names arent debug defaults
    pc: int = 0             # CPU program counter (for debug logging)
    game_timer_counting: bool = False  # BIT_GAME_TIMER_COUNTING: set once by SpecialEnterMap after OakSpeech

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

    def summary(self, verbose: bool = False) -> str:
        lines = [
            f"Mode: {self.mode.name} | Frame: {self.frame}",
            f"Map: {self.map_name} ({self.map_id}) | Pos: ({self.player_x}, {self.player_y})",
            f"Party: {self.party_count} ({self.alive_party_count} alive) | Badges: {self.badge_count} | Money: ${self.money}",
        ]
        if self.game_progress:
            lines.append(f"Progress: {self.game_progress}")
        if self.badge_names:
            lines.append(f"Badges: {', '.join(self.badge_names)}")
        if self.party:
            lead = self.party[0]
            lines.append(
                f"Lead: {lead.species_name} Lv{lead.level} "
                f"HP:{lead.hp}/{lead.max_hp} [{lead.status_name}]"
            )
        if self.battle:
            lines.append(self.battle.summary)

        # Show screen text if available and meaningful
        if self.screen_text and self.screen_text.has_text:
            # Get non-empty lines
            text_lines = [l for l in self.screen_text.lines if l.strip()]
            if text_lines:
                preview = " | ".join(text_lines[:3])[:80]
                lines.append(f"Screen: {preview}")

        # Show name entry state
        if self.mode == GameMode.NAME_ENTRY:
            name_type = ["player", "rival", "pokemon"][self.naming_type] if self.naming_type < 3 else "???"
            lines.append(f"Naming: {name_type} (entered: {self.letters_entered} chars)")

        # Show map info in verbose mode
        if verbose and self.map_info:
            if self.map_info.warps:
                warp_strs = [f"({w.x},{w.y})->map{w.dest_map}" for w in self.map_info.warps]
                lines.append(f"Warps: {', '.join(warp_strs)}")
            if self.map_info.sprites:
                # Show NPCs (skip player sprite)
                npcs = [s for s in self.map_info.sprites if not s.is_player]
                if npcs:
                    npc_strs = [f"NPC({s.x},{s.y})" for s in npcs]
                    lines.append(f"NPCs: {', '.join(npc_strs)}")

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

    @staticmethod
    def _decode_bcd(data: list[int]) -> int:
        """Decode BCD-encoded bytes (already read) into an integer."""
        result = 0
        for b in data:
            result = result * 100 + ((b >> 4) * 10) + (b & 0x0F)
        return result

    async def _read_range(self, address: int, length: int) -> list[int]:
        """Read a contiguous memory range. Returns list of int values."""
        result = await self._call("read_memory", {
            "address": address,
            "length": length,
        })
        if isinstance(result, dict) and "bytes" in result:
            data = result["bytes"]
        elif isinstance(result, dict) and "error" in result:
            data = [0] * length
        else:
            data = [0] * length
        # Pad to expected length if short
        if len(data) < length:
            data.extend([0] * (length - len(data)))
        return data

    async def read_event_flags(self) -> dict[str, bool]:
        """Read early game event flags from memory.

        Each flag is a single bit in the event flags bitfield.
        Flag N is at byte WRAM_EVENT_FLAGS + (N // 8), bit (N % 8).

        Returns:
            Dict mapping flag name -> bool (set or not)
        """
        flags = {}
        # Read enough bytes to cover all flags we care about
        # Max flag number is 0x34 = 52, so we need 52//8 + 1 = 7 bytes
        flag_data = await self._read(mem.WRAM_EVENT_FLAGS, 8)

        for name, flag_num in mem.EVENT_FLAGS.items():
            byte_idx = flag_num // 8
            bit_idx = flag_num % 8
            if byte_idx < len(flag_data):
                flags[name] = bool(flag_data[byte_idx] & (1 << bit_idx))
            else:
                flags[name] = False

        return flags

    async def read_game_progress(self) -> str:
        """Determine current game progress phase from event flags.

        Checks flags in reverse order (most progressed first) and returns
        a human-readable description of the current story phase.

        Returns:
            String like "GOT_POKEDEX - Explore freely with Pokedex"
        """
        flags = await self.read_event_flags()

        for flag_name, description in mem.GAME_PROGRESS_ORDER:
            if flags.get(flag_name, False):
                return f"{flag_name} - {description}"

        return "VERY_START - Beginning of game"

    def _read_badge_names(self, badge_byte: int) -> list[str]:
        """Convert badge bitfield to list of badge names."""
        names = []
        badge_list = [
            (mem.BADGE_BOULDER, "Boulder"),
            (mem.BADGE_CASCADE, "Cascade"),
            (mem.BADGE_THUNDER, "Thunder"),
            (mem.BADGE_RAINBOW, "Rainbow"),
            (mem.BADGE_SOUL, "Soul"),
            (mem.BADGE_MARSH, "Marsh"),
            (mem.BADGE_VOLCANO, "Volcano"),
            (mem.BADGE_EARTH, "Earth"),
        ]
        for bit, name in badge_list:
            if badge_byte & (1 << bit):
                names.append(name)
        return names

    async def _read_screen_text(self) -> ScreenText:
        """Read text from screen tile map (20x18 tiles)."""
        # Read the visible tile map
        tile_data = await self._read(mem.WRAM_TILE_MAP, 360)  # 20x18 = 360

        lines = []
        raw_tiles = []

        for row in range(18):
            row_tiles = tile_data[row * 20:(row + 1) * 20]
            raw_tiles.append(row_tiles)

            # Decode the row to text
            line_text = mem.decode_text(row_tiles, max_len=20)
            lines.append(line_text)

        return ScreenText(lines=lines, raw_tiles=raw_tiles)

    async def _read_warps(self) -> list[WarpPoint]:
        """Read warp points on current map."""
        warps = []
        num_warps = await self._read_byte(mem.WRAM_NUM_WARPS)

        # Each warp entry is 4 bytes: y, x, warp_id, dest_map
        for i in range(min(num_warps, 16)):  # Max 16 warps
            base = mem.WRAM_WARP_ENTRIES + (i * 4)
            data = await self._read(base, 4)
            if len(data) >= 4:
                y, x, warp_id, dest_map = data[0], data[1], data[2], data[3]
                # Coordinates are in 2x2 block units, convert to tile units
                warps.append(WarpPoint(
                    x=x,
                    y=y,
                    dest_map=dest_map,
                    warp_id=warp_id,
                ))

        return warps

    async def _read_sprites(self) -> list[SpriteInfo]:
        """Read sprite/NPC positions on current map."""
        sprites = []
        num_sprites = await self._read_byte(mem.WRAM_NUM_SPRITES)

        # Read up to 16 sprites (including player at index 0)
        for i in range(min(num_sprites + 1, 16)):
            base = mem.WRAM_SPRITE_DATA + (i * 16)
            data = await self._read(base, 16)
            if len(data) >= 14:
                picture_id = data[mem.SPRITE_PICTURE_ID]
                # Skip empty sprites
                if picture_id == 0 and i > 0:
                    continue

                map_y = data[mem.SPRITE_MAP_Y]
                map_x = data[mem.SPRITE_MAP_X]
                facing = data[mem.SPRITE_FACING]

                sprites.append(SpriteInfo(
                    index=i,
                    x=map_x,
                    y=map_y,
                    picture_id=picture_id,
                    facing=facing,
                    is_player=(i == 0),
                ))

        return sprites

    async def _read_map_info(self) -> MapInfo:
        """Read current map layout information."""
        width = await self._read_byte(mem.WRAM_CUR_MAP_WIDTH)
        height = await self._read_byte(mem.WRAM_CUR_MAP_HEIGHT)
        tileset = await self._read_byte(mem.WRAM_CUR_MAP_TILESET)
        connections = await self._read_byte(mem.WRAM_MAP_CONNECTIONS)

        # Read warp points
        warps = await self._read_warps()

        # Read sprites
        sprites = await self._read_sprites()

        return MapInfo(
            width=width,
            height=height,
            tileset=tileset,
            connections=connections,
            warps=warps,
            sprites=sprites,
        )

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
        regs: dict,
        naming_screen: int,
        party_count: int,
        oak_speech: int,
        badges: int,
        screen_text: ScreenText | None = None,
        textbox_open: int = 0,
        script_running: int = 0,
        joypad_sim: int = 0,
        names_set: bool = False,
        pc: int = 0,
        joypad_disabled: bool = False,
        scripted_movement: bool = False,
        font_loaded: bool = False,
    ) -> GameMode:
        """Detect current game mode from memory values."""
        # Lost battle
        if in_battle == 0xFF:
            return GameMode.WHITEOUT

        # In battle
        if in_battle in (1, 2):
            return GameMode.BATTLE

        # Name entry screen - detect by keyboard grid or nickname prompt
        # NOTE: Do NOT check for "YOUR NAME" / "HIS NAME" here — those
        # strings appear in Oak's dialog ("what is your name?") BEFORE the
        # keyboard opens, causing false NAME_ENTRY detection.
        if screen_text and screen_text.has_text:
            text = screen_text.full_text.upper()
            # Character grid pattern — definitive indicator of keyboard
            if "A B C D E F G H I" in text:
                return GameMode.NAME_ENTRY
            # Nickname prompt (naming a caught Pokemon)
            if "NICKNAME" in text:
                return GameMode.NAME_ENTRY

        # NOTE: naming_screen (0xCF91) is NOT reliable — the game reuses
        # this address for other purposes (e.g. PC menus) and doesn't always
        # clear it.  The keyboard grid check above is the definitive test.

        # Universal title/main menu detection for map_id=0
        # These strings only appear on title/main menu screens, so they're
        # reliable regardless of names_set (handles stale name data in RAM)
        if map_id == 0 and screen_text and screen_text.has_text:
            text = screen_text.full_text.upper()
            if "PRESS START" in text:
                print("Debug: Detected 'PRESS START' on map 0, detecting TITLE_SCREEN mode")
                return GameMode.TITLE_SCREEN
            if "NEW GAME" in text:
                print("Debug: Detected 'NEW GAME' on map 0, detecting MAIN_MENU mode")
                return GameMode.MAIN_MENU

        # Title screen / Intro detection (pre-game only)
        # Guarded by `not names_set` to prevent misdetecting Pallet Town
        # (map_id=0) as title screen when the player is actually in-game
        if party_count == 0 and badges == 0 and not names_set:
            if map_id == 0:
                # Check PC range for title screen code
                if pc < 0x4000:
                    print("Debug: Detected PC in title screen code range, detecting TITLE_SCREEN mode")
                    return GameMode.TITLE_SCREEN
                # Oak intro sequence (PC in specific ROM bank)
                if pc >= 0x4000 and pc < 0x8000:
                    if oak_speech & 0x40 == 0:
                        print("Debug: Detected Oak's intro speech (oak_speech flag), detecting INTRO mode")
                        return GameMode.INTRO

        # Fallback: map_id=0 with no party and names not set = title screen
        if map_id == 0 and party_count == 0 and not names_set:
            print("Debug: Fallback detection for title screen (map_id=0, no party, names not set)")
            return GameMode.TITLE_SCREEN

        # Check for scripted sequence using wSimulatedJoypadStatesIndex
        # The game only uses this index when BIT_SCRIPTED_MOVEMENT_STATE (bit 7
        # of wStatusFlags5) is set (see AreInputsSimulated in overworld.asm).
        # A stale non-zero value at 0xCC3F does NOT mean simulation is active —
        # only trust it when the game's own scripted movement flag is also set.
        #
        # For INTRO detection (map_id == 0, no party), we still check joypad_sim
        # alone since the intro sequence may not set BIT_SCRIPTED_MOVEMENT_STATE.
        if joypad_sim != 0:
            if party_count == 0 and badges == 0 and map_id == 0:
                print("Debug: Detected joypad simulation on title/intro map, detecting INTRO mode")
                return GameMode.INTRO
            if scripted_movement:
                print(f"Debug _detect_mode: joypad_sim={joypad_sim} + scripted_movement → DIALOG (map={map_id})")
                return GameMode.DIALOG
            # Stale joypad_sim value without BIT_SCRIPTED_MOVEMENT_STATE — ignore
            print(f"Debug _detect_mode: joypad_sim={joypad_sim} but scripted_movement=False, ignoring stale value")

        # ignore_input counter only indicates INTRO/DIALOG on map 0 when the
        # game hasn't started yet.  Pallet Town is also map_id=0, so guard
        # with `not names_set` to avoid false DIALOG on the actual overworld.
        if ignore_input > 10 and map_id == 0 and not names_set:
            if party_count == 0 and badges == 0:
                return GameMode.INTRO
            print(f"Debug _detect_mode: ignore_input={ignore_input} → DIALOG (map={map_id})")
            return GameMode.DIALOG

        # ── Deterministic dialog detection ──────────────────────
        # Primary: wStatusFlags5 bit 5 (BIT_DISABLE_JOYPAD) at 0xD72F.
        # This is checked by engine/joypad.asm — when set, ALL button
        # presses are discarded by DiscardButtonPresses.  It is the
        # game's own "input blocked" flag and is the authoritative
        # indicator of dialog/text state.
        if joypad_disabled or font_loaded:
            print(f"Debug _detect_mode: joypad_disabled={joypad_disabled} font_loaded={font_loaded} → DIALOG (map={map_id})")
            return GameMode.DIALOG

        # Secondary: screen tile analysis as fallback for menus that
        # don't set BIT_DISABLE_JOYPAD (e.g. START menu, item menus).
        from .pathfinding import is_text_box_visible, has_text_content

        has_visible_textbox = False
        has_text_chars = False
        if screen_text and screen_text.raw_tiles:
            flat_tiles = []
            for row in screen_text.raw_tiles:
                flat_tiles.extend(row)
            has_visible_textbox = is_text_box_visible(flat_tiles)
            has_text_chars = has_text_content(flat_tiles)

        if has_visible_textbox and has_text_chars:
            # Distinguish NPC dialog from menus using prompt tiles:
            #   0xEE = ▼ (continuation prompt — "press A for more text")
            #   0xED = ▶ (menu cursor — selectable option)
            # NPC dialog has ▼ and no ▶; menus have ▶ and no ▼.
            DIALOG_PROMPT_TILE = 0xEE  # ▼
            has_dialog_prompt = DIALOG_PROMPT_TILE in flat_tiles
            if has_dialog_prompt:
                print(f"Debug _detect_mode: textbox + ▼ prompt → DIALOG (map={map_id})")
                return GameMode.DIALOG
            print(f"Debug _detect_mode: textbox={has_visible_textbox} text={has_text_chars} → MENU (map={map_id})")
            return GameMode.MENU

        # Overworld (default for gameplay)
        print(f"Debug _detect_mode: → OVERWORLD (map={map_id}, joypad_sim={joypad_sim}, ignore={ignore_input}, joypad_disabled={joypad_disabled})")
        return GameMode.OVERWORLD

    async def read_state(self) -> GameState:
        """Read complete game state from memory."""
        self._ensure_data()

        # ── Batch memory reads ─────────────────────────────────
        # Group nearby addresses into contiguous range reads to reduce
        # MCP round-trips.  Each cluster is one read_memory call.

        # Cluster 1: 0xCC26..0xCC3F (26 bytes)
        #   menu_cursor(0xCC26), menu_max(0xCC28), joypad_sim(0xCC3F)
        _cc = await self._read_range(0xCC26, 0xCC3F - 0xCC26 + 1)
        menu_cursor  = _cc[mem.WRAM_CURRENT_MENU_ITEM - 0xCC26]
        menu_max     = _cc[mem.WRAM_MAX_MENU_ITEM - 0xCC26]
        joypad_sim   = _cc[mem.WRAM_SIM_JOYPAD_STATES_INDEX - 0xCC26]

        # Cluster 2: 0xCF4A..0xCF94 (75 bytes)
        #   letters_entered(0xCF4A), naming_screen(0xCF91), text_box_id(0xCF94)
        _cf = await self._read_range(0xCF4A, 0xCF94 - 0xCF4A + 1)
        letters_entered = _cf[mem.WRAM_NUM_LETTERS_ENTERED - 0xCF4A]
        naming_screen   = _cf[mem.WRAM_NAMING_SCREEN_TYPE - 0xCF4A]
        text_box_id     = _cf[mem.WRAM_TEXT_BOX_ID - 0xCF4A]

        # Cluster 3: 0xCFC3..0xCFC5 (3 bytes)
        #   font_loaded(0xCFC3), walk_counter(0xCFC4), tile_ahead(0xCFC5)
        _cfc = await self._read_range(0xCFC3, 3)
        font_loaded_byte = _cfc[0]
        font_loaded      = bool(font_loaded_byte & 0x01)
        walk_counter     = _cfc[1]
        tile_ahead       = _cfc[2]

        # Cluster 4: 0xD056 (1 byte) — isolated
        in_battle = await self._read_byte(mem.WRAM_IS_IN_BATTLE)

        # Cluster 5: 0xD119..0xD162 (74 bytes)
        #   ignore_input(0xD139), player_name(0xD157..0xD161), party_count(0xD162)
        _d1 = await self._read_range(0xD119, 0xD162 - 0xD119 + 1)
        ignore_input = _d1[mem.WRAM_IGNORE_INPUT_COUNTER - 0xD119]
        p_bytes      = _d1[mem.WRAM_PLAYER_NAME - 0xD119 : mem.WRAM_PLAYER_NAME - 0xD119 + 11]
        party_count  = _d1[mem.WRAM_PARTY_COUNT - 0xD119]

        # Cluster 6: 0xD346..0xD361 (28 bytes)
        #   money(0xD346,3), rival_name(0xD349,11), badges(0xD355),
        #   map_id(0xD35D), player_y(0xD360), player_x(0xD361)
        _d3 = await self._read_range(0xD346, 0xD361 - 0xD346 + 1)
        money    = self._decode_bcd(_d3[mem.WRAM_MONEY - 0xD346 : mem.WRAM_MONEY - 0xD346 + 3])
        r_bytes  = _d3[mem.WRAM_RIVAL_NAME - 0xD346 : mem.WRAM_RIVAL_NAME - 0xD346 + 11]
        badges   = _d3[mem.WRAM_BADGES - 0xD346]
        map_id   = _d3[mem.WRAM_CUR_MAP - 0xD346]
        player_y = _d3[mem.WRAM_Y_COORD - 0xD346]
        player_x = _d3[mem.WRAM_X_COORD - 0xD346]

        # Cluster 7: 0xD529 (1 byte) — isolated
        facing_raw = await self._read_byte(mem.WRAM_PLAYER_DIRECTION)

        # Cluster 8: 0xD72D..0xD731 (5 bytes)
        #   oak_speech(0xD72D), status_flags5(0xD72F),
        #   script_running(0xD730), status_flags6(0xD731)
        _d7 = await self._read_range(0xD72D, 0xD731 - 0xD72D + 1)
        oak_speech      = _d7[mem.WRAM_OAK_SPEECH_STATUS - 0xD72D]
        status_flags5   = _d7[mem.WRAM_STATUS_FLAGS5 - 0xD72D]
        joypad_disabled = bool(status_flags5 & 0x20)   # bit 5
        scripted_movement = bool(status_flags5 & 0x80)  # bit 7 BIT_SCRIPTED_MOVEMENT_STATE
        script_running  = _d7[mem.WRAM_SCRIPT_RUNNING - 0xD72D]
        status_flags6   = _d7[mem.WRAM_STATUS_FLAGS6 - 0xD72D]
        game_timer_counting = bool(status_flags6 & 0x01)

        # Remaining isolated reads
        pikachu     = await self._read_byte(mem.WRAM_PIKACHU_HAPPINESS)
        textbox_open = await self._read_byte(mem.WRAM_TEXTBOX_OPEN)

        # HRAM cluster: 0xFFB3..0xFFD5 (35 bytes)
        #   joy_pressed(0xFFB3), joy_held(0xFFB4), frame(0xFFD5)
        _hram = await self._read_range(0xFFB3, 0xFFD5 - 0xFFB3 + 1)
        joy_pressed = _hram[mem.HRAM_JOY_PRESSED - 0xFFB3]
        joy_held    = _hram[mem.HRAM_JOY_HELD - 0xFFB3]
        frame       = _hram[mem.HRAM_FRAME_COUNTER - 0xFFB3]

        # Decode player/rival names from batched bytes
        p_name = mem.decode_text(p_bytes, max_len=11)
        r_name = mem.decode_text(r_bytes, max_len=11)

        # Names are "set" when both start with valid uppercase letter tiles (A-Z)
        names_set = p_name != "NINTEN" and r_name != "SONY"

        # Get CPU PC for title screen detection
        regs = await self._call("get_registers", {})
        pc = 0
        if isinstance(regs, dict):
            # Registers come nested: {'16-bit': {'PC': ..., 'SP': ...}, '8-bit': {...}}
            regs_16 = regs.get("16-bit", regs)
            raw_pc = regs_16.get("PC", 0)
            # Value may be int or hex string like "0x0150"
            pc = int(raw_pc, 16) if isinstance(raw_pc, str) else int(raw_pc)

        # Read screen text for dialog/menu detection
        screen_text = await self._read_screen_text()

        # Read map info for navigation
        map_info = None
        if map_id != 0 or party_count > 0:  # Only read in actual gameplay
            map_info = await self._read_map_info()

        # Parse direction
        try:
            facing = Direction(facing_raw & 0x0C)
        except ValueError:
            facing = Direction.DOWN

        # Detect mode with all available signals
        mode = self._detect_mode(
            in_battle=in_battle,
            map_id=map_id,
            menu_cursor=menu_cursor,
            text_box_id=text_box_id,
            ignore_input=ignore_input,
            regs=regs,
            naming_screen=naming_screen,
            party_count=party_count,
            oak_speech=oak_speech,
            badges=badges,
            screen_text=screen_text,
            textbox_open=textbox_open,
            script_running=script_running,
            joypad_sim=joypad_sim,
            names_set=names_set,
            joypad_disabled=joypad_disabled,
            scripted_movement=scripted_movement,
            font_loaded=font_loaded,
        )

        # Read party Pokemon
        party = []
        count = min(party_count, 6)
        for i in range(count):
            mon = await self._read_pokemon(mem.PARTY_MON_ADDRESSES[i])
            party.append(mon)

        # Read game progress (only in actual gameplay, not title/intro)
        game_progress = ""
        event_flags = {}
        badge_names = self._read_badge_names(badges)
        if map_id > 0 or party_count > 0:
            game_progress = await self.read_game_progress()
            event_flags = await self.read_event_flags()

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
            badge_names=badge_names,
            money=money,
            game_progress=game_progress,
            event_flags=event_flags,
            menu_cursor=menu_cursor,
            menu_max=menu_max,
            text_active=(text_box_id != 0 or ignore_input > 0),
            pikachu_happiness=pikachu,
            screen_text=screen_text,
            map_info=map_info,
            naming_type=naming_screen,
            letters_entered=letters_entered,
            ignore_input=ignore_input,
            joypad_sim=joypad_sim,
            joypad_disabled=joypad_disabled,
            font_loaded=font_loaded,
            names_set=names_set,
            pc=pc,
            game_timer_counting=game_timer_counting,
            joypad_pressed=joy_pressed,
            joypad_held=joy_held,
        )
