from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class Context:
    """Planning-time contextual information passed between modules."""

    # OPPONENTS
    opponent_models: Mapping[int, "OpponentModel"] = field(default_factory=dict)
    # THREATS
    threat_map: "ThreatMap" | None = None
    # PHASE INFO / META
    round_index: int | None = None
    phase_name: str | None = None
    # Arbitrary extra
    extras: Dict[str, Any] = field(default_factory=dict)

