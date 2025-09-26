from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .map.hex import Hex, MapGraph, rotated_wormholes
from .map.decks import ExplorationDecks, HexTile, DiscoveryTile, ResourcePool


@dataclass
class PlayerExploreState:
    player_id: str
    resources: ResourcePool = field(default_factory=ResourcePool)
    has_wormhole_generator: bool = False
    influence_discs: int = 0
    discovery_vp: int = 0
    kept_discoveries: list[str] = field(default_factory=list)
    ancient_tech: int = 0
    ancient_cruisers: int = 0
    ancient_parts: int = 0
    turn_ended: bool = False
    colony_ships: Dict[str, int] = field(default_factory=lambda: {"yellow": 0, "blue": 0, "brown": 0, "wild": 0})


@dataclass
class ExploreState:
    map: MapGraph
    decks: ExplorationDecks
    players: Dict[str, PlayerExploreState]
    feature_flags: Dict[str, bool] = field(default_factory=dict)

    def end_turn(self, player_id: str) -> None:
        self.players[player_id].turn_ended = True


def choose_explore_target(state: ExploreState, player_id: str, target: str) -> None:
    """Choose an unexplored space adjacent to a controlled hex or unpinned ship."""

    edges = state.map.connection_edges(target)
    if not edges:
        raise ValueError(f"No unexplored space recorded at {target}")
    player = state.players[player_id]
    ok = False
    for _, (neighbor_id, _) in edges.items():
        if neighbor_id not in state.map.hexes:
            continue
        neighbor = state.map.hexes[neighbor_id]
        if neighbor.owner == player_id or neighbor.ships.get(player_id, 0) > 0:
            ok = True
            break
    if not ok:
        raise ValueError("Explore target must touch a hex with your disc or unpinned ship")
    state.map.set_choice(player_id, target)


def draw_sector_tile(state: ExploreState, player_id: str, ring: int) -> HexTile:
    pos = state.map.explored_choice.get(player_id)
    if pos is None:
        raise ValueError("Player has not chosen an exploration target")
    deck = state.decks.get_sector(ring)
    return deck.draw()


def discard_sector_tile(state: ExploreState, player_id: str, tile: HexTile) -> None:
    deck = state.decks.get_sector(tile.ring)
    deck.discard(tile)
    state.map.clear_choice(player_id)
    state.end_turn(player_id)


def can_place(tile: HexTile, pos: str, orient: int, state: ExploreState, player_id: str) -> bool:
    assert pos == state.map.explored_choice[player_id]
    ok = has_full_connection_to_player(tile, orient, player_id, state)
    if not ok and state.players[player_id].has_wormhole_generator:
        ok = has_half_connection_to_player(tile, orient, player_id, state)
    return ok


def place_tile(state: ExploreState, player_id: str, tile: HexTile, orient: int) -> Hex:
    if not 0 <= orient < 6:
        raise ValueError("Orientation must be between 0 and 5")
    pos = state.map.explored_choice.get(player_id)
    if pos is None:
        raise ValueError("No exploration target recorded for player")
    if not can_place(tile, pos, orient, state, player_id):
        raise ValueError("Tile does not connect to a hex with your disc or ship")

    wormholes = rotated_wormholes(tile, orient)
    placed = Hex(
        id=pos,
        ring=tile.ring,
        wormholes=wormholes,
        symbols=tuple(tile.symbols),
        warp_portal=tile.warp_portal,
        gcds=tile.gcds,
    )
    pending = state.map.take_pending_edges(pos)
    for edge, (neighbor_id, neighbor_edge) in pending.items():
        placed.neighbors[edge] = neighbor_id
        if neighbor_id in state.map.hexes:
            neighbor = state.map.hexes[neighbor_id]
            neighbor.neighbors[neighbor_edge] = pos
    state.map.add_hex(placed)
    _spawn_discovery_and_ancients(state, placed)
    state.map.clear_choice(player_id)
    return placed


def _spawn_discovery_and_ancients(state: ExploreState, hex_obj: Hex) -> None:
    if "discovery" in hex_obj.symbols:
        tile = state.decks.discovery.draw()
        hex_obj.discovery_tile = tile
    ancients = sum(1 for symbol in hex_obj.symbols if symbol == "ancient")
    if ancients:
        hex_obj.ancients += ancients


def has_full_connection_to_player(tile: HexTile, orient: int, player_id: str, state: ExploreState) -> bool:
    pos = state.map.explored_choice[player_id]
    wormholes = set(tile.wormholes)
    edges = state.map.connection_edges(pos)
    for map_edge, (neighbor_id, neighbor_edge) in edges.items():
        tile_edge = (map_edge - orient) % 6
        if tile_edge not in wormholes:
            continue
        neighbor = state.map.hexes.get(neighbor_id)
        if not neighbor:
            continue
        if not neighbor.has_wormhole(neighbor_edge):
            continue
        if neighbor.has_presence(player_id):
            return True
    return False


def has_half_connection_to_player(tile: HexTile, orient: int, player_id: str, state: ExploreState) -> bool:
    pos = state.map.explored_choice[player_id]
    wormholes = set(tile.wormholes)
    edges = state.map.connection_edges(pos)
    for map_edge, (neighbor_id, _) in edges.items():
        tile_edge = (map_edge - orient) % 6
        if tile_edge not in wormholes:
            continue
        neighbor = state.map.hexes.get(neighbor_id)
        if not neighbor:
            continue
        if neighbor.has_presence(player_id):
            return True
    return False


def claim_discovery(state: ExploreState, player_id: str, hex_id: str, keep_vp: bool) -> Optional[DiscoveryTile]:
    hex_obj = state.map.hexes[hex_id]
    if hex_obj.owner != player_id:
        raise ValueError("You must control the hex to claim the discovery")
    if hex_obj.ancients > 0:
        raise ValueError("Ancients must be cleared before claiming the discovery")
    tile = hex_obj.discovery_tile
    if tile is None:
        raise ValueError("No discovery tile present")
    player = state.players[player_id]
    if keep_vp:
        player.discovery_vp += 2
        player.kept_discoveries.append(tile.id)
    else:
        tile.apply(player)
        state.decks.discovery.discard(tile)
    hex_obj.discovery_tile = None
    return tile
