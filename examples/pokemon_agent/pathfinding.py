"""2D Pathfinding for Pokemon Yellow.

Uses BFS and A* to find paths through the map, accounting for:
- Collision tiles (walls, furniture, water)
- Sprite/NPC positions
- Map boundaries
- Tile-pair collision rules (certain tile transitions are blocked)
"""

import heapq
from collections import deque
from dataclasses import dataclass
from typing import Optional

from . import memory_map as mem


# ============================================================
# Tile-Pair Collision Data
# ============================================================
# Certain tile pairs block movement between them even if both tiles
# are individually walkable. Format: (tileset_name, tile1, tile2)
# Bidirectional: blocked in both directions.

TILE_PAIR_COLLISIONS_LAND = [
    ("CAVERN", 288, 261),
    ("CAVERN", 321, 261),
    ("FOREST", 304, 302),
    ("CAVERN", 298, 261),
    ("CAVERN", 261, 289),
    ("FOREST", 338, 302),
    ("FOREST", 341, 302),
    ("FOREST", 342, 302),
    ("FOREST", 288, 302),
    ("FOREST", 350, 302),
    ("FOREST", 351, 302),
]

TILE_PAIR_COLLISIONS_WATER = [
    ("FOREST", 276, 302),
    ("FOREST", 328, 302),
    ("CAVERN", 276, 261),
]


def can_move_between_tiles(tile_from: int, tile_to: int, tileset_name: str) -> bool:
    """Check if movement between two tiles is allowed given tile-pair rules.

    Args:
        tile_from: Tile ID the player is moving from
        tile_to: Tile ID the player is moving to
        tileset_name: Name of the current tileset (e.g., "FOREST", "CAVERN")

    Returns:
        True if the move is allowed, False if blocked by a tile-pair rule
    """
    for ts, t1, t2 in TILE_PAIR_COLLISIONS_LAND:
        if ts == tileset_name:
            if (tile_from == t1 and tile_to == t2) or (tile_from == t2 and tile_to == t1):
                return False
    for ts, t1, t2 in TILE_PAIR_COLLISIONS_WATER:
        if ts == tileset_name:
            if (tile_from == t1 and tile_to == t2) or (tile_from == t2 and tile_to == t1):
                return False
    return True


@dataclass
class Point:
    """2D coordinate."""
    x: int
    y: int

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


@dataclass
class Path:
    """A path from start to goal."""
    steps: list[str]  # Directions: "up", "down", "left", "right"
    positions: list[Point]  # Coordinates along the path

    @property
    def length(self) -> int:
        return len(self.steps)

    @property
    def first_step(self) -> str | None:
        return self.steps[0] if self.steps else None


class CollisionMap:
    """Represents walkable/blocked tiles on the current map."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # True = walkable, False = blocked
        self._grid: list[list[bool]] = [[True for _ in range(width)] for _ in range(height)]
        self._npcs: set[tuple[int, int]] = set()

    def set_blocked(self, x: int, y: int):
        """Mark a tile as blocked."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._grid[y][x] = False

    def set_walkable(self, x: int, y: int):
        """Mark a tile as walkable."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._grid[y][x] = True

    def add_npc(self, x: int, y: int):
        """Mark an NPC position (blocks movement)."""
        self._npcs.add((x, y))

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile is walkable."""
        # Check bounds
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        # Check NPC
        if (x, y) in self._npcs:
            return False
        # Check collision grid
        return self._grid[y][x]

    def get_neighbors(self, x: int, y: int) -> list[tuple[int, int, str]]:
        """Get walkable neighbors with directions."""
        neighbors = []
        # Order: down, left, right, up (prioritize exits which are usually down)
        directions = [
            (0, 1, "down"),
            (-1, 0, "left"),
            (1, 0, "right"),
            (0, -1, "up"),
        ]
        for dx, dy, direction in directions:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                neighbors.append((nx, ny, direction))
        return neighbors

    def __str__(self) -> str:
        """Render the map as ASCII for debugging."""
        lines = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if (x, y) in self._npcs:
                    row += "N"
                elif self._grid[y][x]:
                    row += "."
                else:
                    row += "#"
            lines.append(row)
        return "\n".join(lines)


def find_path(collision_map: CollisionMap, start: Point, goal: Point) -> Optional[Path]:
    """
    Find shortest path from start to goal using BFS.

    Args:
        collision_map: The map with walkable/blocked tiles
        start: Starting position
        goal: Target position

    Returns:
        Path object with steps and positions, or None if no path exists
    """
    if start == goal:
        return Path(steps=[], positions=[start])

    if not collision_map.is_walkable(goal.x, goal.y):
        # Goal is blocked, find closest walkable point to goal
        return None

    # BFS
    queue = deque([(start.x, start.y, [])])  # (x, y, path_so_far)
    visited = {(start.x, start.y)}

    while queue:
        x, y, path = queue.popleft()

        for nx, ny, direction in collision_map.get_neighbors(x, y):
            if (nx, ny) in visited:
                continue

            new_path = path + [(direction, nx, ny)]

            if nx == goal.x and ny == goal.y:
                # Found goal
                steps = [p[0] for p in new_path]
                positions = [start] + [Point(p[1], p[2]) for p in new_path]
                return Path(steps=steps, positions=positions)

            visited.add((nx, ny))
            queue.append((nx, ny, new_path))

    return None  # No path found


def find_path_to_nearest(collision_map: CollisionMap, start: Point, goals: list[Point]) -> Optional[Path]:
    """
    Find shortest path from start to any of the goal points.

    Args:
        collision_map: The map with walkable/blocked tiles
        start: Starting position
        goals: List of target positions (finds nearest reachable one)

    Returns:
        Path object to nearest goal, or None if no goals reachable
    """
    if not goals:
        return None

    goal_set = {(g.x, g.y) for g in goals}

    if (start.x, start.y) in goal_set:
        return Path(steps=[], positions=[start])

    # BFS to find nearest goal
    queue = deque([(start.x, start.y, [])])
    visited = {(start.x, start.y)}

    while queue:
        x, y, path = queue.popleft()

        for nx, ny, direction in collision_map.get_neighbors(x, y):
            if (nx, ny) in visited:
                continue

            new_path = path + [(direction, nx, ny)]

            if (nx, ny) in goal_set:
                # Found a goal
                steps = [p[0] for p in new_path]
                positions = [start] + [Point(p[1], p[2]) for p in new_path]
                return Path(steps=steps, positions=positions)

            visited.add((nx, ny))
            queue.append((nx, ny, new_path))

    return None


def find_path_astar(
    collision_map: CollisionMap,
    start: Point,
    goal: Point,
    tile_map: Optional[dict[tuple[int, int], int]] = None,
    tileset_name: Optional[str] = None,
) -> Optional[Path]:
    """Find shortest path using A* with Manhattan distance heuristic.

    Optionally uses tile-pair collision rules when tile_map and tileset_name
    are provided. Falls back to standard A* (equivalent to BFS on uniform
    cost grid) when tile data is unavailable.

    Args:
        collision_map: The map with walkable/blocked tiles
        start: Starting position
        goal: Target position
        tile_map: Optional dict mapping (x, y) -> tile ID for tile-pair checks
        tileset_name: Optional tileset name for tile-pair collision lookup

    Returns:
        Path object with steps and positions, or None if no path exists
    """
    if start == goal:
        return Path(steps=[], positions=[start])

    if not collision_map.is_walkable(goal.x, goal.y):
        return None

    check_tile_pairs = tile_map is not None and tileset_name is not None

    # Priority queue: (f_score, counter, x, y, path)
    # counter breaks ties for equal f_scores
    counter = 0
    open_set = [(0, counter, start.x, start.y, [])]
    g_scores: dict[tuple[int, int], int] = {(start.x, start.y): 0}

    directions = [
        (0, 1, "down"),
        (-1, 0, "left"),
        (1, 0, "right"),
        (0, -1, "up"),
    ]

    while open_set:
        f, _, x, y, path = heapq.heappop(open_set)

        current_g = g_scores.get((x, y), float("inf"))
        # Skip if we've already found a better path to this node
        if len(path) > current_g:
            continue

        for dx, dy, direction in directions:
            nx, ny = x + dx, y + dy

            if not collision_map.is_walkable(nx, ny):
                continue

            # Check tile-pair collisions if data available
            if check_tile_pairs:
                from_tile = tile_map.get((x, y))
                to_tile = tile_map.get((nx, ny))
                if from_tile is not None and to_tile is not None:
                    if not can_move_between_tiles(from_tile, to_tile, tileset_name):
                        continue

            new_g = current_g + 1

            if new_g < g_scores.get((nx, ny), float("inf")):
                g_scores[(nx, ny)] = new_g
                # Manhattan distance heuristic
                h = abs(nx - goal.x) + abs(ny - goal.y)
                f_score = new_g + h
                new_path = path + [(direction, nx, ny)]

                if nx == goal.x and ny == goal.y:
                    steps = [p[0] for p in new_path]
                    positions = [start] + [Point(p[1], p[2]) for p in new_path]
                    return Path(steps=steps, positions=positions)

                counter += 1
                heapq.heappush(open_set, (f_score, counter, nx, ny, new_path))

    return None


class MapReader:
    """Reads map collision data from game memory."""

    def __init__(self, call_tool):
        """
        Args:
            call_tool: async callable(name, args) → result for MCP tools
        """
        self._call = call_tool

    async def _read_byte(self, address: int) -> int:
        """Read a single byte from memory."""
        result = await self._call("read_memory", {"address": address, "length": 1})
        if isinstance(result, dict) and "bytes" in result:
            return result["bytes"][0]
        return 0

    async def _read_bytes(self, address: int, length: int) -> list[int]:
        """Read multiple bytes from memory."""
        result = await self._call("read_memory", {"address": address, "length": length})
        if isinstance(result, dict) and "bytes" in result:
            return result["bytes"]
        return [0] * length

    async def read_collision_map(self) -> CollisionMap:
        """
        Read the current map's collision data and build a CollisionMap.

        Pokemon Yellow stores collision data as a 2D array of block IDs.
        Each block is 2x2 tiles. Block collision is determined by the tileset.
        """
        # Get map dimensions
        width = await self._read_byte(mem.WRAM_CUR_MAP_WIDTH)
        height = await self._read_byte(mem.WRAM_CUR_MAP_HEIGHT)

        if width == 0 or height == 0:
            # Fallback for invalid dimensions
            width = height = 10

        # Create collision map (in tile coordinates, not block coordinates)
        # Map is stored in blocks (2x2 tiles), so tile dimensions are 2x
        tile_width = width * 2 + 6  # Add border
        tile_height = height * 2 + 6  # Add border

        # For indoor maps, use smaller dimensions
        # Player House 2F is small - about 4x4 blocks = 8x8 tiles walkable
        collision_map = CollisionMap(tile_width, tile_height)

        # Mark everything outside the playable area as blocked
        # The playable area starts at (0,0) and extends to (width*2-1, height*2-1)
        for y in range(tile_height):
            for x in range(tile_width):
                # Default to blocked outside playable area
                if x >= width * 2 or y >= height * 2:
                    collision_map.set_blocked(x, y)

        # Read the actual collision data
        # wOverworldMap has a 3-block border on all sides. The actual map blocks
        # are embedded with stride = width + 6, starting at offset 3*stride+3.
        buf_stride = width + 6
        map_start = mem.WRAM_MAP_DATA + 3 * buf_stride + 3
        map_data = []
        for row in range(height):
            row_data = await self._read_bytes(map_start + row * buf_stride, width)
            map_data.extend(row_data)

        # Simple heuristic: treat high-valued block IDs as solid
        # This is a simplification - real collision depends on tileset
        for i, block_id in enumerate(map_data):
            bx = i % width
            by = i // width
            # Convert to tile coordinates
            tx = bx * 2
            ty = by * 2

            # Check if this block type is typically solid
            # In Gen 1, blocks 0x01-0x03 are often walkable floor
            # Higher values tend to be walls/furniture
            if block_id > 0x10:  # Heuristic: high block IDs are solid
                for dx in range(2):
                    for dy in range(2):
                        collision_map.set_blocked(tx + dx, ty + dy)

        # Read sprite/NPC positions from wSpriteStateData2 (canonical map coords)
        num_sprites = await self._read_byte(mem.WRAM_NUM_SPRITES)
        for i in range(1, min(num_sprites + 1, 16)):  # Skip sprite 0 (player)
            base = mem.WRAM_SPRITE_DATA_2 + (i * 16)
            sprite_data = await self._read_bytes(base, 16)
            if len(sprite_data) >= 6:
                npc_y = sprite_data[mem.SPRITE2_MAP_Y]
                npc_x = sprite_data[mem.SPRITE2_MAP_X]
                if npc_x > 0 and npc_y > 0:  # Valid position
                    collision_map.add_npc(npc_x, npc_y)

        return collision_map

    async def read_tile_collision(self, x: int, y: int) -> bool:
        """
        Check if a specific tile is walkable by reading the tile ahead.

        This uses the game's own tile-ahead check which accounts for
        the actual tileset collision data.
        """
        # The tile in front data at WRAM_TILE_IN_FRONT is what the game
        # uses internally to check collisions
        tile_id = await self._read_byte(mem.WRAM_TILE_IN_FRONT)

        # Check against known solid tiles
        if tile_id in mem.SOLID_TILES:
            return False

        return True

    async def get_player_position(self) -> Point:
        """Get the player's current position."""
        x = await self._read_byte(mem.WRAM_X_COORD)
        y = await self._read_byte(mem.WRAM_Y_COORD)
        return Point(x, y)

    async def get_warp_positions(self) -> list[Point]:
        """Get all warp positions on the current map."""
        warps = []
        num_warps = await self._read_byte(mem.WRAM_NUM_WARPS)

        for i in range(min(num_warps, 16)):
            base = mem.WRAM_WARP_ENTRIES + (i * 4)
            data = await self._read_bytes(base, 4)
            if len(data) >= 4:
                y, x = data[0], data[1]
                warps.append(Point(x, y))

        return warps

    async def read_tileset(self) -> tuple[int, str]:
        """Read the current map's tileset ID and name.

        Returns:
            (tileset_id, tileset_name) tuple
        """
        from .pokemon_data import TILESET_NAMES
        tileset_id = await self._read_byte(mem.WRAM_CUR_MAP_TILESET)
        tileset_name = TILESET_NAMES.get(tileset_id, "UNKNOWN")
        return tileset_id, tileset_name

    async def read_tile_map(self) -> dict[tuple[int, int], int]:
        """Read the current map's tile data for tile-pair collision checks.

        Returns:
            Dict mapping (x, y) tile coords to tile IDs
        """
        width = await self._read_byte(mem.WRAM_CUR_MAP_WIDTH)
        height = await self._read_byte(mem.WRAM_CUR_MAP_HEIGHT)

        if width == 0 or height == 0:
            return {}

        # wOverworldMap has a 3-block border; read with proper stride
        buf_stride = width + 6
        map_start = mem.WRAM_MAP_DATA + 3 * buf_stride + 3
        map_data = []
        for row in range(height):
            row_data = await self._read_bytes(map_start + row * buf_stride, width)
            map_data.extend(row_data)

        tile_map = {}
        for i, block_id in enumerate(map_data):
            bx = i % width
            by = i // width
            # Each block covers 2x2 tiles; store block ID for all 4 tiles
            for dx in range(2):
                for dy in range(2):
                    tile_map[(bx * 2 + dx, by * 2 + dy)] = block_id

        return tile_map


def is_text_box_visible(screen_tiles: list[int], screen_width: int = 20, screen_height: int = 18) -> bool:
    """
    Detect if a text box is visible by checking screen tiles.

    Pokemon text boxes have distinct border tiles that appear on screen.
    This is a more reliable indicator than memory flags.

    Args:
        screen_tiles: 360 bytes from WRAM_TILE_MAP (20x18 tiles)
        screen_width: Screen width in tiles (20)
        screen_height: Screen height in tiles (18)

    Returns:
        True if text box borders are detected
    """
    if len(screen_tiles) < screen_width * screen_height:
        return False

    # Text box border tile IDs in Pokemon Yellow
    # These are the graphical tiles used for menu/text box borders
    TEXT_BOX_CORNER_TL = 0x79  # Top-left corner
    TEXT_BOX_CORNER_TR = 0x7A  # Top-right corner
    TEXT_BOX_CORNER_BL = 0x7B  # Bottom-left corner
    TEXT_BOX_CORNER_BR = 0x7C  # Bottom-right corner
    TEXT_BOX_HORIZ = 0x7F      # Horizontal border
    TEXT_BOX_VERT = 0x7E       # Vertical border

    # Alternative border tiles (different tilesets)
    ALT_BORDER_TILES = {0x63, 0x64, 0x65, 0x66, 0x6C, 0x6D, 0x6E, 0x6F}

    border_tiles = {
        TEXT_BOX_CORNER_TL, TEXT_BOX_CORNER_TR,
        TEXT_BOX_CORNER_BL, TEXT_BOX_CORNER_BR,
        TEXT_BOX_HORIZ, TEXT_BOX_VERT
    } | ALT_BORDER_TILES

    # Check the bottom third of the screen (where text boxes appear)
    # Text boxes in Pokemon usually appear in rows 12-17
    text_region_start = 12 * screen_width

    border_count = 0
    for i in range(text_region_start, len(screen_tiles)):
        if screen_tiles[i] in border_tiles:
            border_count += 1

    # If we see multiple border tiles, there's likely a text box
    return border_count >= 6


def has_text_content(screen_tiles: list[int], screen_width: int = 20) -> bool:
    """
    Check if screen has actual text content (letters/numbers).

    Args:
        screen_tiles: 360 bytes from WRAM_TILE_MAP
        screen_width: Screen width in tiles

    Returns:
        True if text characters are present in the lower portion
    """
    if len(screen_tiles) < 360:
        return False

    # Check rows 13-17 (typical text box area)
    text_start = 13 * screen_width
    text_end = 17 * screen_width

    text_count = 0
    for i in range(text_start, min(text_end, len(screen_tiles))):
        tile = screen_tiles[i]
        # Check for letter tiles (0x80-0x99 = A-Z, 0xA0-0xB9 = a-z)
        if (0x80 <= tile <= 0x99) or (0xA0 <= tile <= 0xB9):
            text_count += 1
        # Check for number tiles (0xF6-0xFF = 0-9)
        elif 0xF6 <= tile <= 0xFF:
            text_count += 1

    return text_count >= 3  # At least a few characters
