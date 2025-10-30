from types import SimpleNamespace

from eclipse_ai.action_gen.prior import score_macro_action
from eclipse_ai.action_gen.schema import MacroAction
from eclipse_ai.context import Context
from eclipse_ai.opponents.types import ThreatMap


def test_prior_defensive_bias_under_danger() -> None:
    state = SimpleNamespace(home_sector_id="X")
    tmap = ThreatMap(danger={"X": {1: 0.9}}, danger_by_opponent={1: 0.9}, predicted_targets={})
    ctx = Context(opponent_models={}, threat_map=tmap, round_index=3)
    build = MacroAction("BUILD", {"foo": "bar"})
    explore = MacroAction("EXPLORE", {"foo": "bar"})
    build_score = score_macro_action(state, build, ctx)
    explore_score = score_macro_action(state, explore, ctx)
    assert build_score > explore_score

