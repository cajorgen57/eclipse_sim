from types import SimpleNamespace
from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner

def test_plan_with_diagnostics_shape():
    # minimal synthetic state; planner should not crash (requires your round_flow to accept no-ops)
    state = SimpleNamespace()
    planner = PW_MCTSPlanner(sims=5, depth=1, seed=0)
    ranked, diag = planner.plan_with_diagnostics(state)
    assert "children" in diag and "params" in diag
