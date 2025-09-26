from typing import Dict, Any, List

from .rules_engine import legal_actions


class LegalityError(AssertionError):
    pass


def _fmt_action(a: Dict[str, Any]) -> str:
    t = a.get("action", a.get("type", ""))
    p = a.get("payload", {})
    return f"{t}:{p}"


def _is_action_legal(state: Dict[str, Any], player_id: int, action: Dict[str, Any]) -> bool:
    allowed = legal_actions(state, player_id)
    # Normalize comparison: match on action type/name and required payload keys
    atype = action.get("action") or action.get("type")
    for a in allowed:
        if (a.get("action") == atype or a.get("type") == atype):
            # Optional: shallow payload key subset check
            need = set((a.get("payload") or {}).keys())
            have = set((action.get("payload") or {}).keys())
            if need.issubset(have) or not need:
                return True
    return False


def assert_test_case_legal(test: Dict[str, Any]) -> None:
    """
    Enforce legality before running a test.

    Required fields:
      test["state"]: full game state dict
      test["player_id"]: int
      test["proposed_action"]: {"action": str, "payload": dict}
    """
    state = test["state"]
    pid = int(test["player_id"])
    action = test["proposed_action"]

    if not _is_action_legal(state, pid, action):
        allowed = legal_actions(state, pid)
        allowed_str = ", ".join(_fmt_action(a) for a in allowed[:20])
        raise LegalityError(
            f"Illegal proposed_action for player {pid}: {_fmt_action(action)}. "
            f"Allowed now: [{allowed_str}]"
        )


def assert_plans_legal(output: Dict[str, Any], state: Dict[str, Any], player_id: int) -> None:
    """
    Enforce legality on engine output shaped like:
      output = {"plans":[{"steps":[{"action": str, "payload": {...}}, ...], "score":..., "risk":...}, ...]}
    Validates each step against current state, stepping state forward if your engine exposes a stepper.
    If no stepper, validate per-step against the original state (strict gate at least).

    Returns None or raises LegalityError.
    """
    plans: List[Dict[str, Any]] = output.get("plans", [])
    if not plans:
        return

    # Optional: if you have a state stepper, plug it here:
    # from .rules_engine import apply_action
    # cur_state = deepcopy(state)

    for p_idx, plan in enumerate(plans):
        steps = plan.get("steps", [])
        # cur_state = deepcopy(state)
        for s_idx, step in enumerate(steps):
            if not _is_action_legal(state, player_id, step):
                allowed = legal_actions(state, player_id)
                allowed_str = ", ".join(_fmt_action(a) for a in allowed[:20])
                raise LegalityError(
                    f"Plan {p_idx} step {s_idx} illegal: {_fmt_action(step)}. "
                    f"Allowed at check: [{allowed_str}]"
                )
            # If you have a true simulator, uncomment:
            # cur_state = apply_action(cur_state, player_id, step)
