"""Tests for the PokeBot waypoint database."""

from examples.pokemon_agent.pokebot_paths import (
    WAYPOINTS,
    WaypointPath,
    get_waypoint_path,
)


def test_waypoint_path_dataclass():
    """Construct a WaypointPath and verify its fields."""
    path = WaypointPath(dest_map=37, points=((3, 6), (5, 6), (7, 1)))
    assert path.dest_map == 37
    assert path.points == ((3, 6), (5, 6), (7, 1))
    # Frozen — should not allow mutation
    try:
        path.dest_map = 99
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_waypoints_dict_not_empty():
    """WAYPOINTS should have at least 50 map entries."""
    assert len(WAYPOINTS) >= 50, f"Only {len(WAYPOINTS)} map entries found"


def test_known_path_player_house_2f():
    """Map 38 (Player House 2F) should have a path leading to map 39."""
    paths = WAYPOINTS.get(38, [])
    dest_maps = {p.dest_map for p in paths}
    assert 39 in dest_maps, f"Map 38 dest_maps: {dest_maps}"


def test_known_path_pallet_to_route1():
    """Map 0 (Pallet Town) should have a path leading to map 12 (Route 1)."""
    paths = WAYPOINTS.get(0, [])
    dest_maps = {p.dest_map for p in paths}
    assert 12 in dest_maps, f"Map 0 dest_maps: {dest_maps}"


def test_all_points_are_tuples():
    """Every point in every path should be a 2-tuple of ints."""
    for map_id, paths in WAYPOINTS.items():
        for path in paths:
            for point in path.points:
                assert isinstance(point, tuple), (
                    f"map {map_id} dest {path.dest_map}: point {point} is {type(point)}"
                )
                assert len(point) == 2, (
                    f"map {map_id} dest {path.dest_map}: point {point} has {len(point)} elements"
                )
                assert isinstance(point[0], int) and isinstance(point[1], int), (
                    f"map {map_id} dest {path.dest_map}: point {point} has non-int elements"
                )


def test_get_waypoint_path_found():
    """Looking up (38, 39) should return a WaypointPath."""
    result = get_waypoint_path(38, 39)
    assert result is not None
    assert result.dest_map == 39
    assert len(result.points) >= 2


def test_get_waypoint_path_not_found():
    """Looking up a nonexistent (9999, 0) should return None."""
    result = get_waypoint_path(9999, 0)
    assert result is None


def test_no_empty_point_lists():
    """Every path should have at least 2 waypoints."""
    for map_id, paths in WAYPOINTS.items():
        for path in paths:
            assert len(path.points) >= 2, (
                f"map {map_id} dest {path.dest_map}: only {len(path.points)} points"
            )


def test_get_waypoint_path_with_player_pos():
    """Lookup with player_pos filters by Manhattan distance to first waypoint."""
    # Map 38 path starts at (3, 6)
    result = get_waypoint_path(38, 39, player_pos=(3, 6), max_start_distance=2)
    assert result is not None

    # Too far away — should return None
    result = get_waypoint_path(38, 39, player_pos=(20, 20), max_start_distance=2)
    assert result is None
