"""Adjacency and pinning helpers shared across rules modules."""
from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, Optional, Sequence, Set, Tuple

from .alliances import are_allied
from .game_models import Hex, MapState
from .movement import LEGAL_CONNECTION_TYPES, classify_connection


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


def compute_connectivity(state: object, pid: str, *, include_jump: bool = True) -> Set[str]:
    """Return the set of hex ids reachable for ``pid`` using MOVE legality."""

    if not state or not pid:
        return set()
    map_state = getattr(state, "map", None)
    if map_state is None or not getattr(map_state, "hexes", None):
        return set()

    player = None
    players = getattr(state, "players", {}) or {}
    try:
        player = players.get(pid)
    except AttributeError:
        player = None

    allow_jump = False
    if include_jump and player is not None:
        try:
            designs = getattr(player, "ship_designs", {}) or {}
            allow_jump = any(getattr(design, "has_jump_drive", False) for design in designs.values())
        except AttributeError:
            allow_jump = False

    reachable: Set[str] = set()
    visited: Set[Tuple[str, bool]] = set()
    queue: deque[Tuple[str, bool]] = deque()

    for hex_id, hx in map_state.hexes.items():
        friendly, enemy = _presence_counts(state, hx, pid)
        has_disc = bool(getattr(hx, "owner", None) == pid)
        pieces_map = getattr(hx, "pieces", {}) or {}
        player_pieces = pieces_map.get(pid) if isinstance(pieces_map, dict) else None
        discs = int(getattr(player_pieces, "discs", 0) or 0)
        if discs > 0:
            has_disc = True
        ships_available = friendly > 0
        anchored = has_disc or ships_available
        if not anchored:
            continue
        reachable.add(hex_id)
        pinned = enemy > 0 and friendly <= enemy
        if pinned:
            continue
        state_key = (hex_id, False)
        if state_key not in visited:
            visited.add(state_key)
            queue.append(state_key)

    while queue:
        current_id, jump_used = queue.popleft()
        current_hex = map_state.hexes.get(current_id)
        if current_hex is None:
            continue
        if getattr(current_hex, "has_gcds", False):
            # You may end in the Galactic Center but cannot continue through it when GCDS active.
            continue
        for neighbor_id in (getattr(current_hex, "neighbors", {}) or {}).values():
            if not neighbor_id:
                continue
            neighbor_hex = map_state.hexes.get(neighbor_id)
            if neighbor_hex is None:
                continue
            if not getattr(neighbor_hex, "explored", True):
                continue
            connection = classify_connection(state, player, current_id, neighbor_id)
            if connection not in LEGAL_CONNECTION_TYPES:
                continue
            next_jump_used = jump_used
            if connection == "jump":
                if not allow_jump or jump_used:
                    continue
                next_jump_used = True

            reachable.add(neighbor_id)

            # Entering a contested hex ends movement for that activation.
            friendly_dst, enemy_dst = _presence_counts(state, neighbor_hex, pid)
            if enemy_dst > 0 and friendly_dst <= enemy_dst:
                continue

            state_key = (neighbor_id, next_jump_used)
            if state_key in visited:
                continue
            visited.add(state_key)
            queue.append(state_key)

    return reachable


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


def _presence_counts(state: object, hex_obj: Optional[Hex], pid: str) -> Tuple[int, int]:
    if not hex_obj:
        return (0, 0)
    try:
        from .alliances import ship_presence

        return ship_presence(state, hex_obj, pid)
    except Exception:
        friendly = 0
        enemy = int(getattr(hex_obj, "ancients", 0) or 0)
        pieces_map = getattr(hex_obj, "pieces", None)
        if isinstance(pieces_map, dict):
            for owner, pieces in pieces_map.items():
                strength = _pieces_ship_strength(pieces)
                if owner == pid:
                    friendly += strength
                else:
                    enemy += strength
        else:
            ships_map = getattr(hex_obj, "ships", None)
            if isinstance(ships_map, dict):
                for owner, count in ships_map.items():
                    strength = int(count or 0)
                    if owner == pid:
                        friendly += strength
                    else:
                        enemy += strength
        return (friendly, enemy)


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
    "compute_connectivity",
    "is_deep_warp_portal",
    "is_pinned",
    "is_warp_nexus",
    "is_warp_portal",
    "valid_edge",
]

