"""Detailed movement legality tests for Eclipse MOVE actions."""

from __future__ import annotations

import copy

import pytest

from eclipse_ai.game_models import GameState
from eclipse_ai.search_policy import _apply_move_action


BASE_PLAYER = {
    "player_id": "P1",
    "color": "orange",
    "known_techs": [],
    "resources": {"money": 5, "science": 5, "materials": 5},
    "ship_designs": {
        "interceptor": {
            "computer": 0,
            "shield": 0,
            "initiative": 2,
            "hull": 1,
            "cannons": 1,
            "missiles": 0,
            "drives": 1,
            "has_jump_drive": False,
            "interceptor_bays": 0,
        },
        "cruiser": {
            "computer": 1,
            "shield": 0,
            "initiative": 3,
            "hull": 2,
            "cannons": 1,
            "missiles": 0,
            "drives": 1,
            "has_jump_drive": False,
            "interceptor_bays": 0,
        },
        "dreadnought": {
            "computer": 1,
            "shield": 1,
            "initiative": 2,
            "hull": 3,
            "cannons": 2,
            "missiles": 0,
            "drives": 1,
            "has_jump_drive": False,
            "interceptor_bays": 0,
        },
    },
    "has_wormhole_generator": False,
}

ENEMY_PLAYER = {
    "player_id": "P2",
    "color": "blue",
    "known_techs": [],
    "resources": {"money": 3, "science": 3, "materials": 3},
    "ship_designs": copy.deepcopy(BASE_PLAYER["ship_designs"]),
    "has_wormhole_generator": False,
}


def _state_with_hexes(hexes: dict, player_overrides: dict | None = None) -> GameState:
    data = {
        "round": 1,
        "active_player": "P1",
        "players": {
            "P1": copy.deepcopy(BASE_PLAYER),
            "P2": copy.deepcopy(ENEMY_PLAYER),
        },
        "map": {"hexes": hexes},
    }
    if player_overrides:
        for key, value in player_overrides.items():
            data["players"]["P1"][key] = value
    return GameState.from_dict(data)


def test_move_requires_explored_and_wormholes() -> None:
    def build_state(has_wg: bool) -> GameState:
        hexes = {
            "A": {
                "id": "A",
                "ring": 1,
                "wormholes": [0],
                "neighbors": {0: "B"},
                "pieces": {"P1": {"ships": {"interceptor": 1}}},
                "explored": True,
            },
            "B": {
                "id": "B",
                "ring": 1,
                "wormholes": [],
                "neighbors": {3: "A"},
                "pieces": {},
                "explored": True,
            },
        }
        overrides = {"has_wormhole_generator": has_wg}
        return _state_with_hexes(hexes, overrides)

    # Non-existent destination
    state = build_state(False)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {"activations": [{"ship_class": "interceptor", "from": "A", "path": ["A", "C"]}]},
        )

    # Half-wormhole without generator is illegal
    state = build_state(False)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {"activations": [{"ship_class": "interceptor", "from": "A", "path": ["A", "B"]}]},
        )

    # With Wormhole Generator it becomes legal
    state = build_state(True)
    _apply_move_action(
        state,
        "P1",
        {"activations": [{"ship_class": "interceptor", "from": "A", "path": ["A", "B"]}]},
    )
    assert state.map.hexes["B"].pieces["P1"].ships.get("interceptor", 0) == 1


def test_movement_points_stack_with_drives() -> None:
    hexes = {
        "H1": {"id": "H1", "ring": 1, "wormholes": [1], "neighbors": {1: "H2"}, "pieces": {"P1": {"ships": {"cruiser": 1}}}},
        "H2": {
            "id": "H2",
            "ring": 1,
            "wormholes": [4, 1],
            "neighbors": {4: "H1", 1: "H3"},
            "pieces": {},
        },
        "H3": {
            "id": "H3",
            "ring": 1,
            "wormholes": [4, 1],
            "neighbors": {4: "H2", 1: "H4"},
            "pieces": {},
        },
        "H4": {
            "id": "H4",
            "ring": 1,
            "wormholes": [4, 1],
            "neighbors": {4: "H3", 1: "H5"},
            "pieces": {},
        },
        "H5": {
            "id": "H5",
            "ring": 1,
            "wormholes": [4],
            "neighbors": {4: "H4"},
            "pieces": {},
        },
    }
    overrides = {
        "ship_designs": {
            **copy.deepcopy(BASE_PLAYER["ship_designs"]),
            "cruiser": {
                **copy.deepcopy(BASE_PLAYER["ship_designs"]["cruiser"]),
                "drives": 4,
            },
        }
    }
    state = _state_with_hexes(hexes, overrides)
    _apply_move_action(
        state,
        "P1",
        {"activations": [{"ship_class": "cruiser", "from": "H1", "path": ["H1", "H2", "H3", "H4", "H5"]}]},
    )
    assert "cruiser" not in state.map.hexes["H1"].pieces["P1"].ships
    assert state.map.hexes["H5"].pieces["P1"].ships.get("cruiser", 0) == 1

    state = _state_with_hexes(hexes, overrides)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {
                "activations": [
                    {
                        "ship_class": "cruiser",
                        "from": "H1",
                        "path": ["H1", "H2", "H3", "H4", "H5", "H4"],
                    }
                ]
            },
        )


def test_pinning_on_exit_and_entry() -> None:
    contested_hexes = {
        "Start": {
            "id": "Start",
            "ring": 1,
            "wormholes": [1],
            "neighbors": {1: "Safe"},
            "pieces": {
                "P1": {"ships": {"interceptor": 2}},
                "P2": {"ships": {"interceptor": 1}},
            },
        },
        "Safe": {"id": "Safe", "ring": 1, "wormholes": [4], "neighbors": {4: "Start"}, "pieces": {}},
    }
    state = _state_with_hexes(contested_hexes)
    # Moving the first interceptor is legal
    _apply_move_action(
        state,
        "P1",
        {"activations": [{"ship_class": "interceptor", "from": "Start", "path": ["Start", "Safe"]}]},
    )
    # The second attempt should fail because it would leave the enemy unpinned
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {"activations": [{"ship_class": "interceptor", "from": "Start", "path": ["Start", "Safe"]}]},
        )

    # Entry pinning: cannot move through a contested middle hex without leaving ships behind
    hexes = {
        "Start": {
            "id": "Start",
            "ring": 1,
            "wormholes": [1],
            "neighbors": {1: "Mid"},
            "pieces": {"P1": {"ships": {"interceptor": 1}}},
        },
        "Mid": {
            "id": "Mid",
            "ring": 1,
            "wormholes": [4, 1],
            "neighbors": {4: "Start", 1: "End"},
            "pieces": {"P2": {"ships": {"interceptor": 1}}},
        },
        "End": {"id": "End", "ring": 1, "wormholes": [4], "neighbors": {4: "Mid"}, "pieces": {}},
    }
    state = _state_with_hexes(hexes)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {"activations": [{"ship_class": "interceptor", "from": "Start", "path": ["Start", "Mid", "End"]}]},
        )
    # Illegal movement does not change the board state
    assert state.map.hexes["Start"].pieces["P1"].ships.get("interceptor", 0) == 1


def test_gcds_blocks_through_traffic() -> None:
    hexes = {
        "A": {
            "id": "A",
            "ring": 1,
            "wormholes": [1],
            "neighbors": {1: "Center"},
            "pieces": {"P1": {"ships": {"cruiser": 1}}},
        },
        "Center": {
            "id": "Center",
            "ring": 0,
            "wormholes": [4, 1],
            "neighbors": {4: "A", 1: "C"},
            "pieces": {},
            "has_gcds": True,
        },
        "C": {
            "id": "C",
            "ring": 1,
            "wormholes": [4],
            "neighbors": {4: "Center"},
            "pieces": {},
        },
    }
    overrides = {
        "ship_designs": {
            **copy.deepcopy(BASE_PLAYER["ship_designs"]),
            "cruiser": {
                **copy.deepcopy(BASE_PLAYER["ship_designs"]["cruiser"]),
                "drives": 2,
            },
        }
    }
    state = _state_with_hexes(hexes, overrides)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {"activations": [{"ship_class": "cruiser", "from": "A", "path": ["A", "Center", "C"]}]},
        )
    assert state.map.hexes["A"].pieces["P1"].ships.get("cruiser", 0) == 1

    hexes["Center"]["has_gcds"] = False
    state = _state_with_hexes(hexes, overrides)
    _apply_move_action(
        state,
        "P1",
        {"activations": [{"ship_class": "cruiser", "from": "A", "path": ["A", "Center", "C"]}]},
    )
    assert state.map.hexes["C"].pieces["P1"].ships.get("cruiser", 0) == 1


def test_jump_drive_once_per_activation() -> None:
    overrides = {
        "ship_designs": {
            **copy.deepcopy(BASE_PLAYER["ship_designs"]),
            "interceptor": {
                **copy.deepcopy(BASE_PLAYER["ship_designs"]["interceptor"]),
                "drives": 0,
                "has_jump_drive": True,
            },
        }
    }
    hexes = {
        "A": {
            "id": "A",
            "ring": 1,
            "wormholes": [],
            "neighbors": {1: "B"},
            "pieces": {"P1": {"ships": {"interceptor": 1}}},
        },
        "B": {
            "id": "B",
            "ring": 1,
            "wormholes": [],
            "neighbors": {4: "A", 1: "C"},
            "pieces": {},
        },
        "C": {
            "id": "C",
            "ring": 1,
            "wormholes": [],
            "neighbors": {4: "B"},
            "pieces": {},
        },
    }
    state = _state_with_hexes(hexes, overrides)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {
                "activations": [
                    {"ship_class": "interceptor", "from": "A", "path": ["A", "B", "C"]}
                ]
            },
        )
    # Ship should remain at the origin because the move failed entirely
    assert state.map.hexes["A"].pieces["P1"].ships.get("interceptor", 0) == 1

    state = _state_with_hexes(hexes, overrides)
    _apply_move_action(
        state,
        "P1",
        {
            "activations": [
                {"ship_class": "interceptor", "from": "A", "path": ["A", "B"]},
                {"ship_class": "interceptor", "from": "B", "path": ["B", "C"]},
            ]
        },
    )
    assert state.map.hexes["C"].pieces["P1"].ships.get("interceptor", 0) == 1


def test_warp_portal_adjacency() -> None:
    hexes = {
        "P1": {
            "id": "P1",
            "ring": 3,
            "wormholes": [],
            "neighbors": {},
            "pieces": {"P1": {"ships": {"cruiser": 1}}},
            "has_warp_portal": True,
        },
        "P2": {
            "id": "P2",
            "ring": 3,
            "wormholes": [],
            "neighbors": {},
            "pieces": {},
            "has_warp_portal": True,
        },
    }
    state = _state_with_hexes(hexes)
    _apply_move_action(
        state,
        "P1",
        {"activations": [{"ship_class": "cruiser", "from": "P1", "path": ["P1", "P2"]}]},
    )
    assert state.map.hexes["P2"].pieces["P1"].ships.get("cruiser", 0) == 1


def test_interceptor_bay_flow() -> None:
    overrides = {
        "ship_designs": {
            **copy.deepcopy(BASE_PLAYER["ship_designs"]),
            "cruiser": {
                **copy.deepcopy(BASE_PLAYER["ship_designs"]["cruiser"]),
                "drives": 1,
                "interceptor_bays": 2,
            },
        }
    }
    hexes = {
        "S": {
            "id": "S",
            "ring": 1,
            "wormholes": [1],
            "neighbors": {1: "D"},
            "pieces": {"P1": {"ships": {"cruiser": 1, "interceptor": 2}}},
        },
        "D": {
            "id": "D",
            "ring": 1,
            "wormholes": [4, 1],
            "neighbors": {4: "S", 1: "E"},
            "pieces": {},
        },
        "E": {
            "id": "E",
            "ring": 1,
            "wormholes": [4],
            "neighbors": {4: "D"},
            "pieces": {},
        },
    }
    state = _state_with_hexes(hexes, overrides)
    _apply_move_action(
        state,
        "P1",
        {
            "activations": [
                {
                    "ship_class": "cruiser",
                    "from": "S",
                    "path": ["S", "D"],
                    "bay": {"interceptors": 2},
                },
                {
                    "ship_class": "interceptor",
                    "from": "D",
                    "path": ["D", "E"],
                },
            ]
        },
    )
    assert state.map.hexes["E"].pieces["P1"].ships.get("interceptor", 0) == 1
    assert state.map.hexes["D"].pieces["P1"].ships.get("interceptor", 0) == 1

    # Carrying interceptors does not help bypass pinning
    contested = copy.deepcopy(hexes)
    contested["D"]["pieces"] = {"P2": {"ships": {"interceptor": 1}}}
    state = _state_with_hexes(contested, overrides)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {
                "activations": [
                    {
                        "ship_class": "cruiser",
                        "from": "S",
                        "path": ["S", "D", "E"],
                        "bay": {"interceptors": 2},
                    }
                ]
            },
        )
    # State remains unchanged because the illegal move was rejected
    assert state.map.hexes["S"].pieces["P1"].ships.get("interceptor", 0) == 2


def test_reaction_move_single_activation_only() -> None:
    hexes = {
        "A": {
            "id": "A",
            "ring": 1,
            "wormholes": [1],
            "neighbors": {1: "B"},
            "pieces": {"P1": {"ships": {"interceptor": 1}}},
        },
        "B": {
            "id": "B",
            "ring": 1,
            "wormholes": [4],
            "neighbors": {4: "A"},
            "pieces": {},
        },
    }
    state = _state_with_hexes(hexes)
    with pytest.raises(ValueError):
        _apply_move_action(
            state,
            "P1",
            {
                "is_reaction": True,
                "activations": [
                    {"ship_class": "interceptor", "from": "A", "path": ["A", "B"]},
                    {"ship_class": "interceptor", "from": "B", "path": ["B", "A"]},
                ],
            },
        )

    state = _state_with_hexes(hexes)
    _apply_move_action(
        state,
        "P1",
        {"is_reaction": True, "activations": [{"ship_class": "interceptor", "from": "A", "path": ["A", "B"]}]},
    )
    assert state.map.hexes["B"].pieces["P1"].ships.get("interceptor", 0) == 1
