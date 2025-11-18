"""
Exploration Intelligence for Multi-Round Simulation.

This module implements intelligent exploration decisions:
- Whether to keep or discard explored tiles
- Where to place kept tiles for maximum benefit

Reference: Eclipse Rulebook - Exploration
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
import math

if TYPE_CHECKING:
    from .game_models import GameState, PlayerState, Hex

from .map.placement import find_valid_rotations, get_connection_hexes
from .map.coordinates import axial_distance, axial_neighbors


def should_keep_tile(
    state: GameState,
    player: PlayerState,
    tile: "Hex",
    source_hex_id: Optional[str] = None,
) -> bool:
    """
    Decide whether to keep an explored tile.
    
    Uses heuristics based on:
    - Number and type of planets
    - Ancient ship count
    - Wormhole connectivity
    - Strategic value
    
    Args:
        state: Current game state
        player: Player who explored the tile
        tile: The explored tile to evaluate
        source_hex_id: Hex from which exploration occurred
        
    Returns:
        True if tile should be kept, False if discarded
        
    Reference: Eclipse Rulebook - Exploration phase
    """
    # Count valuable planets
    planets = getattr(tile, 'planets', [])
    good_planets = sum(
        1 for p in planets
        if hasattr(p, 'type') and p.type in ['orange', 'pink', 'brown']
    )
    
    # Count ancients
    ancients = getattr(tile, 'ancients', 0)
    
    # Count wormholes
    wormholes = getattr(tile, 'wormholes', [])
    num_wormholes = len(wormholes) if isinstance(wormholes, list) else 0
    
    # Check for discovery tile
    has_discovery = getattr(tile, 'discovery_tile', None) is not None
    
    # Check for special features (monolith, etc.)
    has_monolith = getattr(tile, 'has_monolith', False)
    
    # Heuristic 1: Too many ancients without good resources
    if ancients >= 4 and good_planets == 0:
        return False
    
    # Heuristic 2: No resources and poor connectivity
    if good_planets == 0 and num_wormholes <= 1 and not has_monolith and not has_discovery:
        return False
    
    # Heuristic 3: Single ancient with no resources
    if ancients >= 2 and good_planets == 0 and num_wormholes <= 2:
        return False
    
    # Heuristic 4: Keep if good resources
    if good_planets >= 2:
        return True
    
    # Heuristic 5: Keep if good connectivity
    if num_wormholes >= 3:
        return True
    
    # Heuristic 6: Keep special tiles
    if has_monolith or has_discovery:
        return True
    
    # Heuristic 7: Keep if some resources and manageable ancients
    if good_planets >= 1 and ancients <= 2:
        return True
    
    # Default: keep (conservative approach)
    return True


def choose_placement_position(
    state: GameState,
    player_id: str,
    tile: "Hex",
    source_hex_id: str,
) -> Optional[Tuple[int, int, int]]:
    """
    Choose the best position to place an explored tile.
    
    Evaluates all legal positions and selects the one with highest score
    based on:
    - Wormhole connections to owned hexes
    - Distance from home sector
    - Resource value
    - Strategic position
    
    Args:
        state: Current game state
        player_id: Player placing the tile
        tile: The tile to place
        source_hex_id: Hex from which exploration occurred
        
    Returns:
        Tuple of (q, r, rotation) for best placement, or None if no valid placement
    """
    # Get source hex coordinates
    source_hex = state.map.hexes.get(source_hex_id)
    if source_hex is None:
        return None
    
    if not hasattr(source_hex, 'axial_q') or not hasattr(source_hex, 'axial_r'):
        return None
    
    # Find all adjacent positions to source
    neighbors = axial_neighbors(source_hex.axial_q, source_hex.axial_r)
    
    # Check each adjacent position
    best_score = -float('inf')
    best_placement = None
    
    tile_wormholes = getattr(tile, 'wormholes', [])
    
    for edge_to_target, (target_q, target_r) in neighbors.items():
        # Check if position is empty
        position_occupied = False
        for hex_obj in state.map.hexes.values():
            if (hasattr(hex_obj, 'axial_q') and hasattr(hex_obj, 'axial_r') and
                hex_obj.axial_q == target_q and hex_obj.axial_r == target_r):
                position_occupied = True
                break
        
        if position_occupied:
            continue
        
        # Find valid rotations for this position
        valid_rotations = find_valid_rotations(
            state, tile_wormholes, target_q, target_r, player_id
        )
        
        if not valid_rotations:
            continue
        
        # Score each valid rotation
        for rotation in valid_rotations:
            score = score_placement(
                state, player_id, (target_q, target_r), tile, rotation
            )
            
            if score > best_score:
                best_score = score
                best_placement = (target_q, target_r, rotation)
    
    return best_placement


def score_placement(
    state: GameState,
    player_id: str,
    position: Tuple[int, int],
    tile: "Hex",
    rotation: int,
) -> float:
    """
    Score a potential tile placement.
    
    Higher scores are better. Factors:
    - Number of wormhole connections to owned hexes (+10 per connection)
    - Resource value (+5 per good planet)
    - Distance from home (-0.5 per hex distance)
    - Number of ancients (-3 per ancient)
    - Wormhole count (+2 per wormhole for future expansion)
    
    Args:
        state: Current game state
        player_id: Player placing tile
        position: (q, r) coordinates
        tile: Tile being placed
        rotation: Rotation being tested
        
    Returns:
        Score value (higher is better)
    """
    score = 0.0
    
    q, r = position
    
    # Factor 1: Connections to owned hexes
    connections = get_connection_hexes(state, q, r, player_id)
    score += len(connections) * 10.0
    
    # Factor 2: Resource value
    planets = getattr(tile, 'planets', [])
    good_planets = sum(
        1 for p in planets
        if hasattr(p, 'type') and p.type in ['orange', 'pink', 'brown']
    )
    score += good_planets * 5.0
    
    # Factor 3: Distance from home
    player = state.players.get(player_id)
    if player:
        home_hex_id = getattr(player, 'home_hex_id', None)
        if home_hex_id:
            home_hex = state.map.hexes.get(home_hex_id)
            if home_hex and hasattr(home_hex, 'axial_q') and hasattr(home_hex, 'axial_r'):
                distance = axial_distance(q, r, home_hex.axial_q, home_hex.axial_r)
                score -= distance * 0.5
    
    # Factor 4: Ancient penalty
    ancients = getattr(tile, 'ancients', 0)
    score -= ancients * 3.0
    
    # Factor 5: Wormhole count (for future expansion)
    wormholes = getattr(tile, 'wormholes', [])
    num_wormholes = len(wormholes) if isinstance(wormholes, list) else 0
    score += num_wormholes * 2.0
    
    # Factor 6: Special tiles bonus
    if getattr(tile, 'has_monolith', False):
        score += 15.0
    
    if getattr(tile, 'discovery_tile', None):
        score += 8.0
    
    return score


def evaluate_exploration_opportunity(
    state: GameState,
    player_id: str,
    from_hex_id: str,
) -> float:
    """
    Evaluate the value of exploring from a given hex.
    
    Returns an estimated value for exploration action. Used to help
    the action simulator decide whether to explore.
    
    Args:
        state: Current game state
        player_id: Player considering exploration
        from_hex_id: Hex to explore from
        
    Returns:
        Estimated value (higher = better exploration opportunity)
    """
    # Base value for exploration
    base_value = 5.0
    
    # Check if player has explored much already
    player = state.players.get(player_id)
    if not player:
        return 0.0
    
    # Count player's current hexes
    player_hex_count = 0
    for hex_obj in state.map.hexes.values():
        pieces = hex_obj.pieces.get(player_id)
        if pieces and (pieces.discs > 0 or pieces.ships):
            player_hex_count += 1
    
    # Diminishing returns for exploration
    if player_hex_count >= 8:
        base_value *= 0.5
    elif player_hex_count >= 5:
        base_value *= 0.8
    
    # Bonus for exploring from edge hexes (more expansion potential)
    from_hex = state.map.hexes.get(from_hex_id)
    if from_hex:
        # Check how many unexplored neighbors
        if hasattr(from_hex, 'axial_q') and hasattr(from_hex, 'axial_r'):
            neighbors = axial_neighbors(from_hex.axial_q, from_hex.axial_r)
            unexplored_count = 0
            
            for _, (nq, nr) in neighbors.items():
                occupied = False
                for hex_obj in state.map.hexes.values():
                    if (hasattr(hex_obj, 'axial_q') and hasattr(hex_obj, 'axial_r') and
                        hex_obj.axial_q == nq and hex_obj.axial_r == nr):
                        occupied = True
                        break
                
                if not occupied:
                    unexplored_count += 1
            
            if unexplored_count >= 4:
                base_value *= 1.3
            elif unexplored_count >= 2:
                base_value *= 1.1
    
    return base_value


def select_best_exploration_hex(
    state: GameState,
    player_id: str,
) -> Optional[str]:
    """
    Select the best hex to explore from for a player.
    
    Args:
        state: Current game state
        player_id: Player who wants to explore
        
    Returns:
        Hex ID to explore from, or None if no good options
    """
    player = state.players.get(player_id)
    if not player:
        return None
    
    best_score = -float('inf')
    best_hex_id = None
    
    # Evaluate all hexes where player has presence
    for hex_id, hex_obj in state.map.hexes.items():
        pieces = hex_obj.pieces.get(player_id)
        if not pieces or (pieces.discs == 0 and not pieces.ships):
            continue
        
        # Check if hex has any unexplored neighbors
        if not hasattr(hex_obj, 'axial_q') or not hasattr(hex_obj, 'axial_r'):
            continue
        
        neighbors = axial_neighbors(hex_obj.axial_q, hex_obj.axial_r)
        has_unexplored = False
        
        for _, (nq, nr) in neighbors.items():
            occupied = False
            for other_hex in state.map.hexes.values():
                if (hasattr(other_hex, 'axial_q') and hasattr(other_hex, 'axial_r') and
                    other_hex.axial_q == nq and other_hex.axial_r == nr):
                    occupied = True
                    break
            
            if not occupied:
                has_unexplored = True
                break
        
        if not has_unexplored:
            continue
        
        # Evaluate this hex
        score = evaluate_exploration_opportunity(state, player_id, hex_id)
        
        if score > best_score:
            best_score = score
            best_hex_id = hex_id
    
    return best_hex_id

