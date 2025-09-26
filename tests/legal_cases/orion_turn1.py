"""Legality fixtures for the Orion Hegemony opening."""
from __future__ import annotations

from typing import Any, Dict, List


_ORION_TURN1_ROUND1_4P: Dict[str, Any] = {
    "round": 1,
    "active_player": "P1",
    "phase": "ACTION",
    "turn_order": ["P1", "P2", "P3", "P4"],
    "players": {
        "P1": {
            "player_id": "P1",
            "color": "purple",
            "known_techs": ["Gauss Shield", "Neutron Bombs"],
            "resources": {"money": 3, "science": 1, "materials": 5},
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
        "P3": {
            "player_id": "P3",
            "color": "green",
            "known_techs": [],
            "resources": {"money": 3, "science": 1, "materials": 3},
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
        "P4": {
            "player_id": "P4",
            "color": "white",
            "known_techs": [],
            "resources": {"money": 2, "science": 2, "materials": 2},
            "ship_designs": {
                "interceptor": {
                    "computer": 0,
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
            "Sigma": {
                "id": "Sigma",
                "ring": 1,
                "planets": [
                    {"type": "yellow", "colonized_by": "P3"},
                    {"type": "blue", "colonized_by": "P3"},
                ],
                "pieces": {
                    "P3": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 1, "blue": 1},
                    }
                },
            },
            "Hydra": {
                "id": "Hydra",
                "ring": 1,
                "planets": [
                    {"type": "yellow", "colonized_by": "P4"},
                    {"type": "blue", "colonized_by": "P4"},
                ],
                "pieces": {
                    "P4": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"yellow": 1, "blue": 1},
                    }
                },
            },
        }
    },
    "tech_display": {
        "available": ["Plasma Cannon I", "Fusion Drive I", "Advanced Mining"],
        "tier_counts": {"I": 6, "II": 4, "III": 2},
    },
    "bags": {"R1": {"unknown": 4}, "R2": {"unknown": 3}},
}

ORION_TURN1_TEST_CASES: List[Dict[str, Any]] = [
    {
        "state": _ORION_TURN1_ROUND1_4P,
        "player_id": "P1",
        "proposed_action": {
            "action": "Influence",
            "payload": {"hex": "Outer", "income_delta": {"yellow": 1, "blue": 0, "brown": 0}},
        },
        "provenance": "manual/orion_hegemony/round1/action1",
        "expectations": {"should_be_legal": True, "notes": "Influence the richest adjacent neutral hex."},
    }
]
