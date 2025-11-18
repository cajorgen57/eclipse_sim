"""
Combat Phase Resolution for Multi-Round Simulation.

This module handles combat resolution during the Combat Phase:
- Detects hexes with multiple players' ships
- Resolves battles using the combat simulator
- Handles retreats and ship pinning
- Awards reputation tiles to winners

Reference: Eclipse Rulebook - Combat Phase
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

from .game_models import GameState, PlayerState, Hex
from .simulators.combat import (
    resolve_combat,
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
)


@dataclass
class BattleResult:
    """Result of a single battle."""
    hex_id: str
    attacker_id: str
    defender_id: str
    winner_id: Optional[str]
    attacker_ships_lost: int
    defender_ships_lost: int
    reputation_awarded: int


def find_combat_hexes(state: GameState) -> List[str]:
    """
    Find all hexes where combat must occur.
    
    Combat occurs in hexes with ships from multiple players.
    
    Args:
        state: Current game state
        
    Returns:
        List of hex IDs where combat occurs
    """
    combat_hexes = []
    
    for hex_id, hex_obj in state.map.hexes.items():
        # Count players with ships in this hex
        players_with_ships = []
        
        for player_id, pieces in hex_obj.pieces.items():
            if pieces.ships and any(count > 0 for count in pieces.ships.values()):
                players_with_ships.append(player_id)
        
        # Combat occurs if 2+ players have ships
        if len(players_with_ships) >= 2:
            combat_hexes.append(hex_id)
    
    return combat_hexes


def ships_are_pinned(state: GameState, hex_id: str, player_id: str) -> bool:
    """
    Check if a player's ships are pinned in a hex.
    
    Ships are pinned if there are enemy ships in the same hex.
    Pinned ships cannot move out of the hex.
    
    Args:
        state: Current game state
        hex_id: Hex to check
        player_id: Player whose ships to check
        
    Returns:
        True if ships are pinned, False otherwise
        
    Reference: Eclipse Rulebook - Pinning rules
    """
    hex_obj = state.map.hexes.get(hex_id)
    if not hex_obj:
        return False
    
    # Check if any other player has ships in this hex
    for other_player_id, pieces in hex_obj.pieces.items():
        if other_player_id == player_id:
            continue
        
        if pieces.ships and any(count > 0 for count in pieces.ships.values()):
            return True
    
    return False


def convert_ships_to_combatant(
    player: PlayerState,
    hex_obj: Hex,
) -> Combatant:
    """
    Convert player's ships in a hex to Combatant for combat resolution.
    
    Args:
        player: Player state
        hex_obj: Hex containing the ships
        
    Returns:
        Combatant object for combat simulator
    """
    pieces = hex_obj.pieces.get(player.player_id)
    if not pieces or not pieces.ships:
        return Combatant(owner=player.player_id, ships=[])
    
    ships = []
    ship_designs = getattr(player, 'ship_designs', {})
    
    for ship_class, count in pieces.ships.items():
        design = ship_designs.get(ship_class)
        if not design or count == 0:
            continue
        
        # Create ships based on design
        for _ in range(count):
            ship = Ship(
                cls=ship_class,
                initiative=getattr(design, 'initiative', 1),
                hull=getattr(design, 'hull', 1),
                max_hull=getattr(design, 'hull', 1),
                computer=getattr(design, 'computer', 0),
                shield=getattr(design, 'shield', 0),
                weapons=getattr(design, 'weapons', {}),
                missiles=getattr(design, 'missiles', 0),
                missile_damage=getattr(design, 'missile_damage', 1),
            )
            ships.append(ship)
    
    return Combatant(
        owner=player.player_id,
        ships=ships,
    )


def resolve_battle(
    state: GameState,
    hex_id: str,
    attacker_id: str,
    defender_id: str,
    verbose: bool = True,
) -> BattleResult:
    """
    Resolve a battle between two players in a hex.
    
    Args:
        state: Current game state
        hex_id: Hex where battle occurs
        attacker_id: Attacking player ID
        defender_id: Defending player ID
        verbose: Whether to print battle details
        
    Returns:
        BattleResult with outcome
    """
    if verbose:
        print(f"[COMBAT] Battle in {hex_id}: {attacker_id} vs {defender_id}")
    
    hex_obj = state.map.hexes[hex_id]
    
    # Convert ships to combatants
    attacker = state.players[attacker_id]
    defender = state.players[defender_id]
    
    attacker_combatant = convert_ships_to_combatant(attacker, hex_obj)
    defender_combatant = convert_ships_to_combatant(defender, hex_obj)
    
    # Default weapon profiles
    weapon_profiles = {
        "yellow": WeaponProfile(base_to_hit=6, damage=1),
        "orange": WeaponProfile(base_to_hit=5, damage=1),
        "blue": WeaponProfile(base_to_hit=4, damage=1),
        "red": WeaponProfile(base_to_hit=3, damage=2),
    }
    
    # Create combat config
    config = CombatConfig(
        attacker=attacker_combatant,
        defender=defender_combatant,
        weapon_profiles=weapon_profiles,
    )
    
    # Resolve combat
    result = resolve_combat(config)
    
    # Count losses
    attacker_initial = len(attacker_combatant.ships)
    defender_initial = len(defender_combatant.ships)
    
    attacker_survivors = sum(1 for s in result.attacker.ships if s.alive())
    defender_survivors = sum(1 for s in result.defender.ships if s.alive())
    
    attacker_losses = attacker_initial - attacker_survivors
    defender_losses = defender_initial - defender_survivors
    
    # Determine winner
    winner_id = None
    if result.winner == attacker_id:
        winner_id = attacker_id
    elif result.winner == defender_id:
        winner_id = defender_id
    
    # Calculate reputation (1 per ship destroyed)
    reputation = defender_losses if winner_id == attacker_id else attacker_losses
    
    if verbose:
        print(f"[COMBAT] Winner: {winner_id or 'Draw'}")
        print(f"[COMBAT] {attacker_id} losses: {attacker_losses}")
        print(f"[COMBAT] {defender_id} losses: {defender_losses}")
        print(f"[COMBAT] Reputation awarded: {reputation}")
    
    # Update game state with results
    _apply_battle_results(state, hex_id, result, attacker_id, defender_id)
    
    return BattleResult(
        hex_id=hex_id,
        attacker_id=attacker_id,
        defender_id=defender_id,
        winner_id=winner_id,
        attacker_ships_lost=attacker_losses,
        defender_ships_lost=defender_losses,
        reputation_awarded=reputation,
    )


def _apply_battle_results(
    state: GameState,
    hex_id: str,
    combat_result,
    attacker_id: str,
    defender_id: str,
) -> None:
    """
    Apply combat results to game state.
    
    Updates ship counts and removes destroyed ships.
    
    Args:
        state: Game state to update
        hex_id: Hex where battle occurred
        combat_result: CombatResolution from combat simulator
        attacker_id: Attacker player ID
        defender_id: Defender player ID
    """
    hex_obj = state.map.hexes[hex_id]
    
    # Update attacker ships
    attacker_pieces = hex_obj.pieces.get(attacker_id)
    if attacker_pieces:
        # Count survivors by class
        survivor_counts: Dict[str, int] = {}
        for ship in combat_result.attacker.ships:
            if ship.alive():
                survivor_counts[ship.cls] = survivor_counts.get(ship.cls, 0) + 1
        
        # Update ship counts
        attacker_pieces.ships = survivor_counts
    
    # Update defender ships
    defender_pieces = hex_obj.pieces.get(defender_id)
    if defender_pieces:
        # Count survivors by class
        survivor_counts: Dict[str, int] = {}
        for ship in combat_result.defender.ships:
            if ship.alive():
                survivor_counts[ship.cls] = survivor_counts.get(ship.cls, 0) + 1
        
        # Update ship counts
        defender_pieces.ships = survivor_counts


def resolve_combat_phase(state: GameState, verbose: bool = True) -> List[BattleResult]:
    """
    Resolve all combat for the combat phase.
    
    Finds all hexes with multiple players' ships and resolves battles.
    Awards reputation tiles to winners.
    
    Args:
        state: Current game state
        verbose: Whether to print combat details
        
    Returns:
        List of battle results
        
    Reference: Eclipse Rulebook - Combat Phase
    """
    if verbose:
        print("[COMBAT PHASE] Starting combat resolution")
    
    combat_hexes = find_combat_hexes(state)
    
    if not combat_hexes:
        if verbose:
            print("[COMBAT PHASE] No combat this round")
        return []
    
    if verbose:
        print(f"[COMBAT PHASE] Combat in {len(combat_hexes)} hex(es)")
    
    results = []
    
    for hex_id in combat_hexes:
        hex_obj = state.map.hexes[hex_id]
        
        # Find all players with ships
        players_with_ships = [
            player_id for player_id, pieces in hex_obj.pieces.items()
            if pieces.ships and any(count > 0 for count in pieces.ships.values())
        ]
        
        if len(players_with_ships) < 2:
            continue
        
        # For simplicity, resolve as attacker vs defender
        # In full game, this would need to handle multiple players
        attacker_id = players_with_ships[0]
        defender_id = players_with_ships[1]
        
        try:
            result = resolve_battle(state, hex_id, attacker_id, defender_id, verbose)
            results.append(result)
            
            # Award reputation to winner
            if result.winner_id and result.reputation_awarded > 0:
                winner = state.players[result.winner_id]
                winner_reputation = getattr(winner, 'reputation', [])
                winner_reputation.extend([1] * result.reputation_awarded)
                winner.reputation = winner_reputation
                
        except Exception as e:
            if verbose:
                print(f"[COMBAT PHASE] Error resolving battle in {hex_id}: {e}")
    
    if verbose:
        print(f"[COMBAT PHASE] Completed {len(results)} battle(s)")
    
    return results


def check_pinning_restrictions(
    state: GameState,
    player_id: str,
    from_hex_id: str,
) -> bool:
    """
    Check if player's ships can move from a hex (not pinned).
    
    Args:
        state: Current game state
        player_id: Player attempting to move
        from_hex_id: Hex to move from
        
    Returns:
        True if movement allowed, False if pinned
    """
    return not ships_are_pinned(state, from_hex_id, player_id)

