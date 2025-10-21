import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from eclipse_ai import recommend
    from eclipse_ai.board_parser import parse_board
    from eclipse_ai.game_models import Action, ActionType, GameState
    from eclipse_ai.image_ingestion import load_and_calibrate
    from eclipse_ai.search_policy import _forward_model
    from eclipse_ai.state_assembler import assemble_state
    from eclipse_ai.tech_parser import parse_tech
except Exception:  # pragma: no cover - fallback for installed package
    from eclipse_ai import recommend
    from eclipse_ai.board_parser import parse_board
    from eclipse_ai.game_models import Action, ActionType, GameState
    from eclipse_ai.image_ingestion import load_and_calibrate
    from eclipse_ai.search_policy import _forward_model
    from eclipse_ai.state_assembler import assemble_state
    from eclipse_ai.tech_parser import parse_tech


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_BOARD = MODULE_DIR / "board.jpg"
DEFAULT_TECH = MODULE_DIR / "tech.jpg"
RESOURCE_KEYS = ("money", "science", "materials")


ORION_ROUND1_STATE: Dict[str, Any] = {
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


DEFAULT_CASE = "orion_round1"
BUILTIN_CASES: Dict[str, Dict[str, Any]] = {DEFAULT_CASE: ORION_ROUND1_STATE}


def _load_case_state(case_name: str) -> GameState:
    normalized = case_name.strip().lower()
    if normalized not in BUILTIN_CASES:
        available = ", ".join(sorted(BUILTIN_CASES))
        raise ValueError(
            f"Unknown test case {case_name!r}. Available cases: {available}"
        )
    return GameState.from_dict(copy.deepcopy(BUILTIN_CASES[normalized]))


def _normalize_path(raw: Optional[str]) -> Optional[Path]:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _load_state_from_json(path: Path) -> GameState:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "state" in data and isinstance(data["state"], dict):
        data = data["state"]
    if not isinstance(data, dict):
        raise ValueError("State file must contain a JSON object")
    return GameState.from_dict(data)


def _load_state_from_images(board_path: Path, tech_path: Path) -> tuple[GameState, Any, Any]:
    board_img = load_and_calibrate(str(board_path))
    tech_img = load_and_calibrate(str(tech_path))
    map_state = parse_board(board_img)
    tech_display = parse_tech(tech_img)
    state = assemble_state(map_state, tech_display, None, None)
    return state, board_img, tech_img


def _load_initial_state(
    state_path: Optional[Path],
    board_path: Optional[Path],
    tech_path: Optional[Path],
    case_name: Optional[str],
) -> tuple[GameState, Optional[Any], Optional[Any]]:
    if case_name and case_name.strip().lower() != "none":
        return _load_case_state(case_name), None, None
    if state_path is not None:
        return _load_state_from_json(state_path), None, None
    if board_path is None or tech_path is None:
        return _load_case_state(DEFAULT_CASE), None, None
    return _load_state_from_images(board_path, tech_path)


def _summarize_player_positions(state: GameState, player_id: str) -> Dict[str, Dict[str, Any]]:
    if not player_id or player_id not in getattr(state, "players", {}):
        return {}
    summary: Dict[str, Dict[str, Any]] = {}
    for hex_id, hex_obj in getattr(state.map, "hexes", {}).items():
        pieces = hex_obj.pieces.get(player_id) if hex_obj and hex_obj.pieces else None
        if not pieces:
            continue
        entry: Dict[str, Any] = {}
        if getattr(pieces, "ships", None):
            ships = {cls: int(count) for cls, count in pieces.ships.items() if count}
            if ships:
                entry["ships"] = ships
        starbase = int(getattr(pieces, "starbase", 0) or 0)
        if starbase:
            entry["starbase"] = starbase
        discs = int(getattr(pieces, "discs", 0) or 0)
        if discs:
            entry["discs"] = discs
        cubes = getattr(pieces, "cubes", {}) or {}
        cube_summary = {color: int(count) for color, count in cubes.items() if count}
        if cube_summary:
            entry["cubes"] = cube_summary
        discovery = int(getattr(pieces, "discovery", 0) or 0)
        if discovery:
            entry["discovery"] = discovery
        if entry:
            summary[str(hex_id)] = entry
    return summary


def _summarize_resources(state: GameState, player_id: str) -> Dict[str, int]:
    player = getattr(state, "players", {}).get(player_id) if player_id else None
    if not player:
        return {}
    resources = getattr(player, "resources", None)
    if resources is None:
        return {}
    return {key: int(getattr(resources, key, 0) or 0) for key in RESOURCE_KEYS}


def _diff_positions(
    before: Dict[str, Dict[str, Any]],
    after: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    diff: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for hex_id in sorted(set(before) | set(after)):
        b = before.get(hex_id, {})
        a = after.get(hex_id, {})
        if b != a:
            diff[hex_id] = {"before": b, "after": a}
    return diff


def _apply_plan_steps(
    base_state: GameState,
    player_id: str,
    steps: Sequence[Dict[str, Any]],
) -> GameState:
    working = copy.deepcopy(base_state)
    if not player_id:
        return working
    for step in steps:
        action_key = step.get("action")
        if not action_key:
            continue
        payload = step.get("payload") or {}
        try:
            action_type = ActionType(action_key)
        except ValueError:
            key_upper = str(action_key).upper()
            if key_upper in ActionType.__members__:
                action_type = ActionType.__members__[key_upper]
            else:
                raise ValueError(f"Unknown action type: {action_key!r}")
        action = Action(type=action_type, payload=payload)
        working = _forward_model(working, player_id, action)
    return working


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument("--tech", default=str(DEFAULT_TECH))
    parser.add_argument("--state", help="Optional JSON GameState file to bypass image parsing.")
    parser.add_argument(
        "--case",
        default=DEFAULT_CASE,
        help=(
            "Built-in test case to run (default: orion_round1). "
            "Use --case none to disable and rely on --state/--board/--tech."
        ),
    )
    parser.add_argument("--sims", type=int, default=200)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument(
        "--output",
        help="Optional path to write the summarized test result JSON.",
    )
    args = parser.parse_args()

    board_path = _normalize_path(args.board)
    tech_path = _normalize_path(args.tech)
    state_path = _normalize_path(args.state) if args.state else None

    base_state, board_img, tech_img = _load_initial_state(
        state_path,
        board_path,
        tech_path,
        args.case,
    )
    planner_state = copy.deepcopy(base_state)

    manual_inputs = {
        "_planner": {
            "simulations": args.sims,
            "depth": args.depth,
            "risk_aversion": 0.25,
        }
    }

    result = recommend(
        None,
        None,
        prior_state=planner_state,
        manual_inputs=manual_inputs,
        top_k=args.topk,
    )

    active_player = result.get("active_player") or getattr(base_state, "active_player", "")
    initial_positions = _summarize_player_positions(base_state, active_player)
    initial_resources = _summarize_resources(base_state, active_player)

    enriched_plans = []
    for plan in (result.get("plans") or [])[: args.topk]:
        plan_copy = dict(plan)
        steps = plan.get("steps") or []
        try:
            sequential_state = _apply_plan_steps(base_state, active_player, steps)
        except Exception as exc:
            plan_copy["result_state"] = {"error": str(exc)}
        else:
            final_positions = _summarize_player_positions(sequential_state, active_player)
            final_resources = _summarize_resources(sequential_state, active_player)
            resource_delta = {
                key: final_resources.get(key, 0) - initial_resources.get(key, 0)
                for key in RESOURCE_KEYS
            } if initial_resources else {}
            plan_copy["result_state"] = {
                "player_positions": final_positions,
                "resources": final_resources,
                "position_deltas": _diff_positions(initial_positions, final_positions),
            }
            if resource_delta:
                plan_copy["result_state"]["resource_delta"] = resource_delta
        enriched_plans.append(plan_copy)

    display_count = min(len(enriched_plans), 3)
    summary: Dict[str, Any] = {
        "round": result.get("round", getattr(base_state, "round", None)),
        "active_player": active_player,
        "plans": enriched_plans[:display_count],
        "enemy_posteriors": result.get("enemy_posteriors", {}),
        "expected_bags": result.get("expected_bags", {}),
    }
    if args.case and args.case.strip().lower() != "none":
        summary["case"] = args.case
    if initial_positions:
        summary["initial_player_positions"] = initial_positions
    if initial_resources:
        summary["initial_player_resources"] = initial_resources
    if board_img is not None and getattr(board_img, "metadata", None):
        summary["board_metadata"] = board_img.metadata
    if tech_img is not None and getattr(tech_img, "metadata", None):
        summary["tech_metadata"] = tech_img.metadata

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
