"""Ensure curated Orion legality fixtures remain valid."""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any

import pytest

from eclipse_ai.game_models import GameState
from eclipse_ai.validators import assert_test_case_legal

from tests.legal_cases.orion_turn1 import ORION_TURN1_TEST_CASES


def _materialise_state(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep-copied test case with the state coerced into ``GameState``."""
    payload = deepcopy(test_case)
    payload["state"] = GameState.from_dict(deepcopy(test_case["state"]))
    return payload


@pytest.mark.parametrize(
    "test_case",
    ORION_TURN1_TEST_CASES,
    ids=lambda case: case.get("provenance", "orion-case"),
)
def test_orion_opening_case_is_legal(test_case: Dict[str, Any]) -> None:
    materialised = _materialise_state(test_case)
    assert_test_case_legal(materialised)
    expectations = test_case.get("expectations", {})
    if expectations:
        assert expectations.get("should_be_legal", True) is True
