"""Waypoint database extracted from PokeBot's paths.lua for Pokemon Yellow.

Provides pre-computed navigation paths so the agent can follow known routes
instead of doing BFS pathfinding from scratch on every map.

Source: PokeBot/data/yellow/paths.lua (speedrunner bot by Pokemon Challenges)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaypointPath:
    """A sequence of waypoints for navigating within a single map.

    Attributes:
        dest_map: The map_id of the destination (next map in the speedrun route).
        points: Ordered tuple of (x, y) coordinate waypoints to follow.
    """
    dest_map: int
    points: tuple[tuple[int, int], ...]


def get_waypoint_path(
    map_id: int,
    dest_map: int,
    player_pos: tuple[int, int] | None = None,
    max_start_distance: int = 2,
) -> WaypointPath | None:
    """Look up a waypoint path for navigating from map_id toward dest_map.

    Args:
        map_id: Current map ID.
        dest_map: Target map ID to navigate toward.
        player_pos: Optional (x, y) player position. If provided, only returns
            a path whose first waypoint is within max_start_distance of the
            player (Manhattan distance).
        max_start_distance: Maximum Manhattan distance from player_pos to the
            first waypoint for the path to be considered valid.

    Returns:
        A WaypointPath if found, or None if no matching path exists.
    """
    paths = WAYPOINTS.get(map_id)
    if not paths:
        return None

    for path in paths:
        if path.dest_map != dest_map:
            continue
        if player_pos is not None:
            start = path.points[0]
            dist = abs(player_pos[0] - start[0]) + abs(player_pos[1] - start[1])
            if dist > max_start_distance:
                continue
        return path

    return None


# ---------------------------------------------------------------------------
# Pre-converted waypoint data from PokeBot/data/yellow/paths.lua
#
# Conversion rules applied:
# - First field of each Lua entry = map_id
# - {x, y} pairs = waypoints; {s=...} and {c=...} entries stripped
# - Paths split at {s="interact"} boundaries
# - dest_map = map_id of the NEXT entry in the Lua sequence
# - First occurrence kept when (map_id, dest_map) duplicates exist
# - Paths with fewer than 2 waypoints after filtering are skipped
# ---------------------------------------------------------------------------

WAYPOINTS: dict[int, list[WaypointPath]] = {
    0: [
        WaypointPath(dest_map=40, points=((5, 6), (10, 6), (10, 0),)),
        WaypointPath(dest_map=12, points=((12, 12), (9, 12), (9, 2), (10, 2), (10, -1),)),
        WaypointPath(dest_map=32, points=((5, 6), (3, 6), (3, 17), (4, 18),)),
    ],
    1: [
        WaypointPath(dest_map=42, points=((21, 35), (21, 30), (19, 30), (19, 20), (29, 20), (29, 19),)),
        WaypointPath(dest_map=12, points=((29, 20), (29, 21), (26, 21), (26, 30), (20, 30), (20, 36),)),
        WaypointPath(dest_map=13, points=((29, 20), (19, 20), (19, 9), (19, 2), (17, 2), (17, -1),)),
        WaypointPath(dest_map=45, points=((23, 26), (19, 26), (19, 4), (27, 4), (27, 3), (34, 3), (34, 8), (32, 8), (32, 7),)),
        WaypointPath(dest_map=33, points=((32, 8), (32, 12), (17, 12), (17, 16), (16, 16), (16, 17), (-1, 17),)),
    ],
    2: [
        WaypointPath(dest_map=54, points=((18, 35), (18, 26), (18, 22), (19, 22), (19, 13), (10, 13), (10, 18), (16, 18), (16, 17),)),
        WaypointPath(dest_map=14, points=((16, 18), (10, 18), (10, 13), (27, 13), (27, 16), (40, 16),)),
    ],
    3: [
        WaypointPath(dest_map=230, points=((0, 18), (8, 18), (8, 16), (8, 12), (9, 12), (9, 11),)),
        WaypointPath(dest_map=35, points=((9, 12), (21, 12), (21, 6), (21, -1),)),
        WaypointPath(dest_map=65, points=((24, 0), (24, 15), (22, 15), (22, 18), (22, 18), (22, 20), (30, 20), (30, 19),)),
        WaypointPath(dest_map=62, points=((30, 20), (8, 20), (8, 12), (27, 12), (27, 11),)),
        WaypointPath(dest_map=16, points=((27, 9), (28, 9), (30, 9), (33, 9), (33, 18), (36, 18), (36, 31), (25, 31), (25, 36),)),
        WaypointPath(dest_map=66, points=((19, 18), (19, 23), (16, 23), (16, 26), (13, 26), (13, 25),)),
        WaypointPath(dest_map=20, points=((13, 25), (13, 26), (19, 26), (19, 27), (19, 29), (36, 29), (36, 16), (40, 16),)),
    ],
    4: [
        WaypointPath(dest_map=19, points=((6, 0), (6, 6), (0, 6), (0, 8), (-1, 8),)),
        WaypointPath(dest_map=142, points=((3, 6), (14, 6), (14, 5),)),
    ],
    5: [
        WaypointPath(dest_map=91, points=((19, 0), (19, 6), (21, 6), (21, 14), (23, 14), (23, 13),)),
        WaypointPath(dest_map=94, points=((23, 14), (30, 14), (30, 26), (18, 26), (18, 31),)),
        WaypointPath(dest_map=90, points=((18, 29), (18, 26), (30, 26), (30, 14), (15, 14), (9, 14), (9, 13),)),
        WaypointPath(dest_map=92, points=((9, 14), (9, 15), (15, 15), (15, 17), (15, 20), (12, 20), (12, 19),)),
        WaypointPath(dest_map=22, points=((12, 20), (15, 20), (15, 19), (15, 14), (40, 14),)),
    ],
    6: [
        WaypointPath(dest_map=122, points=((49, 11), (14, 11), (14, 14), (8, 14), (8, 13),)),
        WaypointPath(dest_map=27, points=((10, 14), (10, 15), (2, 15), (2, 18), (-1, 18),)),
        WaypointPath(dest_map=133, points=((41, 10), (41, 9),)),
        WaypointPath(dest_map=18, points=((41, 10), (41, 11), (50, 11),)),
        WaypointPath(dest_map=134, points=((41, 10), (41, 13), (36, 13), (36, 23), (25, 23), (25, 30), (35, 30), (35, 31), (35, 34), (5, 34), (5, 29), (12, 29), (12, 27),)),
    ],
    7: [
        WaypointPath(dest_map=156, points=((0, 16), (3, 16), (3, 20), (23, 20), (23, 14), (29, 14), (29, 15), (35, 15), (35, 8), (37, 8), (37, 2), (22, 2), (22, 4), (18, 4), (18, 3),)),
        WaypointPath(dest_map=157, points=((19, 28), (5, 28), (5, 27),)),
        WaypointPath(dest_map=155, points=((5, 28), (6, 28), (6, 30), (24, 30), (30, 30), (30, 28), (27, 28), (27, 27),)),
    ],
    8: [
        WaypointPath(dest_map=165, points=((3, 0), (3, 4), (6, 4), (6, 3),)),
        WaypointPath(dest_map=166, points=((11, 12), (18, 12), (18, 3),)),
    ],
    9: [
        WaypointPath(dest_map=174, points=((10, 17), (10, 5),)),
    ],
    10: [
        WaypointPath(dest_map=181, points=((0, 18), (3, 18), (3, 22), (18, 22), (18, 21),)),
        WaypointPath(dest_map=178, points=((9, 30), (9, 31), (36, 31), (36, 6), (38, 6), (38, 4), (34, 4), (34, 3),)),
    ],
    12: [
        WaypointPath(dest_map=1, points=((10, 35), (10, 30), (8, 30), (8, 24), (12, 24), (12, 20), (9, 20), (9, 14), (14, 14), (14, 2), (11, 2), (11, -1),)),
        WaypointPath(dest_map=0, points=((10, 0), (10, 3), (8, 3), (8, 18), (9, 18), (9, 21), (12, 21), (12, 24), (10, 24), (10, 36),)),
    ],
    13: [
        WaypointPath(dest_map=50, points=((7, 71), (7, 57), (4, 57), (4, 52), (8, 47), (8, 45), (8, 44), (3, 44), (3, 43),)),
        WaypointPath(dest_map=2, points=((3, 11), (3, 8), (8, 8), (8, -1),)),
    ],
    14: [
        WaypointPath(dest_map=14, points=((0, 8), (3, 8), (3, 9), (11, 9), (11, 4), (12, 4), (13, 4),)),
        WaypointPath(dest_map=2, points=((13, 4), (13, 5), (17, 5), (18, 5), (18, 4), (19, 4), (15, 4), (15, 6), (11, 6), (11, 9), (-1, 9),)),
        WaypointPath(dest_map=15, points=((24, 5), (27, 5), (27, 9), (37, 8), (37, 5), (49, 5), (49, 10), (57, 10), (57, 8), (59, 8), (59, -1),)),
    ],
    15: [
        WaypointPath(dest_map=59, points=((9, 17), (12, 17), (12, 6), (18, 6), (18, 5),)),
        WaypointPath(dest_map=3, points=((24, 6), (24, 8), (35, 8), (35, 10), (61, 10), (61, 8), (79, 8), (79, 10), (90, 10),)),
    ],
    16: [
        WaypointPath(dest_map=71, points=((15, 0), (15, 28), (17, 28), (17, 27),)),
    ],
    17: [
        WaypointPath(dest_map=5, points=((17, 14), (17, 25), (15, 25), (15, 27), (15, 28), (11, 28), (11, 29), (10, 29), (10, 30), (10, 31), (9, 31), (9, 36),)),
    ],
    18: [
        WaypointPath(dest_map=6, points=((5, 14), (8, 14), (8, 8), (4, 8), (4, 3), (-1, 3),)),
        WaypointPath(dest_map=76, points=((0, 3), (4, 3), (4, 9), (10, 9), (10, 10), (12, 10),)),
        WaypointPath(dest_map=10, points=((18, 10), (20, 10),)),
    ],
    19: [
        WaypointPath(dest_map=80, points=((59, 8), (52, 8), (52, 13), (47, 13), (47, 14), (42, 14), (42, 7), (40, 7), (40, 6), (29, 6), (29, 7), (23, 7), (23, 12), (14, 12), (14, 4), (13, 4), (13, 3),)),
    ],
    20: [
        WaypointPath(dest_map=21, points=((0, 8), (4, 8), (13, 8), (13, 9), (12, 9), (12, 12), (23, 12), (23, 11), (29, 11), (29, 12), (41, 12), (41, 10), (40, 10), (40, 9), (41, 9), (41, 6), (39, 6), (39, 4), (45, 4), (45, 3), (51, 3), (51, 8), (60, 8),)),
    ],
    21: [
        WaypointPath(dest_map=82, points=((0, 8), (3, 8), (3, 10), (13, 10), (13, 15), (14, 15), (14, 26), (3, 26), (3, 18), (7, 18), (8, 18), (8, 17),)),
        WaypointPath(dest_map=4, points=((8, 54), (15, 54), (15, 65), (11, 65), (11, 69), (6, 69), (6, 72),)),
    ],
    22: [
        WaypointPath(dest_map=85, points=((0, 6), (4, 6), (4, 5),)),
    ],
    27: [
        WaypointPath(dest_map=186, points=((39, 10), (34, 10), (34, 6), (27, 6), (27, 5), (23, 5),)),
        WaypointPath(dest_map=188, points=((17, 4), (10, 4), (10, 6), (7, 6), (7, 5),)),
        WaypointPath(dest_map=4, points=((7, 5), (7, 6),)),
        WaypointPath(dest_map=28, points=((17, 10), (12, 10), (12, 13), (11, 13), (11, 18),)),
    ],
    28: [
        WaypointPath(dest_map=29, points=((11, 0), (11, 5), (15, 5), (15, 12), (15, 14), (18, 14), (18, 122), (13, 122), (13, 143),)),
    ],
    29: [
        WaypointPath(dest_map=190, points=((13, 0), (13, 8), (34, 8),)),
        WaypointPath(dest_map=7, points=((40, 8), (50, 8),)),
    ],
    32: [
        WaypointPath(dest_map=8, points=((4, 0), (4, 14), (3, 14), (3, 90),)),
    ],
    33: [
        WaypointPath(dest_map=193, points=((39, 9), (35, 9), (35, 12), (31, 12), (31, 5), (29, 5), (16, 5), (16, 12), (5, 12), (5, 10), (11, 10), (11, 6), (8, 6), (8, 5),)),
    ],
    34: [
        WaypointPath(dest_map=108, points=((7, 139), (7, 132), (14, 132), (14, 124), (9, 124), (9, 116), (10, 116), (10, 104), (10, 92), (7, 92), (7, 90), (7, 72), (8, 72), (8, 71), (8, 66), (10, 66), (10, 57), (12, 57), (12, 48), (6, 48), (6, 32), (4, 32), (4, 31),)),
        WaypointPath(dest_map=9, points=((14, 32), (18, 32), (18, 20), (14, 20), (14, 10), (13, 10), (13, 6), (10, 6), (10, -1),)),
    ],
    35: [
        WaypointPath(dest_map=36, points=((11, 35), (11, 32), (10, 32), (10, 30), (10, 29), (11, 29), (11, 27), (11, 26), (10, 26), (10, 24), (10, 23), (11, 23), (11, 21), (11, 20), (10, 20), (10, 16), (10, 15), (10, 8), (20, 8),)),
        WaypointPath(dest_map=3, points=((19, 11), (14, 11), (14, 36),)),
    ],
    36: [
        WaypointPath(dest_map=88, points=((0, 8), (9, 8), (9, 7), (11, 7), (11, 9), (14, 9), (14, 6), (15, 6), (15, 4), (17, 4), (17, 7), (18, 7), (20, 7), (20, 8), (22, 8), (22, 6), (23, 6), (35, 6), (35, 4), (36, 4), (36, 5), (38, 5), (38, 4), (45, 4), (45, 3),)),
        WaypointPath(dest_map=35, points=((45, 4), (45, 12), (36, 12), (36, 11), (-1, 11),)),
    ],
    38: [
        WaypointPath(dest_map=39, points=((3, 6), (5, 6), (5, 1), (7, 1),)),
    ],
    39: [
        WaypointPath(dest_map=0, points=((7, 1), (7, 6), (3, 6), (3, 8),)),
    ],
    40: [
        WaypointPath(dest_map=0, points=((5, 3), (5, 4), (7, 4), (5, 3), (5, 6), (5, 12),)),
        WaypointPath(dest_map=40, points=((5, 11), (5, 3), (4, 3), (4, 1), (5, 1),)),
    ],
    42: [
        WaypointPath(dest_map=1, points=((2, 5), (2, 6), (3, 6), (3, 8),)),
    ],
    45: [
        WaypointPath(dest_map=1, points=((16, 17), (16, 16), (14, 16), (14, 9), (13, 9), (13, 7), (15, 7), (15, 4), (12, 4), (12, 5), (11, 5), (10, 5), (10, 4), (13, 5), (13, 4), (15, 4), (15, 7), (13, 7), (13, 11), (14, 11), (14, 16), (16, 16), (16, 18),)),
        WaypointPath(dest_map=45, points=((16, 17), (16, 16), (14, 16), (14, 9), (13, 9), (13, 7), (15, 7), (15, 4), (12, 4), (12, 5), (10, 5), (10, 2), (7, 2), (7, 4), (2, 4), (2, 3), (2, 2),)),
    ],
    47: [
        WaypointPath(dest_map=13, points=((4, 7), (4, 1), (5, 1), (5, 0),)),
    ],
    50: [
        WaypointPath(dest_map=51, points=((4, 7), (4, 1), (5, 1), (5, 0),)),
    ],
    51: [
        WaypointPath(dest_map=51, points=((16, 47), (16, 44), (18, 44), (18, 42), (26, 42), (27, 34), (27, 33), (27, 32), (31, 32), (31, 18), (25, 18), (25, 12), (26, 12), (26, 9), (17, 9), (17, 16), (15, 16), (13, 16),)),
        WaypointPath(dest_map=47, points=((2, 19), (1, 19), (1, 16), (1, -1),)),
    ],
    54: [
        WaypointPath(dest_map=54, points=((4, 13), (4, 9), (4, 8), (3, 8), (3, 7),)),
        WaypointPath(dest_map=2, points=((4, 2), (4, 14),)),
    ],
    59: [
        WaypointPath(dest_map=60, points=((14, 35), (14, 22), (21, 22), (21, 15), (24, 15), (24, 27), (25, 27), (25, 31), (25, 32), (33, 32), (33, 31), (34, 31), (34, 3), (16, 3), (16, 17), (2, 17), (2, 3), (5, 3), (5, 5),)),
    ],
    60: [
        WaypointPath(dest_map=61, points=((5, 5), (5, 17), (21, 17),)),
        WaypointPath(dest_map=15, points=((23, 3), (27, 3),)),
    ],
    61: [
        WaypointPath(dest_map=60, points=((21, 17), (22, 17), (23, 17), (23, 14), (27, 14), (27, 16), (33, 16), (33, 14), (36, 14), (36, 24), (32, 24), (32, 31), (11, 31), (11, 16), (12, 16), (12, 10), (12, 9), (13, 9), (13, 7), (13, 5), (12, 5), (12, 4), (3, 4), (3, 5), (3, 4), (3, 7), (5, 7),)),
    ],
    62: [
        WaypointPath(dest_map=3, points=((2, 7), (2, 2), (3, 2), (3, 0),)),
    ],
    65: [
        WaypointPath(dest_map=3, points=((4, 13), (4, 8), (2, 8), (2, 5), (7, 5), (7, 3), (6, 3), (5, 3), (5, 2), (5, 3), (7, 3), (7, 5), (5, 5), (5, 14),)),
    ],
    66: [
        WaypointPath(dest_map=66, points=((2, 7), (2, 3), (4, 3), (4, 2),)),
        WaypointPath(dest_map=3, points=((4, 2), (4, 6), (3, 6), (3, 8),)),
    ],
    71: [
        WaypointPath(dest_map=119, points=((3, 7), (3, 4), (4, 4),)),
    ],
    74: [
        WaypointPath(dest_map=17, points=((4, 4), (3, 8),)),
    ],
    76: [
        WaypointPath(dest_map=18, points=((0, 3), (6, 3),)),
    ],
    77: [
        WaypointPath(dest_map=18, points=((4, 4), (4, 8),)),
    ],
    80: [
        WaypointPath(dest_map=121, points=((3, 7), (3, 6), (4, 6), (4, 4),)),
    ],
    82: [
        WaypointPath(dest_map=232, points=((15, 3), (15, 6), (23, 6), (23, 7), (22, 7), (22, 10), (37, 10), (37, 3),)),
        WaypointPath(dest_map=21, points=((37, 17), (32, 17), (32, 23), (37, 23), (37, 28), (28, 28), (26, 24), (23, 24), (23, 27), (15, 27), (15, 33),)),
    ],
    88: [
        WaypointPath(dest_map=88, points=((2, 7), (2, 5), (5, 5), (1, 5),)),
        WaypointPath(dest_map=36, points=((1, 5), (4, 5), (3, 5), (3, 8),)),
    ],
    90: [
        WaypointPath(dest_map=5, points=((2, 7), (2, 5), (0, 5), (0, 1), (2, 1), (0, 1), (0, 6), (2, 6), (2, 8),)),
    ],
    91: [
        WaypointPath(dest_map=5, points=((3, 7), (3, 5), (2, 5), (3, 5), (3, 8),)),
    ],
    92: [
        WaypointPath(dest_map=92, points=((4, 17), (4, 15), (1, 15), (1, 12), (4, 6), (4, 3), (5, 3), (5, 2),)),
        WaypointPath(dest_map=5, points=((5, 2), (4, 2), (4, 13), (5, 13), (5, 18),)),
    ],
    94: [
        WaypointPath(dest_map=95, points=((14, 0), (14, 3),)),
    ],
    95: [
        WaypointPath(dest_map=96, points=((27, 0), (27, 1), (26, 1), (26, 7), (2, 7), (2, 6),)),
        WaypointPath(dest_map=94, points=((2, 6), (2, 7), (26, 7), (26, -1),)),
    ],
    96: [
        WaypointPath(dest_map=101, points=((2, 4), (2, 11), (3, 11), (3, 12), (37, 12), (37, 9), (37, 8), (36, 8), (36, 4),)),
        WaypointPath(dest_map=95, points=((36, 4), (36, 12), (3, 12), (3, 11), (2, 11), (2, 4),)),
    ],
    101: [
        WaypointPath(dest_map=101, points=((0, 7), (0, 4), (4, 4), (4, 3),)),
        WaypointPath(dest_map=96, points=((4, 3), (4, 5), (0, 5), (0, 7),)),
    ],
    108: [
        WaypointPath(dest_map=194, points=((8, 17), (8, 16), (4, 16), (4, 14), (5, 14), (5, 15), (4, 15), (4, 16), (7, 16), (7, 17), (9, 17), (9, 15), (8, 15), (8, 14), (15, 14), (15, 15), (16, 15), (16, 14), (14, 14), (14, 12), (16, 12), (16, 11), (17, 11), (17, 12), (14, 12), (14, 14), (8, 14), (8, 16), (5, 16), (5, 12), (11, 12), (11, 6), (7, 6), (7, 8), (3, 8), (3, 5), (2, 5), (2, 1), (1, 1),)),
    ],
    113: [
        WaypointPath(dest_map=120, points=((6, 10), (6, 2), (5, 2), (5, 1), (5, -1),)),
    ],
    119: [
        WaypointPath(dest_map=74, points=((5, 4), (4, 4), (2, 4), (2, 41),)),
    ],
    120: [
        WaypointPath(dest_map=118, points=((4, 3), (3, 0),)),
    ],
    121: [
        WaypointPath(dest_map=77, points=((47, 2), (21, 2), (21, 4), (12, 4), (12, 3), (2, 3), (2, 5),)),
    ],
    122: [
        WaypointPath(dest_map=127, points=((2, 7), (2, 2), (1, 2), (1, 1),)),
        WaypointPath(dest_map=6, points=((12, 2), (12, 6), (16, 6), (16, 8),)),
    ],
    123: [
        WaypointPath(dest_map=122, points=((16, 2), (8, 2), (8, 5), (6, 5), (5, 5), (9, 5), (9, 2), (12, 2), (12, 1),)),
    ],
    124: [
        WaypointPath(dest_map=123, points=((12, 2), (16, 2), (16, 1),)),
    ],
    125: [
        WaypointPath(dest_map=124, points=((16, 2), (10, 2), (10, 5), (5, 5), (11, 5), (11, 2), (12, 2), (12, 1),)),
    ],
    126: [
        WaypointPath(dest_map=136, points=((15, 3), (12, 3), (6, 3), (6, 4), (6, 4), (7, 3), (12, 3), (15, 3), (15, 2),)),
    ],
    127: [
        WaypointPath(dest_map=136, points=((1, 3), (1, 2), (3, 2), (3, 1), (2, 1), (2, 4),)),
    ],
    133: [
        WaypointPath(dest_map=6, points=((3, 7), (3, 3), (3, 8),)),
    ],
    134: [
        WaypointPath(dest_map=6, points=((4, 17), (4, 16), (1, 16), (1, 9), (0, 9), (0, 4), (1, 4), (3, 4), (4, 4), (5, 4), (5, 6), (5, 18),)),
    ],
    136: [
        WaypointPath(dest_map=126, points=((1, 2), (1, 3), (3, 3), (3, 5), (9, 5), (9, 2), (12, 2), (12, 1),)),
        WaypointPath(dest_map=125, points=((12, 2), (16, 2), (16, 1),)),
    ],
    142: [
        WaypointPath(dest_map=143, points=((10, 17), (10, 10), (18, 10), (18, 9),)),
    ],
    143: [
        WaypointPath(dest_map=144, points=((18, 9), (18, 7), (16, 7), (16, 5), (15, 5), (5, 5), (5, 8), (3, 8), (3, 9),)),
    ],
    144: [
        WaypointPath(dest_map=145, points=((3, 9), (3, 10), (6, 10), (6, 13), (8, 13), (8, 6), (17, 6), (17, 9), (18, 9),)),
    ],
    145: [
        WaypointPath(dest_map=146, points=((18, 9), (18, 7), (16, 7), (16, 9), (14, 9), (14, 10), (13, 10), (14, 10), (14, 8), (11, 8), (11, 9), (10, 9), (10, 12), (7, 12), (7, 11), (4, 11), (4, 10), (3, 10), (3, 9),)),
    ],
    146: [
        WaypointPath(dest_map=147, points=((3, 9), (4, 9), (4, 11), (4, 6), (13, 6), (13, 9), (9, 9), (9, 12), (14, 12), (14, 10), (18, 10), (18, 9),)),
    ],
    147: [
        WaypointPath(dest_map=147, points=((18, 9), (18, 7), (15, 7), (15, 3), (11, 3), (11, 5), (10, 5),)),
        WaypointPath(dest_map=148, points=((6, 7), (6, 14), (10, 14), (10, 16), (9, 16),)),
    ],
    148: [
        WaypointPath(dest_map=149, points=((9, 16), (10, 16), (10, 12), (10, 4),)),
    ],
    149: [
        WaypointPath(dest_map=4, points=((3, 7), (3, 6), (2, 6), (2, 1), (2, 8),)),
    ],
    155: [
        WaypointPath(dest_map=7, points=((4, 7), (4, 6), (2, 6), (2, 4), (4, 4), (4, 8),)),
    ],
    156: [
        WaypointPath(dest_map=220, points=((3, 5), (3, 3), (4, 3), (4, 2), (4, -1),)),
    ],
    157: [
        WaypointPath(dest_map=7, points=((4, 17), (4, 16), (9, 16), (9, 9), (7, 9), (9, 9), (9, 1), (1, 1), (1, 2), (1, 3), (2, 3), (2, 5), (1, 5), (1, 7), (1, 9), (2, 9), (4, 9), (1, 9), (1, 5), (2, 5), (2, 3), (1, 3), (1, 1), (9, 1), (9, 16), (5, 16), (5, 18),)),
    ],
    165: [
        WaypointPath(dest_map=214, points=((5, 27), (5, 10),)),
        WaypointPath(dest_map=216, points=((16, 14), (16, 15), (13, 15), (13, 20), (21, 23),)),
    ],
    166: [
        WaypointPath(dest_map=6, points=((16, 17), (16, 14), (18, 14), (18, 10), (15, 10), (15, 8), (16, 8), (16, 7), (18, 7), (18, 1), (12, 1), (12, 2), (10, 2), (12, 2), (12, 7), (10, 7), (10, 8), (9, 8), (9, 11), (12, 11), (12, 13), (10, 13), (10, 14), (9, 14), (9, 16), (1, 16), (1, 14), (2, 14), (2, 13), (4, 13), (4, 9), (1, 9), (1, 8), (2, 8), (2, 7), (4, 7), (4, 5), (3, 5), (3, 4),)),
    ],
    174: [
        WaypointPath(dest_map=245, points=((7, 11), (15, 9), (15, 8), (7, 8), (7, 7), (4, 7), (3, 7), (3, 5), (3, 2), (8, 2), (8, 0),)),
    ],
    178: [
        WaypointPath(dest_map=6, points=((8, 17), (8, 16), (11, 16), (11, 15), (16, 17), (16, 15), (15, 15), (18, 3), (18, 5), (15, 5), (1, 5), (11, 11), (11, 8), (10, 8), (11, 8), (11, 11),)),
    ],
    181: [
        WaypointPath(dest_map=236, points=((10, 17), (10, 9), (8, 9), (8, 1), (20, 1), (20, 0),)),
    ],
    186: [
        WaypointPath(dest_map=27, points=((7, 2), (-1, 2),)),
    ],
    188: [
        WaypointPath(dest_map=27, points=((2, 7), (2, 4), (2, 5), (2, 8),)),
    ],
    190: [
        WaypointPath(dest_map=29, points=((0, 4), (8, 4),)),
    ],
    193: [
        WaypointPath(dest_map=34, points=((4, 7), (4, 0),)),
    ],
    194: [
        WaypointPath(dest_map=198, points=((0, 8), (0, 9), (3, 9), (3, 13), (5, 13), (5, 14), (4, 14), (4, 13), (3, 13), (3, 15), (4, 15), (4, 16), (3, 16), (3, 11), (5, 11), (5, 8), (14, 8), (14, 14), (21, 14), (21, 16), (28, 16), (28, 11), (23, 11), (23, 7),)),
        WaypointPath(dest_map=34, points=((27, 7), (30, 7),)),
    ],
    198: [
        WaypointPath(dest_map=194, points=((23, 7), (23, 6), (22, 6), (22, 4), (22, 2), (23, 2), (23, 1), (7, 1), (7, 0), (6, 0), (6, 1), (7, 1), (7, 2), (3, 2), (3, 1), (2, 1), (2, 4), (1, 4), (1, 5), (2, 5), (2, 4), (4, 4), (4, 2), (7, 2), (7, 1), (20, 1), (20, 6), (17, 6), (17, 4), (9, 4), (9, 10), (5, 10), (5, 8), (1, 8), (1, 15), (11, 15), (11, 16), (20, 16), (20, 15), (23, 15),)),
    ],
    208: [
        WaypointPath(dest_map=208, points=((3, 15), (3, 14), (18, 14), (18, 9),)),
        WaypointPath(dest_map=212, points=((18, 9), (14, 9), (14, 11), (11, 11),)),
    ],
    210: [
        WaypointPath(dest_map=233, points=((9, 15), (9, 16), (20, 16), (9, 16), (9, 15),)),
        WaypointPath(dest_map=210, points=((9, 15), (9, 13), (8, 13),)),
        WaypointPath(dest_map=208, points=((8, 13), (6, 13), (6, 16), (3, 16), (3, 15),)),
    ],
    212: [
        WaypointPath(dest_map=235, points=((5, 3), (4, 3), (4, 2), (3, 2), (3, 5), (2, 5), (2, 6), (5, 6), (5, 7),)),
    ],
    214: [
        WaypointPath(dest_map=215, points=((5, 11), (10, 11), (10, 5), (6, 5), (6, 1),)),
    ],
    215: [
        WaypointPath(dest_map=165, points=((6, 2), (11, 2), (11, 6), (10, 6), (14, 6), (14, 11), (16, 11), (16, 14),)),
    ],
    216: [
        WaypointPath(dest_map=6, points=((23, 22), (23, 16), (23, 15), (17, 15), (17, 19), (18, 19), (18, 23), (17, 23), (17, 26), (18, 26), (14, 26), (14, 22), (12, 22), (12, 15), (24, 15), (24, 18), (26, 18), (26, 6), (24, 6), (24, 4), (20, 4), (24, 4), (24, 6), (12, 6), (12, 2), (11, 2), (12, 2), (12, 7), (4, 7), (4, 9), (2, 9), (5, 9), (5, 10), (5, 11), (5, 12),)),
    ],
    217: [
        WaypointPath(dest_map=218, points=((0, 23), (4, 23), (4, 24), (20, 24), (20, 20), (12, 20), (12, 22), (11, 22), (10, 22), (9, 22), (9, 8), (12, 8), (12, 6), (17, 6), (17, 8), (20, 8), (20, 3), (7, 3), (7, 5), (-1, 5),)),
    ],
    218: [
        WaypointPath(dest_map=219, points=((39, 31), (22, 31), (22, 22), (16, 22), (16, 28), (13, 28), (13, 9), (28, 9), (28, 3), (3, 3), (3, 36),)),
    ],
    219: [
        WaypointPath(dest_map=219, points=((21, 0), (21, 5), (19, 5), (19, 6),)),
        WaypointPath(dest_map=222, points=((19, 6), (19, 5), (7, 5), (7, 6), (3, 6), (3, 3),)),
    ],
    220: [
        WaypointPath(dest_map=217, points=((15, 25), (15, 16), (28, 16), (28, 11), (30, 11),)),
    ],
    222: [
        WaypointPath(dest_map=219, points=((2, 7), (2, 6), (3, 6), (3, 4), (3, 8),)),
    ],
    230: [
        WaypointPath(dest_map=3, points=((2, 7), (2, 0),)),
    ],
    232: [
        WaypointPath(dest_map=82, points=((33, 25), (33, 30), (27, 30), (27, 31), (14, 31), (14, 29), (17, 29), (17, 24), (25, 24), (25, 16), (37, 16), (37, 11), (37, 3), (27, 3),)),
    ],
    233: [
        WaypointPath(dest_map=210, points=((14, 1), (14, 3), (24, 3), (24, 16), (17, 16), (17, 15),)),
    ],
    234: [
        WaypointPath(dest_map=233, points=((12, 1), (12, 3), (4, 3), (4, 9), (6, 9), (6, 11), (6, 16), (3, 16), (3, 14), (3, 15), (1, 15), (1, 13), (1, 12), (1, 16), (3, 16), (6, 16), (6, 9), (4, 9), (4, 1), (8, 1), (8, 0),)),
    ],
    235: [
        WaypointPath(dest_map=235, points=((3, 2), (3, 14), (5, 14), (6, 14),)),
        WaypointPath(dest_map=6, points=((6, 14), (6, 13),)),
    ],
    236: [
        WaypointPath(dest_map=234, points=((1, 3), (1, 2), (3, 2), (3, 1), (2, 1), (2, 4),)),
    ],
    245: [
        WaypointPath(dest_map=246, points=((4, 5), (4, 2), (4, 0),)),
    ],
    246: [
        WaypointPath(dest_map=247, points=((4, 5), (4, 2), (4, 0),)),
    ],
    247: [
        WaypointPath(dest_map=113, points=((4, 5), (4, 2), (4, 1), (4, 0),)),
    ],
}
