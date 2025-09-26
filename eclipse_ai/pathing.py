"""Adjacency and pinning helpers shared across rules modules."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence, Set

from .alliances import are_allied
from .game_models import Hex, MapState


def valid_edge(
    map_state: Optional[MapState],
    src_id: str,
    dst_id: str,
    *,
    feature_flags: Optional[Dict[str, bool]] = None,
    player_has_wormhole_generator: bool = False,
) -> bool:
    """Return ``True`` when movement between the hexes is permitted."""

    if not map_state or not map_state.hexes:
        return False
    if not src_id or not dst_id:
        return False
    if src_id == dst_id:
        return True

    flags = dict(feature_flags or {})
    src_hex = map_state.hexes.get(src_id)
    dst_hex = map_state.hexes.get(dst_id)
    if src_hex is None or dst_hex is None:
        return False

    if _is_portal_link(src_hex, dst_hex, flags):
        return True
    if _is_deep_warp_link(src_hex, dst_hex, flags):
        return True

    src_edges = _edges_to_neighbor(src_hex, dst_id)
    if not src_edges:
        return False
    dst_edges = _edges_to_neighbor(dst_hex, src_id)
    if not dst_edges:
        return False

    src_has = any(_has_wormhole(src_hex, edge) for edge in src_edges)
    dst_has = any(_has_wormhole(dst_hex, edge) for edge in dst_edges)

    if src_has and dst_has:
        return True
    if player_has_wormhole_generator and (src_has or dst_has):
        return True
    return False


def is_pinned(
    hex_obj: Optional[Hex],
    owner_id: str,
    *,
    state: Optional[object] = None,
    allies: Optional[Iterable[str]] = None,
) -> bool:
    """Return ``True`` if the ships owned by ``owner_id`` cannot move out."""

    if hex_obj is None or not owner_id:
        return False

    friendly_ids: Set[str] = {owner_id}
    if allies:
        friendly_ids.update(str(a) for a in allies)

    friendly_strength = 0
    enemy_strength = int(getattr(hex_obj, "ancients", 0) or 0)

    pieces_map = getattr(hex_obj, "pieces", None)
    if isinstance(pieces_map, dict) and pieces_map:
        for pid, pieces in pieces_map.items():
            strength = _pieces_ship_strength(pieces)
            if strength <= 0:
                continue
            if pid in friendly_ids or _are_allied(state, pid, owner_id):
                friendly_strength += strength
            else:
                enemy_strength += strength
    else:
        ships_map = getattr(hex_obj, "ships", None)
        if isinstance(ships_map, dict):
            for pid, count in ships_map.items():
                strength = int(count or 0)
                if strength <= 0:
                    continue
                if pid in friendly_ids or _are_allied(state, pid, owner_id):
                    friendly_strength += strength
                else:
                    enemy_strength += strength
        starbase_count = int(getattr(hex_obj, "starbase", 0) or 0)
        if starbase_count > 0:
            if owner_id in friendly_ids:
                friendly_strength += starbase_count
            else:
                enemy_strength += starbase_count

    if friendly_strength <= 0:
        return False
    if enemy_strength <= 0:
        return False
    return enemy_strength >= friendly_strength


def is_warp_portal(hex_obj: Optional[Hex]) -> bool:
    if not hex_obj:
        return False
    if getattr(hex_obj, "has_warp_portal", False):
        return True
    return bool(getattr(hex_obj, "warp_portal", False))


def is_deep_warp_portal(hex_obj: Optional[Hex]) -> bool:
    if not hex_obj:
        return False
    if getattr(hex_obj, "has_deep_warp_portal", False):
        return True
    symbols: Sequence[str] = getattr(hex_obj, "symbols", ()) or ()
    return any(str(sym).lower() in {"deep_warp", "deep"} for sym in symbols)


def is_warp_nexus(hex_obj: Optional[Hex]) -> bool:
    if not hex_obj:
        return False
    if getattr(hex_obj, "is_warp_nexus", False):
        return True
    return bool(getattr(hex_obj, "warp_nexus", False))


def _edges_to_neighbor(hex_obj: Hex, neighbor_id: str) -> Sequence[int]:
    neighbors = getattr(hex_obj, "neighbors", {}) or {}
    return [edge for edge, nid in neighbors.items() if nid == neighbor_id]


def _has_wormhole(hex_obj: Hex, edge: int) -> bool:
    if hasattr(hex_obj, "has_wormhole"):
        try:
            return bool(hex_obj.has_wormhole(edge))  # type: ignore[attr-defined]
        except TypeError:
            pass
    wormholes = getattr(hex_obj, "wormholes", ()) or ()
    return edge in set(int(e) for e in wormholes)


def _is_portal_link(a: Hex, b: Hex, flags: Dict[str, bool]) -> bool:
    if not flags.get("warp_portals") and not flags.get("rotA"):
        return False
    return is_warp_portal(a) and is_warp_portal(b)


def _is_deep_warp_link(a: Hex, b: Hex, flags: Dict[str, bool]) -> bool:
    if not flags.get("sotR") and not flags.get("deep_warp"):
        return False
    if is_warp_nexus(a) and is_deep_warp_portal(b):
        return True
    if is_warp_nexus(b) and is_deep_warp_portal(a):
        return True
    return False


def _pieces_ship_strength(pieces: object) -> int:
    strength = 0
    ships = getattr(pieces, "ships", None)
    if isinstance(ships, dict):
        strength += sum(int(v or 0) for v in ships.values())
    strength += int(getattr(pieces, "starbase", 0) or 0)
    return strength


def _are_allied(state: Optional[object], a_id: str, b_id: str) -> bool:
    try:
        if state is None:
            return False
        return are_allied(state, a_id, b_id)
    except Exception:
        return False


__all__ = [
    "is_deep_warp_portal",
    "is_pinned",
    "is_warp_nexus",
    "is_warp_portal",
    "valid_edge",
]

