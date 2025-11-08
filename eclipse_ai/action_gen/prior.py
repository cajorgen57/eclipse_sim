from __future__ import annotations

from statistics import mean
from typing import Any, Iterable

from .schema import MacroAction


_BASE_PRIORS = {
    "RESEARCH": 0.6,
    "UPGRADE": 0.5,
    "BUILD": 0.5,
    "EXPLORE": 0.4,
    "MOVE_FIGHT": 0.4,
    "INFLUENCE": 0.3,
    "DIPLOMACY": 0.2,
    "PASS": 0.0,
}


def _iter_dangers(threat_map: Any) -> Iterable[float]:
    if not threat_map:
        return []
    for danger_dict in getattr(threat_map, "danger", {}).values():
        for value in danger_dict.values():
            yield float(value)


def _critical_sector_ids(state: Any, context: Any | None) -> set[Any]:
    critical: set[Any] = set()
    if context is not None:
        extras = getattr(context, "extras", {}) or {}
        extra_ids = extras.get("critical_sectors")
        if isinstance(extra_ids, (list, tuple, set)):
            critical.update(extra_ids)
        elif extra_ids is not None:
            critical.add(extra_ids)
    for attr in ("home_sector_id", "home_sector", "capital_sector"):
        val = getattr(state, attr, None)
        if isinstance(val, (list, tuple, set)):
            critical.update(val)
        elif val is not None:
            critical.add(val)
    return critical


def _round_cap(state: Any, context: Any | None) -> int | None:
    for attr in ("round_cap", "max_rounds", "final_round"):
        val = getattr(state, attr, None)
        if isinstance(val, int) and val > 0:
            return val
    if context is not None:
        extras = getattr(context, "extras", {}) or {}
        cap = extras.get("round_cap")
        if isinstance(cap, int) and cap > 0:
            return cap
    return None


def score_macro_action(state, mac: MacroAction, context: Any | None = None) -> float:
    score = float(_BASE_PRIORS.get(mac.type, 0.1))

    threat_map = getattr(context, "threat_map", None) if context else None
    if threat_map is not None:
        danger_values = list(_iter_dangers(threat_map))
        danger_max = max(getattr(threat_map, "danger_by_opponent", {}).values(), default=0.0)
        danger_mean = mean(danger_values) if danger_values else 0.0

        if danger_max > 0.6:
            if mac.type in {"BUILD", "UPGRADE", "MOVE_FIGHT"}:
                score += 0.25
            elif mac.type in {"EXPLORE", "INFLUENCE"}:
                score -= 0.20

        critical_ids = _critical_sector_ids(state, context)
        if critical_ids:
            defensive_bonus = False
            for prediction in getattr(threat_map, "predicted_targets", {}).values():
                targets = getattr(prediction, "by_sector", {})
                if any(sid in critical_ids for sid in targets):
                    defensive_bonus = True
                    break
            if defensive_bonus and mac.type in {"BUILD", "UPGRADE", "MOVE_FIGHT"}:
                score += 0.15

        if danger_mean > 0.4 and mac.type == "MOVE_FIGHT":
            score += 0.1

    if context is not None:
        round_index = getattr(context, "round_index", None)
        round_cap = _round_cap(state, context)
        if isinstance(round_index, int) and round_cap:
            if round_cap > 0 and round_index >= max(round_cap - 1, 0):
                if mac.type == "EXPLORE":
                    score -= 0.15
                if mac.type in {"DIPLOMACY", "MONOLITH", "BUILD"}:
                    score += 0.1

    return float(score)
