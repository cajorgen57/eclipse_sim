"""
Random Turn 1 Planning Test

Generates random board states and provides multi-step turn recommendations.
Shows the complete board state before making recommendations.

Usage:
    # Generate random board and get recommendations
    python tests/test_random_turn_planning.py --verbose
    
    # Use specific seed for reproducibility
    python tests/test_random_turn_planning.py --seed 42 --verbose
    
    # Different player counts
    python tests/test_random_turn_planning.py --players 4 --verbose
    
    # High quality planning
    python tests/test_random_turn_planning.py --sims 1000 --depth 5 --verbose
"""

import argparse
import copy
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eclipse_ai.game_models import GameState
from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner, Node
from eclipse_ai.action_gen.actions import generate
from eclipse_ai.hidden_info import determinize
from eclipse_ai.context import Context
from eclipse_ai import evaluator
from eclipse_ai.rules import api as rules_api


# Species starting techs and resources
SPECIES_DATA = {
    "Terran": {
        "color": "orange",
        "starting_tech": ["Fusion Drive"],
        "starting_resources": {"money": 3, "science": 2, "materials": 2},
    },
    "Orion": {
        "color": "purple",
        "starting_tech": ["Gauss Shield"],
        "starting_resources": {"money": 2, "science": 1, "materials": 5},
    },
    "Mechanema": {
        "color": "teal",
        "starting_tech": ["Positron Computer"],
        "starting_resources": {"money": 1, "science": 3, "materials": 1},
    },
    "Planta": {
        "color": "green",
        "starting_tech": ["Gauss Shield"],
        "starting_resources": {"money": 2, "science": 1, "materials": 5},
    },
    "Magellan": {
        "color": "blue",
        "starting_tech": ["Ion Thruster"],  # Using Fusion Drive as proxy
        "starting_resources": {"money": 1, "science": 1, "materials": 3},
    },
    "Eridani": {
        "color": "yellow",
        "starting_tech": ["Gluon Computer"],
        "starting_resources": {"money": 4, "science": 0, "materials": 1},
    },
}

# Available technologies by category with correct costs
TECH_LIBRARY = {
    "Military": [
        {"name": "Neutron Bombs", "min_cost": 2, "max_cost": 2},
        {"name": "Starbase", "min_cost": 3, "max_cost": 4},
        {"name": "Plasma Cannon", "min_cost": 4, "max_cost": 6},
        {"name": "Phase Shield", "min_cost": 5, "max_cost": 8},
        {"name": "Advanced Mining", "min_cost": 6, "max_cost": 10},
        {"name": "Tachyon Source", "min_cost": 6, "max_cost": 12},
        {"name": "Gluon Computer", "min_cost": 7, "max_cost": 14},
        {"name": "Plasma Missile", "min_cost": 8, "max_cost": 16},
    ],
    "Grid": [
        {"name": "Gauss Shield", "min_cost": 2, "max_cost": 2},
        {"name": "Fusion Source", "min_cost": 3, "max_cost": 4},
        {"name": "Improved Hull", "min_cost": 4, "max_cost": 6},
        {"name": "Positron Computer", "min_cost": 5, "max_cost": 8},
        {"name": "Advanced Economy", "min_cost": 6, "max_cost": 10},
        {"name": "Tachyon Drive", "min_cost": 6, "max_cost": 12},
        {"name": "Antimatter Cannon", "min_cost": 7, "max_cost": 14},
        {"name": "Quantum Grid", "min_cost": 8, "max_cost": 16},
    ],
    "Nano": [
        {"name": "Nanorobots", "min_cost": 2, "max_cost": 2},
        {"name": "Fusion Drive", "min_cost": 3, "max_cost": 4},
        {"name": "Orbital", "min_cost": 4, "max_cost": 6},
        {"name": "Advanced Robotics", "min_cost": 5, "max_cost": 8},
        {"name": "Advanced Labs", "min_cost": 6, "max_cost": 10},
        {"name": "Monolith", "min_cost": 6, "max_cost": 12},
        {"name": "Wormhole Generator", "min_cost": 7, "max_cost": 14},
        {"name": "Artifact Key", "min_cost": 8, "max_cost": 16},
    ],
}


def generate_random_board_state(seed: int, num_players: int = 4) -> Dict[str, Any]:
    """Generate a random but valid board state for turn 1."""
    random.seed(seed)
    
    # Select random species
    available_species = list(SPECIES_DATA.keys())
    random.shuffle(available_species)
    selected_species = available_species[:num_players]
    
    # Pick active player
    active_species = random.choice(selected_species)
    
    # Build players
    players = {}
    for i, species in enumerate(selected_species):
        species_data = SPECIES_DATA[species]
        player_id = species.lower()
        
        # Randomize resources slightly
        base_resources = species_data["starting_resources"].copy()
        players[player_id] = {
            "player_id": player_id,
            "species": species,
            "color": species_data["color"],
            "known_techs": species_data["starting_tech"].copy(),
            "resources": {
                "money": base_resources["money"] + random.randint(-1, 1),
                "science": base_resources["science"] + random.randint(0, 1),
                "materials": base_resources["materials"] + random.randint(-1, 2),
            },
            "ship_designs": {
                "interceptor": {
                    "computer": 1,
                    "shield": 1 if species == "Orion" else 0,
                    "initiative": 2,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
                "cruiser": {
                    "computer": 1,
                    "shield": 1 if species == "Orion" else 0,
                    "initiative": 3,
                    "hull": 1,
                    "cannons": 1,
                    "missiles": 0,
                    "drive": 1,
                },
            },
        }
    
    # Build map with home sectors
    hexes = {}
    hex_ids = ["101", "102", "103", "104", "105", "106"]
    
    for i, (player_id, player) in enumerate(players.items()):
        hex_id = hex_ids[i]
        
        # Random planet configuration
        planet_types = ["orange", "pink", "brown"]
        random.shuffle(planet_types)
        num_planets = random.randint(2, 3)
        
        planets = []
        cubes = {}
        for j in range(num_planets):
            planet_type = planet_types[j % len(planet_types)]
            planets.append({"type": planet_type, "colonized_by": player_id})
            cubes[planet_type] = cubes.get(planet_type, 0) + 1
        
        # Random fleet
        fleet = {}
        if random.random() > 0.5:
            fleet["interceptor"] = random.randint(1, 2)
        if random.random() > 0.6:
            fleet["cruiser"] = random.randint(0, 1)
        if not fleet:
            fleet["cruiser"] = 1  # Ensure at least one ship
        
        hexes[hex_id] = {
            "id": hex_id,
            "ring": 1,
            "wormholes": random.sample([0, 1, 2, 3, 4, 5], k=random.randint(2, 3)),
            "planets": planets,
            "pieces": {
                player_id: {
                    "ships": fleet,
                    "starbase": 0,
                    "discs": 1,
                    "cubes": cubes,
                }
            },
        }
    
    # Add a few unexplored sectors
    for i in range(2):
        hex_id = f"20{i+1}"
        hexes[hex_id] = {
            "id": hex_id,
            "ring": 2,
            "wormholes": random.sample([0, 1, 2, 3, 4, 5], k=2),
            "explored": False,
            "planets": [],
            "pieces": {},
        }
    
    # Select random available techs (6-8 on display)
    all_techs = []
    for category, techs in TECH_LIBRARY.items():
        all_techs.extend([t["name"] for t in techs])
    
    random.shuffle(all_techs)
    available_techs = all_techs[:random.randint(6, 8)]
    
    return {
        "round": 1,
        "active_player": active_species.lower(),
        "players": players,
        "map": {"hexes": hexes},
        "tech_display": {
            "available": available_techs,
            "tier_counts": {"I": 6, "II": 4, "III": 2},
        },
        "bags": {
            "R1": {"unknown": 5},
            "R2": {"unknown": 4},
        },
    }


def format_board_state_report(state_dict: Dict[str, Any]) -> str:
    """Generate a detailed text report of the board state."""
    lines = []
    lines.append("="*70)
    lines.append("BOARD STATE REPORT")
    lines.append("="*70)
    
    # Game info
    lines.append(f"\n📋 Game Info:")
    lines.append(f"  Round: {state_dict['round']}")
    lines.append(f"  Active Player: {state_dict['active_player']}")
    lines.append(f"  Number of Players: {len(state_dict['players'])}")
    
    # Players
    lines.append(f"\n👥 Players:")
    for player_id, player in state_dict['players'].items():
        lines.append(f"\n  {player_id.upper()} ({player.get('species', 'Unknown')}):")
        lines.append(f"    Color: {player.get('color', 'unknown')}")
        
        # Resources
        resources = player.get('resources', {})
        lines.append(f"    Resources: M:{resources.get('money', 0)} "
                    f"S:{resources.get('science', 0)} "
                    f"Mat:{resources.get('materials', 0)}")
        
        # Technologies
        techs = player.get('known_techs', [])
        if techs:
            lines.append(f"    Technologies: {', '.join(techs)}")
        
        # Find their hexes
        player_hexes = []
        for hex_id, hex_data in state_dict['map']['hexes'].items():
            pieces = hex_data.get('pieces', {}).get(player_id)
            if pieces:
                ships = pieces.get('ships', {})
                ship_str = ", ".join(f"{count}×{ship}" for ship, count in ships.items() if count > 0)
                cubes = pieces.get('cubes', {})
                cube_str = ", ".join(f"{count}×{color}" for color, count in cubes.items())
                player_hexes.append(f"Hex {hex_id}: {ship_str} | Colonies: {cube_str}")
        
        if player_hexes:
            lines.append(f"    Territory:")
            for hex_info in player_hexes:
                lines.append(f"      {hex_info}")
    
    # Map
    lines.append(f"\n🗺️  Map ({len(state_dict['map']['hexes'])} hexes):")
    for hex_id, hex_data in sorted(state_dict['map']['hexes'].items()):
        if not hex_data.get('explored', True):
            lines.append(f"  Hex {hex_id}: Ring {hex_data['ring']} - UNEXPLORED")
        else:
            planets = hex_data.get('planets', [])
            planet_str = ", ".join(p['type'] for p in planets)
            owner_str = ", ".join(set(p.get('colonized_by', 'none') for p in planets if p.get('colonized_by')))
            lines.append(f"  Hex {hex_id}: Ring {hex_data['ring']} | Planets: {planet_str} | Owner: {owner_str or 'none'}")
    
    # Available Technologies
    lines.append(f"\n🔬 Available Technologies ({len(state_dict['tech_display']['available'])}):")
    for i, tech in enumerate(state_dict['tech_display']['available'], 1):
        # Find cost info
        cost_info = None
        for category, techs in TECH_LIBRARY.items():
            for t in techs:
                if t['name'] == tech:
                    cost_info = f"{t['min_cost']}-{t['max_cost']} science"
                    break
            if cost_info:
                break
        
        cost_str = f" (Cost: {cost_info})" if cost_info else ""
        if i % 2 == 1:
            lines.append(f"  {tech}{cost_str}")
        else:
            lines[-1] += f" | {tech}{cost_str}"
    
    lines.append("\n" + "="*70)
    return "\n".join(lines)


def simulate_action_sequence(base_state: GameState, player_id: str, actions: List[Any]) -> List[Dict[str, Any]]:
    """Simulate a sequence of actions and return state after each step."""
    states = []
    current_state = copy.deepcopy(base_state)
    
    for i, mac in enumerate(actions):
        act_type = getattr(mac, "type", "UNKNOWN")
        payload = dict(getattr(mac, "payload", {}))
        payload.pop("__raw__", None)
        
        resources_before = _get_resources(current_state, player_id)
        
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


def get_multi_step_plans(state: GameState, planner: PW_MCTSPlanner, max_steps: int = 4) -> List[Dict[str, Any]]:
    """Generate multi-step plans by exploring the MCTS tree."""
    det = determinize(state)
    me_id = getattr(state, "active_player", list(getattr(state, "players", {}).keys())[0])
    
    rd = getattr(state, "round_index", getattr(det, "round_index", 0))
    if planner.opponent_awareness:
        from eclipse_ai.opponents import analyze_state
        models, tmap = analyze_state(det, my_id=me_id, round_idx=rd)
        context = Context(opponent_models=models, threat_map=tmap, round_index=rd)
    else:
        context = Context(round_index=rd)
    
    root = Node(det, None, None, prior=0.0, context=context, player_id=me_id)
    
    for _ in range(planner.sims):
        node = root
        while node.children and not node.can_expand(planner.pw_c, planner.pw_alpha):
            node = max(node.children, key=lambda child: planner.ucb(child, node.visits))
        if node.can_expand(planner.pw_c, planner.pw_alpha):
            try:
                mac = next(node._action_iter)
                child_state = planner.apply(node.state, mac, player_id=node.player_id) if mac.type != "PASS" else node.state
                next_pid = getattr(child_state, "active_player", None) or getattr(child_state, "active_player_id", None)
                if next_pid is None and isinstance(child_state, dict):
                    next_pid = child_state.get("active_player") or child_state.get("active_player_id", node.player_id)
                child = Node(child_state, node, mac, prior=mac.prior, context=context, player_id=next_pid)
                node.children.append(child)
                node = child
            except StopIteration:
                node.fully_expanded = True
                node._action_iter = None
        value = planner.rollout(node)
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
    
    plans = []
    def explore_tree(node: Node, depth: int):
        if depth >= max_steps or not node.children:
            return
        for child in sorted(node.children, key=lambda c: c.value / max(1, c.visits), reverse=True)[:3]:
            action_sequence = extract_action_path(child, max_steps)
            if len(action_sequence) >= 2:
                mean_value = child.value / max(1, child.visits)
                plans.append({
                    "actions": action_sequence,
                    "value": mean_value,
                    "visits": child.visits,
                    "depth": len(action_sequence)
                })
            explore_tree(child, depth + 1)
    
    explore_tree(root, 0)
    plans.sort(key=lambda p: (p["depth"], p["value"]), reverse=True)
    return plans[:5]


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
            narrative_parts.append(f"Step {step['step']}: Explore Ring {ring}")
        elif action == "BUILD":
            ships = payload.get("ships", {})
            ship_desc = ", ".join(f"{count}×{ship}" for ship, count in ships.items() if count > 0)
            mat_cost = -delta.get("materials", 0)
            narrative_parts.append(f"Step {step['step']}: Build {ship_desc} (Cost: {mat_cost} materials)")
        elif action == "RESEARCH":
            tech = payload.get("tech", "Unknown")
            cost = -delta.get("science", 0)
            narrative_parts.append(f"Step {step['step']}: Research '{tech}' (Cost: {cost} science)")
        else:
            narrative_parts.append(f"Step {step['step']}: {action}")
    
    return "\n    ".join(narrative_parts)


def main():
    parser = argparse.ArgumentParser(description="Random Board State Turn Planning")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for board generation")
    parser.add_argument("--players", type=int, default=4, choices=[2, 3, 4, 5, 6], help="Number of players")
    parser.add_argument("--sims", type=int, default=400, help="MCTS simulations")
    parser.add_argument("--depth", type=int, default=4, help="Search depth")
    parser.add_argument("--max-steps", type=int, default=4, help="Max actions per plan")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", help="Output JSON file")
    args = parser.parse_args()
    
    # Generate seed if not provided
    if args.seed is None:
        args.seed = random.randint(1, 999999)
    
    if args.verbose:
        print(f"\n🎲 Generating random board state (seed: {args.seed}, players: {args.players})\n")
    
    # Generate random state
    state_dict = generate_random_board_state(args.seed, args.players)
    state = GameState.from_dict(copy.deepcopy(state_dict))
    player_id = state_dict["active_player"]
    
    # Display board state
    if args.verbose:
        print(format_board_state_report(state_dict))
        print(f"\n⚙️  Running planner ({args.sims} simulations, depth {args.depth})...\n")
    
    # Plan
    planner = PW_MCTSPlanner(sims=args.sims, depth=args.depth, opponent_awareness=True)
    multi_plans = get_multi_step_plans(state, planner, max_steps=args.max_steps)
    
    # Simulate plans
    enriched_plans = []
    for i, plan_data in enumerate(multi_plans, 1):
        actions = plan_data["actions"]
        plan_steps = simulate_action_sequence(state, player_id, actions)
        
        initial_resources = _get_resources(state, player_id)
        
        # Get final resources (handle failed steps)
        if plan_steps and plan_steps[-1].get("success", False):
            final_resources = plan_steps[-1]["resources_after"]
        else:
            final_resources = initial_resources
        
        total_delta = {
            k: final_resources.get(k, 0) - initial_resources.get(k, 0)
            for k in ["money", "science", "materials"]
        }
        
        enriched_plans.append({
            "plan_number": i,
            "num_actions": len(actions),
            "expected_value": plan_data["value"],
            "visits": plan_data["visits"],
            "steps": plan_steps,
            "final_resources": final_resources,
            "total_resource_delta": total_delta,
            "strategy_narrative": generate_strategy_narrative(plan_steps)
        })
    
    # Display results
    if args.verbose:
        print("="*70)
        print("🎯 RECOMMENDED STRATEGIES")
        print("="*70)
        
        for plan in enriched_plans:
            print(f"\n{'─'*70}")
            print(f"Plan {plan['plan_number']}: {plan['num_actions']}-Action Strategy")
            print(f"Expected Value: {plan['expected_value']:.3f} | Confidence: {plan['visits']} visits")
            print(f"{'─'*70}")
            print(f"\n  Strategy:")
            print(f"    {plan['strategy_narrative']}")
            
            delta = plan['total_resource_delta']
            print(f"\n  Net Resource Impact:")
            for resource in ["money", "science", "materials"]:
                change = delta.get(resource, 0)
                sign = "+" if change >= 0 else ""
                print(f"    {resource.capitalize():12s} {sign}{change:2d}")
            
            print(f"\n  Final Resources: M:{plan['final_resources']['money']} "
                  f"S:{plan['final_resources']['science']} "
                  f"Mat:{plan['final_resources']['materials']}")
        
        print(f"\n{'='*70}")
        print(f"✓ Generated {len(enriched_plans)} strategic options")
        print(f"  Seed: {args.seed} | Players: {args.players}\n")
    
    # Save output
    if args.output:
        output_data = {
            "seed": args.seed,
            "board_state": state_dict,
            "configuration": {
                "players": args.players,
                "simulations": args.sims,
                "depth": args.depth,
                "max_steps": args.max_steps
            },
            "plans": enriched_plans
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        if args.verbose:
            print(f"💾 Results saved to: {args.output}\n")
    
    if not args.verbose:
        print(json.dumps({
            "seed": args.seed,
            "board_state": state_dict,
            "plans": enriched_plans
        }, indent=2))


if __name__ == "__main__":
    main()

