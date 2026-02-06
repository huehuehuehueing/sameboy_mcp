"""Layer 4: Realtime ROM Analysis via MCP disassembly tools.

Uses the MCP server's disassemble_function/disassemble_rom tools during gameplay
to inspect game routines as they become relevant. Results are cached so each
routine is only disassembled once per session.

Key Pokemon Yellow (US) ROM landmarks discovered by direct ROM analysis:
- Type effectiveness table: bank 15, CPU $65FA (82 entries)
- Base stats table: bank 14, CPU $43DF (28 bytes per species, Pokedex order)
- Enemy AI / move selection: bank 15
- Battle damage stores: wDamage at $D0D6
"""

from typing import Any

from . import memory_map as mem


# ============================================================
# Known Pokemon Yellow (US) ROM Landmarks
# These are fixed addresses in the ROM, found by pattern scanning.
# CPU addresses assume the correct bank is mapped at $4000-$7FFF.
# ============================================================

ROM_LANDMARKS = {
    # Data tables
    "type_chart": {
        "rom_offset": 0x3E5FA,
        "bank": 15,
        "cpu_addr": 0x65FA,
        "description": "Type effectiveness table: 82 entries of (atk_type, def_type, multiplier). "
                       "Multipliers: 0x00=immune, 0x05=not_very_effective, 0x14=super_effective. "
                       "Ends with 0xFF sentinel at $66F0.",
        "size": 247,  # 82*3 + 1 sentinel
    },
    "base_stats": {
        "rom_offset": 0x383DF,
        "bank": 14,
        "cpu_addr": 0x43DF,
        "description": "Base stats table: 28 bytes per species in Pokedex order. "
                       "Format: HP, ATK, DEF, SPD, SPC, Type1, Type2, CatchRate, "
                       "ExpYield, FrontSpriteDims, FrontPtr, BackPtr, "
                       "Attacks(4), GrowthRate, TMflags(7), padding.",
        "entry_size": 28,
    },
    # Battle routines (CPU addresses when bank 15 is loaded)
    "type_effectiveness_routine": {
        "rom_offset": 0x3E517,
        "bank": 15,
        "cpu_addr": 0x6517,
        "description": "Routine that checks move type vs defender types and applies "
                       "effectiveness multiplier. Loads types from $D018/$D019 (player) "
                       "or $CFE9/$CFEA (enemy), references TypeEffectivenessTable at $65FA.",
    },
    "damage_store_routine": {
        "rom_offset": 0x3DB29,
        "bank": 15,
        "cpu_addr": 0x5B29,
        "description": "Area where damage result is stored to wDamage ($D0D6/$D0D7).",
    },
    # Enemy AI
    "enemy_move_selection": {
        "rom_offset": 0x3D76F,
        "bank": 15,
        "cpu_addr": 0x576F,
        "description": "Routine that stores enemy's selected move to wEnemySelectedMove ($CCDD). "
                       "The AI chooses from wEnemyMonMoves ($CFEC). Trainer AI modifiers "
                       "are applied based on wTrainerClass ($D030).",
    },
    "enemy_move_refs": {
        "rom_offset": 0x3D6F9,
        "bank": 15,
        "cpu_addr": 0x56F9,
        "description": "Region that loads and processes wEnemyMonMoves ($CFEC). "
                       "Part of the enemy turn logic.",
    },
    # Trainer AI in bank 14
    "trainer_ai_bank14": {
        "rom_offset": 0x396BB,
        "bank": 14,
        "cpu_addr": 0x56BB,
        "description": "Trainer AI reference - loads wTrainerClass ($D030) to determine "
                       "AI behavior. Different trainer classes use different AI strategies.",
    },
}

# Trainer class names (from pokeyellow disassembly)
TRAINER_CLASSES = {
    0x00: "Wild Pokemon",
    0x01: "Youngster", 0x02: "Bug Catcher", 0x03: "Lass",
    0x04: "Sailor", 0x05: "Jr. Trainer M", 0x06: "Jr. Trainer F",
    0x07: "Pokemaniac", 0x08: "Super Nerd", 0x09: "Hiker",
    0x0A: "Biker", 0x0B: "Burglar", 0x0C: "Engineer",
    0x0D: "Juggler", 0x0E: "Fisher", 0x0F: "Swimmer",
    0x10: "Cue Ball", 0x11: "Gambler", 0x12: "Beauty",
    0x13: "Psychic", 0x14: "Rocker", 0x15: "Juggler2",
    0x16: "Tamer", 0x17: "Bird Keeper", 0x18: "Blackbelt",
    0x19: "Rival1", 0x1A: "Prof. Oak", 0x1B: "Chief",
    0x1C: "Scientist", 0x1D: "Giovanni", 0x1E: "Rocket",
    0x1F: "Cool Trainer M", 0x20: "Cool Trainer F",
    0x21: "Bruno", 0x22: "Brock", 0x23: "Misty",
    0x24: "Lt. Surge", 0x25: "Erika", 0x26: "Koga",
    0x27: "Blaine", 0x28: "Sabrina", 0x29: "Gentleman",
    0x2A: "Rival2", 0x2B: "Rival3", 0x2C: "Lorelei",
    0x2D: "Channeler", 0x2E: "Agatha", 0x2F: "Lance",
}

# Gen 1 text character encoding (for reading text from RAM)
CHARMAP = {
    0x50: '\0',  # string terminator
    0x4F: '\n',  # newline
    0x51: '\n',  # paragraph
    0x55: '\n',  # cont/next
    0x7F: ' ',   # space
}
# A-Z: 0x80-0x99
for i in range(26):
    CHARMAP[0x80 + i] = chr(ord('A') + i)
# a-z: 0xA0-0xB9
for i in range(26):
    CHARMAP[0xA0 + i] = chr(ord('a') + i)
# 0-9: 0xF6-0xFF
for i in range(10):
    CHARMAP[0xF6 + i] = str(i)
# Common symbols
CHARMAP[0xE0] = "'"
CHARMAP[0xE1] = "PK"
CHARMAP[0xE2] = "MN"
CHARMAP[0xE3] = "-"
CHARMAP[0xE6] = "?"
CHARMAP[0xE7] = "!"
CHARMAP[0xE8] = "."
CHARMAP[0xEF] = "M"  # male
CHARMAP[0xF5] = "F"  # female


def decode_game_text(data: list[int] | bytes) -> str:
    """Decode Gen 1 encoded text bytes to string."""
    result = []
    for b in data:
        if b == 0x50:  # terminator
            break
        result.append(CHARMAP.get(b, f'[{b:02X}]'))
    return ''.join(result)


class GameAnalyzer:
    """Realtime ROM analysis using MCP disassembly tools.

    Disassembles game routines on-demand during gameplay and caches results.
    Provides the agent with understanding of game internals.
    """

    def __init__(self, call_tool, verbose: bool = False):
        """
        Args:
            call_tool: async callable(name, args) -> result for MCP tools
            verbose: print debug info
        """
        self._call = call_tool
        self._verbose = verbose
        self._cache: dict[str, Any] = {}  # routine_name -> analysis result
        self._rom_header: dict | None = None

    def _log(self, msg: str):
        if self._verbose:
            print(f"  [analysis] {msg}")

    # ============================================================
    # MCP tool wrappers
    # ============================================================

    async def disassemble_function(self, address: int, max_size: int = 256) -> dict:
        """Disassemble a function at CPU address via MCP."""
        result = await self._call("disassemble_function", {
            "address": address,
            "max_size": max_size,
        })
        return result if isinstance(result, dict) else {}

    async def disassemble_rom(self, start: int, end: int,
                               max_instructions: int = 200) -> dict:
        """Disassemble a ROM range via MCP."""
        result = await self._call("disassemble_rom", {
            "start": start,
            "end": end,
            "max_instructions": max_instructions,
        })
        return result if isinstance(result, dict) else {}

    async def read_memory(self, address: int, length: int) -> list[int]:
        """Read memory bytes."""
        result = await self._call("read_memory", {
            "address": address,
            "length": length,
        })
        if isinstance(result, dict) and "bytes" in result:
            return result["bytes"]
        return [0] * length

    # ============================================================
    # Startup analysis (run once at start)
    # ============================================================

    async def startup_analysis(self) -> dict:
        """Run quick startup analysis. Returns summary dict."""
        self._log("running startup ROM analysis...")

        # Get ROM header
        self._rom_header = await self._call("get_rom_header", {})
        if isinstance(self._rom_header, dict):
            self._log(f"ROM: {self._rom_header.get('title', '?')}")

        summary = {
            "rom_title": self._rom_header.get("title", "Unknown") if self._rom_header else "Unknown",
            "landmarks": list(ROM_LANDMARKS.keys()),
            "trainer_classes": len(TRAINER_CLASSES),
        }

        self._cache["startup"] = summary
        return summary

    # ============================================================
    # On-demand analysis routines
    # ============================================================

    async def analyze_type_chart(self) -> str:
        """Disassemble and explain the type effectiveness lookup routine."""
        if "type_chart" in self._cache:
            return self._cache["type_chart"]

        self._log("analyzing type effectiveness routine...")
        info = ROM_LANDMARKS["type_effectiveness_routine"]
        result = await self.disassemble_function(info["cpu_addr"], max_size=150)

        instructions = result.get("instructions", [])
        summary = (
            f"TypeEffectiveness routine at CPU ${info['cpu_addr']:04X} "
            f"(ROM ${info['rom_offset']:05X}, bank {info['bank']}):\n"
            f"  - Loads attacker types from $D018/$D019 or $CFE9/$CFEA\n"
            f"  - Checks hWhoseTurn ($FFF3) to determine attacker/defender\n"
            f"  - Walks the type chart at $65FA (82 entries)\n"
            f"  - Applies multiplier: 0x14=2x, 0x05=0.5x, 0x00=immune\n"
            f"  - Stores result in wDamageMultipliers ($D05A)\n"
            f"  Instructions: {len(instructions)}"
        )

        self._cache["type_chart"] = summary
        return summary

    async def analyze_enemy_ai(self) -> str:
        """Disassemble the enemy AI move selection routine."""
        if "enemy_ai" in self._cache:
            return self._cache["enemy_ai"]

        self._log("analyzing enemy AI routine...")
        info = ROM_LANDMARKS["enemy_move_refs"]
        result = await self.disassemble_function(info["cpu_addr"], max_size=300)

        instructions = result.get("instructions", [])

        # Also disassemble the selection store
        info2 = ROM_LANDMARKS["enemy_move_selection"]
        result2 = await self.disassemble_function(info2["cpu_addr"], max_size=200)
        instructions2 = result2.get("instructions", [])

        summary = (
            f"Enemy AI Move Selection:\n"
            f"  Move processing at CPU ${info['cpu_addr']:04X} ({len(instructions)} instructions)\n"
            f"  Move store at CPU ${info2['cpu_addr']:04X} ({len(instructions2)} instructions)\n"
            f"  - Reads available moves from wEnemyMonMoves ($CFEC)\n"
            f"  - Stores choice to wEnemySelectedMove ($CCDD)\n"
            f"  - AI is modified by wTrainerClass ($D030)\n"
            f"  - Wild Pokemon choose randomly from their moves\n"
            f"  - Trainers have class-specific AI layers that modify probabilities"
        )

        self._cache["enemy_ai"] = summary
        return summary

    async def analyze_damage_calc(self) -> str:
        """Analyze the damage calculation routine."""
        if "damage_calc" in self._cache:
            return self._cache["damage_calc"]

        self._log("analyzing damage calculation...")
        info = ROM_LANDMARKS["damage_store_routine"]
        result = await self.disassemble_function(info["cpu_addr"], max_size=200)
        instructions = result.get("instructions", [])

        # Gen 1 damage formula (documented from disassembly):
        summary = (
            f"Damage Calculation (Gen 1 formula):\n"
            f"  damage = ((2*Level/5 + 2) * Power * Attack / Defense) / 50 + 2\n"
            f"  Then modified by:\n"
            f"    - STAB: 1.5x if move type matches attacker type\n"
            f"    - Type effectiveness: 0x/0.5x/1x/2x/4x from type chart\n"
            f"    - Critical hit: 2x (ignores stat mods, uses base stats)\n"
            f"    - Random: multiply by [217-255]/255\n"
            f"  Key addresses:\n"
            f"    - wDamage: $D0D6 (2 bytes, result)\n"
            f"    - wCriticalHit: $D05D\n"
            f"    - wMoveMissed: $D05E\n"
            f"    - wDamageMultipliers: $D05A (STAB + type)\n"
            f"    - hWhoseTurn: $FFF3 (0=player, 1=enemy)\n"
            f"  Gen 1 bugs:\n"
            f"    - Focus Energy DIVIDES crit rate by 4 (bug, not multiplies)\n"
            f"    - 1/256 miss chance on 100% accuracy moves\n"
            f"    - Stat mods ignored during critical hits\n"
            f"  Routine at CPU ${info['cpu_addr']:04X}, {len(instructions)} instructions"
        )

        self._cache["damage_calc"] = summary
        return summary

    async def analyze_current_battle_routine(self) -> str:
        """Disassemble whatever routine the CPU is currently executing.
        Useful during battle to see what the game is doing right now."""
        regs = await self._call("get_registers", {})
        if not isinstance(regs, dict):
            return "(could not read registers)"

        pc = regs.get("PC", 0)
        bank = regs.get("ROM_BANK", 0)
        self._log(f"current PC=${pc:04X} bank={bank}")

        result = await self.disassemble_function(pc, max_size=100)
        instructions = result.get("instructions", [])

        lines = [f"Current routine at PC=${pc:04X} (bank {bank}):"]
        for inst in instructions[:20]:
            addr = inst.get("address", 0)
            mnem = inst.get("mnemonic", "???")
            ops = inst.get("operands", "")
            line = f"  ${addr:04X}: {mnem} {ops}"
            # Annotate known addresses
            if "$D0D6" in ops: line += "  ; wDamage"
            if "$CFEC" in ops: line += "  ; wEnemyMonMoves"
            if "$CCDD" in ops: line += "  ; wEnemySelectedMove"
            if "$D030" in ops: line += "  ; wTrainerClass"
            if "$FFF3" in ops: line += "  ; hWhoseTurn"
            if "$D056" in ops: line += "  ; wIsInBattle"
            lines.append(line)

        return "\n".join(lines)

    # ============================================================
    # Text reading from RAM
    # ============================================================

    async def read_text_at(self, address: int, max_length: int = 50) -> str:
        """Read and decode game text from a RAM address."""
        data = await self.read_memory(address, max_length)
        return decode_game_text(data)

    async def read_enemy_nickname(self) -> str:
        """Read the enemy Pokemon's nickname from RAM."""
        return await self.read_text_at(mem.WRAM_ENEMY_MON_NICK, 11)

    async def read_player_name(self) -> str:
        """Read the player's name from RAM."""
        return await self.read_text_at(mem.WRAM_PLAYER_NAME, 11)

    async def read_rival_name(self) -> str:
        """Read the rival's name from RAM."""
        return await self.read_text_at(mem.WRAM_RIVAL_NAME, 11)

    # ============================================================
    # Battle context for LLM
    # ============================================================

    async def get_battle_analysis_context(self, trainer_class: int) -> str:
        """Get analysis context relevant to the current battle.
        Called once per battle, cached."""

        cache_key = f"battle_ctx_{trainer_class}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        parts = []

        # Trainer info
        trainer_name = TRAINER_CLASSES.get(trainer_class, f"Unknown({trainer_class})")
        if trainer_class == 0:
            parts.append(f"Wild battle. Wild Pokemon choose moves randomly.")
        else:
            parts.append(f"Trainer: {trainer_name} (class ${trainer_class:02X}).")
            parts.append("Trainers use class-specific AI to select moves.")

        # Damage formula reminder
        parts.append(
            "Damage formula: ((2*Level/5+2)*Power*Atk/Def)/50+2, "
            "then STAB(1.5x), type(0-4x), crit(2x), random(0.85-1.0)."
        )

        # Gen 1 specific notes
        parts.append(
            "Gen 1 quirks: Focus Energy is bugged (reduces crit rate). "
            "1/256 miss chance even at 100% accuracy. "
            "Special stat handles both SpAtk and SpDef. "
            "Critical hits ignore all stat modifications."
        )

        # Memory layout reminder
        parts.append(
            "Enemy data in RAM: species=$CFE4, HP=$CFE5, moves=$CFEC, "
            "stats=$CFF5-$CFFB, PP=$CFFD, catch_rate=$D006. "
            "Stat mods at $CD2E-$CD31 (7=neutral, range 1-13). "
            "Battle status at $D066-$D068."
        )

        result = "\n".join(parts)
        self._cache[cache_key] = result
        return result

    def get_trainer_name(self, trainer_class: int) -> str:
        """Look up trainer class name."""
        return TRAINER_CLASSES.get(trainer_class, f"Trainer_{trainer_class}")

    # ============================================================
    # Cache management
    # ============================================================

    def clear_cache(self):
        """Clear analysis cache (e.g., on ROM change)."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)
