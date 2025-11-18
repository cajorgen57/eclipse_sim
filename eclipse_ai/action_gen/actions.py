"""Action generation bridge to the centralized rules API.

This module provides a compatibility layer that wraps the centralized rules.api
to produce MacroAction objects compatible with the planner interface.
"""
from typing import List, Any, Mapping, Dict
from dataclasses import is_dataclass, asdict

from eclipse_ai.rules import api as rules_api
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


def _typename_from_str(v: str) -> ActionType:
    key = v.upper()
    return _MAP.get(key, "LEGACY")


def _typename(a: Any) -> ActionType:
    # kept for backward compatibility in case something still calls this
    for attr in ("type", "kind", "action_type", "name"):
        v = getattr(a, attr, None)
        if isinstance(v, str):
            return _typename_from_str(v)
    key = a.__class__.__name__.upper()
    return _MAP.get(key, "LEGACY")


def _payload(a: Any) -> Mapping[str, Any]:
    # kept for backward compatibility
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
        out: Dict[str, Any] = {}
        for k, v in vars(a).items():
            if isinstance(v, (str, int, float, bool, type(None), list, tuple, dict)):
                out[k] = v
            else:
                out[k] = repr(v)
        return out
    return {"repr": repr(a)}


def generate(state) -> List[MacroAction]:
    """
    Compatibility bridge for action generation.
    
    This function provides a MacroAction-compatible interface to the centralized
    rules API. It wraps rules.api.enumerate_actions() to maintain compatibility
    with code that expects MacroAction objects.
    
    Note: Despite the module name "legacy", this is actively used as a bridge
    to the new rules API and should not be removed.
    """
    macros: List[MacroAction] = []
    player_id = getattr(state, "active_player", None)
    if player_id is None and isinstance(state, dict):
        player_id = state.get("active_player")
    if player_id is None:
        return macros

    # single source of truth
    actions = rules_api.enumerate_actions(state, player_id)

    for a in actions:
        # a is already a dict because rules.api normalized it
        atype = a.get("type") or a.get("action") or "LEGACY"
        mapped_type: ActionType = _typename_from_str(atype)
        payload: Dict[str, Any] = dict(a.get("payload", {}))
        # Preserve raw action dict for backward compatibility with report code
        # This can be removed once all report code is updated
        payload["__raw__"] = a
        macros.append(MacroAction(mapped_type, payload, prior=0.0))

    return macros
