from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from .game_models import GameState, Action, ActionType, PlayerState, Hex, Planet, Pieces, Resources, ShipDesign

# =============================
# Config
# =============================

@dataclass
class RulesConfig:
    expansions: Dict[str, bool] = field(default_factory=lambda: {"RoA": True, "SoTR": False})
    enable_influence: bool = True
    enable_diplomacy: bool = True
    max_actions: int = 40  # hard cap to avoid explosion

# Ship material costs (approximate, tweak as needed for your edition/house rules)
SHIP_COSTS = {
    "interceptor": 2,
    "cruiser": 3,
    "dreadnought": 5,
    "starbase": 4,
}

# =============================
# Public API
# =============================

def legal_actions(state: GameState, player_id: str, config: Optional[RulesConfig]=None) -> List[Action]:
    """
    Produces a practical set of candidate actions for the active player.
    Resource-aware. No pathfinding. Conservative about rules we cannot infer.
    """
    cfg = config or RulesConfig()
    acts: List[Action] = []
    you = state.players.get(player_id) if state.players else None
    if you is None:
        return [Action(ActionType.PASS, {})]

    # Explore
    acts.extend(_enum_explore(state, you))

    # Research
    acts.extend(_enum_research(state, you))

    # Build
    acts.extend(_enum_build(state, you))

    # Move (includes "assault in place" if enemies are already in hex)
    acts.extend(_enum_moves(state, you))

    # Upgrade (suggest small design improvements)
    acts.extend(_enum_upgrades(state, you))

    # Influence
    if cfg.enable_influence:
        acts.extend(_enum_influence(state, you))

    # Diplomacy
    if cfg.enable_diplomacy:
        acts.extend(_enum_diplomacy(state, you))

    # Pass is always an option
    acts.append(Action(ActionType.PASS, {}))

    # Deduplicate and cap
    uniq = _dedup_actions(acts)
    return uniq[:cfg.max_actions]

# =============================
# Enumerators
# =============================

def _enum_explore(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    # Heuristic: explore outward from any hex you occupy. If bags exist for R2/R3, use them.
    rings_to_consider = set()
    for hx in state.map.hexes.values():
        if you.player_id in hx.pieces:
            rings_to_consider.add(max(1, hx.ring))           # same ring
            rings_to_consider.add(max(1, hx.ring + 1))       # outward
    for r in sorted(rings_to_consider):
        bag = state.bags.get(f"R{r}", {})
        if bag:
            out.append(Action(ActionType.EXPLORE, {"ring": r, "draws": 1, "direction": f"adjacent from ring {r-1 if r>1 else r}"}))
    return out

def _enum_research(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    avail = list(state.tech_display.available) if state.tech_display else []
    known = set(you.known_techs or [])
    science = you.resources.science if you.resources else 0
    # Sort by a simple preference: combat techs, mobility, economy
    priority = sorted(avail, key=_tech_priority_key, reverse=True)
    for tech in priority:
        if tech in known:
            continue
        cost = _approx_tech_cost(tech, len(known))
        if science >= cost:
            out.append(Action(ActionType.RESEARCH, {"tech": tech, "approx_cost": cost}))
        # propose one stretch pick even if not fully affordable (you might have discounts)
        elif len(out) < 1 and science >= max(1, cost - 1):
            out.append(Action(ActionType.RESEARCH, {"tech": tech, "approx_cost": cost, "note": "stretch"}))
        if len(out) >= 5:
            break
    return out

def _enum_build(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    mats = you.resources.materials if you.resources else 0
    your_hexes = _player_hexes(state, you.player_id)
    contested = [hx for hx in your_hexes if _enemy_presence_in_hex(state, you.player_id, hx) > 0]

    # Build starbase in contested hex if affordable
    for hx in contested:
        if mats >= SHIP_COSTS["starbase"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "starbase": 1}))

    # Build ships in any controlled hex
    for hx in your_hexes:
        # Try a few affordable bundles
        if mats >= SHIP_COSTS["dreadnought"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"dreadnought": 1}}))
        if mats >= SHIP_COSTS["cruiser"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"cruiser": 1}}))
        if mats >= 2 * SHIP_COSTS["interceptor"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"interceptor": 2}}))
        elif mats >= SHIP_COSTS["interceptor"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"interceptor": 1}}))

    return out

def _enum_moves(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    your_hexes = _player_hexes(state, you.player_id)
    # 1) Assault in place if enemies present
    for hx in your_hexes:
        if _enemy_presence_in_hex(state, you.player_id, hx) > 0:
            ships = dict(hx.pieces[you.player_id].ships)
            if ships:
                out.append(Action(ActionType.MOVE, {"from": hx.id, "to": hx.id, "ships": ships}))
    # 2) Move toward valuable or enemy-held hexes (range-agnostic placeholder)
    enemy_hexes = [hx for hx in state.map.hexes.values() if _enemy_presence_in_hex(state, you.player_id, hx) > 0]
    valuable_empty = sorted(
        [hx for hx in state.map.hexes.values() if _enemy_presence_in_hex(state, you.player_id, hx) == 0],
        key=_hex_value_key,
        reverse=True
    )[:3]
    for src in your_hexes:
        ships = dict(src.pieces[you.player_id].ships)
        if not ships:
            continue
        # aim at top 2 enemy hexes
        for dst in enemy_hexes[:2]:
            if dst.id == src.id:
                continue
            out.append(Action(ActionType.MOVE, {"from": src.id, "to": dst.id, "ships": ships}))
        # aim at one valuable empty hex
        for dst in valuable_empty[:1]:
            if dst.id == src.id:
                continue
            out.append(Action(ActionType.MOVE, {"from": src.id, "to": dst.id, "ships": ships}))
    return out

def _enum_upgrades(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    # Suggest small design improvements if you have ships of that class on the board
    counts: Dict[str,int] = {}
    for hx in state.map.hexes.values():
        p = hx.pieces.get(you.player_id)
        if not p:
            continue
        for cls, n in p.ships.items():
            counts[cls] = counts.get(cls, 0) + int(n)
    if counts.get("interceptor", 0) > 0:
        out.append(Action(ActionType.UPGRADE, {"apply": {"interceptor": {"cannons": +1, "computer": +1}}}))
    if counts.get("cruiser", 0) > 0:
        out.append(Action(ActionType.UPGRADE, {"apply": {"cruiser": {"shield": +1}}}))
    if counts.get("dreadnought", 0) > 0:
        out.append(Action(ActionType.UPGRADE, {"apply": {"dreadnought": {"hull": +1}}}))
    return out

def _enum_influence(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    # Simple heuristic: if a nearby hex has uncolonized planets, consider placing a disc (income +1)
    # We do not track disc supply; caller should filter later if needed.
    target = None
    best_score = 0.0
    for hx in state.map.hexes.values():
        if you.player_id in hx.pieces:
            continue
        score = _hex_value_key(hx)
        if score > best_score:
            best_score, target = score, hx
    if target:
        # approximate one income increase of the dominant color
        color, inc = _dominant_planet_color(target)
        if color:
            income_delta = {"yellow":0, "blue":0, "brown":0}
            income_delta[color] = 1
            out.append(Action(ActionType.INFLUENCE, {"hex": target.id, "income_delta": income_delta}))
    return out

def _enum_diplomacy(state: GameState, you: PlayerState) -> List[Action]:
    out: List[Action] = []
    for pid in (state.players or {}):
        if pid == you.player_id:
            continue
        out.append(Action(ActionType.DIPLOMACY, {"with": pid}))
        if len(out) >= 2:
            break
    return out

# =============================
# Helpers
# =============================

def _player_hexes(state: GameState, pid: str) -> List[Hex]:
    return [hx for hx in state.map.hexes.values() if pid in hx.pieces]

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

def _hex_value_key(hx: Hex) -> float:
    # Value proxy: number of uncolonized planets + monolith bonus
    planets = 0
    for pl in hx.planets:
        if pl.colonized_by is None:
            planets += 1
    return planets + (1.5 if hx.monolith else 0.0)

def _dominant_planet_color(hx: Hex) -> Tuple[Optional[str], int]:
    counts = {"yellow":0, "blue":0, "brown":0}
    for pl in hx.planets:
        if pl.colonized_by is None:
            t = pl.type.lower()
            if t.startswith("y"): counts["yellow"] += 1
            elif t.startswith("b"): counts["blue"] += 1
            elif t.startswith("p") or t.startswith("m"): counts["brown"] += 1
    color = max(counts, key=lambda k: counts[k]) if any(counts.values()) else None
    return (color, counts[color]) if color else (None, 0)

def _tech_priority_key(name: str) -> float:
    s = name.lower()
    score = 0.0
    if any(k in s for k in ("plasma","positron","gauss","antimatter","ion")): score += 2.0
    if "drive" in s: score += 1.5
    if "shield" in s or "hull" in s: score += 1.2
    if "wormhole" in s: score += 1.5
    if "advanced" in s or "labs" in s or "mining" in s or "nanorobot" in s: score += 1.0
    return score

def _approx_tech_cost(name: str, known_count: int) -> int:
    s = name.lower()
    base = 3
    if "iii" in s: base = 7
    elif "ii" in s or "advanced" in s: base = 5
    elif "i" in s: base = 3
    # very rough scaling by known techs simulating track cost increases
    return max(2, base + min(2, known_count//4))

def _dedup_actions(actions: List[Action]) -> List[Action]:
    seen = set()
    out = []
    for a in actions:
        key = (a.type.value, _freeze(a.payload))
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out

def _freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return tuple(sorted((k, _freeze(v)) for k,v in obj.items()))
    if isinstance(obj, list):
        return tuple(_freeze(v) for v in obj)
    return obj