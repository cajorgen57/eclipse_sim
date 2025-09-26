"""Endgame scoring helpers for diplomacy and alliances."""
from __future__ import annotations

from typing import Dict

from ..game_models import GameState, PlayerState


def diplomacy_vp(player: PlayerState) -> int:
    if not player:
        return 0
    return sum(1 for active in player.ambassadors.values() if active)


def traitor_penalty(player: PlayerState) -> int:
    if not player:
        return 0
    return -2 if player.has_traitor else 0


def alliance_tile_vp(player: PlayerState) -> int:
    if not player:
        return 0
    if player.alliance_tile == "+2":
        return 2
    if player.alliance_tile == "-3":
        return -3
    return 0


def calculate_endgame_vp(state: GameState, player_id: str, base_vp: int = 0) -> int:
    player = state.players.get(player_id) if state else None
    if player is None:
        return base_vp
    total = base_vp
    total += diplomacy_vp(player)
    total += traitor_penalty(player)
    total += alliance_tile_vp(player)
    return total


def alliance_average_vp(state: GameState, totals: Dict[str, int]) -> Dict[str, float]:
    """Return the per-alliance average VP used for ranking comparisons."""
    if not state:
        return {}
    averages: Dict[str, float] = {}
    for alliance_id, alliance in state.alliances.items():
        if not alliance.members:
            continue
        member_scores = [totals.get(pid, 0) for pid in alliance.members]
        if not member_scores:
            continue
        averages[alliance_id] = sum(member_scores) / float(len(member_scores))
    return averages


__all__ = [
    "diplomacy_vp",
    "traitor_penalty",
    "alliance_tile_vp",
    "calculate_endgame_vp",
    "alliance_average_vp",
]
