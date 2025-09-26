"""Tests for the rules engine heuristics respecting Agents_Testing guidelines."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Set

import pytest

from eclipse_ai.rules_engine import RulesConfig, legal_actions
from eclipse_ai.game_models import Action, ActionType, GameState


_BASE_STATE: Dict[str, Any] = {
    "round": 2,
    "active_player": "P1",
    "players": {
        "P1": {
            "player_id": "P1",
            "color": "orange",
            "known_techs": [],
            "resources": {"money": 6, "science": 5, "materials": 6},
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 0,
                    "initiative": 2,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
                "cruiser": {
                    "computer": 1,
                    "shield": 0,
                    "initiative": 3,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
            },
        },
        "P2": {
            "player_id": "P2",
            "color": "blue",
            "known_techs": ["Positron Computer"],
            "resources": {"money": 4, "science": 3, "materials": 3},
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 0,
                    "initiative": 2,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                }
            },
        },
    },
    "map": {
        "hexes": {
            "H1": {
                "id": "H1",
                "ring": 1,
                "planets": [
                    {"type": "yellow", "colonized_by": "P1"},
                    {"type": "blue", "colonized_by": "P1"},
                ],
                "pieces": {
                    "P1": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 2, "blue": 1},
                    }
                },
            },
            "H2": {
                "id": "H2",
                "ring": 2,
                "planets": [
                    {"type": "brown", "colonized_by": "P1"},
                    {"type": "yellow", "colonized_by": "P2"},
                ],
                "pieces": {
                    "P1": {
                        "ships": {"cruiser": 1},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"brown": 1},
                    },
                    "P2": {
                        "ships": {"interceptor": 1},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 1},
                    },
                },
            },
            "H3": {
                "id": "H3",
                "ring": 2,
                "planets": [
                    {"type": "yellow", "colonized_by": None},
                    {"type": "yellow", "colonized_by": None},
                ],
                "pieces": {},
            },
        }
    },
    "tech_display": {
        "available": ["Plasma Cannon I", "Fusion Drive II", "Advanced Mining"],
        "tier_counts": {"I": 6, "II": 3, "III": 1},
    },
    "bags": {"R1": {"unknown": 4}, "R2": {"unknown": 3}},
}


_ORION_OPENING: Dict[str, Any] = {
    "round": 1,
    "active_player": "P1",
    "players": {
        "P1": {
            "player_id": "P1",
            "color": "purple",
            "known_techs": ["Gauss Shield", "Neutron Bombs"],  # Orion Hegemony starting tech (Rise of the Ancients)
            "resources": {"money": 3, "science": 3, "materials": 5},
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 1,
                    "initiative": 4,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
                "cruiser": {
                    "computer": 1,
                    "shield": 1,
                    "initiative": 3,
                    "hull": 2,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
            },
        },
        "P2": {
            "player_id": "P2",
            "color": "orange",
            "known_techs": [],
            "resources": {"money": 2, "science": 2, "materials": 2},
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 0,
                    "initiative": 2,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
            },
        },
    },
    "map": {
        "hexes": {
            "230": {
                "id": "230",
                "ring": 1,
                "planets": [
                    {"type": "yellow", "colonized_by": "P1"},
                    {"type": "blue", "colonized_by": "P1"},
                    {"type": "brown", "colonized_by": "P1"},
                ],
                "pieces": {
                    "P1": {
                        "ships": {"interceptor": 2, "cruiser": 1},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 1, "blue": 1, "brown": 1},
                    }
                },
            },
            "Terran": {
                "id": "Terran",
                "ring": 1,
                "planets": [
                    {"type": "yellow", "colonized_by": "P2"},
                    {"type": "blue", "colonized_by": "P2"},
                    {"type": "brown", "colonized_by": "P2"},
                ],
                "pieces": {
                    "P2": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 1, "blue": 1, "brown": 1},
                    }
                },
            },
            "Outer": {
                "id": "Outer",
                "ring": 2,
                "planets": [
                    {"type": "yellow", "colonized_by": None},
                    {"type": "blue", "colonized_by": None},
                ],
                "pieces": {},
            },
        }
    },
    "tech_display": {
        "available": ["Plasma Cannon I", "Fusion Drive I", "Advanced Mining"],
        "tier_counts": {"I": 6, "II": 4, "III": 2},
    },
    "bags": {"R1": {"unknown": 4}, "R2": {"unknown": 3}},
}


@pytest.fixture(name="base_state")
def fixture_base_state() -> GameState:
    """Return an independent copy of the representative base scenario."""

    payload = json.loads(json.dumps(_BASE_STATE))
    return GameState.from_dict(payload)


@pytest.fixture(name="orion_state")
def fixture_orion_state() -> GameState:
    """Return the Orion Hegemony opening from the Rise of the Ancients pack."""

    payload = json.loads(json.dumps(_ORION_OPENING))
    return GameState.from_dict(payload)


def _action_types(actions: Iterable[Action]) -> Set[ActionType]:
    return {a.type for a in actions}


def test_unknown_player_only_passes() -> None:
    """Missing players default to a solitary pass action."""

    state = GameState()
    actions = legal_actions(state, "ghost")
    assert actions == [Action(ActionType.PASS, {})]


def test_explore_considers_adjacent_rings(base_state: GameState) -> None:
    """Exploration proposals draw from rings touching the player's footprint."""

    actions = legal_actions(base_state, "P1")
    explore_rings = {a.payload["ring"] for a in actions if a.type is ActionType.EXPLORE}
    assert explore_rings == {1, 2}


def test_research_respects_affordability(base_state: GameState) -> None:
    """Research options ignore owned technologies and respect science availability."""

    base_state.players["P1"].known_techs = ["Plasma Cannon I"]
    base_state.players["P1"].resources.science = 4

    actions = legal_actions(base_state, "P1")
    research = [a for a in actions if a.type is ActionType.RESEARCH]

    researched_techs = {a.payload["tech"] for a in research}
    assert "Plasma Cannon I" not in researched_techs
    for act in research:
        approx_cost = act.payload["approx_cost"]
        is_stretch = act.payload.get("note") == "stretch"
        assert approx_cost <= 4 or is_stretch


def test_build_prioritises_contested_starbase(base_state: GameState) -> None:
    """A contested hex with sufficient materials yields a starbase recommendation."""

    actions = legal_actions(base_state, "P1")
    build_payloads = [a.payload for a in actions if a.type is ActionType.BUILD]
    assert any(p.get("hex") == "H2" and p.get("starbase") == 1 for p in build_payloads)


def test_influence_recommends_high_value_hex(base_state: GameState) -> None:
    """Influence suggestions target the richest available neutral hex."""

    actions = legal_actions(base_state, "P1")
    influence = [a for a in actions if a.type is ActionType.INFLUENCE]
    assert influence
    assert influence[0].payload["hex"] == "H3"


def test_influence_can_be_disabled(base_state: GameState) -> None:
    """When influence is disabled the rules engine omits those actions entirely."""

    config = RulesConfig(enable_influence=False)
    actions = legal_actions(base_state, "P1", config)
    assert ActionType.INFLUENCE not in _action_types(actions)


def test_diplomacy_toggle_removes_offers(base_state: GameState) -> None:
    """Disabling diplomacy removes diplomatic offers from the action list."""

    config = RulesConfig(enable_diplomacy=False)
    actions = legal_actions(base_state, "P1", config)
    assert ActionType.DIPLOMACY not in _action_types(actions)


def test_orion_opening_recommendations(orion_state: GameState) -> None:
    """On round one the Orion Hegemony gets explore, aggression, and influence suggestions."""

    actions = legal_actions(orion_state, "P1")

    # Explore should target both the current ring and the next ring (home sector 230 in Rise of the Ancients).
    explore_payloads = [a.payload for a in actions if a.type is ActionType.EXPLORE]
    assert {p["ring"] for p in explore_payloads} == {1, 2}

    # Limited science (1) means no immediate research options are offered.
    assert ActionType.RESEARCH not in _action_types(actions)

    # Building another interceptor in the home hex is the affordable combat reinforcement.
    build_payloads = [a.payload for a in actions if a.type is ActionType.BUILD]
    assert {"hex": "230", "ships": {"interceptor": 1}} in build_payloads

    # Aggressive move suggestion toward the Terran neighbour plus an influence target on the richest empty hex.
    move_targets = {(a.payload["from"], a.payload["to"]) for a in actions if a.type is ActionType.MOVE}
    assert ("230", "Terran") in move_targets

    influence_targets = [a.payload.get("hex") for a in actions if a.type is ActionType.INFLUENCE]
    assert influence_targets == ["Outer"]
