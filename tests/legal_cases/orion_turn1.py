"""Legality fixtures derived from the Orion opening state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "orion_round1_start.json"


def _load_fixture(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_ORION_NO_MOVE_STATE: Dict[str, Any] = _load_fixture(_FIXTURE_PATH)


ORION_TURN1_TEST_CASES: List[Dict[str, Any]] = [
    {
        "state": _ORION_NO_MOVE_STATE,
        "player_id": "orion",
        "proposed_action": {
            "action": "Explore",
            "payload": {"ring": 1, "draws": 1, "direction": "adjacent from ring 1"},
        },
        "provenance": "manual/orion_hegemony/round1/no_move_fixture",
        "expectations": {
            "should_be_legal": True,
            "notes": "Opening explore from the no-move fixture should be legal.",
        },
    }
]

