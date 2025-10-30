from typing import List, Any, Mapping
from dataclasses import is_dataclass, asdict

from .. import rules_engine
from .schema import MacroAction, ActionType

_MAP = {
    "EXPLORE": "EXPLORE",
    "INFLUENCE": "INFLUENCE",
    "RESEARCH": "RESEARCH",
    "UPGRADE": "UPGRADE",
    "BUILD": "BUILD",
    "MOVE": "MOVE_FIGHT",
    "MOVE_FIGHT": "MOVE_FIGHT",
    "DIPLOMACY": "DIPLOMACY",
    "PASS": "PASS",
}


def _typename(a: Any) -> ActionType:
    for attr in ("type", "kind", "action_type", "name"):
        v = getattr(a, attr, None)
        if isinstance(v, str):
            key = v.upper()
            return _MAP.get(key, "LEGACY")
    key = a.__class__.__name__.upper()
    return _MAP.get(key, "LEGACY")


def _payload(a: Any) -> Mapping[str, Any]:
    if is_dataclass(a):
        try:
            return asdict(a)
        except Exception:
            pass
    if hasattr(a, "to_dict"):
        try:
            return a.to_dict()
        except Exception:
            pass
    if isinstance(a, dict):
        return a
    if hasattr(a, "__dict__"):
        out = {}
        for k, v in vars(a).items():
            out[k] = v if isinstance(v, (str, int, float, bool, type(None), list, tuple, dict)) else repr(v)
        return out
    return {"repr": repr(a)}


def generate(state) -> List[MacroAction]:
    macros: List[MacroAction] = []
    player_id = getattr(state, "active_player", None)
    if player_id is None:
        return macros
    for a in rules_engine.legal_actions(state, player_id):
        t = _typename(a)
        p = dict(_payload(a))
        p["__raw__"] = a
        macros.append(MacroAction(t, p, prior=0.0))
    return macros
