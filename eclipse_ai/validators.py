from __future__ import annotations

from typing import Dict, Any, List, Tuple
from copy import deepcopy

from eclipse_ai.rules import api as rules_api


class LegalityError(AssertionError):
    pass


def _fmt_action(a: Dict[str, Any]) -> str:
    t = a.get("action", a.get("type", ""))
    p = a.get("payload", {})
    return f"{t}:{p}"


def _extract_action_shape(candidate: Any) -> Tuple[Any, Dict[str, Any]]:
    """
    Normalize actions coming from old code (dicts, dataclass-like, objects with .type/.payload).
    """
    if isinstance(candidate, dict):
        return (
            candidate.get("action") or candidate.get("type"),
            candidate.get("payload") or {},
        )
    act_type = getattr(candidate, "type", None)
    if hasattr(act_type, "value"):
        act_type = act_type.value
    payload = getattr(candidate, "payload", {}) or {}
    return act_type, payload


def _is_action_legal(state: Dict[str, Any], player_id: int | str, action: Dict[str, Any]) -> bool:
    """
    Strict legality: action must be in the centralized rules API.
    We do not do "subset of payload keys" anymore because that is how drift happens.
    """
    return rules_api.is_action_legal(state, player_id, action)


def assert_test_case_legal(test: Dict[str, Any]) -> None:
    """
    Enforce legality before running a test.

    Required fields:
      test["state"]: full game state dict
      test["player_id"]: str | int
      test["proposed_action"]: {"action": str, "payload": dict}
    """
    state = test["state"]
    pid = test["player_id"]
    action = test["proposed_action"]

    if not _is_action_legal(state, pid, action):
        allowed = rules_api.enumerate_actions(state, pid)
        allowed_str = ", ".join(_fmt_action(a) for a in allowed[:20])
        raise LegalityError(
            f"Illegal proposed_action for player {pid}: {_fmt_action(action)}. "
            f"Allowed now: [{allowed_str}]"
        )


def assert_plans_legal(output: Dict[str, Any], state: Dict[str, Any], player_id: int | str) -> None:
    """
    Enforce legality on engine output shaped like:
      output = {
        "plans": [
          {
            "steps": [
              {"type": str, "payload": {...}},
              ...
            ],
            "score": ...,
            "risk": ...
          },
          ...
        ]
      }

    We now validate each step against the CURRENT state and step the state forward
    using the same centralized rules transition. That removes plan-vs-single-step drift.
    """
    plans: List[Dict[str, Any]] = output.get("plans", [])
    if not plans:
        return

    for p_idx, plan in enumerate(plans):
        steps = plan.get("steps", [])
        cur_state = deepcopy(state)
        cur_player = player_id
        for s_idx, step in enumerate(steps):
            if not _is_action_legal(cur_state, cur_player, step):
                allowed = rules_api.enumerate_actions(cur_state, cur_player)
                allowed_str = ", ".join(_fmt_action(a) for a in allowed[:20])
                raise LegalityError(
                    f"Plan {p_idx} step {s_idx} illegal: {_fmt_action(step)}. "
                    f"Allowed at check: [{allowed_str}]"
                )
            # step forward using centralized transition
            cur_state = rules_api.apply_action(cur_state, cur_player, step)
            # if your state advances active player each step, refresh it
            cur_player = getattr(cur_state, "active_player", None) or cur_state.get("active_player", cur_player)

