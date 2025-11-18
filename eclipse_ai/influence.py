from __future__ import annotations

from typing import Dict

from .explore import ExploreState
from .map.hex import MapGraph
from .pathing import valid_edge


def place_influence_disc(state: ExploreState, player_id: str, hex_id: str) -> None:
    hex_obj = state.map.hexes[hex_id]
    if hex_obj.ancients > 0:
        raise ValueError("Cannot take control while Ancients remain on the hex")
    if hex_obj.gcds:
        raise ValueError("Galactic Center Defense System must be destroyed before control")
    for owner, count in (hex_obj.ships or {}).items():
        if owner != player_id and int(count or 0) > 0:
            raise ValueError("Cannot Influence a hex containing enemy ships")
    hex_obj.owner = player_id


def _flags(state_or_flags) -> Dict[str, bool]:
    if isinstance(state_or_flags, ExploreState):
        return state_or_flags.feature_flags
    return dict(state_or_flags or {})


def connection_allows_influence(map_state: MapGraph, a: str, b: str, *, feature_flags=None, player_has_wg: bool = False) -> bool:
    flags = _flags(feature_flags)
    return valid_edge(
        map_state,
        a,
        b,
        feature_flags=flags,
        player_has_wormhole_generator=player_has_wg,
    )


def connection_allows_diplomacy(map_state: MapGraph, a: str, b: str, *, feature_flags=None) -> bool:
    flags = _flags(feature_flags)
    return valid_edge(map_state, a, b, feature_flags=flags)

