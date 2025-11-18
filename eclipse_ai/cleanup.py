"""
Cleanup Phase Implementation for Multi-Round Simulation.

This module implements the Cleanup Phase mechanics:
- Draw new technology tiles based on player count
- Return action discs to influence track
- Refresh colony ships
- Reset per-round flags

Reference: Eclipse Rulebook - Cleanup Phase
"""
from __future__ import annotations

from typing import Dict, List, Optional
import random

from .game_models import GameState, PlayerState


# Tech tiles drawn per player count during cleanup
# Reference: SETUP_GUIDE.md - Tech Tile Replenishment (Cleanup Phase)
TECH_TILES_PER_ROUND = {
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 9,
}


def draw_tech_tiles(state: GameState, count: int, verbose: bool = True) -> List[str]:
    """
    Draw new technology tiles from the deck.
    
    In a full implementation, this would draw from the tech deck.
    For simulation purposes, we mark that tiles were drawn.
    
    Args:
        state: Current game state
        count: Number of tiles to draw
        verbose: Whether to print details
        
    Returns:
        List of tech IDs drawn (or placeholders)
        
    Reference: Eclipse Rulebook - Cleanup Phase
    """
    if verbose:
        print(f"[CLEANUP] Drawing {count} new technology tiles")
    
    # In a full implementation, this would:
    # 1. Remove tiles from tech deck
    # 2. Add them to available tech display
    # 3. Handle deck reshuffling if needed
    
    # For now, return placeholder IDs
    drawn = [f"tech_{i}" for i in range(count)]
    
    # Update state's tech display if it exists
    if hasattr(state, 'available_techs') and state.available_techs is not None:
        # Add drawn tiles to display
        state.available_techs.extend(drawn)
    
    return drawn


def return_action_discs(player: PlayerState, verbose: bool = True) -> int:
    """
    Return action discs from action spaces to influence track.
    
    At cleanup, all discs used for actions return to the influence track,
    reducing upkeep for the next round. Colonization discs (on hexes) stay off.
    
    Args:
        player: Player whose discs to return
        verbose: Whether to print details
        
    Returns:
        Number of discs returned
        
    Reference: Eclipse Rulebook - Cleanup Phase
    """
    discs_returned = 0
    
    # Get count of action discs used this round
    action_discs = getattr(player, 'action_discs_this_round', 0)
    discs_returned = action_discs
    
    # Return discs to influence track (leftmost positions)
    if discs_returned > 0 and hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
        track = player.influence_track_detailed
        
        # Add discs back to leftmost empty positions
        # (This is the reverse of removal, maintaining track order)
        discs_added = 0
        for i in range(len(track.disc_positions)):
            if not track.disc_positions[i]:
                track.add_disc_at(i)
                discs_added += 1
                if discs_added >= discs_returned:
                    break
        
        if verbose:
            upkeep_before = track.get_upkeep()
            # Note: upkeep will be calculated in next round
            print(f"[CLEANUP] Player {player.player_id}: Returned {discs_returned} action discs (upkeep was {upkeep_before})")
    
    # Reset action disc counter for next round
    if hasattr(player, 'action_discs_this_round'):
        player.action_discs_this_round = 0
    
    return discs_returned


def refresh_colony_ships(player: PlayerState, verbose: bool = True) -> None:
    """
    Refresh colony ships (mark all as available for use).
    
    Colony ships that were used this round become available again.
    
    Args:
        player: Player whose colony ships to refresh
        verbose: Whether to print details
        
    Reference: Eclipse Rulebook - Cleanup Phase
    """
    if hasattr(player, 'colony_ships') and player.colony_ships:
        # Reset any "used this round" flags
        if hasattr(player.colony_ships, 'used_this_round'):
            player.colony_ships.used_this_round = 0
        
        if verbose:
            print(f"[CLEANUP] Player {player.player_id}: Refreshed colony ships")


def reset_player_flags(player: PlayerState) -> None:
    """
    Reset per-round flags for player.
    
    Clears:
    - Passed status
    - Per-round action flags
    
    Args:
        player: Player to reset
    """
    player.passed = False
    
    # Reset any other per-round flags
    if hasattr(player, 'actions_this_round'):
        player.actions_this_round = 0


def cleanup_phase(state: GameState, verbose: bool = True) -> GameState:
    """
    Execute the cleanup phase for one round.
    
    Steps:
    1. Draw new technology tiles based on player count
    2. Return all action discs to influence tracks
    3. Refresh colony ships
    4. Reset per-round player flags
    5. Increment round counter
    
    Args:
        state: Current game state
        verbose: Whether to print cleanup details
        
    Returns:
        Updated game state
        
    Reference: Eclipse Rulebook - Cleanup Phase
    """
    if verbose:
        print(f"[CLEANUP PHASE] Round {state.round}: Starting cleanup")
    
    # Step 1: Draw new tech tiles
    num_players = len(state.players)
    num_tiles = TECH_TILES_PER_ROUND.get(num_players, 7)
    
    drawn_tiles = draw_tech_tiles(state, num_tiles, verbose)
    
    # Step 2-4: Process each player
    total_discs_returned = 0
    
    for player_id, player in state.players.items():
        # Return action discs
        discs_returned = return_action_discs(player, verbose)
        total_discs_returned += discs_returned
        
        # Refresh colony ships
        refresh_colony_ships(player, verbose)
        
        # Reset flags
        reset_player_flags(player)
    
    if verbose:
        print(f"[CLEANUP PHASE] Round {state.round}: Completed")
        print(f"  - Drew {len(drawn_tiles)} tech tiles")
        print(f"  - Returned {total_discs_returned} action discs")
        print(f"  - Refreshed colony ships for {num_players} players")
    
    return state


def increment_round(state: GameState) -> GameState:
    """
    Increment the round counter and prepare for next round.
    
    Args:
        state: Current game state
        
    Returns:
        State with incremented round
    """
    state.round += 1
    
    # Reset turn order for new round
    if hasattr(state, 'turn_index'):
        state.turn_index = 0
    
    if hasattr(state, 'turn_order') and state.turn_order:
        state.active_player = state.turn_order[0]
    
    return state

