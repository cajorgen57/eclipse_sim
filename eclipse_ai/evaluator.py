"""Action evaluation and scoring system.

This module provides comprehensive evaluation of game actions, combining:
- Heuristic evaluation for exploration, research, building, movement
- Monte Carlo simulation for combat and exploration outcomes
- Feature-based state evaluation with configurable profiles
- Risk-adjusted scoring for decision making
"""
from __future__ import annotations
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import math
import os

import yaml

from .game_models import GameState, Action, Score, ActionType, PlayerState, Hex, Planet, Pieces, ShipDesign
from .simulators.combat import score_combat
from .explore_eval import explore_ev
from .simulators.exploration import exploration_ev
from .resource_colors import RESOURCE_COLOR_ORDER, normalize_resource_color, canonical_resource_counts
from .value.features import extract_features

_WEIGHTS = None
_ACTIVE_PROFILE = None


def _load_weights(path: str | None = None, profile: str | None = None):
    """
    Load evaluation weights, optionally applying a strategy profile.
    
    Args:
        path: Optional custom path to weights.yaml
        profile: Optional profile name to apply (e.g., "aggressive", "economic")
        
    Returns:
        Dictionary of feature weights
    """
    global _WEIGHTS, _ACTIVE_PROFILE
    
    # Reload if profile changed or weights not loaded
    if _WEIGHTS is None or profile != _ACTIVE_PROFILE:
        p = path or os.path.join(os.path.dirname(__file__), "value", "weights.yaml")
        with open(p, "r", encoding="utf-8") as f:
            base_weights = yaml.safe_load(f) or {}
        
        # Apply profile if specified
        if profile and profile.lower() not in ("none", "balanced", "default"):
            try:
                from .value.profiles import apply_profile_to_weights
                _WEIGHTS = apply_profile_to_weights(base_weights, profile)
                _ACTIVE_PROFILE = profile
            except Exception as e:
                # Fall back to base weights if profile loading fails
                print(f"Warning: Could not load profile '{profile}': {e}")
                _WEIGHTS = base_weights
                _ACTIVE_PROFILE = None
        else:
            _WEIGHTS = base_weights
            _ACTIVE_PROFILE = None
    
    return _WEIGHTS


def evaluate_state(state, context=None, profile: str | None = None) -> float:
    """
    Evaluate a game state using weighted feature extraction.
    
    Args:
        state: GameState to evaluate
        context: Optional context with opponent models and threat data
        profile: Optional strategy profile to use (e.g., "aggressive", "economic")
        
    Returns:
        Scalar evaluation score (higher is better)
    """
    w = _load_weights(None, profile)
    feats = extract_features(state, context)
    return sum(float(w.get(k, 0.0)) * float(v) for k, v in feats.items())


def set_evaluation_profile(profile: str | None) -> None:
    """
    Set the active evaluation profile globally.
    
    Args:
        profile: Profile name or None to use default weights
    """
    global _WEIGHTS, _ACTIVE_PROFILE
    _WEIGHTS = None  # Force reload
    _ACTIVE_PROFILE = profile
    _load_weights(None, profile)  # Pre-load with new profile

# ===== Public API =====

def evaluate_action(state: GameState, action: Action) -> Score:
    """
    Heuristic + simulator-backed scoring to an expected VP delta and risk.
    Robust to missing fields. Uses conservative defaults.
    """
    t = action.type
    pid = state.active_player or "you"
    if t == ActionType.EXPLORE:
        return _score_explore(state, pid, action.payload)
    if t == ActionType.MOVE:
        return _score_move(state, pid, action.payload)
    if t == ActionType.BUILD:
        return _score_build(state, pid, action.payload)
    if t == ActionType.RESEARCH:
        return _score_research(state, pid, action.payload)
    if t == ActionType.UPGRADE:
        return _score_upgrade(state, pid, action.payload)
    if t == ActionType.INFLUENCE:
        return _score_influence(state, pid, action.payload)
    if t == ActionType.DIPLOMACY:
        return _score_diplomacy(state, pid, action.payload)
    if t == ActionType.PASS:
        return Score(expected_vp=0.0, risk=0.0, details={})
    return Score(expected_vp=0.0, risk=0.5, details={"unknown_action": str(t)})

# ===== Explore =====

def _score_explore(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    tile_payload = payload.get("tile")
    target_hex = payload.get("pos") or payload.get("position") or payload.get("hex")
    if tile_payload and target_hex:
        orient = int(payload.get("orient", payload.get("orientation", 0)))
        try:
            ev_value = explore_ev(state, pid, tile_payload, str(target_hex), orient)
            risk = 0.25
            return Score(expected_vp=float(ev_value), risk=risk, details={"heuristic": "tile_ev"})
        except Exception:
            pass

    ring = int(payload.get("ring", 2))
    bag = dict(state.bags.get(f"R{ring}", {}))
    if not bag:
        return Score(expected_vp=0.0, risk=0.35, details={"reason":"no_bag_data","ring": ring})

    you = state.players.get(pid) if state.players else None
    draws = int(payload.get("draws", 1))
    owned = you.owned_tech_ids if you and you.owned_tech_ids else set()
    wormhole_gen = ("wormhole_generator" in owned) or bool(payload.get("wormhole_generator", False))
    discs_payload = payload.get("discs_available")
    if discs_payload is None:
        discs_available = int(getattr(you, "influence_discs", 0) or 0)
    else:
        try:
            discs_available = int(discs_payload)
        except (TypeError, ValueError):
            discs_available = 0
    discs_available = max(0, discs_available)
    raw_colony_ships = payload.get("colony_ships", {"orange": 1, "pink": 1, "brown": 1, "wild": 0})
    colony_ships = canonical_resource_counts(raw_colony_ships, include_zero=True)
    try:
        colony_ships["wild"] = int((raw_colony_ships or {}).get("wild", 0))
    except Exception:
        colony_ships["wild"] = 0
    p_connect_default = float(payload.get("p_connect_default", 0.70))
    require_disc_to_claim = bool(payload.get("require_disc_to_claim", True))

    q = {
        "ring": ring,
        "bag": bag,
        "draws": draws,
        "wormhole_generator": wormhole_gen,
        "discs_available": discs_available,
        "require_disc_to_claim": require_disc_to_claim,
        "colony_ships": colony_ships,
        "p_connect_default": p_connect_default,
        "n_sims": int(payload.get("n_sims", 4000)),
    }
    # If the caller wants to model Ancients clearing EV, pass a combat query through
    if "ancient_combat_query" in payload:
        q["ancient_combat_query"] = payload["ancient_combat_query"]

    ev = exploration_ev(q)

    # Enhanced risk calculation considering multiple factors
    total = max(1, sum(bag.values()))
    p_anc = float(bag.get("ancient", 0)) / total
    p_discovery = float(bag.get("discovery", 0)) / total
    p_vp = sum(float(bag.get(k, 0)) for k in bag if "vp" in str(k).lower()) / total
    
    # Base risk from ancients and connection failure
    ancient_risk = 0.5 * p_anc
    connection_risk = 0.15 * (1.0 - (1.0 if wormhole_gen else p_connect_default))
    
    # Context-aware risk adjustments
    you = state.players.get(pid) if state.players else None
    if you:
        # Consider fleet strength when evaluating ancient risk
        fleet_info = _get_fleet_summary(state, pid)
        total_combat_power = fleet_info.get("cruiser", 0) * 2 + fleet_info.get("dreadnought", 0) * 4
        
        if total_combat_power >= 4 and p_anc > 0:
            # Strong fleet reduces ancient risk
            ancient_risk *= 0.6
        elif total_combat_power < 2 and p_anc > 0:
            # Weak fleet increases ancient risk
            ancient_risk *= 1.3
    
    # Opportunity bonus: good tiles reduce effective risk
    opportunity_bonus = p_discovery * 0.1 + p_vp * 0.15
    
    base_risk = 0.15 + ancient_risk + connection_risk - opportunity_bonus
    base_risk = max(0.05, min(0.85, base_risk))
    
    # EV adjustment based on game state
    ev_multiplier = 1.0
    if you:
        # Early game: exploration is more valuable (more time to benefit)
        round_idx = getattr(state, "round_index", 1) or getattr(state, "round", 1)
        if round_idx <= 3:
            ev_multiplier *= 1.2
        elif round_idx >= 7:
            ev_multiplier *= 0.9  # Less time to benefit from new planets
        
        # If low on resources, exploration for new planets is critical
        resources = getattr(you, "resources", None)
        if resources:
            total_res = getattr(resources, "money", 0) + getattr(resources, "science", 0) + getattr(resources, "materials", 0)
            if total_res < 5:
                ev_multiplier *= 1.15  # Desperate for resources
    
    final_ev = float(ev.expected_value_vp) * ev_multiplier

    can_immediate_influence = (discs_available > 0) or not require_disc_to_claim
    details = {
        "explore_notes": ev.notes,
        "immediate_influence_if_no_ancients": can_immediate_influence,
        "p_ancient": round(p_anc, 3),
        "p_discovery": round(p_discovery, 3),
        "ev_multiplier": round(ev_multiplier, 2),
    }
    if discs_available <= 0 and require_disc_to_claim:
        details["immediate_influence_note"] = "Needs a spare influence disc to claim immediately"
    
    return Score(expected_vp=final_ev, risk=base_risk, details=details)

# ===== Move (with optional combat) =====

def _score_move(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    src = payload.get("from")
    dst = payload.get("to")
    if not dst:
        return Score(expected_vp=0.0, risk=0.2, details={"reason":"missing_destination"})
    h_from = _get_hex(state, src) if src else None
    h_to = _get_hex(state, dst)

    # Fleet to move
    move_ships: Dict[str,int] = dict(payload.get("ships", {}))
    if not move_ships and h_from and pid in h_from.pieces:
        # Default: move all small ships if unspecified
        move_ships = dict(h_from.pieces[pid].ships)

    # If destination empty of enemies and ancients, movement is positional.
    enemy_presence = _enemy_presence_in_hex(state, pid, h_to) if h_to else 0
    ancients = int(h_to.ancients) if h_to else 0

    if (enemy_presence + ancients) == 0:
        terr_ev = _territory_value_of_hex(h_to)
        # Slight bonus for consolidating fleets
        fleet_bonus = 0.05 * sum(move_ships.values())
        return Score(expected_vp=terr_ev + fleet_bonus, risk=0.1, details={"positional": True, "territory_ev": round(terr_ev,3)})

    # Build combat query from state + payload
    cq = _combat_query_from_state(state, pid, h_from, h_to, move_ships, ancient_count=ancients)
    cq["n_sims"] = int(payload.get("n_sims", 50))
    res = score_combat(cq)

    # Post-control EV if attacker wins: ability to claim planets / monolith
    post_ctrl_ev = 0.0
    if h_to:
        post_ctrl_ev = _territory_value_of_hex(h_to) * res.win_prob

    expected_vp = float(res.expected_vp_swing) + post_ctrl_ev
    risk = max(0.05, min(0.95, 1.0 - float(res.win_prob)))

    details = {
        "combat_win_prob": round(res.win_prob, 3),
        "post_control_ev": round(post_ctrl_ev, 3),
        "expected_losses_attacker": round(res.expected_losses_attacker, 3),
        "expected_losses_defender": round(res.expected_losses_defender, 3),
    }
    return Score(expected_vp=expected_vp, risk=risk, details=details)

def _combat_query_from_state(state: GameState, pid: str, h_from: Optional[Hex], h_to: Optional[Hex], move_ships: Dict[str,int], ancient_count: int = 0) -> Dict[str,Any]:
    # Attacker
    you = state.players.get(pid) if state.players else None
    atk_designs = _designs_from_player(you)
    attacker = {"ships": dict(move_ships), "designs": atk_designs}

    # Defender union of all enemies + ancients in hex
    def_ships: Dict[str,int] = {}
    def_designs: Dict[str,Any] = {}

    if h_to:
        for opp_id, pieces in h_to.pieces.items():
            if opp_id == pid:
                continue
            # merge ships
            for cls, n in pieces.ships.items():
                def_ships[cls] = def_ships.get(cls, 0) + int(n)
                if cls not in def_designs:
                    def_designs[cls] = _default_enemy_design(cls)
            if pieces.starbase:
                def_ships["starbase"] = def_ships.get("starbase", 0) + int(pieces.starbase)
                if "starbase" not in def_designs:
                    def_designs["starbase"] = _default_enemy_design("starbase")
    if ancient_count > 0:
        def_ships["ancient"] = def_ships.get("ancient", 0) + ancient_count
        def_designs["ancient"] = _default_enemy_design("ancient")

    defender = {"ships": def_ships, "designs": def_designs}
    return {"attacker": attacker, "defender": defender, "targeting":"focus_fire"}

def _designs_from_player(p: Optional[PlayerState]) -> Dict[str,Any]:
    designs: Dict[str,Any] = {}
    if not p or not p.ship_designs:
        return designs
    for cls, d in p.ship_designs.items():
        if not isinstance(d, ShipDesign):
            # tolerate dict-like
            comp = int(d.get("computer", 0))
            sh = int(d.get("shield", 0))
            ini = int(d.get("initiative", 2))
            hull = int(d.get("hull", 1))
            cann = int(d.get("cannons", 1))
            mis = int(d.get("missiles", 0))
        else:
            comp, sh, ini, hull, cann, mis = d.computer, d.shield, d.initiative, d.hull, d.cannons, d.missiles
        designs[cls] = {"initiative": ini, "hull": hull, "computer": comp, "shield": sh, "weapons":{"ion": max(0,int(cann))}, "missiles": max(0,int(mis))}
    return designs

def _default_enemy_design(cls: str) -> Dict[str,Any]:
    # Reasonable generic enemy designs
    table = {
        "interceptor": {"initiative":3,"hull":1,"computer":0,"shield":0,"weapons":{"ion":1},"missiles":0},
        "cruiser":     {"initiative":2,"hull":2,"computer":0,"shield":0,"weapons":{"ion":2},"missiles":0},
        "dreadnought": {"initiative":1,"hull":3,"computer":0,"shield":0,"weapons":{"ion":3},"missiles":0},
        "starbase":    {"initiative":4,"hull":2,"computer":0,"shield":0,"weapons":{"ion":2},"missiles":0},
        "ancient":     {"initiative":2,"hull":2,"computer":1,"shield":1,"weapons":{"ion":2},"missiles":0}
    }
    return dict(table.get(cls, {"initiative":2,"hull":1,"computer":0,"shield":0,"weapons":{"ion":1},"missiles":0}))

def _enemy_presence_in_hex(state: GameState, pid: str, hx: Optional[Hex]) -> int:
    if not hx:
        return 0
    count = 0
    for owner, p in hx.pieces.items():
        if owner == pid:
            continue
        count += int(p.starbase)
        for n in p.ships.values():
            count += int(n)
    return count

def _territory_value_of_hex(hx: Optional[Hex]) -> float:
    if not hx:
        return 0.0
    # Convert planets and monoliths to VP-equivalent present value
    counts = {color: 0 for color in RESOURCE_COLOR_ORDER}
    counts["wild"] = 0
    for pl in hx.planets:
        if pl.colonized_by is None:  # available potential
            ptype = str(getattr(pl, "type", ""))
            color = normalize_resource_color(ptype)
            if color in counts:
                counts[color] += 1
            elif ptype.lower().startswith("w"):
                counts["wild"] += 1
    # Basic PV weights similar to exploration module
    pv = _present_value_factor(3, 0.90)
    ev = sum(counts[color] for color in RESOURCE_COLOR_ORDER) * 0.20 * pv
    if hx.monolith:
        ev += 3.0 * 0.5
    return ev

# ===== Build =====

def _score_build(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    ships = dict(payload.get("ships", {}))
    starbase = int(payload.get("starbase", 0))
    # Econ/position proxy values
    v = 0.15*ships.get("interceptor",0) + 0.45*ships.get("cruiser",0) + 0.90*ships.get("dreadnought",0) + 0.70*starbase
    # Slight threat bonus if building in contested hex
    hx = _get_hex(state, payload.get("hex"))
    threat = 0.15 if _enemy_presence_in_hex(state, pid, hx) > 0 else 0.0
    expected_vp = v + threat
    risk = 0.12 if threat == 0.0 else 0.22
    return Score(expected_vp=expected_vp, risk=risk, details={"ships": ships, "starbase": starbase, "contested": threat > 0})

# ===== Research =====

def _score_research(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    """
    Evaluate research actions with context-aware tech prioritization.
    
    Considers:
    - Base tech value and upgrade potential
    - Current game phase (early/mid/late)
    - Enemy pressure and military needs
    - Economic position and tech synergies
    - Species-specific tech benefits
    """
    tech = str(payload.get("tech", ""))
    if not tech:
        return Score(expected_vp=0.0, risk=0.1, details={"reason":"no_tech"})
    
    you = state.players.get(pid) if state.players else None
    key = tech.lower()
    
    # Enhanced base weights with more nuance
    weights = {
        # Weapons (offensive tech)
        "plasma": 1.0, "antimatter": 1.2, "positron": 0.8, "fusion": 0.75, "gauss": 0.65, "ion": 0.45,
        
        # Defensive tech
        "shield": 0.65, "hull": 0.55, "phase": 0.75, "sentient": 0.9,
        
        # Mobility & tactical
        "drive": 0.60, "fusion drive": 0.70, "advanced economy": 0.80, "jump": 0.85,
        "wormhole": 0.85, "orbital": 0.50,
        
        # Economic tech
        "advanced mining": 0.70, "advanced labs": 0.75, "nanorobots": 0.65,
        "quantum": 0.60, "monolith": 0.70, "grid": 0.55,
        
        # Strategic tech
        "starbase": 0.50, "point defense": 0.60, "artifact": 0.65,
        "neutron": 0.80, "tachyon": 0.70,
    }
    
    base = 0.40  # Default for unknown tech
    tech_category = "unknown"
    
    for k, w in weights.items():
        if k in key:
            base = max(base, w)
            if k in ("plasma", "antimatter", "positron", "fusion", "gauss", "ion", "neutron"):
                tech_category = "weapon"
            elif k in ("shield", "hull", "phase", "sentient"):
                tech_category = "defense"
            elif k in ("drive", "jump", "wormhole", "orbital"):
                tech_category = "mobility"
            elif k in ("mining", "labs", "nanorobots", "quantum", "grid"):
                tech_category = "economy"
    
    # Context-aware multipliers
    multiplier = 1.0
    
    # Round-based priorities
    round_idx = getattr(state, "round_index", 1) or getattr(state, "round", 1)
    if round_idx <= 2:
        # Early game: prioritize economy and basic upgrades
        if tech_category == "economy":
            multiplier *= 1.3
        elif tech_category == "weapon" and "ion" not in key:
            multiplier *= 0.8  # Don't rush expensive weapons
    elif round_idx >= 7:
        # Late game: prioritize immediate impact (weapons, mobility)
        if tech_category in ("weapon", "mobility"):
            multiplier *= 1.25
        elif tech_category == "economy":
            multiplier *= 0.75  # Less time to benefit
    
    # Enemy pressure analysis
    pressure = _global_enemy_pressure(state, pid)
    if pressure > 0.5:
        # High pressure: value combat tech
        if tech_category in ("weapon", "defense"):
            multiplier *= (1.0 + 0.4 * pressure)
        elif tech_category == "economy":
            multiplier *= (1.0 - 0.2 * pressure)
    else:
        # Low pressure: value economy and expansion
        if tech_category == "economy":
            multiplier *= 1.2
        elif tech_category == "mobility":
            multiplier *= 1.15
    
    # Fleet composition awareness
    if you:
        fleet_info = _get_fleet_summary(state, pid)
        total_ships = sum(fleet_info.values())
        
        # If have many ships but weak firepower, prioritize weapons
        if total_ships >= 4:
            designs = getattr(you, "ship_designs", {})
            avg_guns = sum(getattr(designs.get(cls, {}), "cannons", 0) for cls in ["interceptor", "cruiser", "dreadnought"]) / 3
            if avg_guns < 2.0 and tech_category == "weapon":
                multiplier *= 1.3
        
        # If have few drives, prioritize mobility
        if total_ships >= 2:
            designs = getattr(you, "ship_designs", {})
            avg_drives = sum(getattr(designs.get(cls, {}), "drives", 0) or getattr(designs.get(cls, {}), "drive", 0) 
                           for cls in ["interceptor", "cruiser", "dreadnought"]) / 3
            if avg_drives < 1.0 and tech_category == "mobility":
                multiplier *= 1.4
    
    # Special tech bonuses
    if "wormhole" in key:
        # Wormhole generator is extremely valuable
        connectivity = _get_connectivity_value(state, pid)
        if connectivity < 0.5:  # Low connectivity = high value
            multiplier *= 1.5
    
    if "antimatter" in key or "plasma" in key:
        # Top-tier weapons deserve extra consideration when affordable
        if you and getattr(getattr(you, "resources", None), "science", 0) >= 8:
            multiplier *= 1.2
    
    score = base * multiplier
    risk = 0.08 + (0.12 if base > 0.8 else 0.0)  # Expensive tech = higher risk
    
    details = {
        "tech": tech,
        "category": tech_category,
        "pressure": round(pressure, 2),
        "round": round_idx,
        "multiplier": round(multiplier, 2)
    }
    
    return Score(expected_vp=score, risk=risk, details=details)

def _global_enemy_pressure(state: GameState, pid: str) -> float:
    # 0..1 proxy of how contested the map looks
    enemy_ships = 0
    your_hexes = 0
    contested = 0
    for hx in state.map.hexes.values():
        you_here = pid in hx.pieces and any(v>0 for v in hx.pieces[pid].ships.values())
        if you_here:
            your_hexes += 1
        e_here = _enemy_presence_in_hex(state, pid, hx)
        enemy_ships += e_here
        if you_here and e_here>0:
            contested += 1
    if your_hexes == 0:
        return 0.5 if enemy_ships>0 else 0.0
    frac_contested = contested/your_hexes
    return max(0.0, min(1.0, 0.2 + 0.6*frac_contested + 0.2*(enemy_ships/ max(1, len(state.map.hexes)))))

# ===== Upgrade =====

def _score_upgrade(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    """
    Evaluate design upgrades by estimating delta fleet power across existing ships.
    payload may include:
      {"apply": {"interceptor":{"cannons":+1,"computer":+1}, "cruiser":{"shield":+1}}}
    """
    you = state.players.get(pid) if state.players else None
    if not you:
        return Score(expected_vp=0.2, risk=0.1, details={"note":"no_player_state"})
    old_power = _fleet_power(state, pid, you.ship_designs)
    new_designs = _apply_design_changes(you.ship_designs, payload.get("apply", {}))
    new_power = _fleet_power(state, pid, new_designs)
    delta = max(0.0, new_power - old_power)
    # Map power delta to VP-equivalent
    expected_vp = 0.25 * delta
    return Score(expected_vp=expected_vp, risk=0.12, details={"delta_power": round(delta,3)})

def _apply_design_changes(designs: Dict[str,ShipDesign], changes: Dict[str,Dict[str,int]]) -> Dict[str,ShipDesign]:
    out: Dict[str,ShipDesign] = {}
    for cls, d in designs.items():
        out[cls] = ShipDesign(**{k:getattr(d,k) for k in ("computer","shield","initiative","hull","cannons","missiles","drive")})
    for cls, mods in changes.items():
        if cls not in out:
            out[cls] = ShipDesign()
        sd = out[cls]
        for k, dv in mods.items():
            if hasattr(sd, k):
                setattr(sd, k, max(0, getattr(sd, k) + int(dv)))
    return out

def _fleet_power(state: GameState, pid: str, designs: Dict[str,ShipDesign]) -> float:
    # Power = sum over ships on board of (guns + 0.8*computer + 0.6*missiles + 0.5*hull + 0.4*shield + 0.3*initiative)
    counts: Dict[str,int] = {}
    for hx in state.map.hexes.values():
        p = hx.pieces.get(pid)
        if not p:
            continue
        for cls, n in p.ships.items():
            counts[cls] = counts.get(cls, 0) + int(n)
        if p.starbase:
            counts["starbase"] = counts.get("starbase", 0) + int(p.starbase)
    power = 0.0
    for cls, n in counts.items():
        d = designs.get(cls, ShipDesign())
        g = max(0, d.cannons)
        power += n * (g + 0.8*d.computer + 0.6*d.missiles + 0.5*d.hull + 0.4*d.shield + 0.3*d.initiative)
    return power

# ===== Influence =====

def _score_influence(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    # If income deltas provided, compute PV. Else modest default.
    income = canonical_resource_counts(payload.get("income_delta", {}), include_zero=False)
    pv = _present_value_factor(int(payload.get("horizon_rounds", 3)), float(payload.get("discount", 0.90)))
    rates = {color: 0.20 for color in RESOURCE_COLOR_ORDER}
    for key, value in (payload.get("vp_per_income", {}) or {}).items():
        color = normalize_resource_color(key)
        if color in rates:
            try:
                rates[color] = float(value)
            except Exception:
                continue
    ev = 0.0
    for color, delta in income.items():
        if color in rates:
            ev += float(delta) * float(rates[color]) * pv
    if ev == 0.0:
        ev = 0.25  # typical influence has some tempo value
    return Score(expected_vp=ev, risk=0.08, details={"pv": round(pv,3), "income_delta": income})

# ===== Diplomacy =====

def _score_diplomacy(state: GameState, pid: str, payload: Dict[str, Any]) -> Score:
    # Small positive by default; can increase if targeting the current main rival.
    target = payload.get("with")
    base = 0.3
    # Heuristic: if target has many ships, alliance yields more.
    ships = 0
    if target and state.map:
        for hx in state.map.hexes.values():
            p = hx.pieces.get(target)
            if p:
                ships += sum(int(n) for n in p.ships.values()) + int(p.starbase)
    bonus = 0.1 if ships >= 4 else 0.0
    return Score(expected_vp=base + bonus, risk=0.05, details={"ally": target, "ally_ships": ships})

# ===== Utilities =====

def _get_hex(state: GameState, hex_id: Optional[str]) -> Optional[Hex]:
    if not hex_id or not state or not state.map:
        return None
    return state.map.hexes.get(hex_id)

def _present_value_factor(h: int, d: float) -> float:
    if h <= 0: return 0.0
    if abs(d - 1.0) < 1e-9:
        return float(h)
    return (1.0 - d**h) / (1.0 - d)


def _get_fleet_summary(state: GameState, pid: str) -> Dict[str, int]:
    """Get total ship counts across all hexes for a player."""
    fleet = {"interceptor": 0, "cruiser": 0, "dreadnought": 0, "starbase": 0}
    map_state = getattr(state, "map", None)
    if not map_state:
        return fleet
    
    hexes = getattr(map_state, "hexes", {})
    for hex_obj in hexes.values():
        pieces = getattr(hex_obj, "pieces", {}).get(pid)
        if pieces:
            ships = getattr(pieces, "ships", {})
            for ship_class, count in ships.items():
                if ship_class in fleet:
                    fleet[ship_class] += int(count)
            starbase = getattr(pieces, "starbase", 0)
            fleet["starbase"] += int(starbase)
    
    return fleet


def _get_connectivity_value(state: GameState, pid: str) -> float:
    """
    Estimate connectivity as a 0-1 value.
    Returns ratio of reachable hexes to controlled hexes.
    """
    connectivity_metrics = getattr(state, "connectivity_metrics", {})
    player_metrics = connectivity_metrics.get(pid, {})
    reachable = int(player_metrics.get("count", 0))
    
    # Count controlled hexes
    map_state = getattr(state, "map", None)
    if not map_state:
        return 0.0
    
    hexes = getattr(map_state, "hexes", {})
    controlled = 0
    for hex_obj in hexes.values():
        pieces = getattr(hex_obj, "pieces", {}).get(pid)
        if pieces:
            discs = int(getattr(pieces, "discs", 0))
            ships = getattr(pieces, "ships", {})
            starbase = int(getattr(pieces, "starbase", 0))
            if discs > 0 or starbase > 0 or sum(ships.values()) > 0:
                controlled += 1
    
    if controlled == 0:
        return 0.0
    
    # Ratio: higher is better connectivity
    return min(1.0, reachable / max(1, controlled))


