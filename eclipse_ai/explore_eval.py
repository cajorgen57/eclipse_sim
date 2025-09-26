"""Heuristic exploration evaluation shared across recommendation layers."""
from __future__ import annotations

import copy
from typing import Any, Iterable, Optional, Sequence, Set, Tuple

from .game_models import GameState, Hex as GameHex, Planet
from .pathing import compute_connectivity


def explore_ev(state: GameState, pid: str, tile: Any, pos: str, orient: int = 0) -> float:
    """Return a heuristic EV for placing ``tile`` at ``pos`` for ``pid``.

    The evaluation combines connectivity gain, new frontier reach, tile
    resources, portal utility, hostile exposure, and Ancient penalties. It is
    deliberately coarse but consistent between the action recommender and the
    global action scorer.
    """

    if state is None or not getattr(state, "map", None):
        return 0.0
    if pid not in (getattr(state, "players", {}) or {}):
        return 0.0

    base_reach = compute_connectivity(state, pid)
    base_frontier = _count_frontier_targets(state, base_reach)
    base_threat = _estimate_enemy_pressure(state, pid, base_reach)

    working = copy.deepcopy(state)
    new_hex = _coerce_hex(tile, pos, orient, working)
    _inject_virtual_hex(working, new_hex)

    post_reach = compute_connectivity(working, pid)
    post_frontier = _count_frontier_targets(working, post_reach)
    post_threat = _estimate_enemy_pressure(working, pid, post_reach)

    connectivity_gain = len(post_reach) - len(base_reach)
    frontier_gain = post_frontier - base_frontier
    resource_ev = _resource_value(new_hex, pid)
    portal_bonus = 1.0 if getattr(new_hex, "has_warp_portal", False) else 0.0
    ancient_penalty = -0.75 * int(getattr(new_hex, "ancients", 0) or 0)
    threat_delta = post_threat - base_threat

    # Larger weight on connectivity, moderate on frontier/resources, penalise
    # exposing discs to hostile reach.
    return (
        1.6 * connectivity_gain
        + 0.6 * frontier_gain
        + resource_ev
        + portal_bonus
        - 0.8 * threat_delta
        + ancient_penalty
    )


def _coerce_hex(tile: Any, pos: str, orient: int, state: GameState) -> GameHex:
    if isinstance(tile, GameHex):
        out = copy.deepcopy(tile)
        out.id = pos
        out.explored = True
        if not out.neighbors:
            out.neighbors = {}
        return out

    wormholes: Sequence[int] = tuple(getattr(tile, "wormholes", ()) or ())
    rotated = tuple(sorted((edge + orient) % 6 for edge in wormholes))

    symbols: Sequence[str] = tuple(getattr(tile, "symbols", ()) or ())
    planets: Iterable[Planet] = getattr(tile, "planets", ()) or ()
    planets_list = []
    for planet in planets:
        if isinstance(planet, Planet):
            planets_list.append(copy.deepcopy(planet))
        elif isinstance(planet, dict):
            planets_list.append(Planet(type=str(planet.get("type", "wild")), colonized_by=None))

    ancients = sum(1 for sym in symbols if str(sym).lower() == "ancient")

    out = GameHex(
        id=pos,
        ring=int(getattr(tile, "ring", getattr(state.map.hexes.get(pos, GameHex(id=pos, ring=0)).ring, 0)) or 0),
        wormholes=list(rotated),
        neighbors=dict(getattr(tile, "neighbors", {}) or {}),
        planets=list(planets_list),
        pieces={},
        ancients=ancients,
        monolith=any(str(sym).lower() == "monolith" for sym in symbols),
        orbital=any(str(sym).lower() == "orbital" for sym in symbols),
        anomaly=any(str(sym).lower() == "anomaly" for sym in symbols),
        explored=True,
        has_warp_portal=bool(getattr(tile, "warp_portal", False)),
        has_deep_warp_portal=bool(getattr(tile, "has_deep_warp_portal", False)),
        is_warp_nexus=bool(getattr(tile, "is_warp_nexus", False)),
        has_gcds=bool(getattr(tile, "gcds", False)),
    )
    return out


def _inject_virtual_hex(state: GameState, hex_obj: GameHex) -> None:
    state.map.hexes[hex_obj.id] = hex_obj
    for edge, neighbor_id in (hex_obj.neighbors or {}).items():
        if neighbor_id not in state.map.hexes:
            continue
        neighbor = state.map.hexes[neighbor_id]
        neighbor.neighbors.setdefault(_opposite_edge(edge), hex_obj.id)


def _opposite_edge(edge: int) -> int:
    return (edge + 3) % 6


def _count_frontier_targets(state: GameState, reachable: Set[str]) -> int:
    map_state = state.map
    frontier: Set[Tuple[str, int]] = set()
    for hex_id in reachable:
        hx = map_state.hexes.get(hex_id)
        if hx is None:
            continue
        for edge, neighbor_id in (hx.neighbors or {}).items():
            if not neighbor_id or neighbor_id in map_state.hexes:
                continue
            frontier.add((hex_id, edge))
    return len(frontier)


def _resource_value(hex_obj: GameHex, pid: str) -> float:
    total = 0.0
    if not getattr(hex_obj, "planets", None):
        return total
    weights = {"yellow": 0.45, "blue": 0.5, "brown": 0.55, "wild": 0.65}
    for planet in hex_obj.planets:
        planet_type = getattr(planet, "type", "wild")
        total += weights.get(str(planet_type).lower(), 0.4)
    return total


def _estimate_enemy_pressure(state: GameState, pid: str, reachable: Set[str]) -> float:
    pressure = 0.0
    for hex_id in reachable:
        hx = state.map.hexes.get(hex_id)
        if hx is None:
            continue
        for neighbor_id in (hx.neighbors or {}).values():
            if neighbor_id not in state.map.hexes:
                continue
            neighbor = state.map.hexes[neighbor_id]
            friendly, enemy = _presence_counts(state, neighbor, pid)
            if enemy > 0 and friendly <= enemy:
                pressure += enemy
    return pressure


def _presence_counts(state: GameState, hex_obj: Optional[GameHex], pid: str) -> Tuple[int, int]:
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
                ships = getattr(pieces, "ships", {}) or {}
                strength = sum(int(v or 0) for v in ships.values()) + int(getattr(pieces, "starbase", 0) or 0)
                if owner == pid:
                    friendly += strength
                else:
                    enemy += strength
        return (friendly, enemy)


__all__ = ["explore_ev"]
