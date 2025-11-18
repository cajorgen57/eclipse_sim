"""
Upkeep and Production Engine for Eclipse.

Implements the Upkeep Phase mechanics:
- Calculate resource production from population tracks
- Calculate influence upkeep cost
- Apply net money change (income - upkeep)
- Add science and materials production
- Handle bankruptcy (trading resources, removing discs)

Reference: Eclipse Rulebook - Upkeep Phase
"""
from typing import Dict, Tuple
from .game_models import GameState, PlayerState


def calculate_production(player: PlayerState) -> Dict[str, int]:
    """
    Calculate resource production from population tracks.
    
    Production is determined by the leftmost visible (no cube) square
    on each population track.
    
    Args:
        player: The player to calculate production for
        
    Returns:
        Dict with keys "money", "science", "materials" and production values
        
    Reference: Eclipse Rulebook - Upkeep Phase
    """
    return {
        "money": player.get_money_production(),
        "science": player.get_science_production(),
        "materials": player.get_materials_production(),
    }


def calculate_upkeep_cost(player: PlayerState) -> int:
    """
    Calculate influence upkeep cost.
    
    Upkeep cost is determined by the leftmost visible (no disc) circle
    on the influence track. Each disc off the track (on hexes or actions)
    increases the upkeep cost.
    
    Args:
        player: The player to calculate upkeep for
        
    Returns:
        Money cost to pay during upkeep
        
    Reference: Eclipse Rulebook - Upkeep Phase
    """
    return player.get_upkeep_cost()


def can_afford_upkeep(player: PlayerState, production: Dict[str, int], upkeep: int) -> bool:
    """
    Check if player can afford upkeep after production.
    
    Args:
        player: The player
        production: Production values from calculate_production()
        upkeep: Upkeep cost from calculate_upkeep_cost()
        
    Returns:
        True if player can afford upkeep, False if bankrupt
    """
    money_after = player.resources.money + production["money"] - upkeep
    return money_after >= 0


def trade_resources_to_money(player: PlayerState, money_needed: int) -> int:
    """
    Trade science and materials to money at 3:1 ratio.
    
    Trades as many resources as needed (and available) to reach the money goal.
    Science is traded first, then materials.
    
    Args:
        player: The player trading resources
        money_needed: How much money is needed
        
    Returns:
        Amount of money gained from trading
        
    Reference: Eclipse Rulebook - Upkeep Phase (Bankruptcy rules)
    """
    money_gained = 0
    
    # Trade science first (3:1 ratio)
    while money_gained < money_needed and player.resources.science >= 3:
        player.resources.science -= 3
        player.resources.money += 1
        money_gained += 1
    
    # Then trade materials (3:1 ratio)
    while money_gained < money_needed and player.resources.materials >= 3:
        player.resources.materials -= 3
        player.resources.money += 1
        money_gained += 1
    
    return money_gained


def remove_influence_discs_for_upkeep(
    state: GameState,
    player: PlayerState,
    money_needed: int
) -> Tuple[int, int]:
    """
    Remove influence discs from hexes to reduce upkeep cost.
    
    When a player cannot pay upkeep even after trading resources, they must
    remove influence discs from hexes. When a disc is removed, population
    cubes from that hex return to the tracks, reducing future production.
    
    Args:
        state: The game state
        player: The player removing discs
        money_needed: How much money reduction is needed
        
    Returns:
        Tuple of (discs_removed, money_saved)
        
    Reference: Eclipse Rulebook - Upkeep Phase (Bankruptcy rules)
    """
    discs_removed = 0
    money_saved = 0
    
    # Make a copy of discs list since we'll be modifying it
    hexes_to_remove = list(player.discs_on_hexes)
    
    for hex_id in hexes_to_remove:
        if money_saved >= money_needed:
            break
        
        # Remove disc from hex
        player.discs_on_hexes.remove(hex_id)
        
        # Add disc back to influence track
        if player.influence_track_detailed:
            # Find rightmost empty position and add disc there
            for i in range(len(player.influence_track_detailed.disc_positions) - 1, -1, -1):
                if not player.influence_track_detailed.disc_positions[i]:
                    player.influence_track_detailed.add_disc_at(i)
                    break
        
        # Return population cubes from this hex to tracks
        if hex_id in player.cubes_on_hexes:
            cubes = player.cubes_on_hexes[hex_id]
            for resource_type, count in cubes.items():
                if resource_type in player.population_tracks:
                    track = player.population_tracks[resource_type]
                    # Add cubes back to rightmost positions
                    for _ in range(count):
                        for i in range(len(track.cube_positions) - 1, -1, -1):
                            if not track.cube_positions[i]:
                                track.add_cube_at(i)
                                break
            
            # Clear cubes from hex
            del player.cubes_on_hexes[hex_id]
        
        # Remove from game map
        if hex_id in state.map.hexes:
            hex_obj = state.map.hexes[hex_id]
            if player.player_id in hex_obj.pieces:
                # Remove disc from hex pieces
                if hasattr(hex_obj.pieces[player.player_id], 'discs'):
                    hex_obj.pieces[player.player_id].discs = 0
        
        discs_removed += 1
        
        # Recalculate upkeep after removing disc
        new_upkeep = calculate_upkeep_cost(player)
        money_saved = player.get_upkeep_cost() - new_upkeep
    
    return discs_removed, money_saved


def apply_upkeep(state: GameState, player_id: str) -> Dict[str, any]:
    """
    Apply upkeep phase for one player.
    
    Steps:
    1. Calculate production from population tracks
    2. Calculate upkeep cost from influence track
    3. Apply net money change
    4. Add science and materials production
    5. Handle bankruptcy if needed (trade resources, remove discs)
    
    Args:
        state: The game state
        player_id: ID of player to apply upkeep for
        
    Returns:
        Dict with upkeep results:
        - "production": Dict of production values
        - "upkeep": Upkeep cost
        - "net_money": Net money change
        - "traded_resources": Whether resources were traded
        - "discs_removed": Number of discs removed (if bankrupt)
        - "collapsed": Whether player collapsed (eliminated)
        
    Reference: Eclipse Rulebook - Upkeep Phase
    """
    player = state.players[player_id]
    
    # Step 1: Calculate production and upkeep
    production = calculate_production(player)
    upkeep = calculate_upkeep_cost(player)
    net_money = production["money"] - upkeep
    
    result = {
        "production": production,
        "upkeep": upkeep,
        "net_money": net_money,
        "traded_resources": False,
        "discs_removed": 0,
        "collapsed": False,
    }
    
    # Step 2: Check if player can afford upkeep
    if player.resources.money + net_money < 0:
        # Bankruptcy handling
        money_shortage = abs(player.resources.money + net_money)
        
        # Try trading resources first (3:1 ratio)
        money_gained = trade_resources_to_money(player, money_shortage)
        result["traded_resources"] = money_gained > 0
        
        # Check if still can't afford
        if player.resources.money + net_money < 0:
            # Must remove influence discs
            money_still_needed = abs(player.resources.money + net_money)
            discs_removed, money_saved = remove_influence_discs_for_upkeep(
                state, player, money_still_needed
            )
            result["discs_removed"] = discs_removed
            
            # Recalculate upkeep after removing discs
            upkeep = calculate_upkeep_cost(player)
            net_money = production["money"] - upkeep
            
            # If still can't afford after removing all discs, player collapses
            if player.resources.money + net_money < 0:
                player.collapsed = True
                result["collapsed"] = True
                print(f"[UPKEEP] Player {player_id} has collapsed (eliminated)!")
                return result
    
    # Step 3: Apply money change
    player.resources.money = max(0, player.resources.money + net_money)
    
    # Step 4: Add science and materials production
    player.resources.science += production["science"]
    player.resources.materials += production["materials"]
    
    print(f"[UPKEEP] Player {player_id}: "
          f"Money {production['money']}-{upkeep}={net_money}, "
          f"Science +{production['science']}, "
          f"Materials +{production['materials']}")
    
    return result


def apply_upkeep_all_players(state: GameState) -> Dict[str, Dict[str, any]]:
    """
    Apply upkeep phase for all players.
    
    Args:
        state: The game state
        
    Returns:
        Dict mapping player_id to upkeep results
    """
    results = {}
    
    for player_id in state.players:
        results[player_id] = apply_upkeep(state, player_id)
    
    return results

