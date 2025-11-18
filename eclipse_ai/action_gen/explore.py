"""Generate Explore actions for Eclipse.

Exploration allows players to place new hex tiles adjacent to hexes where
they have influence discs or ships, following wormhole connectivity rules.
"""
from typing import List, Set, Tuple

from .schema import MacroAction
from ..map.coordinates import (
    axial_neighbors,
    ring_radius,
    sector_for_ring,
)
from ..map.placement import get_connection_hexes


def generate(state) -> List[MacroAction]:
    """Generate all legal Explore actions for the active player.
    
    Args:
        state: Current game state
    
    Returns:
        List of Explore macro actions
    """
    player_id = state.active_player
    player = state.players.get(player_id)
    
    if not player or player.passed:
        return []
    
    # Check if player has passed
    if getattr(player, 'passed', False):
        return []
    
    actions = []
    
    # Find all positions where player could explore
    explore_targets = _find_explore_targets(state, player_id)
    
    for target_q, target_r in explore_targets:
        ring = ring_radius(target_q, target_r)
        sector = sector_for_ring(ring)
        
        # Check if there are tiles available in this sector
        bag_key = f"R{ring}"
        if bag_key in state.bags:
            tile_count = state.bags[bag_key].get("unknown", 0)
            if tile_count > 0:
                # Create explore action
                action = MacroAction(
                    type="EXPLORE",
                    payload={
                        "player_id": player_id,
                        "target_coords": (target_q, target_r),
                        "target_q": target_q,
                        "target_r": target_r,
                        "sector": sector,
                        "ring": ring,
                        "description": f"Explore ring {ring} at ({target_q}, {target_r})",
                    },
                )
                actions.append(action)
    
    return actions


def _find_explore_targets(state, player_id: str) -> Set[Tuple[int, int]]:
    """Find all unexplored positions adjacent to player's presence.
    
    Args:
        state: Game state
        player_id: Player ID
    
    Returns:
        Set of (q, r) coordinates where player can explore
    """
    targets = set()
    
    # Get all hexes where player has presence
    player_hexes = []
    for hex_id, hex_obj in state.map.hexes.items():
        if not hasattr(hex_obj, 'axial_q') or not hasattr(hex_obj, 'axial_r'):
            continue
        
        # Check if player has influence disc or ships
        pieces = hex_obj.pieces.get(player_id)
        if pieces:
            has_presence = False
            if pieces.discs > 0:
                has_presence = True
            if pieces.ships:
                has_presence = True
            
            if has_presence:
                player_hexes.append((hex_obj.axial_q, hex_obj.axial_r))
    
    # Find all adjacent unexplored positions
    for q, r in player_hexes:
        neighbors = axial_neighbors(q, r)
        for edge, (neighbor_q, neighbor_r) in neighbors.items():
            # Check if this position is already explored
            is_explored = False
            for hex_obj in state.map.hexes.values():
                if (
                    hasattr(hex_obj, 'axial_q') and
                    hasattr(hex_obj, 'axial_r') and
                    hex_obj.axial_q == neighbor_q and
                    hex_obj.axial_r == neighbor_r
                ):
                    is_explored = True
                    break
            
            if not is_explored:
                targets.add((neighbor_q, neighbor_r))
    
    return targets


__all__ = ["generate"]
