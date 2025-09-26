from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .decks import HexTile, DiscoveryTile


def rotate_edge(edge: int, orient: int) -> int:
    return (edge + orient) % 6


def opposite_edge(edge: int) -> int:
    return (edge + 3) % 6


def rotated_wormholes(tile: HexTile, orient: int) -> Tuple[int, ...]:
    return tuple(sorted(rotate_edge(edge, orient) for edge in tile.wormholes))


@dataclass
class Hex:
    id: str
    ring: int
    wormholes: Tuple[int, ...]
    symbols: Tuple[str, ...] = tuple()
    warp_portal: bool = False
    gcds: bool = False
    neighbors: Dict[int, str] = field(default_factory=dict)
    owner: Optional[str] = None
    ships: Dict[str, int] = field(default_factory=dict)
    ancients: int = 0
    discovery_tile: Optional[DiscoveryTile] = None

    def has_wormhole(self, edge: int) -> bool:
        return edge in self.wormholes

    def has_presence(self, player_id: str) -> bool:
        return self.owner == player_id or self.ships.get(player_id, 0) > 0


@dataclass
class MapGraph:
    hexes: Dict[str, Hex] = field(default_factory=dict)
    explored_choice: Dict[str, str] = field(default_factory=dict)
    pending_edges: Dict[str, Dict[int, Tuple[str, int]]] = field(default_factory=dict)

    def add_hex(self, hex_obj: Hex) -> None:
        self.hexes[hex_obj.id] = hex_obj

    def register_exploration_target(self, *, origin: str, edge: int, target: str) -> None:
        origin_hex = self.hexes[origin]
        origin_hex.neighbors[edge] = target
        new_edge = opposite_edge(edge)
        self.pending_edges.setdefault(target, {})[new_edge] = (origin, edge)

    def set_choice(self, player_id: str, target: str) -> None:
        if target not in self.pending_edges:
            raise ValueError(f"No unexplored space recorded at {target}")
        self.explored_choice[player_id] = target

    def clear_choice(self, player_id: str) -> None:
        self.explored_choice.pop(player_id, None)

    def take_pending_edges(self, pos: str) -> Dict[int, Tuple[str, int]]:
        return self.pending_edges.pop(pos, {})

    def connection_edges(self, pos: str) -> Dict[int, Tuple[str, int]]:
        return dict(self.pending_edges.get(pos, {}))

    def neighbors(self, hex_id: str) -> Iterable[str]:
        hx = self.hexes[hex_id]
        for nb in hx.neighbors.values():
            if nb is None:
                continue
            if nb in self.hexes:
                yield nb

    def connection_type(self, a: str, b: str) -> str:
        if a == b:
            return "full"
        hex_a = self.hexes[a]
        hex_b = self.hexes[b]
        for edge, nb in hex_a.neighbors.items():
            if nb != b:
                continue
            opp = opposite_edge(edge)
            a_has = hex_a.has_wormhole(edge)
            b_has = hex_b.has_wormhole(opp)
            if a_has and b_has:
                return "full"
            if a_has or b_has:
                return "half"
        return "none"

    def ensure_neighbor_link(self, a: str, edge: int, b: str) -> None:
        self.hexes[a].neighbors[edge] = b
        self.hexes[b].neighbors[opposite_edge(edge)] = a


__all__ = [
    "Hex",
    "MapGraph",
    "rotate_edge",
    "opposite_edge",
    "rotated_wormholes",
]
