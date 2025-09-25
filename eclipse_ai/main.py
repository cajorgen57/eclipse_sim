from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
import json
from . import state_assembler, board_parser, tech_parser, image_ingestion, rules_engine, evaluator  # keep existing imports; note: image_injestion file name
from .image_ingestion import load_and_calibrate
from .board_parser import parse_board
from .tech_parser import parse_tech
from .state_assembler import assemble_state
from .search_policy import MCTSPlanner, Plan, PlanStep
from .types import GameState
from .uncertainty import BeliefState
from .overlay import plan_overlays

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
# Public API
# -----------------------------

def recommend(
    board_image_path: Optional[str],
    tech_image_path: Optional[str],
    prior_state: Optional[Union[GameState, Dict[str, Any]]] = None,
    manual_inputs: Optional[Dict[str, Any]] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """Main orchestration. Returns top plans, overlays, and belief summaries."""
    # 1) Build/assemble state
    board_img = tech_img = None
    if prior_state is not None:
        state = prior_state if isinstance(prior_state, GameState) else state_assembler.from_dict(prior_state)
    else:
        board_img = load_and_calibrate(board_image_path) if board_image_path else None
        tech_img = load_and_calibrate(tech_image_path) if tech_image_path else None
        map_state = parse_board(board_img) if board_img is not None else None
        tech_disp = parse_tech(tech_img) if tech_img is not None else None
        state = assemble_state(map_state, tech_disp, None, None)

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
    planner_args = (manual_inputs or {}).get("_planner", {})
    simulations = int(planner_args.get("simulations", 400))
    depth = int(planner_args.get("depth", 2))
    risk_aversion = float(planner_args.get("risk_aversion", 0.25))

    planner = MCTSPlanner(simulations=simulations, risk_aversion=risk_aversion)
    plans = planner.plan(state, state.active_player, depth=depth, top_k=top_k)

    # 5) Package results
    out_plans: List[Dict[str, Any]] = []
    for p in plans:
        steps = [{"action": s.action.type.value, "payload": s.action.payload, "score": float(s.score.expected_vp), "risk": float(s.score.risk)} for s in p.steps]
        out_plans.append({
            "score": float(p.total_score),
            "risk": float(p.risk),
            "steps": steps,
            "overlays": plan_overlays(p)
        })

    enemy_posts = _enemy_posteriors_all(belief, rho=float((manual_inputs or {}).get("belief_rho", 0.9)))

    return {
        "round": state.round,
        "active_player": state.active_player,
        "plans": out_plans,
        "belief": belief.to_dict(include_particles=False),
        "enemy_posteriors": enemy_posts,
        "expected_bags": {bid: belief.expected_bag(bid) for bid in getattr(state, "bags", {}).keys()},
        "board_meta": getattr(board_img, "metadata", None),
        "tech_meta": getattr(tech_img, "metadata", None),
    }