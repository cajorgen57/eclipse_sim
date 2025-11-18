"""
Multi-Round Runner for Eclipse Game Simulation.

This module integrates all phases to simulate complete game rounds:
- Action Phase (using MCTS planner)
- Combat Phase (battle resolution)
- Upkeep Phase (resource production and costs)
- Cleanup Phase (tech tiles, disc return, reset)

Reference: Eclipse Rulebook - Round Flow
"""
from __future__ import annotations

from typing import Dict, Optional, Any
import copy

from .game_models import GameState
from .round_simulator import simulate_action_phase
from .combat_phase import resolve_combat_phase
from .upkeep import apply_upkeep_all_players
from .cleanup import cleanup_phase, increment_round


def run_full_round(
    state: GameState,
    round_num: int,
    planner_config: Optional[Dict[str, Any]] = None,
    verbose: bool = True,
) -> GameState:
    """
    Run one complete round of Eclipse.
    
    Executes all four phases in order:
    1. Action Phase - Players take turns choosing actions
    2. Combat Phase - Resolve battles
    3. Upkeep Phase - Pay upkeep, produce resources
    4. Cleanup Phase - Draw tech tiles, return discs, reset
    
    Args:
        state: Current game state
        round_num: Current round number (for logging)
        planner_config: Optional configuration for MCTS planner
        verbose: Whether to print detailed progress
        
    Returns:
        Updated game state after all phases
        
    Reference: Eclipse Rulebook - Round Structure
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"[ROUND {round_num}] Starting round simulation")
        print(f"{'='*60}\n")
        
        # Log initial board state
        hex_count_before = len(state.map.hexes)
        print(f"[ROUND {round_num}] Board state: {hex_count_before} hexes")
    
    # Phase 1: Action Phase
    if verbose:
        print(f"[ROUND {round_num}] === ACTION PHASE ===")
    
    try:
        state = simulate_action_phase(
            state,
            round_num,
            planner_config=planner_config,
            safety_margin=0,
            verbose=verbose,
        )
        
        # Log board state after actions
        if verbose:
            hex_count_after = len(state.map.hexes)
            if hex_count_after > hex_count_before:
                print(f"[ROUND {round_num}] Exploration: +{hex_count_after - hex_count_before} hexes (now {hex_count_after} total)")
    except Exception as e:
        if verbose:
            print(f"[ROUND {round_num}] Action phase error: {e}")
            print(f"[ROUND {round_num}] Continuing to next phase...")
    
    # Phase 2: Combat Phase
    if verbose:
        print(f"\n[ROUND {round_num}] === COMBAT PHASE ===")
    
    try:
        battle_results = resolve_combat_phase(state, verbose=verbose)
        
        if verbose and battle_results:
            print(f"[ROUND {round_num}] Resolved {len(battle_results)} battle(s)")
    except Exception as e:
        if verbose:
            print(f"[ROUND {round_num}] Combat phase error: {e}")
            print(f"[ROUND {round_num}] Continuing to next phase...")
    
    # Phase 3: Upkeep Phase
    if verbose:
        print(f"\n[ROUND {round_num}] === UPKEEP PHASE ===")
    
    try:
        upkeep_results = apply_upkeep_all_players(state)
        
        if verbose:
            for player_id, result in upkeep_results.items():
                if result.get('collapsed'):
                    print(f"[ROUND {round_num}] Player {player_id} has collapsed!")
    except Exception as e:
        if verbose:
            print(f"[ROUND {round_num}] Upkeep phase error: {e}")
            print(f"[ROUND {round_num}] Continuing to next phase...")
    
    # Phase 4: Cleanup Phase
    if verbose:
        print(f"\n[ROUND {round_num}] === CLEANUP PHASE ===")
    
    try:
        state = cleanup_phase(state, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"[ROUND {round_num}] Cleanup phase error: {e}")
    
    if verbose:
        print(f"\n[ROUND {round_num}] Round complete")
        # Final board state summary
        hex_count_final = len(state.map.hexes)
        hexes_by_ring = {}
        for hex_obj in state.map.hexes.values():
            ring = hex_obj.ring
            hexes_by_ring[ring] = hexes_by_ring.get(ring, 0) + 1
        print(f"[ROUND {round_num}] Final board: {hex_count_final} hexes - Ring distribution: {dict(sorted(hexes_by_ring.items()))}")
        print(f"{'='*60}\n")
    
    return state


def simulate_rounds(
    state: GameState,
    start_round: int,
    end_round: int,
    planner_config: Optional[Dict[str, Any]] = None,
    verbose: bool = True,
) -> GameState:
    """
    Simulate multiple rounds from start to end.
    
    This is used when generating a game that starts at round > 1.
    Simulates all prior rounds to create a realistic game state.
    
    Args:
        state: Initial game state (typically round 1 setup)
        start_round: First round to simulate (usually 1)
        end_round: Last round to simulate (usually starting_round - 1)
        planner_config: Optional MCTS configuration
        verbose: Whether to print progress
        
    Returns:
        Game state after simulating all rounds
        
    Example:
        # To start a game at round 5, simulate rounds 1-4
        state = new_game(num_players=4, starting_round=5)
        # The new_game function will call:
        # state = simulate_rounds(state, 1, 4)
    """
    if verbose:
        print(f"\n{'#'*60}")
        print(f"[MULTI-ROUND SIMULATION] Simulating rounds {start_round} to {end_round}")
        print(f"{'#'*60}\n")
    
    # Ensure state is at the correct starting round
    state.round = start_round
    
    # Default planner config for simulation (faster than full planning)
    if planner_config is None:
        planner_config = {
            "simulations": 50,  # Fewer sims for speed
            "depth": 2,
            "pw_c": 1.5,
            "pw_alpha": 0.6,
        }
    
    # Simulate each round
    for round_num in range(start_round, end_round + 1):
        try:
            state = run_full_round(
                state,
                round_num,
                planner_config=planner_config,
                verbose=verbose,
            )
            
            # Increment round counter
            state = increment_round(state)
            
        except Exception as e:
            if verbose:
                print(f"[MULTI-ROUND] Error in round {round_num}: {e}")
                print(f"[MULTI-ROUND] Stopping simulation")
            break
    
    # Set final round number
    state.round = end_round + 1
    
    if verbose:
        print(f"\n{'#'*60}")
        print(f"[MULTI-ROUND SIMULATION] Completed - Final round: {state.round}")
        
        # Show final board state
        hex_count = len(state.map.hexes)
        hexes_by_ring = {}
        for hex_obj in state.map.hexes.values():
            ring = hex_obj.ring
            hexes_by_ring[ring] = hexes_by_ring.get(ring, 0) + 1
        print(f"[MULTI-ROUND SIMULATION] Final board state: {hex_count} hexes")
        print(f"[MULTI-ROUND SIMULATION] Ring distribution: {dict(sorted(hexes_by_ring.items()))}")
        
        # Count hexes with coordinates
        hexes_with_coords = sum(
            1 for h in state.map.hexes.values()
            if hasattr(h, 'axial_q') and hasattr(h, 'axial_r')
            and h.axial_q is not None and h.axial_r is not None
        )
        print(f"[MULTI-ROUND SIMULATION] Hexes with coordinates: {hexes_with_coords}/{hex_count}")
        
        print(f"{'#'*60}\n")
    
    return state


def get_round_summary(state: GameState) -> Dict[str, Any]:
    """
    Get a summary of the current game state.
    
    Useful for debugging and verifying simulation results.
    
    Args:
        state: Current game state
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        "round": state.round,
        "num_players": len(state.players),
        "players": {},
    }
    
    for player_id, player in state.players.items():
        player_summary = {
            "money": player.resources.money,
            "science": player.resources.science,
            "materials": player.resources.materials,
            "collapsed": player.collapsed,
            "hexes_controlled": 0,
        }
        
        # Count hexes where player has presence
        for hex_obj in state.map.hexes.values():
            pieces = hex_obj.pieces.get(player_id)
            if pieces and (pieces.discs > 0 or pieces.ships):
                player_summary["hexes_controlled"] += 1
        
        # Get production and upkeep
        if hasattr(player, 'get_money_production'):
            player_summary["money_production"] = player.get_money_production()
        
        if hasattr(player, 'get_upkeep_cost'):
            player_summary["upkeep_cost"] = player.get_upkeep_cost()
        
        if hasattr(player, 'get_net_money_change'):
            player_summary["net_money"] = player.get_net_money_change()
        
        summary["players"][player_id] = player_summary
    
    return summary

