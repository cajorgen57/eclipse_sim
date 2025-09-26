from eclipse_ai.rules_engine import legal_actions
from eclipse_ai.types import ActionType, GameState


def _orion_turn_one_state() -> GameState:
    """Construct a minimal, rules-respecting two-player opening state."""

    state_dict = {
        "round": 1,
        "active_player": "orion",
        "players": {
            "orion": {
                "player_id": "orion",
                "color": "black",
                # Orion starts with strong materials economy and modest science.
                "resources": {"money": 3, "science": 3, "materials": 5},
                # Basic interceptor design matching the reference ship sheet.
                "ship_designs": {
                    "interceptor": {
                        "computer": 1,
                        "shield": 1,
                        "initiative": 2,
                        "hull": 1,
                        "cannons": 1,
                        "missiles": 0,
                        "drive": 1,
                    }
                    "cruiser": {
                        "computer": 1,
                        "shield": 1,
                        "initiative": 3,
                        "hull": 1,
                        "cannons": 1,
                        "missiles": 0,
                        "drive": 1,
                    }
                },
                "known_techs": [],
            },
            "hydran": {
                "player_id": "hydran",
                "color": "blue",
                "resources": {"money": 2, "science": 5, "materials": 2},
                "known_techs": [],
            },
        },
        "map": {
            "hexes": {
                # Orion home system with occupied planets and starting fleet.
                "232": {
                    "id": "232",
                    "ring": 2,
                    "planets": [
                        {"type": "brown", "colonized_by": "orion"},
                        {"type": "pink", "colonized_by": "orion"},
                    ],
                    "pieces": {
                        "orion": {
                            "ships": {"cruiser": 1},
                            "starbase": 0,
                            "discs": 1,
                            "cubes": {"yellow": 2, "blue": 1},
                            "discovery": 0,
                        }
                    },
                    "ancients": 0,
                    "monolith": False,
                },
                # Adjacent unexplored sector with open planets to encourage influence/explore.
   
                # Rival home system to show enemy presence.
                "224": {
                    "id": "224",
                    "ring": 2,
                    "planets": [
                        {"type": "yellow", "colonized_by": "hydran"},
                        {"type": "brown", "colonized_by": None},
                    ],
                    "pieces": {
                        "hydran": {
                            "ships": {"interceptor": 1},
                            "starbase": 0,
                            "discs": 1,
                            "cubes": {"pink": 2, "orange": 1},
                            "discovery": 0,
                        }
                    },
                    "ancients": 0,
                    "monolith": False,
                },
            }
        },
        # Tier I techs are available and affordable with current science.
        "tech_display": {
            "available": ["Plasma Cannon I", "Fusion Drive I", "Advanced Mining"],
            "tier_counts": {"I": 6, "II": 0, "III": 0},
        },
        # First ring bag seeded so explore actions are legal.
        "bags": {"R1": {"unknown": 6}},
    }
    return GameState.from_dict(state_dict)


def test_orion_turn_one_action_suite():
    state = _orion_turn_one_state()
    actions = legal_actions(state, "orion")
    action_types = {a.type for a in actions}

    # Ensure the core first-turn options are present.
    assert ActionType.PASS in action_types
    assert ActionType.EXPLORE in action_types
    assert ActionType.BUILD in action_types
    assert ActionType.RESEARCH in action_types
    assert ActionType.INFLUENCE in action_types

    # Confirm the dataclass conversion preserved nested structures.
    assert state.players["orion"].resources.materials == 3
    assert state.map.hexes["000"].pieces["orion"].ships["interceptor"] == 2
