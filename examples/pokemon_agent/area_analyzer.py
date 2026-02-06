"""Area Analyzer - MCP-driven visual + memory analysis for map areas.

Triggered during map changes/warps to detect and catalog:
- NPCs with positions and types
- Items on the ground
- Interactive objects (signs, PCs, etc.)
- Warps/exits
- Terrain features

Uses LLM function calling to invoke MCP tools directly.
"""

from dataclasses import dataclass, field
from typing import Any
import json

from .config import AgentConfig
from .game_state import GameState, SpriteInfo, WarpPoint
from . import memory_map as mem


# ============================================================
# Pokemon Yellow Sprite Picture IDs
# From pret/pokeyellow disassembly
# ============================================================

# Trainer sprite picture IDs (these NPCs can battle)
TRAINER_SPRITE_IDS = {
    0x02,  # Blue (rival)
    0x03,  # Bug Catcher
    0x04,  # Lass
    0x05,  # Black Belt
    0x06,  # Jr Trainer M
    0x07,  # Jr Trainer F
    0x08,  # Youngster
    0x09,  # Super Nerd
    0x0A,  # Rocker
    0x0B,  # Biker
    0x0C,  # Burglar
    0x0D,  # Engineer
    0x0E,  # Juggler
    0x0F,  # Fisher
    0x10,  # Swimmer
    0x11,  # Cue Ball
    0x12,  # Gambler
    0x13,  # Beauty
    0x14,  # Psychic
    0x15,  # Gentleman
    0x16,  # Sailor
    0x17,  # Hiker
    0x18,  # Scientist
    0x19,  # Rocket
    0x1A,  # Cool Trainer M
    0x1B,  # Cool Trainer F
    0x1C,  # Bird Keeper
    0x1D,  # Channeler
    0x1E,  # Tamer
    0x1F,  # Chief
    0x20,  # Lorelei / Agatha / Bruno / Lance
    0x21,  # Giovanni
}

# NPC sprite IDs that give items or are important
ITEM_GIVER_SPRITE_IDS = {
    0x22,  # Prof Oak
    0x23,  # Old Man
    0x24,  # Nurse
    0x25,  # Officer Jenny
    0x26,  # Mart Clerk
}

# Item ball sprite ID
ITEM_BALL_SPRITE_ID = 0x29  # Pokeball item on ground


# ============================================================
# Data structures for detected entities
# ============================================================

@dataclass
class DetectedNPC:
    """An NPC detected in the area."""
    x: int
    y: int
    sprite_id: int
    picture_id: int
    facing: int
    npc_type: str = ""  # "trainer", "npc", "item_giver", etc.
    description: str = ""
    can_battle: bool = False

    def __hash__(self):
        return hash((self.x, self.y, self.sprite_id))


@dataclass
class DetectedItem:
    """An item detected on the ground or in a ball."""
    x: int
    y: int
    item_id: int = 0
    item_name: str = ""
    is_hidden: bool = False
    collected: bool = False

    def __hash__(self):
        return hash((self.x, self.y))


@dataclass
class DetectedObject:
    """An interactive object in the area."""
    x: int
    y: int
    object_type: str  # "sign", "pc", "healing_machine", "item_ball", etc.
    description: str = ""

    def __hash__(self):
        return hash((self.x, self.y, self.object_type))


@dataclass
class AreaData:
    """Complete data about an area/map."""
    map_id: int
    map_name: str
    width: int
    height: int
    npcs: list[DetectedNPC] = field(default_factory=list)
    items: list[DetectedItem] = field(default_factory=list)
    objects: list[DetectedObject] = field(default_factory=list)
    warps: list[WarpPoint] = field(default_factory=list)

    # Analysis metadata
    analyzed_at_frame: int = 0
    vision_analysis: str = ""
    disasm_context: str = ""

    def summary(self) -> str:
        lines = [
            f"=== Area: {self.map_name} (ID: {self.map_id}) ===",
            f"Size: {self.width}x{self.height}",
        ]
        if self.npcs:
            lines.append(f"NPCs ({len(self.npcs)}):")
            for npc in self.npcs:
                desc = f"  ({npc.x},{npc.y}) {npc.npc_type or 'sprite'}"
                if npc.description:
                    desc += f" - {npc.description}"
                lines.append(desc)
        if self.items:
            lines.append(f"Items ({len(self.items)}):")
            for item in self.items:
                status = " [collected]" if item.collected else ""
                hidden = " (hidden)" if item.is_hidden else ""
                lines.append(f"  ({item.x},{item.y}) {item.item_name or 'unknown'}{hidden}{status}")
        if self.objects:
            lines.append(f"Objects ({len(self.objects)}):")
            for obj in self.objects:
                lines.append(f"  ({obj.x},{obj.y}) {obj.object_type}")
        if self.warps:
            lines.append(f"Warps ({len(self.warps)}):")
            for warp in self.warps:
                lines.append(f"  ({warp.x},{warp.y}) -> map {warp.dest_map}")
        return "\n".join(lines)


# ============================================================
# MCP Tool definitions for area analysis
# ============================================================

AREA_ANALYSIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read bytes from Game Boy memory. Use for sprite data, item data, map info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "integer", "description": "Memory address (0x0000-0xFFFF)"},
                    "length": {"type": "integer", "description": "Number of bytes to read", "default": 1},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Capture the current Game Boy screen as a PNG image for visual analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["png"], "default": "png"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_registers",
            "description": "Get CPU register values (AF, BC, DE, HL, SP, PC).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sprites",
            "description": "Get OAM/sprite information for all visible sprites on screen.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disassemble_function",
            "description": "Disassemble code at an address to understand game logic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "integer", "description": "Address to disassemble from"},
                    "max_size": {"type": "integer", "description": "Max bytes to disassemble", "default": 64},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_analysis",
            "description": "Report the final area analysis results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "npcs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "npc_type": {"type": "string"},
                                "description": {"type": "string"},
                                "can_battle": {"type": "boolean"},
                            },
                        },
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "item_name": {"type": "string"},
                                "is_hidden": {"type": "boolean"},
                            },
                        },
                    },
                    "objects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "object_type": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                    },
                    "observations": {"type": "string", "description": "General observations about the area"},
                },
                "required": ["npcs", "items", "objects"],
            },
        },
    },
]


AREA_ANALYSIS_SYSTEM_PROMPT = """You are an area analyzer for Pokemon Yellow. When entering a new map/area, you analyze the environment using MCP tools to detect NPCs, items, and interactive objects.

Your task:
1. Use get_sprites to see all sprites on the map
2. Use read_memory to read sprite data from WRAM for position info:
   - Sprite data starts at 0xC100 (16 bytes per sprite)
   - Sprite 0 is the player
   - Key offsets: +0x0C = map Y, +0x0D = map X, +0x00 = picture ID
3. Use capture_screen to visually analyze the area
4. Optionally use disassemble_function if you need to understand map scripts

Analyze what you see:
- NPCs: trainers have distinct sprites, regular NPCs may give items or info
- Items: Pokeballs on ground contain items, some items are hidden
- Objects: Signs, PCs, healing machines, ledges, etc.

After gathering data, call report_analysis with your findings.

Memory addresses for Pokemon Yellow:
- Sprite data: 0xC100 (16 bytes each, up to 16 sprites)
- Number of sprites: 0xD4E0
- Map width: 0xD368, Map height: 0xD367
- Player X: 0xD361, Player Y: 0xD360

Common sprite picture IDs:
- 0x01: Player (walking)
- 0x02-0x10: Various NPC types
- Trainers often have distinctive sprites"""


# ============================================================
# Area Analyzer class
# ============================================================

class AreaAnalyzer:
    """Analyzes areas using MCP tools and optional LLM vision."""

    def __init__(self, config: AgentConfig, call_tool):
        """
        Args:
            config: Agent configuration
            call_tool: async callable(name, args) -> result for MCP tools
        """
        self.config = config
        self._call = call_tool
        self._verbose = config.verbose

        # Cached area data by map_id
        self._area_cache: dict[int, AreaData] = {}

        # OpenAI client for vision analysis
        self._client = None
        self._model = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM client for vision analysis."""
        try:
            from openai import OpenAI
            import httpx
            vis_cfg = self.config.get_vision_config()
            if vis_cfg.get("base_url") and vis_cfg.get("supports_vision"):
                base_url = vis_cfg["base_url"]
                self._client = OpenAI(
                    base_url=base_url,
                    api_key=vis_cfg.get("api_key") or "not-needed",
                )

                # Query actual model name from server (vLLM uses "default" as placeholder)
                model_name = vis_cfg.get("model", "default")
                if model_name == "default":
                    try:
                        # Query /v1/models to get actual model name
                        models_url = base_url.rstrip("/") + "/models"
                        resp = httpx.get(models_url, timeout=5.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("data") and len(data["data"]) > 0:
                                model_name = data["data"][0].get("id", "default")
                                if self._verbose:
                                    print(f"  [area-analyzer] discovered model: {model_name}")
                    except Exception as e:
                        if self._verbose:
                            print(f"  [area-analyzer] model discovery failed: {e}")

                self._model = model_name
        except ImportError:
            pass

    def _log(self, msg: str):
        if self._verbose:
            print(f"  [area-analyzer] {msg}")

    async def _read_memory(self, address: int, length: int = 1) -> list[int]:
        """Read memory bytes."""
        result = await self._call("read_memory", {"address": address, "length": length})
        if isinstance(result, dict) and "bytes" in result:
            return result["bytes"]
        return [0] * length

    async def _read_sprite_data(self) -> list[SpriteInfo]:
        """Read all sprite data from memory."""
        sprites = []
        num_sprites = (await self._read_memory(mem.WRAM_NUM_SPRITES_ACTUAL, 1))[0]

        # Read each sprite (16 bytes each, starting at 0xC100)
        for i in range(min(num_sprites + 1, 16)):
            base = mem.WRAM_SPRITE_DATA + (i * 16)
            data = await self._read_memory(base, 16)

            if len(data) >= 14:
                picture_id = data[mem.SPRITE_PICTURE_ID]
                # Skip empty sprites (except player at index 0)
                if picture_id == 0 and i > 0:
                    continue

                sprites.append(SpriteInfo(
                    index=i,
                    x=data[mem.SPRITE_MAP_X],
                    y=data[mem.SPRITE_MAP_Y],
                    picture_id=picture_id,
                    facing=data[mem.SPRITE_FACING],
                    is_player=(i == 0),
                ))

        return sprites

    async def _get_cpu_context(self) -> dict:
        """Get CPU registers and PC disassembly for context."""
        regs = await self._call("get_registers", {})
        if not isinstance(regs, dict):
            return {"registers": {}, "disasm": ""}

        pc = regs.get("PC", 0)

        # Get a small disassembly around PC for context
        disasm_result = await self._call("disassemble_function", {
            "address": pc,
            "max_size": 32,
        })

        disasm_text = ""
        if isinstance(disasm_result, dict) and "instructions" in disasm_result:
            lines = []
            for instr in disasm_result["instructions"][:5]:
                addr = instr.get("address", 0)
                text = instr.get("text", "???")
                lines.append(f"  ${addr:04X}: {text}")
            disasm_text = "\n".join(lines)

        return {
            "registers": regs,
            "disasm": disasm_text,
        }

    async def analyze_area(self, state: GameState, force: bool = False) -> AreaData:
        """
        Perform comprehensive area analysis.

        Args:
            state: Current game state
            force: Force re-analysis even if cached

        Returns:
            AreaData with detected entities
        """
        map_id = state.map_id

        # Check cache
        if not force and map_id in self._area_cache:
            cached = self._area_cache[map_id]
            self._log(f"using cached area data for map {map_id}")
            return cached

        self._log(f"analyzing area: {state.map_name} (map {map_id})")

        # Gather base data from memory
        sprites = await self._read_sprite_data()
        cpu_ctx = await self._get_cpu_context()

        # Get map dimensions
        width = state.map_info.width * 2 if state.map_info else 10
        height = state.map_info.height * 2 if state.map_info else 10

        # Create base area data
        area = AreaData(
            map_id=map_id,
            map_name=state.map_name,
            width=width,
            height=height,
            warps=list(state.map_info.warps) if state.map_info else [],
            analyzed_at_frame=state.frame,
            disasm_context=cpu_ctx.get("disasm", ""),
        )

        # Convert sprites to NPCs (skip player sprite at index 0)
        for sprite in sprites:
            if sprite.is_player:
                continue

            # Classify the sprite based on picture ID
            pic_id = sprite.picture_id
            npc_type = ""
            can_battle = False
            description = ""

            if pic_id in TRAINER_SPRITE_IDS:
                npc_type = "trainer"
                can_battle = True
                description = "Battle-ready trainer"
            elif pic_id in ITEM_GIVER_SPRITE_IDS:
                npc_type = "item_giver"
                description = "May give item or important info"
            elif pic_id == ITEM_BALL_SPRITE_ID:
                # This is an item ball, not an NPC
                area.items.append(DetectedItem(
                    x=sprite.x,
                    y=sprite.y,
                    item_name="unknown (item ball)",
                ))
                continue
            else:
                npc_type = "npc"
                description = f"sprite_{pic_id:#04x}"

            npc = DetectedNPC(
                x=sprite.x,
                y=sprite.y,
                sprite_id=sprite.index,
                picture_id=sprite.picture_id,
                facing=sprite.facing,
                npc_type=npc_type,
                can_battle=can_battle,
                description=description,
            )
            area.npcs.append(npc)

        self._log(f"found {len(area.npcs)} NPCs from memory")

        # If vision is available, do visual analysis
        if self._client and self.config.has_vision:
            await self._do_vision_analysis(area, state)

        # Cache the result
        self._area_cache[map_id] = area

        return area

    async def _do_vision_analysis(self, area: AreaData, state: GameState):
        """Use vision model to analyze the screen and enhance detections."""
        self._log("performing vision analysis")

        # Capture screen
        screen_result = await self._call("capture_screen", {"format": "png"})
        if not isinstance(screen_result, dict) or "data_base64" not in screen_result:
            self._log("failed to capture screen")
            return

        image_b64 = screen_result["data_base64"]

        # Build context about what we already know
        known_info = []
        if area.npcs:
            npc_list = ", ".join(f"({n.x},{n.y})" for n in area.npcs)
            known_info.append(f"NPCs at: {npc_list}")
        if area.warps:
            warp_list = ", ".join(f"({w.x},{w.y})->map{w.dest_map}" for w in area.warps)
            known_info.append(f"Warps at: {warp_list}")

        known_context = "\n".join(known_info) if known_info else "No entities detected from memory yet."

        # Ask vision model to analyze the screen
        prompt = f"""Analyze this Pokemon Yellow screenshot. The player is at ({state.player_x}, {state.player_y}) on {state.map_name}.

Known from memory:
{known_context}

Describe what you see:
1. Any NPCs visible (trainers, regular NPCs)
2. Any item balls on the ground
3. Any interactive objects (signs, PCs, desks)
4. Any notable terrain features

Be specific about positions relative to the player if possible."""

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=500,
                temperature=0.3,
            )

            if response.choices:
                analysis = response.choices[0].message.content
                area.vision_analysis = analysis
                self._log(f"vision analysis: {analysis[:100]}...")

                # Parse vision analysis for additional objects
                self._parse_vision_results(area, analysis, state)

        except Exception as e:
            self._log(f"vision analysis error: {e}")

    def _parse_vision_results(self, area: AreaData, analysis: str, state: GameState):
        """Parse vision analysis text to extract detected objects."""
        analysis_lower = analysis.lower()

        # Detect common objects from description
        if "pokeball" in analysis_lower or "item ball" in analysis_lower:
            # Try to find position hints
            if "near" in analysis_lower or "beside" in analysis_lower:
                # Approximate position near player
                area.items.append(DetectedItem(
                    x=state.player_x + 1,
                    y=state.player_y,
                    item_name="unknown (seen visually)",
                ))

        if "sign" in analysis_lower:
            area.objects.append(DetectedObject(
                x=state.player_x,
                y=state.player_y - 1,  # Signs usually in front
                object_type="sign",
                description="Sign (seen visually)",
            ))

        if "pc" in analysis_lower or "computer" in analysis_lower:
            area.objects.append(DetectedObject(
                x=state.player_x,
                y=state.player_y,
                object_type="pc",
                description="PC (seen visually)",
            ))

        if "trainer" in analysis_lower:
            # Mark existing NPCs as potential trainers
            for npc in area.npcs:
                if not npc.npc_type:
                    npc.npc_type = "potential_trainer"
                    npc.can_battle = True

    async def run_llm_analysis(self, state: GameState) -> AreaData:
        """
        Run full LLM-driven area analysis using MCP tool calling.

        The LLM can call MCP tools directly to gather information.
        """
        if not self._client:
            self._log("no LLM client, using memory-only analysis")
            return await self.analyze_area(state)

        self._log("running LLM-driven area analysis")

        # Build initial context
        context = f"""You are entering a new area in Pokemon Yellow.
Map: {state.map_name} (ID: {state.map_id})
Player position: ({state.player_x}, {state.player_y})
Map dimensions: {state.map_info.width * 2}x{state.map_info.height * 2} tiles

Use the available tools to analyze this area:
1. First capture_screen to see the visual layout
2. Read sprite data from memory (0xC100, 16 bytes per sprite)
3. Check the number of sprites at 0xD4E0

Then call report_analysis with all detected NPCs, items, and objects."""

        messages = [
            {"role": "system", "content": AREA_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        # Run tool-calling loop
        max_turns = 5
        result_data = None

        for turn in range(max_turns):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=AREA_ANALYSIS_TOOLS,
                    tool_choice="auto",
                    max_tokens=1024,
                    temperature=0.3,
                )
            except Exception as e:
                self._log(f"LLM error: {e}")
                break

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                messages.append(message)

                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    self._log(f"LLM calling: {func_name}({func_args})")

                    if func_name == "report_analysis":
                        result_data = func_args
                        break

                    # Execute the MCP tool
                    result = await self._call(func_name, func_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    })

                if result_data:
                    break
            else:
                break

        # Build AreaData from LLM results
        area = AreaData(
            map_id=state.map_id,
            map_name=state.map_name,
            width=state.map_info.width * 2 if state.map_info else 10,
            height=state.map_info.height * 2 if state.map_info else 10,
            warps=list(state.map_info.warps) if state.map_info else [],
            analyzed_at_frame=state.frame,
        )

        if result_data:
            # Parse LLM results
            for npc_data in result_data.get("npcs", []):
                area.npcs.append(DetectedNPC(
                    x=npc_data.get("x", 0),
                    y=npc_data.get("y", 0),
                    sprite_id=0,
                    picture_id=0,
                    facing=0,
                    npc_type=npc_data.get("npc_type", ""),
                    description=npc_data.get("description", ""),
                    can_battle=npc_data.get("can_battle", False),
                ))

            for item_data in result_data.get("items", []):
                area.items.append(DetectedItem(
                    x=item_data.get("x", 0),
                    y=item_data.get("y", 0),
                    item_name=item_data.get("item_name", ""),
                    is_hidden=item_data.get("is_hidden", False),
                ))

            for obj_data in result_data.get("objects", []):
                area.objects.append(DetectedObject(
                    x=obj_data.get("x", 0),
                    y=obj_data.get("y", 0),
                    object_type=obj_data.get("object_type", ""),
                    description=obj_data.get("description", ""),
                ))

            area.vision_analysis = result_data.get("observations", "")

        # Cache and return
        self._area_cache[state.map_id] = area
        return area

    def get_cached_area(self, map_id: int) -> AreaData | None:
        """Get cached area data if available."""
        return self._area_cache.get(map_id)

    def get_npcs_at(self, map_id: int, x: int, y: int) -> list[DetectedNPC]:
        """Get NPCs at a specific position."""
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [npc for npc in area.npcs if npc.x == x and npc.y == y]

    def get_items_at(self, map_id: int, x: int, y: int) -> list[DetectedItem]:
        """Get items at a specific position."""
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [item for item in area.items if item.x == x and item.y == y]

    def mark_item_collected(self, map_id: int, x: int, y: int):
        """Mark an item as collected."""
        items = self.get_items_at(map_id, x, y)
        for item in items:
            item.collected = True

    def get_all_areas(self) -> dict[int, AreaData]:
        """Get all cached area data."""
        return dict(self._area_cache)

    def clear_cache(self, map_id: int | None = None):
        """Clear area cache."""
        if map_id is not None:
            self._area_cache.pop(map_id, None)
        else:
            self._area_cache.clear()

    def get_nearby_npcs(self, map_id: int, x: int, y: int, radius: int = 5) -> list[DetectedNPC]:
        """Get NPCs within radius of a position."""
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [
            npc for npc in area.npcs
            if abs(npc.x - x) <= radius and abs(npc.y - y) <= radius
        ]

    def get_nearby_items(self, map_id: int, x: int, y: int, radius: int = 5) -> list[DetectedItem]:
        """Get uncollected items within radius of a position."""
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [
            item for item in area.items
            if not item.collected and abs(item.x - x) <= radius and abs(item.y - y) <= radius
        ]

    def get_nearest_item(self, map_id: int, x: int, y: int) -> tuple[DetectedItem, int] | None:
        """Get the nearest uncollected item and its Manhattan distance."""
        area = self._area_cache.get(map_id)
        if not area:
            return None

        nearest = None
        nearest_dist = float('inf')

        for item in area.items:
            if item.collected:
                continue
            dist = abs(item.x - x) + abs(item.y - y)
            if dist < nearest_dist:
                nearest = item
                nearest_dist = dist

        return (nearest, int(nearest_dist)) if nearest else None

    def get_trainers_in_path(self, map_id: int, start_x: int, start_y: int, direction: str) -> list[DetectedNPC]:
        """Get trainers that might see the player when walking in a direction."""
        area = self._area_cache.get(map_id)
        if not area:
            return []

        # Trainers have line-of-sight range (typically 4-5 tiles)
        trainer_range = 5
        trainers = []

        for npc in area.npcs:
            if not npc.can_battle:
                continue

            # Check if trainer is in the path
            dx = npc.x - start_x
            dy = npc.y - start_y

            if direction == "up" and dx == 0 and dy < 0 and abs(dy) <= trainer_range:
                trainers.append(npc)
            elif direction == "down" and dx == 0 and dy > 0 and abs(dy) <= trainer_range:
                trainers.append(npc)
            elif direction == "left" and dy == 0 and dx < 0 and abs(dx) <= trainer_range:
                trainers.append(npc)
            elif direction == "right" and dy == 0 and dx > 0 and abs(dx) <= trainer_range:
                trainers.append(npc)

        return trainers

    def get_area_context_for_llm(self, map_id: int, player_x: int, player_y: int) -> str:
        """Get a text description of the area for LLM context."""
        area = self._area_cache.get(map_id)
        if not area:
            return "No area data available."

        lines = [f"Current area: {area.map_name}"]

        # Nearby NPCs
        nearby_npcs = self.get_nearby_npcs(map_id, player_x, player_y, radius=6)
        if nearby_npcs:
            npc_desc = []
            for npc in nearby_npcs:
                dx, dy = npc.x - player_x, npc.y - player_y
                dir_str = self._relative_direction(dx, dy)
                desc = f"{npc.npc_type or 'NPC'} {dir_str}"
                if npc.can_battle:
                    desc += " (TRAINER)"
                npc_desc.append(desc)
            lines.append(f"Nearby NPCs: {', '.join(npc_desc)}")

        # Nearby items
        nearby_items = self.get_nearby_items(map_id, player_x, player_y, radius=6)
        if nearby_items:
            item_desc = []
            for item in nearby_items:
                dx, dy = item.x - player_x, item.y - player_y
                dir_str = self._relative_direction(dx, dy)
                desc = f"{item.item_name or 'item'} {dir_str}"
                item_desc.append(desc)
            lines.append(f"Nearby items: {', '.join(item_desc)}")

        # Warps
        if area.warps:
            warp_desc = []
            for warp in area.warps:
                dx, dy = warp.x - player_x, warp.y - player_y
                dist = abs(dx) + abs(dy)
                dir_str = self._relative_direction(dx, dy)
                warp_desc.append(f"exit {dir_str} (dist {dist})")
            lines.append(f"Exits: {', '.join(warp_desc[:3])}")  # Limit to 3

        return "\n".join(lines)

    def _relative_direction(self, dx: int, dy: int) -> str:
        """Convert delta to relative direction string."""
        if dx == 0 and dy == 0:
            return "here"

        parts = []
        if dy < 0:
            parts.append(f"{abs(dy)} north")
        elif dy > 0:
            parts.append(f"{dy} south")
        if dx < 0:
            parts.append(f"{abs(dx)} west")
        elif dx > 0:
            parts.append(f"{dx} east")

        return ", ".join(parts) if parts else "nearby"
