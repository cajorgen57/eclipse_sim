"""Species-specific scoring helpers."""
from __future__ import annotations

from typing import Optional

from ..game_models import GameState, PlayerState


def unity_deathmoon_bonus(state: GameState, player: PlayerState) -> int:
    """Return the endgame VP bonus Unity receives for deployed Deathmoons."""
    if not player or not player.vp_bonuses:
        return 0
    per_deathmoon = player.vp_bonuses.get("endgame_per_deathmoon")
    if not per_deathmoon:
        return 0
    if not player.species_flags.get("starbase_minis_are_deathmoons"):
        return 0
    return int(per_deathmoon) * _count_deathmoons(state, player.player_id)


def deathmoon_reputation_draws(player: Optional[PlayerState]) -> int:
    """Number of reputation tiles opponents draw when destroying a Deathmoon."""
    if not player or not player.species_flags:
        return 0
    return int(player.species_flags.get("destroy_deathmoon_opponent_rep_draw", 0))


def _count_deathmoons(state: GameState, player_id: str) -> int:
    if not state.map or not state.map.hexes:
        return 0
    total = 0
    for hx in state.map.hexes.values():
        pieces = hx.pieces.get(player_id) if hx.pieces else None
        if not pieces:
            continue
        total += int(pieces.starbase or 0)
    return total
