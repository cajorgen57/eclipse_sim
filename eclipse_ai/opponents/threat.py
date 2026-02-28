from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set, Tuple

from .types import TargetPrediction, ThreatMap


def _neighbors_of_sector(board: Any, sector: Any) -> List[Any]:
    neigh = getattr(sector, "neighbors", None)
    if neigh is None:
        return []
    if callable(neigh):
        try:
            return list(neigh())
        except Exception:
            return []
    if isinstance(neigh, (list, tuple, set)):
        return list(neigh)
    return []


def _sector_owner(sector: Any) -> int | None:
    return getattr(sector, "owner", None)


def _all_sectors(board: Any) -> List[Any]:
    sec = getattr(board, "sectors", None) or getattr(board, "hexes", None)
    if sec is None:
        return []
    if isinstance(sec, dict):
        return list(sec.values())
    return list(sec)


def _sector_id(sector: Any) -> Any:
    return getattr(sector, "id", id(sector))


def _sector_ship_count(sector: Any, player_id: int) -> int:
    """Count ships in a sector belonging to a player."""
    pieces = getattr(sector, "pieces", {})
    if isinstance(pieces, dict):
        p = pieces.get(player_id)
        if p:
            ships = getattr(p, "ships", {})
            count = sum(int(v) for v in ships.values())
            count += int(getattr(p, "starbase", 0))
            return count
    return 0


def _find_nearest_enemy_fleet(
    board: Any, my_sector: Any, opp_id: int, max_depth: int = 3
) -> Tuple[int, int]:
    """BFS to find nearest enemy fleet and its distance.

    Returns (distance, ship_count) of nearest enemy concentration.
    """
    start_id = _sector_id(my_sector)
    visited: Set[Any] = {start_id}
    queue: deque[Tuple[Any, int]] = deque()

    for n in _neighbors_of_sector(board, my_sector):
        nid = _sector_id(n)
        if nid not in visited:
            visited.add(nid)
            queue.append((n, 1))

    while queue:
        sector, dist = queue.popleft()
        if dist > max_depth:
            break

        ships = _sector_ship_count(sector, opp_id)
        if ships > 0:
            return dist, ships

        for n in _neighbors_of_sector(board, sector):
            nid = _sector_id(n)
            if nid not in visited:
                visited.add(nid)
                queue.append((n, dist + 1))

    return max_depth + 1, 0


def _proximity_factor(distance: int, mobility: float = 0.5) -> float:
    """Convert distance to a danger proximity factor.

    Accounts for opponent mobility: faster opponents are dangerous from farther away.
    """
    if distance <= 0:
        return 1.0
    base_decay = 0.7 ** distance
    mobility_boost = 1.0 + 0.5 * mobility
    return min(1.0, base_decay * mobility_boost)


def _hex_strategic_value(sector: Any) -> float:
    """Estimate the strategic value of a hex for targeting prediction."""
    value = 0.0
    ring = getattr(sector, "ring", 2)
    if ring == 1:
        value += 0.3
    elif ring == 0:
        value += 0.5

    planets = getattr(sector, "planets", [])
    value += 0.15 * len(planets)

    if getattr(sector, "monolith", False):
        value += 0.2

    return min(1.0, value)


def build_threat_map(board: Any, my_id: int, metrics_by_player: Dict[int, Any]) -> ThreatMap:
    """Build an improved threat map with distance-aware danger calculations.

    Improvements over baseline:
    - Uses actual hex distance instead of fixed proximity=1.0
    - Accounts for opponent mobility when computing threat projection
    - Considers fleet concentration near borders (not just adjacency)
    - Weights threat by strategic value of targeted hexes
    - Considers border pressure from opponent metrics
    """
    sectors = _all_sectors(board)
    my_borders: List[Any] = []

    for sector in sectors:
        if _sector_owner(sector) != my_id:
            continue
        neighbors = _neighbors_of_sector(board, sector)
        if any(_sector_owner(n) not in (None, my_id) for n in neighbors):
            my_borders.append(sector)

    danger_map: Dict[Any, Dict[int, float]] = {}
    danger_by_opponent: Dict[int, float] = {}
    predicted_targets: Dict[int, Dict[Any, float]] = {}

    opp_ids = set(metrics_by_player.keys())

    for sector in my_borders:
        sid = _sector_id(sector)
        danger_map[sid] = {}
        neighbors = _neighbors_of_sector(board, sector)

        adj_opps = {
            owner
            for n in neighbors
            if (owner := _sector_owner(n)) not in (None, my_id)
        }

        for opp in opp_ids:
            metrics = metrics_by_player.get(opp)
            if not metrics:
                continue

            opp_mobility = getattr(metrics, "mobility", 0.5)

            if opp in adj_opps:
                # Adjacent: highest threat. Check for ships nearby.
                dist, ship_count = _find_nearest_enemy_fleet(board, sector, opp, max_depth=2)
                proximity = _proximity_factor(dist, opp_mobility)

                fleet_factor = min(1.0, ship_count / 4.0) if ship_count > 0 else 0.3

                # Adjacent opponents are always at least proximity 1.0
                # (they own a neighboring sector, so they're right there)
                if dist > 2:
                    # No ships found nearby, but they own adjacent territory
                    # Use metrics-based threat estimation instead
                    proximity = 1.0

                danger = min(1.0, proximity * (
                    0.35 * metrics.fleet_power +
                    0.25 * metrics.aggression +
                    0.20 * fleet_factor +
                    0.10 * getattr(metrics, "border_pressure", 0.0) +
                    0.10 * getattr(metrics, "risk_tolerance", 0.3)
                ))
            else:
                # Not adjacent but might still be a threat if mobile
                dist, ship_count = _find_nearest_enemy_fleet(board, sector, opp, max_depth=3)
                if dist > 3 or ship_count == 0:
                    continue
                proximity = _proximity_factor(dist, opp_mobility)
                danger = min(0.6, proximity * (
                    0.4 * metrics.fleet_power +
                    0.3 * metrics.aggression +
                    0.3 * opp_mobility
                ))

            if danger > 0.05:
                strat_value = _hex_strategic_value(sector)
                target_priority = danger * (0.7 + 0.3 * strat_value)

                danger_map[sid][opp] = danger
                danger_by_opponent[opp] = max(danger_by_opponent.get(opp, 0.0), danger)
                predicted_targets.setdefault(opp, {})[sid] = target_priority

    norm_predictions: Dict[int, TargetPrediction] = {}
    for opp, raw in predicted_targets.items():
        mx = max(raw.values()) if raw else 1.0
        norm_predictions[opp] = TargetPrediction({sid: (v / mx if mx > 0 else 0.0) for sid, v in raw.items()})

    return ThreatMap(danger_map, danger_by_opponent, norm_predictions)
