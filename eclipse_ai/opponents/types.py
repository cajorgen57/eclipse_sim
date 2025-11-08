from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Mapping, Tuple


class OpponentStyle(Enum):
    BALANCED = auto()
    RUSHER = auto()  # emphasizes early fleet, pressure, fights
    TURTLE = auto()  # emphasizes economy, sectors, defense
    TECHER = auto()  # emphasizes research/upgrade tempo
    OPPORTUNIST = auto()  # fights when EV is high, otherwise grows
    RAIDER = auto()  # skirmishes, picks off weak sectors


@dataclass(frozen=True)
class OpponentMetrics:
    # per-round or rate-like metrics normalized to 0..1 where possible
    aggression: float = 0.0  # combat frequency / initiated battles / border incursions
    expansion: float = 0.0  # sectors gained per round normalized by map size
    tech_pace: float = 0.0  # techs researched per round normalized by pool
    build_intensity: float = 0.0  # ships built per round normalized by capacity
    upgrade_intensity: float = 0.0  # upgrades per round normalized
    mobility: float = 0.0  # avg drive/initiative proxy (0..1)
    fleet_power: float = 0.0  # proxy for combat strength (0..1)
    border_pressure: float = 0.0  # presence near borders (0..1)
    diplomacy_rate: float = 0.0  # diplomatic actions fraction
    risk_tolerance: float = 0.0  # attacks with negative EV (observed)


@dataclass(frozen=True)
class TargetPrediction:
    # sector_id -> desirability 0..1
    by_sector: Mapping[Any, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ThreatMap:
    # danger[our_sector_id][opponent_id] -> 0..1
    danger: Mapping[Any, Mapping[int, float]] = field(default_factory=dict)
    # aggregate per-opponent total border danger 0..1
    danger_by_opponent: Mapping[int, float] = field(default_factory=dict)
    # predicted targets for each opponent
    predicted_targets: Mapping[int, TargetPrediction] = field(default_factory=dict)


@dataclass(frozen=True)
class OpponentModel:
    player_id: int
    style: OpponentStyle
    confidence: float  # 0..1
    metrics: OpponentMetrics
    tags: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

