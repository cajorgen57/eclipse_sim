# tests/test_planner_legality_integration.py
import json
from pathlib import Path

from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner
from eclipse_ai import validators

# ---- helpers ----
class DotDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def to_dotdict(x):
    if isinstance(x, dict):
        return DotDict({k: to_dotdict(v) for k, v in x.items()})
    if isinstance(x, list):
        return [to_dotdict(v) for v in x]
    return x

def _load_orion_state():
    p = Path("orion_round1.json")
    with p.open("r") as f:
        data = json.load(f)
    return to_dotdict(data.get("state", data))

def _active_player(state):
    return (
        getattr(state, "active_player", None)
        or getattr(state, "active_player_id", None)
        or (state.get("active_player") if isinstance(state, dict) else None)
        or 0
    )

# ---- test ----
def test_planner_outputs_legal_plans_on_orion_snapshot():
    state = _load_orion_state()
    pid = _active_player(state)

    planner = PW_MCTSPlanner(sims=25, depth=2, opponent_awareness=False)
    plans = planner.plan(state)

    # adapt planner output to validator shape
    output = {"plans": []}
    for mac in plans:
        if mac is None:
            continue
        payload = dict(getattr(mac, "payload", {}))
        payload.pop("__raw__", None)
        output["plans"].append(
            {"steps": [{"type": getattr(mac, "type", payload.get("action", "PASS")), "payload": payload}]}
        )

    validators.assert_plans_legal(output, state, pid)
