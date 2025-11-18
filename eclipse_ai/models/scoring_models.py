"""Lightweight models used by the scoring helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ReputationTile:
    """Representation of a kept reputation tile with its printed value."""

    value: int
    is_special: bool = False


@dataclass(slots=True)
class EvolutionTile:
    """Subset of Evolution tile data required for endgame scoring."""

    endgame_key: Optional[str] = None
    value: int = 0

