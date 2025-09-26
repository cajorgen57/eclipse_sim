"""Alliance management and helper utilities."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from .game_models import Alliance, GameState, PlayerState, Hex, Pieces
from . import diplomacy


class AllianceError(RuntimeError):
    """Raised when an illegal alliance operation is attempted."""


_MAX_ROUND = 9


def are_allied(state: GameState, a_id: str, b_id: str) -> bool:
    if a_id == b_id:
        return True
    player_a = state.players.get(a_id) if state else None
    player_b = state.players.get(b_id) if state else None
    if player_a is None or player_b is None:
        return False
    if not player_a.alliance_id or not player_b.alliance_id:
        return False
    return player_a.alliance_id == player_b.alliance_id


def allies_for_player(state: GameState, player_id: str) -> List[str]:
    player = state.players.get(player_id) if state else None
    if player is None or not player.alliance_id:
        return []
    alliance = state.alliances.get(player.alliance_id)
    if alliance is None:
        return []
    return [pid for pid in alliance.members if pid != player_id]


def can_found_alliance(state: GameState, a_id: str, b_id: str, third_id: Optional[str] = None) -> bool:
    if not state or not state.players:
        return False
    if not state.feature_flags.get("rotA"):
        return False
    if state.round >= _MAX_ROUND:
        return False
    if a_id == b_id:
        return False
    a = state.players.get(a_id)
    b = state.players.get(b_id)
    if a is None or b is None:
        return False
    if a.alliance_id or b.alliance_id:
        return False
    if a.alliance_tile == "-3" or b.alliance_tile == "-3":
        return False
    if not diplomacy.has_diplomatic_relation(state, a_id, b_id):
        return False
    player_count = len(state.players)
    allow_third = player_count >= 6
    if third_id:
        if not allow_third:
            return False
        third = state.players.get(third_id)
        if third is None:
            return False
        if third.alliance_id or third.alliance_tile == "-3":
            return False
        if not diplomacy.has_diplomatic_relation(state, third_id, a_id):
            return False
        if not diplomacy.has_diplomatic_relation(state, third_id, b_id):
            return False
    else:
        third = None
    return True


def found_alliance(state: GameState, a_id: str, b_id: str, third_id: Optional[str] = None) -> Alliance:
    if not can_found_alliance(state, a_id, b_id, third_id):
        raise AllianceError("Alliance requirements not met")
    alliance_id = _next_alliance_id(state)
    members = [a_id, b_id]
    if third_id:
        members.append(third_id)
    alliance = Alliance(id=alliance_id, members=list(members), founded=True)
    state.alliances[alliance_id] = alliance
    for pid in members:
        player = state.players[pid]
        player.alliance_id = alliance_id
        player.alliance_tile = "+2"
    return alliance


def join_alliance(state: GameState, alliance_id: str, player_id: str) -> None:
    alliance = state.alliances.get(alliance_id)
    if alliance is None or not alliance.founded:
        raise AllianceError("Alliance not available")
    if state.round >= _MAX_ROUND:
        raise AllianceError("Cannot join on the final round")
    player = state.players.get(player_id)
    if player is None:
        raise AllianceError("Unknown player")
    if player.alliance_id:
        raise AllianceError("Player already in alliance")
    if player.alliance_tile == "-3":
        raise AllianceError("Betrayers cannot rejoin an alliance")
    if len(alliance.members) >= 3:
        raise AllianceError("Alliance is at capacity")
    if len(state.players) < 6:
        raise AllianceError("Alliance cannot add members in small games")
    for member_id in alliance.members:
        if not diplomacy.has_diplomatic_relation(state, player_id, member_id):
            raise AllianceError("Joining player lacks diplomacy with alliance member")
    alliance.members.append(player_id)
    player.alliance_id = alliance_id
    player.alliance_tile = "+2"


def leave_alliance(state: GameState, player_id: str) -> None:
    player = state.players.get(player_id)
    if player is None or not player.alliance_id:
        raise AllianceError("Player is not in an alliance")
    if state.round >= _MAX_ROUND:
        raise AllianceError("Cannot leave on the final round")
    alliance = state.alliances.get(player.alliance_id)
    if alliance is None:
        raise AllianceError("Alliance not found")

    player.alliance_tile = "-3"
    alliance.betrayers.add(player_id)

    allies = list(alliance.members)
    if player_id in allies:
        allies.remove(player_id)

    for ally_id in allies:
        if _counts_as_attack(state, player_id, ally_id):
            diplomacy.break_diplomacy(state, player_id, ally_id)
        else:
            diplomacy.clear_diplomacy(state, player_id, ally_id)

    if player_id in alliance.members:
        alliance.members.remove(player_id)
    player.alliance_id = None

    if not alliance.members and alliance.id in state.alliances:
        del state.alliances[alliance.id]


def ship_presence(state: GameState, hex_obj: Hex, player_id: str) -> Tuple[int, int]:
    """Return ``(friendly, enemy)`` ship counts for pinning checks."""
    if not hex_obj:
        return (0, 0)
    friendly = 0
    enemy = int(hex_obj.ancients or 0)
    for owner, pieces in (hex_obj.pieces or {}).items():
        ships = _ship_count(pieces)
        if owner == player_id:
            friendly += ships
        elif are_allied(state, owner, player_id):
            friendly += ships
        else:
            enemy += ships
    return friendly, enemy


def merge_combat_sides(state: GameState, defenders: Iterable[str], attackers: Iterable[str]) -> Tuple[List[str], List[str], bool]:
    """Return combat sides, merging alliances and resolving defender initiative."""
    defender_side: List[str] = []
    attacker_side: List[str] = []

    for pid in defenders:
        defender_side.extend(_expand_allied_members(state, pid))
    defender_side = _unique_preserve_order(defender_side)

    for pid in attackers:
        members = _expand_allied_members(state, pid)
        if any(member in defender_side for member in members):
            for member in members:
                if member not in defender_side:
                    defender_side.append(member)
            continue
        attacker_side.extend(members)

    attacker_side = [pid for pid in _unique_preserve_order(attacker_side) if pid not in defender_side]
    defender_tie_advantage = bool(defender_side)
    return defender_side, attacker_side, defender_tie_advantage


def _expand_allied_members(state: GameState, player_id: str) -> List[str]:
    player = state.players.get(player_id)
    if player is None:
        return []
    if not player.alliance_id:
        return [player_id]
    alliance = state.alliances.get(player.alliance_id)
    if alliance is None:
        return [player_id]
    return list(alliance.members)


def _ship_count(pieces: Pieces) -> int:
    total = int(pieces.starbase or 0)
    total += sum(int(v) for v in (pieces.ships or {}).values())
    return total


def _next_alliance_id(state: GameState) -> str:
    idx = 1
    while True:
        candidate = f"alliance-{idx}"
        if candidate not in state.alliances:
            return candidate
        idx += 1


def _counts_as_attack(state: GameState, player_id: str, ally_id: str) -> bool:
    if not state or not state.map or not state.map.hexes:
        return False
    for hx in state.map.hexes.values():
        pieces_player = hx.pieces.get(player_id) if hx.pieces else None
        pieces_ally = hx.pieces.get(ally_id) if hx.pieces else None
        player_controls = bool(pieces_player and int(pieces_player.discs) > 0)
        ally_controls = bool(pieces_ally and int(pieces_ally.discs) > 0)
        player_has_ships = bool(pieces_player and _ship_count(pieces_player) > 0)
        ally_has_ships = bool(pieces_ally and _ship_count(pieces_ally) > 0)
        if ally_controls and player_has_ships:
            return True
        if player_controls and (ally_has_ships or bool(pieces_ally and int(pieces_ally.discs) > 0)):
            return True
    return False


def _unique_preserve_order(ids: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for pid in ids:
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
    return ordered


__all__ = [
    "AllianceError",
    "are_allied",
    "allies_for_player",
    "can_found_alliance",
    "found_alliance",
    "join_alliance",
    "leave_alliance",
    "ship_presence",
    "merge_combat_sides",
]
