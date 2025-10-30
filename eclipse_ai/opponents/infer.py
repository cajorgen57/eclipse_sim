from __future__ import annotations

from typing import Dict, Tuple

from .types import OpponentMetrics, OpponentStyle


def _score_style(m: OpponentMetrics) -> Dict[OpponentStyle, float]:
    scores: Dict[OpponentStyle, float] = {
        OpponentStyle.RUSHER: 0.55 * m.aggression + 0.30 * m.build_intensity + 0.15 * m.mobility,
        OpponentStyle.TURTLE: 0.50 * m.expansion + 0.20 * m.upgrade_intensity + 0.30 * (1.0 - m.risk_tolerance),
        OpponentStyle.TECHER: 0.60 * m.tech_pace + 0.25 * m.upgrade_intensity + 0.15 * (1.0 - m.aggression),
        OpponentStyle.OPPORTUNIST: 0.40 * m.fleet_power + 0.30 * m.mobility + 0.30 * (1.0 - abs(m.expansion - m.aggression)),
        OpponentStyle.RAIDER: 0.50 * m.mobility + 0.25 * m.aggression + 0.25 * (1.0 - m.build_intensity),
        OpponentStyle.BALANCED: 0.25 * m.expansion + 0.25 * m.tech_pace + 0.25 * m.build_intensity + 0.25 * (1.0 - abs(m.aggression - m.expansion)),
    }
    mx = max(scores.values()) if scores else 1.0
    if mx > 0:
        for key in scores:
            scores[key] /= mx
    return scores


def infer_style(m: OpponentMetrics) -> Tuple[OpponentStyle, float, Tuple[str, ...]]:
    scores = _score_style(m)
    style, score = max(scores.items(), key=lambda kv: kv[1])
    second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    confidence = max(0.0, min(1.0, 0.5 + 0.5 * (score - second)))
    tags = []
    if m.aggression > 0.6:
        tags.append("aggressive")
    if m.tech_pace > 0.6:
        tags.append("techer")
    if m.mobility > 0.6:
        tags.append("mobile")
    if m.expansion > 0.6:
        tags.append("expander")
    return style, confidence, tuple(tags)

