from __future__ import annotations
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import math

from .types import GameState, Action, Score, ActionType, PlayerState, Hex, Planet, Pieces, ShipDesign
from .simulators.combat import score_combat
from .simulators.exploration import exploration_ev

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
    ring = int(payload.get("ring", 2))
    bag = dict(state.bags.get(f"R{ring}", {}))
    if not bag:
        return Score(expected_vp=0.0, risk=0.35, details={"reason":"no_bag_data","ring": ring})

    you = state.players.get(pid) if state.players else None
    draws = int(payload.get("draws", 1))
    wormhole_gen = ("Wormhole Generator" in (you.known_techs if you else [])) or bool(payload.get("wormhole_generator", False))
    discs_available = int(payload.get("discs_available", 1))
    colony_ships = dict(payload.get("colony_ships", {"yellow":1,"blue":1,"brown":1,"wild":0}))
    p_connect_default = float(payload.get("p_connect_default", 0.70))

    q = {
        "ring": ring,
        "bag": bag,
        "draws": draws,
        "wormhole_generator": wormhole_gen,
        "discs_available": discs_available,
        "colony_ships": colony_ships,
        "p_connect_default": p_connect_default,
        "n_sims": int(payload.get("n_sims", 4000)),
    }
    # If the caller wants to model Ancients clearing EV, pass a combat query through
    if "ancient_combat_query" in payload:
        q["ancient_combat_query"] = payload["ancient_combat_query"]

    ev = exploration_ev(q)

    # Risk: chance to hit an Ancient or fail connection dominates.
    total = max(1, sum(bag.values()))
    p_anc = float(bag.get("ancient", 0)) / total
    base_risk = 0.2 + 0.5 * p_anc + 0.2 * (1.0 - (1.0 if wormhole_gen else p_connect_default))
    base_risk = max(0.05, min(0.95, base_risk))

    return Score(expected_vp=float(ev.expected_value_vp), risk=base_risk, details={"explore_notes": ev.notes})

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
    cq["n_sims"] = int(payload.get("n_sims", 4000))
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
    counts = {"yellow":0, "blue":0, "brown":0, "wild":0}
    for pl in hx.planets:
        if pl.colonized_by is None:  # available potential
            if pl.type in counts:
                counts[pl.type] += 1
            elif pl.type.lower().startswith("y"):
                counts["yellow"] += 1
            elif pl.type.lower().startswith("b"):
                counts["blue"] += 1
            elif pl.type.lower().startswith("p") or pl.type.lower().startswith("m"):
                counts["brown"] += 1
            elif pl.type.lower().startswith("w"):
                counts["wild"] += 1
    # Basic PV weights similar to exploration module
    pv = _present_value_factor(3, 0.90)
    ev = (counts["yellow"] + counts["blue"] + counts["brown"]) * 0.20 * pv
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
    tech = str(payload.get("tech", ""))
    if not tech:
        return Score(expected_vp=0.0, risk=0.1, details={"reason":"no_tech"})
    # Base weights
    weights = {
        "plasma": 0.8, "positron": 0.7, "fusion": 0.7, "gauss": 0.6, "ion": 0.4,
        "shield": 0.5, "drive": 0.5, "hull": 0.4,
        "advanced mining": 0.6, "advanced labs": 0.6, "nanorobots": 0.5,
        "wormhole": 0.7, "starbase": 0.4,
    }
    key = tech.lower()
    base = 0.35
    for k, w in weights.items():
        if k in key:
            base = max(base, w)

    # Scale by pressure: more enemies -> more value for combat tech
    pressure = _global_enemy_pressure(state, pid)
    combat_bias = 1.0 + 0.3*pressure
    econ_bias = 1.0 + 0.2*max(0.0, 1.0-pressure)

    if any(k in key for k in ("plasma","positron","gauss","ion","shield","drive","hull","starbase")):
        score = base * combat_bias
    elif any(k in key for k in ("mining","labs","nanorobots")):
        score = base * econ_bias
    elif "wormhole" in key:
        score = base * (1.0 + 0.15)  # improves connectivity
    else:
        score = base

    risk = 0.10
    return Score(expected_vp=score, risk=risk, details={"tech": tech, "pressure": round(pressure,2)})

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
    income = payload.get("income_delta", {})  # {"yellow": +1, "blue": 0, "brown": -1}
    pv = _present_value_factor(int(payload.get("horizon_rounds", 3)), float(payload.get("discount", 0.90)))
    rates = {"yellow":0.20, "blue":0.20, "brown":0.20}
    rates.update(payload.get("vp_per_income", {}))
    ev = 0.0
    for k, dv in income.items():
        if k in ("yellow","blue","brown"):
            ev += float(dv) * float(rates[k]) * pv
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


