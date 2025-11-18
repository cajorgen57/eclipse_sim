"""Connectivity helpers for wormhole and adjacency checks."""
from __future__ import annotations

from typing import Optional

from ..game_models import MapState, Hex
from .coordinates import axial_neighbors, opposite_edge


def is_neighbor(map_state: Optional[MapState], a: str, b: str) -> bool:
    """Return ``True`` when two hexes share an edge on the map."""
    if not map_state or not map_state.hexes:
        return False
    hx_a = map_state.hexes.get(a)
    hx_b = map_state.hexes.get(b)
    if hx_a is None or hx_b is None:
        return False
    if b in hx_a.neighbors.values():
        return True
    if a in hx_b.neighbors.values():
        return True
    
    # Also check via axial coordinates if available
    if hasattr(hx_a, 'axial_q') and hasattr(hx_a, 'axial_r'):
        if hasattr(hx_b, 'axial_q') and hasattr(hx_b, 'axial_r'):
            neighbors_of_a = axial_neighbors(hx_a.axial_q, hx_a.axial_r)
            for _, (q, r) in neighbors_of_a.items():
                if q == hx_b.axial_q and r == hx_b.axial_r:
                    return True
    
    return False


def has_full_wormhole(map_state: Optional[MapState], src_id: str, dst_id: str) -> bool:
    """Return ``True`` when both edges of an adjacency contain wormholes."""
    if not map_state or not map_state.hexes:
        return False
    if src_id == dst_id:
        return True
    src_hex = map_state.hexes.get(src_id)
    dst_hex = map_state.hexes.get(dst_id)
    if src_hex is None or dst_hex is None:
        return False
    if not is_neighbor(map_state, src_id, dst_id):
        return False
    src_edges = _edges_to_neighbor(src_hex, dst_id)
    if not src_edges:
        return False
    dst_edges = _edges_to_neighbor(dst_hex, src_id)
    if not dst_edges:
        return False
    return any(edge in src_hex.wormholes for edge in src_edges) and any(
        edge in dst_hex.wormholes for edge in dst_edges
    )


def _edges_to_neighbor(hex_obj: Hex, neighbor_id: str) -> list[int]:
    return [edge for edge, nid in hex_obj.neighbors.items() if nid == neighbor_id]


def has_half_wormhole(map_state: Optional[MapState], src_id: str, dst_id: str) -> bool:
    """Return ``True`` when either side of an adjacency has a wormhole."""
    if not map_state or not map_state.hexes:
        return False
    if src_id == dst_id:
        return True
    src_hex = map_state.hexes.get(src_id)
    dst_hex = map_state.hexes.get(dst_id)
    if src_hex is None or dst_hex is None:
        return False
    if not is_neighbor(map_state, src_id, dst_id):
        return False
    src_edges = _edges_to_neighbor(src_hex, dst_id)
    dst_edges = _edges_to_neighbor(dst_hex, src_id)
    has_src = any(edge in src_hex.wormholes for edge in src_edges)
    has_dst = any(edge in dst_hex.wormholes for edge in dst_edges)
    return has_src or has_dst


__all__ = ["is_neighbor", "has_full_wormhole", "has_half_wormhole"]
