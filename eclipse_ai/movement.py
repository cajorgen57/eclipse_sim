"""Movement utility helpers."""
from __future__ import annotations

from typing import Optional

from .game_models import PlayerState

_DEFAULT_MOVE_ACTIVATIONS = 3


def max_ship_activations_per_action(player: Optional[PlayerState], is_reaction: bool = False) -> int:
    """Return the legal number of ship activations for a MOVE action.

    Shadows of the Rift factions from Ship Pack One may replace the default
    three activations with a stricter limit. Reactions remain capped at a single
    activation regardless of species modifiers.
    """
    if is_reaction:
        return 1
    if not player:
        return _DEFAULT_MOVE_ACTIVATIONS
    override = None
    try:
        override = player.move_overrides.get("move_ship_activations_per_action") if player.move_overrides else None
    except AttributeError:
        override = None
    if override is None:
        return _DEFAULT_MOVE_ACTIVATIONS
    try:
        return max(1, int(override))
    except (TypeError, ValueError):
        return _DEFAULT_MOVE_ACTIVATIONS
