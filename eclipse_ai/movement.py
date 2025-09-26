"""Movement utility helpers."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .game_models import GameState, Hex, PlayerState

_DEFAULT_MOVE_ACTIVATIONS = 3

# Movement connection categories recognised by the tactical layer.
LEGAL_CONNECTION_TYPES = {"wormhole", "warp", "wg", "jump"}


def max_ship_activations_per_action(player: Optional[PlayerState], is_reaction: bool = False) -> int:
    """Return the legal number of ship activations for a MOVE action.

    Shadows of the Rift factions from Ship Pack One may replace the default
    three activations with a stricter limit. Reactions remain capped at a single
    activation regardless of species modifiers.
    """
    if is_reaction:
        return 1
    if not player:
        return _DEFAULT_MOVE_ACTIVATIONS
    override = None
    try:
        override = player.move_overrides.get("move_ship_activations_per_action") if player.move_overrides else None
    except AttributeError:
        override = None
    if override is None:
        return _DEFAULT_MOVE_ACTIVATIONS
    try:
        return max(1, int(override))
    except (TypeError, ValueError):
        return _DEFAULT_MOVE_ACTIVATIONS


def classify_connection(state: GameState, player: Optional[PlayerState], src_id: str, dst_id: str) -> Optional[str]:
    """Classify the link between two hexes for movement validation.

    Returns one of ``"wormhole"``, ``"warp"``, ``"wg"`` (wormhole generator
    half-link), ``"jump"`` (adjacent without a wormhole) or ``None`` when no
    legal connection exists.
    """

    if not state or not getattr(state, "map", None):
        return None
    if not src_id or not dst_id:
        return None
    if src_id == dst_id:
        return "wormhole"

    map_state = state.map
    src_hex = map_state.hexes.get(src_id)
    dst_hex = map_state.hexes.get(dst_id)
    if src_hex is None or dst_hex is None:
        return None

    if _is_warp_connection(src_hex, dst_hex):
        return "warp"

    if _has_full_wormhole(map_state, src_id, dst_id):
        return "wormhole"

    player_has_wg = bool(getattr(player, "has_wormhole_generator", False))
    if player_has_wg and _has_half_wormhole_for_wg(map_state, src_id, dst_id):
        return "wg"

    if _is_neighbor(map_state, src_id, dst_id):
        return "jump"

    return None


def _is_neighbor(map_state: object, a: str, b: str) -> bool:
    try:
        hx_a = map_state.hexes.get(a)
        hx_b = map_state.hexes.get(b)
    except AttributeError:
        return False
    if hx_a is None or hx_b is None:
        return False
    neighbors_a = getattr(hx_a, "neighbors", {}) or {}
    neighbors_b = getattr(hx_b, "neighbors", {}) or {}
    return b in neighbors_a.values() or a in neighbors_b.values()


def _is_warp_connection(a: Hex, b: Hex) -> bool:
    return bool(getattr(a, "has_warp_portal", False) and getattr(b, "has_warp_portal", False))


def _has_full_wormhole(map_state: object, src_id: str, dst_id: str) -> bool:
    src = getattr(map_state, "hexes", {}).get(src_id)
    dst = getattr(map_state, "hexes", {}).get(dst_id)
    if src is None or dst is None:
        return False
    if not _is_neighbor(map_state, src_id, dst_id):
        return False
    src_edges = _edges_to_neighbor(src, dst_id)
    dst_edges = _edges_to_neighbor(dst, src_id)
    if not src_edges or not dst_edges:
        return False
    src_has = any(_has_wormhole(src, edge) for edge in src_edges)
    dst_has = any(_has_wormhole(dst, edge) for edge in dst_edges)
    return src_has and dst_has


def _has_half_wormhole_for_wg(map_state: object, src_id: str, dst_id: str) -> bool:
    src = getattr(map_state, "hexes", {}).get(src_id)
    dst = getattr(map_state, "hexes", {}).get(dst_id)
    if src is None or dst is None:
        return False
    if not _is_neighbor(map_state, src_id, dst_id):
        return False
    src_edges = _edges_to_neighbor(src, dst_id)
    dst_edges = _edges_to_neighbor(dst, src_id)
    src_has = any(_has_wormhole(src, edge) for edge in src_edges)
    dst_has = any(_has_wormhole(dst, edge) for edge in dst_edges)
    return src_has or dst_has


def _edges_to_neighbor(hex_obj: Hex, neighbor_id: str) -> Sequence[int]:
    neighbors = getattr(hex_obj, "neighbors", {}) or {}
    return [edge for edge, nid in neighbors.items() if nid == neighbor_id]


def _has_wormhole(hex_obj: Hex, edge: int) -> bool:
    wormholes: Iterable[int]
    if hasattr(hex_obj, "has_wormhole"):
        try:
            return bool(hex_obj.has_wormhole(edge))  # type: ignore[attr-defined]
        except Exception:
            pass
    wormholes = getattr(hex_obj, "wormholes", ()) or ()
    return edge in set(int(e) for e in wormholes)


__all__ = [
    "LEGAL_CONNECTION_TYPES",
    "classify_connection",
    "max_ship_activations_per_action",
]
