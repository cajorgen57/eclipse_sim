"""Main Eclipse AI planner entry point and recommendation API.

This module provides the primary `recommend()` function for generating action
recommendations in Eclipse Second Dawn. It orchestrates:
- State assembly from images or JSON
- Belief state tracking for hidden information
- PW-MCTS planning for action selection
- Opponent modeling and threat analysis
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from types import SimpleNamespace

from . import state_assembler
from .game_models import GameState
from .overlay import plan_overlays
from .forward_model import Plan, PlanStep
from .state_assembler import assemble_state
from .uncertainty import BeliefState

# -----------------------------
# Helpers
# -----------------------------

def _signals_from_tech(name: str) -> List[str]:
    s = name.lower()
    sigs: List[str] = []
    if "plasma" in s: sigs.append("plasma")
    if "positron" in s: sigs.append("positron")
    if "fusion" in s or "drive" in s: sigs.append("drive")
    if "gauss" in s: sigs.append("gauss")
    if "shield" in s: sigs.append("shields")
    if "missile" in s: sigs.append("missiles")
    return sigs

def _enemy_posteriors_all(belief: BeliefState, rho: float = 0.9) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for pid in belief.hmm_by_player.keys() | belief.obs_history_by_player.keys():
        out[pid] = belief.enemy_posterior(pid, rho=rho)
    return out

# -----------------------------
# Public API for other modules (used by eclipse_ai.cli)
# -----------------------------

def build_state_from_args(args) -> GameState:
    """
    Build and return a GameState from --state or --board/--tech.
    If nothing is provided, try round_flow.new_game(); otherwise error clearly.
    """
    # 1) Prior state via --state (path or inline JSON)
    state_arg = getattr(args, "state", None)
    if state_arg:
        p = Path(state_arg)
        text = p.read_text(encoding="utf-8") if p.exists() else state_arg
        prior_state_payload = json.loads(text)
        return state_assembler.from_dict(prior_state_payload)

    # 2) Fallback: brand-new game from game_setup
    try:
        from .game_setup import new_game
        num_players = int(getattr(args, "num_players", 4))
        seed = int(getattr(args, "seed", 0)) if hasattr(args, "seed") else None
        return new_game(num_players=num_players, seed=seed)
    except Exception:
        raise RuntimeError(
            "No --state provided. "
            "Please provide --state <json|path> with a game state."
        )

# -----------------------------
# Main recommendable API
# -----------------------------

def recommend(
    board_image_path: Optional[str] = None,  # DEPRECATED: Use prior_state instead
    tech_image_path: Optional[str] = None,    # DEPRECATED: Use prior_state instead
    prior_state: Optional[Union[GameState, Dict[str, Any]]] = None,
    manual_inputs: Optional[Dict[str, Any]] = None,
    top_k: int = 5,
    planner: str = "pw_mcts",  # PW-MCTS is the default recommended planner
    pw_alpha: float = 0.65,     # Increased from 0.6 for better exploration
    pw_c: float = 1.8,          # Increased from 1.5 for more progressive widening
    prior_scale: float = 0.6,   # Increased from 0.5 to trust heuristics more
    seed: int = 0,
) -> Dict[str, Any]:
    """
    Main orchestration. Returns top plans, overlays, and belief summaries.
    
    Args:
        board_image_path: DEPRECATED - no longer supported
        tech_image_path: DEPRECATED - no longer supported
        prior_state: GameState or dict to use as starting state (required)
        manual_inputs: Configuration overrides
        top_k: Number of top plans to return
        planner: Planner to use (only "pw_mcts" supported)
        pw_alpha: PW-MCTS alpha parameter
        pw_c: PW-MCTS exploration constant
        prior_scale: Scale for prior heuristics
        seed: Random seed
    
    Returns:
        Dict with 'plans', 'overlays', 'belief', 'expected_bags'
    """
    # Build/assemble state
    if board_image_path or tech_image_path:
        raise ValueError("Image-based API is no longer supported. Use prior_state with a GameState or dict.")
    
    if prior_state is None:
        raise ValueError("prior_state is required. Create a game with game_setup.new_game().")
    
    state = prior_state if isinstance(prior_state, GameState) else state_assembler.from_dict(prior_state)

    # 2) Apply targeted overrides (resources, bags, belief hints, planner cfg passthrough, etc.)
    if manual_inputs:
        state = state_assembler.apply_overrides(state, dict(manual_inputs))  # copy to avoid caller mutation

    # 3) Belief state: restore or initialize
    belief_dict = (manual_inputs or {}).get("belief_state") or (manual_inputs or {}).get("belief")
    belief = BeliefState.from_dict(belief_dict) if isinstance(belief_dict, dict) else BeliefState()

    # Ensure particle filters for each bag
    for bag_id, bag in getattr(state, "bags", {}).items():
        belief.ensure_bag(bag_id, bag, particles=512)

    # Observe tech signals for enemies
    for pid, p in (getattr(state, "players", {}) or {}).items():
        if pid == "you":
            continue
        for tech in getattr(p, "known_techs", []):
            for sig in _signals_from_tech(tech):
                belief.observe_enemy_signal(pid, sig)

    if "blue" in (getattr(state, "players", {}) or {}):
        for tech in getattr(state.tech_display, "available", []):
            for sig in _signals_from_tech(tech):
                belief.observe_enemy_signal("blue", sig)

    # 4) Plan
    planner_args_in = (manual_inputs or {}).get("_planner", {})
    planner_args = dict(planner_args_in) if isinstance(planner_args_in, dict) else {}
    simulations = int(planner_args.get("simulations", 600))      # Increased from 400 for better quality
    depth = int(planner_args.get("depth", 3))                     # Increased from 2 for deeper lookahead
    planner_choice = str(
        planner_args.get("type")
        or planner_args.get("planner")
        or planner
    ).lower()

    # Use PW-MCTS planner (only supported planner)
    from .planners.mcts_pw import PW_MCTSPlanner

    pw_alpha_val = float(planner_args.get("pw_alpha", pw_alpha))
    pw_c_val = float(planner_args.get("pw_c", pw_c))
    prior_scale_val = float(planner_args.get("prior_scale", prior_scale))
    seed_val = int(planner_args.get("seed", seed))

    planner_impl = PW_MCTSPlanner(
        pw_alpha=pw_alpha_val,
        pw_c=pw_c_val,
        prior_scale=prior_scale_val,
        sims=simulations,
        depth=depth,
        seed=seed_val,
    )
    
    out_plans: List[Dict[str, Any]] = []
    macro_actions = planner_impl.plan(state)
    for idx, macro in enumerate(macro_actions[: max(0, top_k)]):
        if macro is None:
            continue
        details = {
            "planner": "pw_mcts",
            "prior": float(getattr(macro, "prior", 0.0)),
            "rank": idx + 1,
        }
        out_plans.append({
            "score": None,
            "risk": None,
            "steps": [
                {
                    "action": getattr(macro, "type", None),
                    "payload": dict(getattr(macro, "payload", {})),
                    "score": None,
                    "risk": None,
                    "details": details,
                }
            ],
            "state_summary": {},
            "overlays": [],
        })

    enemy_posts = _enemy_posteriors_all(belief, rho=float((manual_inputs or {}).get("belief_rho", 0.9)))

    return {
        "round": state.round,
        "active_player": state.active_player,
        "plans": out_plans,
        "belief": belief.to_dict(include_particles=False),
        "enemy_posteriors": enemy_posts,
        "expected_bags": {bid: belief.expected_bag(bid) for bid in getattr(state, "bags", {}).keys()},
    }


def _load_json_resource(resource: Optional[str]) -> Optional[Any]:
    """Load JSON content from a path or inline string."""
    if not resource:
        return None
    candidate = Path(resource)
    try:
        text = candidate.read_text(encoding="utf-8") if candidate.exists() else resource
    except OSError as exc:  # pragma: no cover - passthrough for filesystem errors
        raise RuntimeError(f"Failed to read resource {resource!r}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload for {resource!r}") from exc


def main() -> None:
    """CLI entry point for running planners against a reconstructed state."""
    parser = argparse.ArgumentParser(description="Run Eclipse AI planner recommendations")
    parser.add_argument("--board", dest="board", default=None, help="Path to a calibrated board image")
    parser.add_argument("--tech", dest="tech", default=None, help="Path to a calibrated tech display image")
    parser.add_argument("--state", dest="state", default=None, help="Path to a JSON state file or inline JSON string")
    parser.add_argument("--manual", dest="manual", default=None, help="Manual override payload (path or JSON string)")
    parser.add_argument("--topk", dest="topk", type=int, default=5, help="Number of top plans to return")
    parser.add_argument("--sims", dest="sims", type=int, default=600, help="Simulation count for the planner (increased default for better quality)")
    parser.add_argument("--depth", dest="depth", type=int, default=3, help="Depth limit for planner rollouts (increased default for better lookahead)")
    parser.add_argument(
        "--planner",
        choices=["pw_mcts"],
        default="pw_mcts",
        help="Planner backend to use (only pw_mcts is supported)",
    )
    parser.add_argument("--pw-alpha", dest="pw_alpha", type=float, default=0.65, help="Progressive widening alpha (exploration rate)")
    parser.add_argument("--pw-c", dest="pw_c", type=float, default=1.8, help="Progressive widening constant (action diversity)")
    parser.add_argument("--prior-scale", dest="prior_scale", type=float, default=0.6, help="Prior scale factor (heuristic trust)")
    parser.add_argument("--seed", dest="seed", type=int, default=0, help="Random seed for PW-MCTS")
    parser.add_argument(
        "--belief-rho",
        dest="belief_rho",
        type=float,
        default=0.9,
        help="Belief smoothing coefficient",
    )
    parser.add_argument("--output", dest="output", default=None, help="Optional path to write JSON output")

    args = parser.parse_args()

    prior_state_payload = _load_json_resource(args.state)
    manual_inputs_payload = _load_json_resource(args.manual)
    manual_inputs_dict: Dict[str, Any] = dict(manual_inputs_payload or {})

    planner_cfg: Dict[str, Any] = dict(manual_inputs_dict.get("_planner", {}))
    planner_cfg.update(
        {
            "simulations": args.sims,
            "depth": args.depth,
            "type": args.planner,
            "pw_alpha": args.pw_alpha,
            "pw_c": args.pw_c,
            "prior_scale": args.prior_scale,
            "seed": args.seed,
        }
    )
    manual_inputs_dict["_planner"] = planner_cfg
    manual_inputs_dict["belief_rho"] = args.belief_rho

    result = recommend(
        args.board,
        args.tech,
        prior_state=prior_state_payload,
        manual_inputs=manual_inputs_dict,
        top_k=args.topk,
        planner=args.planner,
        pw_alpha=args.pw_alpha,
        pw_c=args.pw_c,
        prior_scale=args.prior_scale,
        seed=args.seed,
    )

    output_text = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")
    else:
        print(output_text)


if __name__ == "__main__":
    main()




