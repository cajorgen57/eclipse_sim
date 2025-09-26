import pytest

from eclipse_ai.validators import assert_test_case_legal, assert_plans_legal, LegalityError


@pytest.fixture(autouse=True)
def stub_legal_actions(monkeypatch):
    allowed = [
        {"action": "PASS", "payload": {}},
        {"action": "EXPLORE", "payload": {"sector": 1}},
    ]

    def _stub(state, player_id):
        return allowed

    monkeypatch.setattr("eclipse_ai.validators.legal_actions", _stub)
    return allowed


@pytest.fixture
def sample_state():
    return {"hexes": []}


@pytest.fixture
def sample_player_id():
    return 0


@pytest.fixture
def sample_test(sample_state, sample_player_id):
    return {
        "state": sample_state,
        "player_id": sample_player_id,
        "proposed_action": {"action": "PASS", "payload": {}},
    }


@pytest.fixture
def planner_output():
    return {
        "plans": [
            {
                "steps": [
                    {"action": "EXPLORE", "payload": {"sector": 1, "extra": True}},
                    {"action": "PASS", "payload": {}},
                ]
            }
        ]
    }


def test_generator_outputs_only_legal_cases(sample_test):
    assert_test_case_legal(sample_test)


def test_planner_outputs_only_legal_steps(sample_state, sample_player_id, planner_output):
    assert_plans_legal(planner_output, sample_state, sample_player_id)


def test_illegal_action_raises(sample_state, sample_player_id):
    bad_test = {
        "state": sample_state,
        "player_id": sample_player_id,
        "proposed_action": {"action": "BUILD", "payload": {}},
    }
    with pytest.raises(LegalityError):
        assert_test_case_legal(bad_test)
