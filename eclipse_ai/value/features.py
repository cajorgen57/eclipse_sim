from __future__ import annotations

from statistics import mean
from typing import Any, Dict


def extract_features(state: Any, context: Any | None = None) -> Dict[str, float]:
    """Derive normalized heuristic features from a game state."""
    feats = {
        "vp_now": float(getattr(state, "vp", 0.0)) if hasattr(state, "vp") else 0.0,
        "spare_discs": float(getattr(state, "spare_discs", 0.0)) if hasattr(state, "spare_discs") else 0.0,
    }

    if context is not None:
        threat_map = getattr(context, "threat_map", None)
        if threat_map is not None:
            danger_values = []
            for sector_danger in getattr(threat_map, "danger", {}).values():
                danger_values.extend(float(v) for v in sector_danger.values())
            danger_max = max(getattr(threat_map, "danger_by_opponent", {}).values(), default=0.0)
            feats["danger_max"] = float(danger_max)
            feats["danger_mean"] = float(mean(danger_values)) if danger_values else 0.0
        else:
            feats["danger_max"] = 0.0
            feats["danger_mean"] = 0.0

        opponent_models = getattr(context, "opponent_models", {}) or {}
        if opponent_models:
            agg_aggression = max(
                (model.metrics.aggression for model in opponent_models.values()),
                default=0.0,
            )
            agg_tech = max(
                (model.metrics.tech_pace for model in opponent_models.values()),
                default=0.0,
            )
        else:
            agg_aggression = 0.0
            agg_tech = 0.0
        feats["opp_aggression_max"] = float(agg_aggression)
        feats["opp_tech_max"] = float(agg_tech)

    return feats
