"""Decision cache for LLM responses.

Persists LLM decisions to disk so identical game situations
don't require another API call. Uses bucketing to increase
cache hit rates (e.g., HP 73% and HP 78% both map to "high").
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict


@dataclass
class CachedDecision:
    """A cached LLM decision."""
    decision: str
    context: str           # Human-readable description of what was decided
    timestamp: float = 0
    hits: int = 0
    max_hits: int = 50     # Expire after this many uses

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


class DecisionCache:
    """Disk-persisted LLM decision cache with bucketing."""

    def __init__(self, cache_dir: str, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.cache: dict[str, CachedDecision] = {}
        self._stats = {"hits": 0, "misses": 0, "puts": 0}

        if enabled:
            os.makedirs(cache_dir, exist_ok=True)
            self._load()

    def _cache_file(self) -> str:
        return os.path.join(self.cache_dir, "decisions.json")

    def _load(self):
        path = self._cache_file()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    raw = json.load(f)
                for key, val in raw.items():
                    self.cache[key] = CachedDecision(**val)
            except (json.JSONDecodeError, TypeError):
                self.cache = {}

    def _save(self):
        if not self.enabled:
            return
        path = self._cache_file()
        raw = {k: asdict(v) for k, v in self.cache.items()}
        with open(path, "w") as f:
            json.dump(raw, f, indent=2)

    def get(self, key: str) -> str | None:
        """Look up a cached decision. Returns None on miss."""
        if not self.enabled:
            return None

        entry = self.cache.get(key)
        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.hits >= entry.max_hits:
            del self.cache[key]
            self._stats["misses"] += 1
            return None

        entry.hits += 1
        self._stats["hits"] += 1
        return entry.decision

    def put(self, key: str, decision: str, context: str = "", max_hits: int = 50):
        """Store a decision in the cache."""
        if not self.enabled:
            return

        self.cache[key] = CachedDecision(
            decision=decision,
            context=context,
            max_hits=max_hits,
        )
        self._stats["puts"] += 1
        self._save()

    @property
    def stats(self) -> dict:
        return {**self._stats, "size": len(self.cache)}

    def clear(self):
        self.cache.clear()
        self._save()


# ============================================================
# Bucketing functions for cache key generation
# ============================================================

def bucket_hp(current_hp: int, max_hp: int) -> str:
    """Bucket HP ratio into categories for cache keys."""
    if max_hp == 0:
        return "dead"
    ratio = current_hp / max_hp
    if ratio <= 0:
        return "dead"
    if ratio <= 0.25:
        return "critical"
    if ratio <= 0.50:
        return "low"
    if ratio <= 0.75:
        return "mid"
    return "high"


def bucket_level(level: int) -> str:
    """Bucket level into ranges."""
    if level <= 5:
        return "1-5"
    if level <= 10:
        return "6-10"
    if level <= 15:
        return "11-15"
    if level <= 20:
        return "16-20"
    if level <= 25:
        return "21-25"
    if level <= 30:
        return "26-30"
    if level <= 40:
        return "31-40"
    if level <= 50:
        return "41-50"
    return "51+"


def make_battle_cache_key(
    my_species: int,
    my_level: int,
    my_hp: int,
    my_max_hp: int,
    my_moves: list[int],
    enemy_species: int,
    enemy_level: int,
    enemy_hp_bucket: str,
) -> str:
    """Generate cache key for a battle decision."""
    parts = [
        f"battle",
        f"my:{my_species}",
        f"lv:{bucket_level(my_level)}",
        f"hp:{bucket_hp(my_hp, my_max_hp)}",
        f"moves:{','.join(str(m) for m in my_moves if m > 0)}",
        f"vs:{enemy_species}",
        f"elvl:{bucket_level(enemy_level)}",
        f"ehp:{enemy_hp_bucket}",
    ]
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def make_navigation_cache_key(
    map_id: int,
    badge_count: int,
    objective: str,
) -> str:
    """Generate cache key for a navigation decision."""
    raw = f"nav|map:{map_id}|badges:{badge_count}|obj:{objective}"
    return hashlib.md5(raw.encode()).hexdigest()


def make_strategy_cache_key(
    map_id: int,
    badge_count: int,
    party_species: list[int],
    party_avg_level: int,
) -> str:
    """Generate cache key for a strategic decision (what to do next)."""
    species_str = ",".join(str(s) for s in sorted(party_species))
    lvl_bucket = bucket_level(party_avg_level)
    raw = f"strategy|map:{map_id}|badges:{badge_count}|party:{species_str}|avg_lv:{lvl_bucket}"
    return hashlib.md5(raw.encode()).hexdigest()


def make_pathfinding_cache_key(
    map_id: int,
    player_x: int,
    player_y: int,
    target_type: str,  # "exit", "npc", "item", etc.
) -> str:
    """Generate cache key for a pathfinding decision."""
    # Bucket position into quadrants to improve cache hits
    quad_x = player_x // 4
    quad_y = player_y // 4
    raw = f"pathfind|map:{map_id}|pos:{quad_x},{quad_y}|target:{target_type}"
    return hashlib.md5(raw.encode()).hexdigest()
