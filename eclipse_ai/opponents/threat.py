from __future__ import annotations

from typing import Any, Dict, List

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


def build_threat_map(board: Any, my_id: int, metrics_by_player: Dict[int, Any]) -> ThreatMap:
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

    for sector in my_borders:
        sid = _sector_id(sector)
        danger_map[sid] = {}
        neighbors = _neighbors_of_sector(board, sector)
        adj_opps = {
            owner
            for n in neighbors
            if (owner := _sector_owner(n)) not in (None, my_id)
        }
        for opp in adj_opps:
            metrics = metrics_by_player.get(opp)
            if not metrics:
                continue
            proximity = 1.0
            danger = min(1.0, proximity * (0.6 * metrics.fleet_power + 0.4 * metrics.aggression))
            danger_map[sid][opp] = danger
            danger_by_opponent[opp] = max(danger_by_opponent.get(opp, 0.0), danger)
            predicted_targets.setdefault(opp, {})[sid] = danger

    norm_predictions: Dict[int, TargetPrediction] = {}
    for opp, raw in predicted_targets.items():
        mx = max(raw.values()) if raw else 1.0
        norm_predictions[opp] = TargetPrediction({sid: (v / mx if mx > 0 else 0.0) for sid, v in raw.items()})

    return ThreatMap(danger_map, danger_by_opponent, norm_predictions)

