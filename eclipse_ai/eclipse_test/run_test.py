import os, sys, json, argparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    from eclipse_ai import recommend
    from eclipse_ai.game_models import GameState
except Exception:
    # fallback: try installed package
    from eclipse_ai import recommend
    from eclipse_ai.game_models import GameState


ORION_ROUND1_STATE = {
    "round": 1,
    "active_player": "orion",
    "players": {
        "orion": {
            "player_id": "orion",
            "color": "purple",
            "known_techs": ["Gauss Shield"],
            "resources": {"money": 2, "science": 1, "materials": 5},
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 1,
                    "initiative": 2,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
                "cruiser": {
                    "computer": 1,
                    "shield": 1,
                    "initiative": 3,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
            },
        },
        "terran": {
            "player_id": "terran",
            "color": "orange",
            "known_techs": ["Fusion Drive"],
            "resources": {"money": 3, "science": 2, "materials": 2},
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
        "mechanema": {
            "player_id": "mechanema",
            "color": "teal",
            "known_techs": ["Positron Computer"],
            "resources": {"money": 1, "science": 3, "materials": 1},
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
        "magellan": {
            "player_id": "magellan",
            "color": "green",
            "known_techs": ["Ion Thruster"],
            "resources": {"money": 1, "science": 1, "materials": 3},
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
        "rho_indi": {
            "player_id": "rho_indi",
            "color": "yellow",
            "known_techs": ["Gluon Computer"],
            "resources": {"money": 4, "science": 0, "materials": 1},
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
    },
    "map": {
        "hexes": {
            "230": {
                "id": "230",
                "ring": 1,
                "wormholes": [0, 3, 5],
                "planets": [
                    {"type": "orange", "colonized_by": "orion"},
                    {"type": "pink", "colonized_by": "orion"},
                    {"type": "brown", "colonized_by": "orion"},
                ],
                "pieces": {
                    "orion": {
                        "ships": {"interceptor": 0, "cruiser": 1},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"orange": 1, "pink": 1, "brown": 1},
                    }
                },
            },
            "terran_home": {
                "id": "terran_home",
                "ring": 1,
                "wormholes": [1, 4],
                "planets": [
                    {"type": "orange", "colonized_by": "terran"},
                    {"type": "pink", "colonized_by": "terran"},
                    {"type": "brown", "colonized_by": "terran"},
                ],
                "pieces": {
                    "terran": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"orange": 1, "pink": 1, "brown": 1},
                    }
                },
            },
            "mechanema_home": {
                "id": "mechanema_home",
                "ring": 1,
                "wormholes": [0, 2, 5],
                "planets": [
                    {"type": "pink", "colonized_by": "mechanema"},
                    {"type": "pink", "colonized_by": "mechanema"},
                    {"type": "brown", "colonized_by": "mechanema"},
                ],
                "pieces": {
                    "mechanema": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"pink": 2, "brown": 1},
                    }
                },
            },
            "magellan_home": {
                "id": "magellan_home",
                "ring": 1,
                "wormholes": [1, 3, 4],
                "planets": [
                    {"type": "brown", "colonized_by": "magellan"},
                    {"type": "brown", "colonized_by": "magellan"},
                    {"type": "orange", "colonized_by": "magellan"},
                ],
                "pieces": {
                    "magellan": {
                        "ships": {"interceptor": 2},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"brown": 2, "orange": 1},
                    }
                },
            },
            "rho_home": {
                "id": "rho_home",
                "ring": 1,
                "wormholes": [0, 2, 4],
                "planets": [
                    {"type": "orange", "colonized_by": "rho_indi"},
                    {"type": "orange", "colonized_by": "rho_indi"},
                    {"type": "pink", "colonized_by": None},
                ],
                "pieces": {
                    "rho_indi": {
                        "ships": {"cruiser": 1},
                        "starbase": 0,
                        "discs": 1,
                        "cubes": {"orange": 2},
                    }
                },
            },
            "outer_frontier": {
                "id": "outer_frontier",
                "ring": 2,
                "wormholes": [1, 4],
                "explored": False,
                "planets": [
                    {"type": "orange", "colonized_by": None},
                    {"type": "pink", "colonized_by": None},
                    {"type": "brown", "colonized_by": None},
                ],
                "pieces": {},
            },
        }
    },
    "tech_display": {
        "available": [
            "Plasma Cannon I",
            "Fusion Drive I",
            "Advanced Mining",
            "Positron Computer",
            "Gauss Shield",
            "Neutron Absorber",
        ],
        "tier_counts": {"I": 6, "II": 4, "III": 2},
    },
    "bags": {
        "R1": {"unknown": 5},
        "R2": {"unknown": 4},
    },
}

p = argparse.ArgumentParser()
p.add_argument("--board", default="board.jpg")
p.add_argument("--tech",  default="tech.jpg")
p.add_argument("--sims",  type=int, default=200)
p.add_argument("--depth", type=int, default=2)
p.add_argument("--topk",  type=int, default=5)
p.add_argument(
    "--output",
    help="Optional path to write the summarized test result JSON."
)
args = p.parse_args()

manual = {"_planner": {"simulations": args.sims, "depth": args.depth, "risk_aversion": 0.25}}
state = GameState.from_dict(ORION_ROUND1_STATE)
out = recommend(args.board, args.tech, prior_state=state, manual_inputs=manual, top_k=args.topk)

summary = {
    "round": out.get("round"),
    "active_player": out.get("active_player"),
    "plans": out.get("plans")[:3],   # show top 3
    "enemy_posteriors": out.get("enemy_posteriors", {}),
    "expected_bags": out.get("expected_bags", {}),
}

if args.output:
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

print(json.dumps(summary, indent=2))
