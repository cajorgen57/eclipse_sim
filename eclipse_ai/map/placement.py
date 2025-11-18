"""Tile placement logic for Eclipse exploration.

Implements the wormhole-matching rules for placing exploration tiles,
including rotation validation and Wormhole Generator technology exceptions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from .coordinates import (
    axial_neighbors,
    direction_between_coords,
    effective_wormholes,
    opposite_edge,
)

if TYPE_CHECKING:
    from ..game_models import GameState, Hex


def has_player_presence(state: GameState, hex_id: str, player_id: str) -> bool:
    """Check if player has influence disc or unpinned ships in a hex.
    
    Args:
        state: Current game state
        hex_id: Hex identifier
        player_id: Player to check
    
    Returns:
        True if player has disc or ships in the hex
    """
    hex_obj = state.map.hexes.get(hex_id)
    if hex_obj is None:
        return False
    
    pieces = hex_obj.pieces.get(player_id)
    if pieces is None:
        return False
    
    # Check for influence disc
    if pieces.discs > 0:
        return True
    
    # Check for ships (TODO: add pinning check when combat logic is integrated)
    if pieces.ships:
        return True
    
    return False


def get_connection_hexes(state: GameState, target_q: int, target_r: int, player_id: str) -> List[Tuple[str, int]]:
    """Find hexes where player has presence that are adjacent to target.
    
    Args:
        state: Current game state
        target_q, target_r: Target coordinates to explore
        player_id: Player attempting to explore
    
    Returns:
        List of (hex_id, edge_from_hex) tuples where player can explore from
    """
    connections = []
    
    # Check all 6 potential neighbors
    neighbors = axial_neighbors(target_q, target_r)
    
    for edge_to_target, (neighbor_q, neighbor_r) in neighbors.items():
        # Find hex at this position
        for hex_id, hex_obj in state.map.hexes.items():
            if not hasattr(hex_obj, 'axial_q') or not hasattr(hex_obj, 'axial_r'):
                continue
            
            if hex_obj.axial_q == neighbor_q and hex_obj.axial_r == neighbor_r:
                # Check if player has presence
                if has_player_presence(state, hex_id, player_id):
                    # Edge from neighbor pointing to target
                    edge_from_hex = opposite_edge(edge_to_target)
                    connections.append((hex_id, edge_from_hex))
                break
    
    return connections


def check_wormhole_connection(
    tile_wormholes: List[int],
    tile_rotation: int,
    edge_from_tile: int,
    neighbor_hex: Hex,
    edge_from_neighbor: int,
    has_wormhole_generator: bool,
) -> bool:
    """Check if wormhole connection is valid between tile and neighbor.
    
    Args:
        tile_wormholes: Base wormhole edges for the tile being placed
        tile_rotation: Rotation (0-5) being tested
        edge_from_tile: Edge of tile facing the neighbor
        neighbor_hex: Existing neighbor hex
        edge_from_neighbor: Edge of neighbor facing the tile
        has_wormhole_generator: Whether player has Wormhole Generator tech
    
    Returns:
        True if connection is valid (full or half with tech)
    """
    # Get effective wormholes after rotation
    rotated_wormholes = effective_wormholes(tile_wormholes, tile_rotation)
    
    # Check if tile has wormhole on the connecting edge
    tile_has_wormhole = edge_from_tile in rotated_wormholes
    
    # Check if neighbor has wormhole on its connecting edge
    neighbor_wormholes = getattr(neighbor_hex, 'wormholes', [])
    neighbor_has_wormhole = edge_from_neighbor in neighbor_wormholes
    
    # Full match: both sides have wormholes
    if tile_has_wormhole and neighbor_has_wormhole:
        return True
    
    # Half match: only one side has wormhole (allowed with Wormhole Generator)
    if has_wormhole_generator and (tile_has_wormhole or neighbor_has_wormhole):
        return True
    
    return False


def find_valid_rotations(
    state: GameState,
    tile_wormholes: List[int],
    target_q: int,
    target_r: int,
    player_id: str,
) -> List[int]:
    """Find all valid rotations for placing a tile.
    
    A rotation is valid if it creates at least one wormhole connection
    to a hex where the player has presence.
    
    Args:
        state: Current game state
        tile_wormholes: Base wormhole edges for tile
        target_q, target_r: Target coordinates
        player_id: Player placing the tile
    
    Returns:
        List of valid rotation values (0-5)
    """
    # Check if player has Wormhole Generator tech
    player = state.players.get(player_id)
    has_wormhole_gen = False
    if player:
        has_wormhole_gen = getattr(player, 'has_wormhole_generator', False)
        if not has_wormhole_gen:
            # Check in known_techs
            has_wormhole_gen = 'wormhole_generator' in (player.known_techs or [])
    
    # Get hexes where player has presence adjacent to target
    connection_hexes = get_connection_hexes(state, target_q, target_r, player_id)
    
    if not connection_hexes:
        # No adjacent hexes with player presence
        return []
    
    valid_rotations = []
    
    # Try each rotation
    for rotation in range(6):
        has_valid_connection = False
        
        # Check connection to each neighbor where player has presence
        for hex_id, edge_from_neighbor in connection_hexes:
            neighbor_hex = state.map.hexes[hex_id]
            
            # Find which edge of the new tile faces this neighbor
            # The neighbor is at edge_from_neighbor from the target's perspective
            # So the tile's edge facing the neighbor is the opposite
            edge_from_tile = opposite_edge(edge_from_neighbor)
            
            # Check wormhole match
            if check_wormhole_connection(
                tile_wormholes,
                rotation,
                edge_from_tile,
                neighbor_hex,
                edge_from_neighbor,
                has_wormhole_gen,
            ):
                has_valid_connection = True
                break
        
        if has_valid_connection:
            valid_rotations.append(rotation)
    
    return valid_rotations


def can_place_tile(
    state: GameState,
    tile_wormholes: List[int],
    target_q: int,
    target_r: int,
    rotation: int,
    player_id: str,
) -> bool:
    """Check if a tile can be placed at target with given rotation.
    
    Args:
        state: Current game state
        tile_wormholes: Base wormhole edges for tile
        target_q, target_r: Target coordinates
        rotation: Rotation to test (0-5)
        player_id: Player placing the tile
    
    Returns:
        True if placement is valid
    """
    valid_rotations = find_valid_rotations(
        state, tile_wormholes, target_q, target_r, player_id
    )
    return rotation in valid_rotations


def place_explored_tile(
    state: GameState,
    tile_id: str,
    tile_wormholes: List[int],
    target_q: int,
    target_r: int,
    rotation: int,
    discovery_slots: int = 0,
    ancients: int = 0,
    vp: int = 0,
    tile_number: int = 0,
) -> None:
    """Place an exploration tile on the map.
    
    This function:
    1. Creates a new Hex at the target coordinates
    2. Sets wormholes with the applied rotation
    3. Places discovery tile if applicable
    4. Places Ancient ships if applicable
    5. Updates neighbor connections
    
    Args:
        state: Game state to modify
        tile_id: Hex tile identifier
        tile_wormholes: Base wormhole edges
        target_q, target_r: Target coordinates
        rotation: Applied rotation (0-5)
        discovery_slots: Number of discovery slots on tile
        ancients: Number of Ancient ships
        vp: Victory points printed on tile
        tile_number: Combat ordering number
    """
    from ..game_models import Hex
    from .coordinates import ring_radius
    
    # Calculate ring
    ring = ring_radius(target_q, target_r)
    
    # Create effective wormholes after rotation
    rotated_wormholes = effective_wormholes(tile_wormholes, rotation)
    
    # Build neighbor links
    neighbors_dict = {}
    for edge, (neighbor_q, neighbor_r) in axial_neighbors(target_q, target_r).items():
        # Find hex at neighbor position
        for existing_hex_id, existing_hex in state.map.hexes.items():
            if (
                hasattr(existing_hex, 'axial_q') and
                hasattr(existing_hex, 'axial_r') and
                existing_hex.axial_q == neighbor_q and
                existing_hex.axial_r == neighbor_r
            ):
                neighbors_dict[edge] = existing_hex_id
                # Update neighbor's link back to this tile
                existing_hex.neighbors[opposite_edge(edge)] = tile_id
                break
    
    # Create the hex
    new_hex = Hex(
        id=tile_id,
        ring=ring,
        axial_q=target_q,
        axial_r=target_r,
        wormholes=rotated_wormholes,
        rotation=rotation,
        neighbors=neighbors_dict,
        explored=True,
        revealed=True,
        ancients=ancients,
        tile_number=tile_number,
    )
    
    # Place discovery tile if applicable
    if discovery_slots > 0:
        # Mark that a discovery tile should be drawn and placed
        new_hex.discovery_tile = "pending"
    
    # Add to map
    state.map.hexes[tile_id] = new_hex


__all__ = [
    "can_place_tile",
    "check_wormhole_connection",
    "find_valid_rotations",
    "get_connection_hexes",
    "has_player_presence",
    "place_explored_tile",
]

