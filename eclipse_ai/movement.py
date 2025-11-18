"""Movement utility helpers."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .game_models import GameState, Hex, PlayerState, ShipDesign

_MOVE_ACTIVATIONS_DICT_BY_SPECIES = {
    "Terrans": 3,
    "Eridani Empire": 2,
    "Hydrans": 2,
    "Planta": 2,
    "Orion Hegemony": 2,
    "Descendants of Draco": 2,
    "Mechanema": 2,
    "Magellan": 2,
    "Rho Indi Syndicate": 4,
    "Wardens": 2,
    "Exiles": 2,
    "Enlightened of Lyra": 2
}

# Movement connection categories recognised by the tactical layer.
LEGAL_CONNECTION_TYPES = {"wormhole", "warp", "wg", "jump", "deep_warp"}


def max_ship_activations_per_action(player: Optional[PlayerState], is_reaction: bool = False) -> int:
    """Return the legal number of ship activations for a MOVE action.

    Shadows of the Rift factions from Ship Pack One may replace the default
    three activations with a stricter limit. Reactions remain capped at a single
    activation regardless of species modifiers.
    """
    if is_reaction:
        return 1
    if not player:
        return 3  # Default value for standard Eclipse rules
    override = None
    try:
        override = player.move_overrides.get("move_ship_activations_per_action") if player.move_overrides else None
    except AttributeError:
        override = None
    if override is None:
        species_id = getattr(player, "species_id", None)
        if species_id and species_id in _MOVE_ACTIVATIONS_DICT_BY_SPECIES:
            return _MOVE_ACTIVATIONS_DICT_BY_SPECIES[species_id]
        return 3  # Default fallback
    try:
        return max(1, int(override))
    except (TypeError, ValueError):
        species_id = getattr(player, "species_id", None)
        if species_id and species_id in _MOVE_ACTIVATIONS_DICT_BY_SPECIES:
            return _MOVE_ACTIVATIONS_DICT_BY_SPECIES[species_id]
        return 3  # Default fallback


def classify_connection(
    state: GameState,
    player: Optional[PlayerState],
    src_id: str,
    dst_id: str,
    *,
    ship_design: Optional[ShipDesign] = None,
    ship_class: Optional[str] = None,
) -> Optional[str]:
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

    if _is_warp_connection(src_hex, dst_hex) and _warp_network_enabled(state, player):
        return "warp"

    if _has_full_wormhole(map_state, src_id, dst_id):
        return "wormhole"

    player_has_wg = _player_has_wormhole_generator(player)
    if player_has_wg and _has_half_wormhole_for_wg(map_state, src_id, dst_id):
        return "wg"

    if _is_neighbor(map_state, src_id, dst_id):
        if _ship_has_jump_drive(player, ship_design, ship_class):
            return "jump"
        return None

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


def _player_has_wormhole_generator(player: Optional[PlayerState]) -> bool:
    if not player:
        return False
    if bool(getattr(player, "has_wormhole_generator", False)):
        return True
    known = set(str(t).lower() for t in getattr(player, "known_techs", []) or [])
    owned = set(str(t).lower() for t in getattr(player, "owned_tech_ids", []) or [])
    if "wormhole generator" in known or "wormhole_generator" in owned:
        return True
    return False


def _ship_has_jump_drive(
    player: Optional[PlayerState],
    design: Optional[ShipDesign],
    ship_class: Optional[str],
) -> bool:
    if design and getattr(design, "has_jump_drive", False):
        return True
    if not player:
        return False
    designs = getattr(player, "ship_designs", {}) or {}
    if ship_class:
        candidate = designs.get(ship_class)
        if candidate and getattr(candidate, "has_jump_drive", False):
            return True
    return any(getattr(d, "has_jump_drive", False) for d in designs.values())


def _warp_network_enabled(state: Optional[GameState], player: Optional[PlayerState]) -> bool:
    if state is None:
        return False
    flags = getattr(state, "feature_flags", {}) or {}
    if flags:
        for key in ("warp_portals", "rotA", "warp_network", "warp", "warp_portal_network"):
            if bool(flags.get(key)):
                return True
        # Explicit feature map provided without warp support -> disabled
        return False
    # Default to allowing warp if the player explicitly knows a warp tech
    if player:
        known = set(str(t).lower() for t in getattr(player, "known_techs", []) or [])
        if any("warp" in tech for tech in known):
            return True
    # No explicit feature flags: assume the standard warp network is active when portals exist
    return True


__all__ = [
    "LEGAL_CONNECTION_TYPES",
    "classify_connection",
    "max_ship_activations_per_action",
]
