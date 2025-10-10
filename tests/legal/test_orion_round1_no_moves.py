from eclipse_ai.rules_engine import legal_actions
from eclipse_ai.game_models import ActionType
from eclipse_ai.state.loaders import load_state


def test_orion_round1_has_no_moves_until_explore() -> None:
    gs = load_state("tests/fixtures/orion_round1_start.json")
    acts = list(legal_actions(gs, player_id="orion"))
    types = {a.type for a in acts}
    assert ActionType.EXPLORE in types
    assert ActionType.MOVE not in types
