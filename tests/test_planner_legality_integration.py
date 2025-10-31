from copy import deepcopy

from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner
from eclipse_ai.rules import api as rules_api
from eclipse_ai import validators
from eclipse_ai.state_assembler import build_demo_state  # use your real builder


def _make_state():
    # if you don't have build_demo_state, swap for your existing test builder
    state = build_demo_state()
    # ensure active player set
    if not getattr(state, "active_player", None) and not getattr(state, "active_player_id", None):
        if isinstance(state, dict):
            state.setdefault("active_player", 0)
    return state


def test_planner_outputs_legal_plans():
    state = _make_state()
    pid = (
        getattr(state, "active_player", None)
        or getattr(state, "active_player_id", None)
        or (state["active_player"] if isinstance(state, dict) and "active_player" in state else 0)
    )

    planner = PW_MCTSPlanner(sims=50, depth=3, opponent_awareness=False)
    plans = planner.plan(state)

    # wrap to match your validator output shape
    output = {"plans": [{"steps": [p.__dict__ if hasattr(p, "__dict__") else p][0:1]} for p in plans if p]}

    validators.assert_plans_legal(output, state, pid)
