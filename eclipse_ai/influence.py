from __future__ import annotations

from typing import Dict

from .explore import ExploreState
from .map.hex import MapGraph


def place_influence_disc(state: ExploreState, player_id: str, hex_id: str) -> None:
    hex_obj = state.map.hexes[hex_id]
    if hex_obj.ancients > 0:
        raise ValueError("Cannot take control while Ancients remain on the hex")
    if hex_obj.gcds:
        raise ValueError("Galactic Center Defense System must be destroyed before control")
    hex_obj.owner = player_id


def _flags(state_or_flags) -> Dict[str, bool]:
    if isinstance(state_or_flags, ExploreState):
        return state_or_flags.feature_flags
    return dict(state_or_flags or {})


def connection_allows_influence(map_state: MapGraph, a: str, b: str, *, feature_flags=None, player_has_wg: bool = False) -> bool:
    flags = _flags(feature_flags)
    if flags.get("warp_portals") and _both_have_portals(map_state, a, b):
        return True
    link = map_state.connection_type(a, b)
    if link == "full":
        return True
    if link == "half" and player_has_wg:
        return True
    return False


def connection_allows_diplomacy(map_state: MapGraph, a: str, b: str, *, feature_flags=None) -> bool:
    flags = _flags(feature_flags)
    if flags.get("warp_portals") and _both_have_portals(map_state, a, b):
        return True
    return map_state.connection_type(a, b) == "full"


def _both_have_portals(map_state: MapGraph, a: str, b: str) -> bool:
    hex_a = map_state.hexes.get(a)
    hex_b = map_state.hexes.get(b)
    if not hex_a or not hex_b:
        return False
    return bool(hex_a.warp_portal and hex_b.warp_portal)
