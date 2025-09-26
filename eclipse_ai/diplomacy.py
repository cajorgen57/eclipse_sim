"""Diplomatic relation management."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from .game_models import GameState, PlayerState, Hex, Pieces
from .map.connectivity import has_full_wormhole


class DiplomacyError(RuntimeError):
    """Raised when attempting to perform an illegal diplomatic action."""


def can_form_diplomacy(state: GameState, a_id: str, b_id: str) -> bool:
    """Return ``True`` when two players may legally form diplomatic relations."""
    if not state or not state.players:
        return False
    if a_id == b_id:
        return False
    if len(state.players) <= 3:
        return False
    player_a = state.players.get(a_id)
    player_b = state.players.get(b_id)
    if player_a is None or player_b is None:
        return False
    if player_a.has_traitor or player_b.has_traitor:
        return False
    if player_a.ambassadors.get(b_id) or player_b.ambassadors.get(a_id):
        return False
    if not (_has_available_population(player_a) and _has_available_population(player_b)):
        return False

    for hex_a in _controlled_hexes(state, a_id):
        for hex_b in _controlled_hexes(state, b_id):
            if not has_full_wormhole(state.map, hex_a.id, hex_b.id):
                continue
            if _has_other_player_ships(hex_a, b_id):
                continue
            if _has_other_player_ships(hex_b, a_id):
                continue
            return True
    return False


def form_diplomacy(state: GameState, a_id: str, b_id: str) -> None:
    """Establish mutual ambassadors and spend population cubes."""
    if not can_form_diplomacy(state, a_id, b_id):
        raise DiplomacyError("Diplomatic relation requirements not met")

    player_a = state.players[a_id]
    player_b = state.players[b_id]
    color_a = _spend_population_cube(player_a)
    color_b = _spend_population_cube(player_b)

    player_a.ambassadors[b_id] = True
    player_b.ambassadors[a_id] = True
    player_a.diplomacy[b_id] = color_a
    player_b.diplomacy[a_id] = color_b


def break_diplomacy(state: GameState, attacker_id: str, defender_id: str) -> None:
    """Break diplomatic relations due to hostile action."""
    removed = _remove_ambassadors(state, attacker_id, defender_id)
    if not removed:
        return
    attacker = state.players.get(attacker_id)
    if attacker:
        attacker.has_traitor = True


def clear_diplomacy(state: GameState, a_id: str, b_id: str) -> None:
    """Remove ambassadors for a pair without assigning the Traitor penalty."""
    _remove_ambassadors(state, a_id, b_id)


def has_diplomatic_relation(state: GameState, a_id: str, b_id: str) -> bool:
    player_a = state.players.get(a_id) if state else None
    player_b = state.players.get(b_id) if state else None
    if player_a is None or player_b is None:
        return False
    return bool(player_a.ambassadors.get(b_id) and player_b.ambassadors.get(a_id))


# ----- Internal helpers -----

def _remove_ambassadors(state: GameState, a_id: str, b_id: str) -> bool:
    player_a = state.players.get(a_id) if state else None
    player_b = state.players.get(b_id) if state else None
    if player_a is None or player_b is None:
        return False
    removed = False
    color_a = player_a.diplomacy.pop(b_id, None)
    color_b = player_b.diplomacy.pop(a_id, None)
    if color_a:
        player_a.population[color_a] = player_a.population.get(color_a, 0) + 1
        removed = True
    if color_b:
        player_b.population[color_b] = player_b.population.get(color_b, 0) + 1
        removed = True
    if player_a.ambassadors.pop(b_id, None):
        removed = True
    if player_b.ambassadors.pop(a_id, None):
        removed = True
    return removed


def _controlled_hexes(state: GameState, player_id: str) -> Iterable[Hex]:
    if not state or not state.map or not state.map.hexes:
        return []
    result = []
    for hx in state.map.hexes.values():
        pieces = hx.pieces.get(player_id) if hx.pieces else None
        if pieces and int(pieces.discs) > 0:
            result.append(hx)
    return result


def _has_other_player_ships(hex_obj: Hex, player_id: str) -> bool:
    if not hex_obj or not hex_obj.pieces:
        return False
    pieces = hex_obj.pieces.get(player_id)
    if pieces is None:
        return False
    return _has_ships(pieces)


def _has_ships(pieces: Pieces) -> bool:
    if pieces.starbase:
        return True
    return any(int(count) > 0 for count in pieces.ships.values())


def _has_available_population(player: Optional[PlayerState]) -> bool:
    if player is None:
        return False
    return any(count > 0 for count in player.population.values())


def _spend_population_cube(player: PlayerState) -> str:
    for color, count in player.population.items():
        if count > 0:
            player.population[color] = count - 1
            return color
    raise DiplomacyError("Player lacks population cubes to become ambassador")


__all__ = [
    "DiplomacyError",
    "can_form_diplomacy",
    "form_diplomacy",
    "break_diplomacy",
    "clear_diplomacy",
    "has_diplomatic_relation",
]
