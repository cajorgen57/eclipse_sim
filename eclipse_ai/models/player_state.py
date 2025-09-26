"""Lightweight player state models used by the scoring helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


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


AllianceSide = Literal["faceup", "+2", "betrayer", "-3", None]


@dataclass(slots=True)
class PlayerState:
    """Player view consumed by :mod:`eclipse_ai.scoring` utilities."""

    player_id: str
    reputation_kept: List[ReputationTile] = field(default_factory=list)
    ambassadors: int = 0
    controlled_hex_ids: List[str] = field(default_factory=list)
    discoveries_kept: int = 0
    monolith_count: int = 0
    tech_track_counts: Dict[str, int] = field(default_factory=dict)
    has_traitor: bool = False
    alliance_tile: AllianceSide = None
    ancient_kill_tokens: Dict[str, int] = field(
        default_factory=lambda: {"cruiser": 0, "dreadnought": 0}
    )
    evolution_tiles: List[EvolutionTile] = field(default_factory=list)
    artifacts_controlled: int = 0
    controls_galactic_center: bool = False
