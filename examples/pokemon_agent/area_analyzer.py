"""Area Analyzer - uses render_ascii_map MCP tool to catalog map entities.

Triggered during map changes/warps to detect and catalog:
- NPCs with positions and types (trainers, regular NPCs)
- Items on the ground
- Interactive objects (signs, PCs, etc.)
- Warps/exits
"""

from dataclasses import dataclass, field

from .game_state import GameState, WarpPoint


# ============================================================
# Data structures for detected entities
# ============================================================

@dataclass
class DetectedNPC:
    """An NPC detected in the area."""
    x: int
    y: int
    sprite_id: int = 0
    picture_id: int = 0
    facing: int = 0
    npc_type: str = ""  # "trainer", "npc", etc.
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
    object_type: str  # "sign", "pc", "bookshelf", etc.
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
    ascii_map: str = ""

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
# Area Analyzer class
# ============================================================

class AreaAnalyzer:
    """Analyzes areas by calling the render_ascii_map MCP tool."""

    def __init__(self, call_tool):
        """
        Args:
            call_tool: async callable(name, args) -> result for MCP tools
        """
        self._call = call_tool
        self._area_cache: dict[int, AreaData] = {}

    async def analyze_area(self, state: GameState, force: bool = False) -> AreaData:
        """Analyze current area using render_ascii_map.

        Args:
            state: Current game state
            force: Force re-analysis even if cached

        Returns:
            AreaData with detected entities
        """
        map_id = state.map_id

        if not force and map_id in self._area_cache:
            return self._area_cache[map_id]

        # Call the render_ascii_map MCP tool
        result = await self._call("render_ascii_map", {})
        if not isinstance(result, dict) or result.get("error"):
            # Return minimal area data on error
            area = AreaData(
                map_id=map_id,
                map_name=state.map_name,
                width=0,
                height=0,
                analyzed_at_frame=state.frame,
            )
            self._area_cache[map_id] = area
            return area

        dims = result.get("dimensions", {})
        area = AreaData(
            map_id=result.get("map_id", map_id),
            map_name=result.get("map_name", state.map_name),
            width=dims.get("width_steps", 0),
            height=dims.get("height_steps", 0),
            analyzed_at_frame=state.frame,
            ascii_map=result.get("ascii", ""),
        )

        # Parse sprites
        for sprite in result.get("sprites", []):
            stype = sprite.get("type", "npc")
            sx = sprite.get("x", 0)
            sy = sprite.get("y", 0)
            pic_id = sprite.get("picture_id", 0)

            if stype == "item":
                area.items.append(DetectedItem(
                    x=sx, y=sy,
                    item_name="unknown (item ball)",
                ))
            elif stype == "trainer":
                area.npcs.append(DetectedNPC(
                    x=sx, y=sy,
                    picture_id=pic_id,
                    npc_type="trainer",
                    can_battle=True,
                    description="Battle-ready trainer",
                ))
            else:
                area.npcs.append(DetectedNPC(
                    x=sx, y=sy,
                    picture_id=pic_id,
                    npc_type="npc",
                    description=f"sprite_{pic_id:#04x}",
                ))

        # Parse bg_events (signs)
        for ev in result.get("bg_events", []):
            area.objects.append(DetectedObject(
                x=ev.get("x", 0),
                y=ev.get("y", 0),
                object_type="sign",
                description=f"text_id={ev.get('text_id', 0)}",
            ))

        # Parse warps
        for warp in result.get("warps", []):
            area.warps.append(WarpPoint(
                x=warp.get("x", 0),
                y=warp.get("y", 0),
                dest_map=warp.get("dest_map", 0),
                warp_id=warp.get("warp_id", 0),
            ))

        self._area_cache[map_id] = area
        return area

    # ----------------------------------------------------------
    # Lookup helpers (same public API as before)
    # ----------------------------------------------------------

    def get_cached_area(self, map_id: int) -> AreaData | None:
        return self._area_cache.get(map_id)

    def get_npcs_at(self, map_id: int, x: int, y: int) -> list[DetectedNPC]:
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [npc for npc in area.npcs if npc.x == x and npc.y == y]

    def get_items_at(self, map_id: int, x: int, y: int) -> list[DetectedItem]:
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [item for item in area.items if item.x == x and item.y == y]

    def mark_item_collected(self, map_id: int, x: int, y: int):
        for item in self.get_items_at(map_id, x, y):
            item.collected = True

    def get_all_areas(self) -> dict[int, AreaData]:
        return dict(self._area_cache)

    def clear_cache(self, map_id: int | None = None):
        if map_id is not None:
            self._area_cache.pop(map_id, None)
        else:
            self._area_cache.clear()

    def get_nearby_npcs(self, map_id: int, x: int, y: int, radius: int = 5) -> list[DetectedNPC]:
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [
            npc for npc in area.npcs
            if abs(npc.x - x) <= radius and abs(npc.y - y) <= radius
        ]

    def get_nearby_items(self, map_id: int, x: int, y: int, radius: int = 5) -> list[DetectedItem]:
        area = self._area_cache.get(map_id)
        if not area:
            return []
        return [
            item for item in area.items
            if not item.collected and abs(item.x - x) <= radius and abs(item.y - y) <= radius
        ]

    def get_nearest_item(self, map_id: int, x: int, y: int) -> tuple[DetectedItem, int] | None:
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
        area = self._area_cache.get(map_id)
        if not area:
            return []
        trainer_range = 5
        trainers = []
        for npc in area.npcs:
            if not npc.can_battle:
                continue
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
            lines.append(f"Exits: {', '.join(warp_desc[:3])}")

        # Include truncated ASCII map for spatial context
        if area.ascii_map:
            map_lines = area.ascii_map.split("\n")
            if len(map_lines) > 25:
                map_lines = map_lines[:25]
                map_lines.append("... (truncated)")
            lines.append(f"\nMap:\n" + "\n".join(map_lines))

        return "\n".join(lines)

    def _relative_direction(self, dx: int, dy: int) -> str:
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
