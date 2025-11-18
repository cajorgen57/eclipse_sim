"""
Orion Turn 1 Full Turn Planning Test

This test generates multi-step coherent turn plans where each action builds on the previous.
It shows the complete strategy with expected outcomes after each step.

Usage:
    # Full turn planning with default settings
    python tests/test_orion_full_turn.py
    
    # With verbose output showing full state evolution
    python tests/test_orion_full_turn.py --verbose
    
    # High quality deep planning
    python tests/test_orion_full_turn.py --sims 1000 --depth 5 --verbose
    
    # Test different strategy profiles
    python tests/test_orion_full_turn.py --profile aggressive --verbose
    python tests/test_orion_full_turn.py --profile economic --verbose
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eclipse_ai import recommend
from eclipse_ai.game_models import GameState
from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner, Node
from eclipse_ai.action_gen.actions import generate
from eclipse_ai.hidden_info import determinize
from eclipse_ai.context import Context
from eclipse_ai import evaluator
from eclipse_ai.rules import api as rules_api


# Same Orion scenario as the single-action test
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


def extract_action_path(node: Node, max_depth: int = 10) -> List[Any]:
    """Extract the sequence of actions from root to this node."""
    path = []
    current = node
    depth = 0
    while current.parent is not None and depth < max_depth:
        if current.action_from_parent is not None:
            path.insert(0, current.action_from_parent)
        current = current.parent
        depth += 1
    return path


def get_multi_step_plans(state: GameState, planner: PW_MCTSPlanner, max_steps: int = 5) -> List[Dict[str, Any]]:
    """Generate multi-step plans by exploring the MCTS tree."""
    
    det = determinize(state)
    me_id = getattr(state, "active_player", "orion")
    
    # Build context
    rd = getattr(state, "round_index", getattr(det, "round_index", 0))
    if planner.opponent_awareness:
        from eclipse_ai.opponents import analyze_state
        models, tmap = analyze_state(det, my_id=me_id, round_idx=rd)
        context = Context(opponent_models=models, threat_map=tmap, round_index=rd)
    else:
        context = Context(round_index=rd)
    
    # Build root node
    root = Node(det, None, None, prior=0.0, context=context, player_id=me_id)
    
    # Run simulations
    for _ in range(planner.sims):
        node = root
        # Selection
        while node.children and not node.can_expand(planner.pw_c, planner.pw_alpha):
            node = max(node.children, key=lambda child: planner.ucb(child, node.visits))
        # Expansion
        if node.can_expand(planner.pw_c, planner.pw_alpha):
            try:
                mac = next(node._action_iter)
                child_state = planner.apply(node.state, mac, player_id=node.player_id) if mac.type != "PASS" else node.state
                next_pid = getattr(child_state, "active_player", None) or getattr(
                    child_state, "active_player_id", None
                )
                if next_pid is None and isinstance(child_state, dict):
                    next_pid = child_state.get("active_player") or child_state.get("active_player_id", node.player_id)
                child = Node(
                    child_state,
                    node,
                    mac,
                    prior=mac.prior,
                    context=context,
                    player_id=next_pid,
                )
                node.children.append(child)
                node = child
            except StopIteration:
                node.fully_expanded = True
                node._action_iter = None
        # Rollout
        value = planner.rollout(node)
        # Backup
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
    
    # Extract multi-step plans by traversing the tree depth-first
    plans = []
    
    def explore_tree(node: Node, depth: int):
        if depth >= max_steps or not node.children:
            return
        
        # For each child, extract the path and simulate
        for child in sorted(node.children, key=lambda c: c.value / max(1, c.visits), reverse=True)[:3]:
            action_sequence = extract_action_path(child, max_steps)
            if len(action_sequence) >= 2:  # Only include multi-step plans
                mean_value = child.value / max(1, child.visits)
                plans.append({
                    "actions": action_sequence,
                    "value": mean_value,
                    "visits": child.visits,
                    "depth": len(action_sequence)
                })
            
            # Recursively explore deeper
            explore_tree(child, depth + 1)
    
    explore_tree(root, 0)
    
    # Sort by value and return top plans
    plans.sort(key=lambda p: (p["depth"], p["value"]), reverse=True)
    return plans[:5]


def simulate_action_sequence(base_state: GameState, player_id: str, actions: List[Any]) -> List[Dict[str, Any]]:
    """Simulate a sequence of actions and return state after each step."""
    states = []
    current_state = copy.deepcopy(base_state)
    
    for i, mac in enumerate(actions):
        # Extract action details
        act_type = getattr(mac, "type", "UNKNOWN")
        payload = dict(getattr(mac, "payload", {}))
        payload.pop("__raw__", None)
        
        # Record state before action
        resources_before = _get_resources(current_state, player_id)
        
        # Apply action
        try:
            action_dict = {"type": act_type, "payload": payload}
            current_state = rules_api.apply_action(current_state, player_id, action_dict)
        except Exception as e:
            states.append({
                "step": i + 1,
                "action": act_type,
                "payload": payload,
                "error": str(e),
                "success": False
            })
            break
        
        # Record state after action
        resources_after = _get_resources(current_state, player_id)
        resource_delta = {
            k: resources_after.get(k, 0) - resources_before.get(k, 0)
            for k in ["money", "science", "materials"]
        }
        
        states.append({
            "step": i + 1,
            "action": act_type,
            "payload": payload,
            "resources_before": resources_before,
            "resources_after": resources_after,
            "resource_delta": resource_delta,
            "success": True
        })
    
    return states


def _get_resources(state: GameState, player_id: str) -> Dict[str, int]:
    """Extract resources for a player."""
    player = getattr(state, "players", {}).get(player_id)
    if not player:
        return {"money": 0, "science": 0, "materials": 0}
    resources = getattr(player, "resources", None)
    if resources is None:
        return {"money": 0, "science": 0, "materials": 0}
    return {
        "money": int(getattr(resources, "money", 0)),
        "science": int(getattr(resources, "science", 0)),
        "materials": int(getattr(resources, "materials", 0))
    }


def generate_strategy_narrative(plan_steps: List[Dict[str, Any]]) -> str:
    """Generate a human-readable strategy narrative."""
    if not plan_steps:
        return "No valid actions in plan."
    
    narrative_parts = []
    
    for step in plan_steps:
        if not step.get("success", False):
            narrative_parts.append(f"Step {step['step']}: Failed - {step.get('error', 'Unknown error')}")
            continue
        
        action = step["action"]
        payload = step.get("payload", {})
        delta = step.get("resource_delta", {})
        
        if action == "EXPLORE":
            ring = payload.get("ring", "?")
            narrative_parts.append(
                f"Step {step['step']}: Explore Ring {ring} sector to expand territory and discover resources"
            )
        elif action == "BUILD":
            ships = payload.get("ships", {})
            ship_desc = ", ".join(f"{count}× {ship}" for ship, count in ships.items() if count > 0)
            mat_cost = -delta.get("materials", 0)
            narrative_parts.append(
                f"Step {step['step']}: Build {ship_desc} (Cost: {mat_cost} materials)"
            )
        elif action == "RESEARCH":
            tech = payload.get("tech", "Unknown")
            cost = -delta.get("science", 0)
            narrative_parts.append(
                f"Step {step['step']}: Research '{tech}' technology (Cost: {cost} science)"
            )
        elif action == "UPGRADE":
            narrative_parts.append(
                f"Step {step['step']}: Upgrade ship blueprints"
            )
        elif action == "MOVE_FIGHT":
            to_hex = payload.get("to", "?")
            narrative_parts.append(
                f"Step {step['step']}: Move fleet to hex {to_hex}"
            )
        elif action == "INFLUENCE":
            hex_id = payload.get("hex", "?")
            narrative_parts.append(
                f"Step {step['step']}: Place influence disc in hex {hex_id}"
            )
        else:
            narrative_parts.append(
                f"Step {step['step']}: {action}"
            )
    
    return "\n    ".join(narrative_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Orion Turn 1 Full Turn Planning - Multi-step coherent strategies"
    )
    parser.add_argument("--sims", type=int, default=600, help="MCTS simulations")
    parser.add_argument("--depth", type=int, default=4, help="Maximum plan depth")
    parser.add_argument("--max-steps", type=int, default=5, help="Maximum actions per plan")
    parser.add_argument("--profile", help="Strategy profile (aggressive, economic, etc.)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", help="Output JSON file path")
    args = parser.parse_args()
    
    # Load state
    state = GameState.from_dict(copy.deepcopy(ORION_ROUND1_STATE))
    player_id = "orion"
    
    if args.verbose:
        print("\n" + "="*70)
        print("ORION TURN 1 - FULL TURN PLANNING")
        print("="*70)
        print(f"\nConfiguration:")
        print(f"  Simulations: {args.sims}")
        print(f"  Max Depth: {args.depth}")
        print(f"  Max Steps per Plan: {args.max_steps}")
        print(f"  Profile: {args.profile or 'balanced (default)'}")
        
        initial_resources = _get_resources(state, player_id)
        print(f"\n📊 Initial State:")
        print(f"  Money: {initial_resources['money']}")
        print(f"  Science: {initial_resources['science']}")
        print(f"  Materials: {initial_resources['materials']}")
        print(f"  Fleet: 1× cruiser in hex 230")
        print(f"  Colonies: 3 (orange, pink, brown)")
        
        print(f"\n⚙️  Running deep planning with {args.sims} simulations...")
        print("="*70 + "\n")
    
    # Create planner
    planner = PW_MCTSPlanner(
        sims=args.sims,
        depth=args.depth,
        opponent_awareness=True
    )
    
    # Get multi-step plans
    multi_plans = get_multi_step_plans(state, planner, max_steps=args.max_steps)
    
    # Simulate and display plans
    enriched_plans = []
    for i, plan_data in enumerate(multi_plans, 1):
        actions = plan_data["actions"]
        plan_steps = simulate_action_sequence(state, player_id, actions)
        
        # Calculate final resources
        final_resources = plan_steps[-1]["resources_after"] if plan_steps else _get_resources(state, player_id)
        initial_resources = _get_resources(state, player_id)
        total_delta = {
            k: final_resources.get(k, 0) - initial_resources.get(k, 0)
            for k in ["money", "science", "materials"]
        }
        
        enriched_plan = {
            "plan_number": i,
            "num_actions": len(actions),
            "expected_value": plan_data["value"],
            "visits": plan_data["visits"],
            "steps": plan_steps,
            "final_resources": final_resources,
            "total_resource_delta": total_delta,
            "strategy_narrative": generate_strategy_narrative(plan_steps)
        }
        enriched_plans.append(enriched_plan)
    
    # Display results
    if args.verbose:
        print("="*70)
        print("🎯 MULTI-STEP TURN STRATEGIES")
        print("="*70)
        
        for plan in enriched_plans:
            print(f"\n{'─'*70}")
            print(f"Plan {plan['plan_number']}: {plan['num_actions']}-Action Strategy")
            print(f"Expected Value: {plan['expected_value']:.3f} | Confidence: {plan['visits']} visits")
            print(f"{'─'*70}")
            
            print(f"\n  Strategy:")
            print(f"    {plan['strategy_narrative']}")
            
            print(f"\n  Resource Impact:")
            delta = plan['total_resource_delta']
            for resource in ["money", "science", "materials"]:
                change = delta.get(resource, 0)
                sign = "+" if change >= 0 else ""
                print(f"    {resource.capitalize():12s} {sign}{change:2d}")
            
            print(f"\n  Final Resources: M:{plan['final_resources']['money']} "
                  f"S:{plan['final_resources']['science']} "
                  f"Mat:{plan['final_resources']['materials']}")
        
        print(f"\n{'='*70}")
        print("✓ Full Turn Planning Complete")
        print("="*70)
        print(f"\nGenerated {len(enriched_plans)} coherent multi-step strategies")
        print(f"Average plan length: {sum(p['num_actions'] for p in enriched_plans) / len(enriched_plans):.1f} actions\n")
    
    # Save output
    if args.output:
        output_data = {
            "round": 1,
            "active_player": player_id,
            "initial_resources": _get_resources(state, player_id),
            "configuration": {
                "simulations": args.sims,
                "depth": args.depth,
                "max_steps": args.max_steps,
                "profile": args.profile or "balanced"
            },
            "plans": enriched_plans
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        if args.verbose:
            print(f"💾 Results saved to: {args.output}\n")
    
    # Non-verbose JSON output
    if not args.verbose:
        print(json.dumps({
            "plans": enriched_plans,
            "config": {
                "sims": args.sims,
                "depth": args.depth,
                "max_steps": args.max_steps
            }
        }, indent=2))


if __name__ == "__main__":
    main()

