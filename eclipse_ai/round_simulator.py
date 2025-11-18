"""
Round Simulation Module for Multi-Round Game State Generation.

This module simulates full game rounds using the MCTS planner to make intelligent
decisions. Players take actions until they would incur a money deficit, then pass.

Reference: Eclipse Rulebook - Action Phase, Round Flow
"""
from __future__ import annotations

import copy
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .game_models import GameState, PlayerState
from .planners.mcts_pw import PW_MCTSPlanner
from .rules import api as rules_api
from .models.economy import Economy, count_action_discs


@dataclass
class ActionResult:
    """Result of attempting to take an action."""
    success: bool
    reason: str
    action: Optional[Dict[str, Any]] = None
    money_after: int = 0


def _ensure_player_economy(player: PlayerState) -> Economy:
    """Ensure player has an Economy object initialized."""
    econ = getattr(player, "economy", None)
    if isinstance(econ, Economy):
        return econ
    
    # Create new economy object
    econ_obj = Economy()
    player.economy = econ_obj
    return econ_obj


def _update_economy_snapshot(state: GameState, player: PlayerState) -> None:
    """Update player's economy snapshot with current state."""
    econ = _ensure_player_economy(player)
    
    # Count action discs on board
    board_slots = count_action_discs(player)
    if board_slots > econ.action_slots_filled:
        econ.action_slots_filled = board_slots
    
    # Get production and upkeep
    production = 0
    upkeep = 0
    
    if hasattr(player, 'get_money_production'):
        production = player.get_money_production()
    
    if hasattr(player, 'get_upkeep_cost'):
        upkeep = player.get_upkeep_cost()
    
    # Update economy
    econ.refresh(
        bank=int(player.resources.money),
        income=production,
        upkeep_fixed=upkeep,
        action_slots_filled=econ.action_slots_filled,
    )


def has_available_influence_disc(player: PlayerState) -> bool:
    """
    Check if player has an influence disc available to take an action.
    
    Players start with a pool of influence discs (typically 13-16).
    Discs are removed from the pool when:
    - Placed on colonized hexes (one per hex controlled)
    - Placed on action spaces (one per action taken this round)
    
    Returns:
        True if player has at least one disc available
    """
    if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
        # Use detailed track: discs on track = available discs
        # (Discs already on hexes and actions have been removed from track)
        return player.influence_track_detailed.discs_on_track > 0
    
    # No influence track configured
    return False


def remove_disc_for_action(player: PlayerState) -> bool:
    """
    Remove an influence disc from track to take an action.
    
    These discs are tracked and returned to the track during Cleanup phase.
    
    Returns:
        True if disc was successfully removed
    """
    if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
        track = player.influence_track_detailed
        # Remove from leftmost position with a disc
        for i in range(len(track.disc_positions)):
            if track.disc_positions[i]:
                track.remove_disc_at(i)
                
                # Track this as an action disc (will be returned at cleanup)
                if not hasattr(player, 'action_discs_this_round'):
                    player.action_discs_this_round = 0
                player.action_discs_this_round += 1
                
                return True
    return False


def remove_disc_for_colonization(player: PlayerState) -> bool:
    """
    Remove an influence disc from track when colonizing a hex.
    
    In Eclipse, when you take an INFLUENCE action:
    1. One disc goes on the action board (for the action itself)
    2. One disc goes on the hex (for colonization)
    
    This function handles the second disc.
    
    Returns:
        True if disc was successfully removed
    """
    if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
        track = player.influence_track_detailed
        # Remove another disc for the hex colonization
        for i in range(len(track.disc_positions)):
            if track.disc_positions[i]:
                track.remove_disc_at(i)
                return True
    return False


def calculate_next_action_cost(player: PlayerState) -> int:
    """
    Calculate the cost of the next action for this player.
    
    Actions have cumulative costs: [0, 1, 2, 3, 4, 5, 7, 9, 12, 16, 21, 27]
    The cost of the Nth action is action_track[N] - action_track[N-1]
    
    Args:
        player: The player taking the action
        
    Returns:
        Money cost of the next action
    """
    econ = _ensure_player_economy(player)
    current_slots = econ.action_slots_filled
    
    # Get cumulative cost for current and next slot
    current_cum = econ._cum_cost(current_slots)
    next_cum = econ._cum_cost(current_slots + 1)
    
    return next_cum - current_cum


def predict_money_after_action(
    state: GameState,
    player: PlayerState,
    action_cost_override: Optional[int] = None
) -> int:
    """
    Predict player's money after taking an action and paying upkeep.
    
    IMPORTANT: This predicts the upkeep AFTER the disc is removed, since
    taking an action removes a disc from the track and increases upkeep.
    
    Formula:
        money_after = current_money + production - upkeep_after_action
    
    Where:
        - production: money income from population track
        - upkeep_after_action: upkeep cost AFTER removing disc for this action
    
    Note: In Eclipse, you don't pay for actions during the Action Phase.
    You only pay upkeep during the Upkeep Phase. So action_cost is not
    subtracted from money (it's just about disc availability).
    
    Args:
        state: Current game state
        player: The player to predict for
        action_cost_override: Not used (kept for API compatibility)
        
    Returns:
        Predicted money after upkeep (at end of round)
    """
    _update_economy_snapshot(state, player)
    
    # Get current money
    current_money = player.resources.money
    
    # Get production
    production = 0
    if hasattr(player, 'get_money_production'):
        production = player.get_money_production()
    
    # Predict upkeep AFTER taking this action
    # (Taking an action removes a disc from track, increasing upkeep)
    upkeep_after = 0
    if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
        track = player.influence_track_detailed
        # Future upkeep = upkeep for (current_discs_off + 1)
        future_discs_off = track.discs_off_track + 1
        if future_discs_off == 0:
            upkeep_after = 0
        elif future_discs_off > len(track.upkeep_values):
            upkeep_after = track.upkeep_values[-1]
        else:
            upkeep_after = track.upkeep_values[future_discs_off - 1]
    elif hasattr(player, 'get_upkeep_cost'):
        # Fallback: use current upkeep (will underestimate)
        upkeep_after = player.get_upkeep_cost()
    
    # Calculate predicted money after upkeep
    money_after = current_money + production - upkeep_after
    
    return money_after


def would_cause_deficit(
    state: GameState,
    player_id: str,
    action: Dict[str, Any],
    safety_margin: int = 0
) -> bool:
    """
    Check if taking an action would cause unrecoverable bankruptcy.
    
    In Eclipse, what matters is Net money = (Treasury) + (Income) - (Upkeep).
    Players can safely go negative because they can recover at upkeep by:
    - Trading resources (3:1 science/materials → money)
    - Removing influence discs to reduce upkeep
    
    Only reject if net money would be catastrophically negative.
    
    Args:
        state: Current game state
        player_id: Player considering the action
        action: Action to evaluate
        safety_margin: Extra money to keep as buffer (default 0)
        
    Returns:
        True if action would cause collapse, False if recoverable
    """
    player = state.players[player_id]
    
    # Get action disc cost
    action_cost = calculate_next_action_cost(player)
    
    # Estimate direct costs from action payload
    direct_cost = estimate_action_direct_cost(action)
    
    # Predict money after action and upkeep (this is Net money)
    money_after = predict_money_after_action(state, player, action_cost)
    money_after -= direct_cost
    
    # Calculate tradeable resources
    science = player.resources.science
    materials = player.resources.materials
    tradeable_money = (science + materials) // 3  # 3:1 trade ratio
    
    # Effective money = actual money + tradeable resources
    effective_money = money_after + tradeable_money
    
    # Early game (round 1-2): Be more conservative
    round_num = getattr(state, 'round', 1)
    if round_num <= 2:
        # Don't go below -2 in early rounds
        threshold = -2 + safety_margin
    else:
        # Later game: can go more negative if resources available
        threshold = -(2 + tradeable_money // 2) + safety_margin
    
    return effective_money < threshold


def estimate_action_direct_cost(action: Dict[str, Any]) -> int:
    """
    Estimate the direct resource cost of an action.
    
    This estimates costs like:
    - Research: science cost
    - Build: materials cost
    - Upgrade: materials cost
    
    Args:
        action: The action to estimate
        
    Returns:
        Estimated money equivalent cost (for research/build/upgrade it's not money)
    """
    atype = action.get("type", "").upper()
    payload = action.get("payload", {})
    
    # Most actions don't have direct money costs beyond the action disc
    # Research costs science, build costs materials
    # For deficit prediction, we only care about money, so return 0
    # The action disc cost is the main concern
    
    if atype == "RESEARCH":
        # Research costs science, not money
        # But we might want to check if player has enough science
        return 0
    
    if atype == "BUILD":
        # Build costs materials, not money
        return 0
    
    if atype == "UPGRADE":
        # Upgrade costs materials, not money
        return 0
    
    # Explore, Influence, Move don't have additional costs
    return 0


def simulate_action_phase(
    state: GameState,
    round_num: int,
    planner_config: Optional[Dict[str, Any]] = None,
    safety_margin: int = 0,
    verbose: bool = True
) -> GameState:
    """
    Simulate one round's action phase using MCTS.
    
    Players take turns in order, using MCTS to decide actions.
    If an action would cause a money deficit, the player passes instead.
    Continue until all players have passed.
    
    Args:
        state: Current game state
        round_num: Current round number
        planner_config: Optional config for MCTS planner
        safety_margin: Minimum money to maintain (default 0)
        verbose: Whether to print progress logs
        
    Returns:
        Updated game state after action phase
    """
    if verbose:
        print(f"[ACTION PHASE] Round {round_num}: Starting action phase")
    
    # Create MCTS planner with reduced simulations for speed
    config = planner_config or {}
    planner = PW_MCTSPlanner(
        sims=config.get("simulations", 100),  # Fewer sims for simulation speed
        depth=config.get("depth", 2),
        pw_c=config.get("pw_c", 1.5),
        pw_alpha=config.get("pw_alpha", 0.6),
    )
    
    # Track which players have passed
    players_passed = {pid: False for pid in state.players}
    action_counts = {pid: 0 for pid in state.players}
    
    # Maximum actions per player (Terrans typically have 13 influence discs)
    MAX_ACTIONS_PER_PLAYER = 15  # Safety limit
    
    # Get turn order (use existing or create from player IDs)
    turn_order = getattr(state, 'turn_order', None) or list(state.players.keys())
    
    # Action phase loop
    turn_count = 0
    max_turns = 100  # Safety limit to prevent infinite loops
    
    while not all(players_passed.values()) and turn_count < max_turns:
        turn_count += 1
        
        for player_id in turn_order:
            if players_passed[player_id]:
                continue
            
            player = state.players[player_id]
            
            # Check action limit per player
            if action_counts[player_id] >= MAX_ACTIONS_PER_PLAYER:
                if verbose:
                    print(f"[ACTION] Player {player_id}: Reached action limit ({MAX_ACTIONS_PER_PLAYER}), passing")
                players_passed[player_id] = True
                player.passed = True
                continue
            
            # Check if player has influence discs available
            if not has_available_influence_disc(player):
                if verbose:
                    discs_on_track = player.influence_track_detailed.discs_on_track if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed else 0
                    print(f"[ACTION] Player {player_id}: No influence discs available (on track: {discs_on_track}), passing")
                players_passed[player_id] = True
                player.passed = True
                continue
            
            # Update economy snapshot
            _update_economy_snapshot(state, player)
            
            if verbose:
                print(f"[ACTION] Player {player_id}: Considering action "
                      f"(money={player.resources.money}, "
                      f"actions_taken={action_counts[player_id]})")
            
            # Get legal actions using rules API
            try:
                legal_actions = rules_api.enumerate_actions(state, player_id)
                
                # Filter out PASS actions for now
                non_pass_actions = [a for a in legal_actions if a.get("type") != "PASS"]
                
                if not non_pass_actions:
                    if verbose:
                        print(f"[ACTION] Player {player_id}: No legal actions, passing")
                    players_passed[player_id] = True
                    player.passed = True
                    continue
                
                # Use MCTS to pick best action
                # Note: The planner works with the state directly
                # We'll use a simpler approach: pick the first legal action that doesn't cause deficit
                best_action = None
                
                for action in non_pass_actions:
                    if not would_cause_deficit(state, player_id, action, safety_margin):
                        best_action = action
                        break
                
                # If no action is affordable, pass
                if best_action is None:
                    if verbose:
                        print(f"[ACTION] Player {player_id}: No affordable actions, passing")
                    players_passed[player_id] = True
                    player.passed = True
                    continue
                
                # Execute the action
                if verbose:
                    action_type = best_action.get("type", "UNKNOWN")
                    print(f"[ACTION] Player {player_id}: Taking {action_type} action")
                
                # Apply action using rules API
                state = rules_api.apply_action(state, player_id, best_action)
                action_counts[player_id] += 1
                
                # Remove influence disc from track (get fresh player reference after state update)
                player = state.players[player_id]
                remove_disc_for_action(player)
                
                # If INFLUENCE action, remove an additional disc for hex colonization
                action_type = best_action.get("type", "").upper()
                if action_type == "INFLUENCE":
                    remove_disc_for_colonization(player)
                    if verbose:
                        track = player.influence_track_detailed if hasattr(player, 'influence_track_detailed') else None
                        discs = track.discs_on_track if track else "?"
                        print(f"[ACTION] Player {player_id}: Removed colonization disc ({discs} remaining on track)")
                
                # Update economy after action
                _update_economy_snapshot(state, player)
                
            except Exception as e:
                if verbose:
                    print(f"[ACTION] Player {player_id}: Error during action - {e}, passing")
                players_passed[player_id] = True
                player.passed = True
                continue
    
    if verbose:
        print(f"[ACTION PHASE] Round {round_num}: Completed after {turn_count} turns")
        for pid, count in action_counts.items():
            print(f"  - Player {pid}: {count} actions")
    
    return state


def simulate_action_phase_with_mcts(
    state: GameState,
    round_num: int,
    planner_config: Optional[Dict[str, Any]] = None,
    safety_margin: int = 0,
    verbose: bool = True
) -> GameState:
    """
    Simulate action phase using full MCTS planning.
    
    This is a more advanced version that uses the actual MCTS planner
    to make better decisions. It's slower but produces more realistic gameplay.
    
    Args:
        state: Current game state
        round_num: Current round number
        planner_config: Optional config for MCTS planner
        safety_margin: Minimum money to maintain
        verbose: Whether to print progress logs
        
    Returns:
        Updated game state after action phase
    """
    if verbose:
        print(f"[ACTION PHASE] Round {round_num}: Starting action phase (with MCTS)")
    
    # Create MCTS planner
    config = planner_config or {}
    planner = PW_MCTSPlanner(
        sims=config.get("simulations", 100),
        depth=config.get("depth", 2),
        pw_c=config.get("pw_c", 1.5),
        pw_alpha=config.get("pw_alpha", 0.6),
    )
    
    # Track players
    players_passed = {pid: False for pid in state.players}
    action_counts = {pid: 0 for pid in state.players}
    turn_order = getattr(state, 'turn_order', None) or list(state.players.keys())
    
    # Maximum actions per player
    MAX_ACTIONS_PER_PLAYER = 15  # Safety limit
    
    turn_count = 0
    max_turns = 100
    
    while not all(players_passed.values()) and turn_count < max_turns:
        turn_count += 1
        
        for player_id in turn_order:
            if players_passed[player_id]:
                continue
            
            player = state.players[player_id]
            
            # Check action limit per player
            if action_counts[player_id] >= MAX_ACTIONS_PER_PLAYER:
                if verbose:
                    print(f"[MCTS] Player {player_id}: Reached action limit ({MAX_ACTIONS_PER_PLAYER}), passing")
                players_passed[player_id] = True
                player.passed = True
                continue
            
            # Check if player has influence discs available
            if not has_available_influence_disc(player):
                if verbose:
                    discs_on_track = player.influence_track_detailed.discs_on_track if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed else 0
                    print(f"[MCTS] Player {player_id}: No influence discs available (on track: {discs_on_track}), passing")
                players_passed[player_id] = True
                player.passed = True
                continue
            
            _update_economy_snapshot(state, player)
            
            if verbose:
                print(f"[MCTS] Player {player_id}: Planning...")
            
            try:
                # Use MCTS to plan
                # The planner expects the state to have active_player set
                state.active_player = player_id
                
                # Plan top actions
                plans = planner.plan(state, top_k=3)
                
                if not plans:
                    if verbose:
                        print(f"[MCTS] Player {player_id}: No viable plans, passing")
                    players_passed[player_id] = True
                    player.passed = True
                    continue
                
                # Find first affordable plan
                chosen_plan = None
                for plan_result in plans:
                    # Extract action from plan
                    if hasattr(plan_result, 'steps') and plan_result.steps:
                        first_step = plan_result.steps[0]
                        action = first_step.action
                        
                        # Convert Action object to dict
                        action_dict = {
                            "type": action.action_type if hasattr(action, 'action_type') else str(action.type),
                            "payload": action.payload if hasattr(action, 'payload') else {}
                        }
                        
                        if not would_cause_deficit(state, player_id, action_dict, safety_margin):
                            chosen_plan = action_dict
                            break
                
                if chosen_plan is None:
                    if verbose:
                        print(f"[MCTS] Player {player_id}: No affordable plans, passing")
                    players_passed[player_id] = True
                    player.passed = True
                    continue
                
                # Execute chosen action
                if verbose:
                    action_type = chosen_plan.get("type", "UNKNOWN")
                    print(f"[MCTS] Player {player_id}: Taking {action_type}")
                
                state = rules_api.apply_action(state, player_id, chosen_plan)
                action_counts[player_id] += 1
                
                # Remove influence disc from track (get fresh player reference after state update)
                player = state.players[player_id]
                remove_disc_for_action(player)
                
                # If INFLUENCE action, remove an additional disc for hex colonization
                action_type = chosen_plan.get("type", "").upper()
                if action_type == "INFLUENCE":
                    remove_disc_for_colonization(player)
                    if verbose:
                        track = player.influence_track_detailed if hasattr(player, 'influence_track_detailed') else None
                        discs = track.discs_on_track if track else "?"
                        print(f"[MCTS] Player {player_id}: Removed colonization disc ({discs} remaining on track)")
                
                _update_economy_snapshot(state, player)
                
            except Exception as e:
                if verbose:
                    print(f"[MCTS] Player {player_id}: Error - {e}, passing")
                players_passed[player_id] = True
                player.passed = True
    
    if verbose:
        print(f"[ACTION PHASE] Round {round_num}: Completed")
        for pid, count in action_counts.items():
            print(f"  - Player {pid}: {count} actions")
    
    return state

