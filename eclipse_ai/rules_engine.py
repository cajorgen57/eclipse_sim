from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from .game_models import GameState, Action, ActionType, PlayerState, Hex, Planet, Pieces, Resources
from .ship_parts import SHIP_PARTS, SHIP_BLUEPRINT_SLOTS, MOBILE_SHIPS
from .types import ShipDesign

# =============================
# Config
# =============================

@dataclass
class RulesConfig:
    expansions: Dict[str, bool] = field(default_factory=lambda: {"RoA": True, "SoTR": False})
    enable_influence: bool = True
    enable_diplomacy: bool = True
    max_actions: int = 40  # hard cap to avoid explosion

# Build costs and fleet caps share a single source of truth for the UI/tests.
BUILD_COST: Dict[str, int] = {
    "interceptor": 3,
    "cruiser": 5,
    "dreadnought": 8,
    "starbase": 3,
    "orbital": 5,
    "monolith": 10,
}

FLEET_CAP: Dict[str, int] = {
    "interceptor": 8,
    "cruiser": 4,
    "dreadnought": 2,
    "starbase": 4,
}

STRUCTURE_TECH_REQUIREMENTS: Dict[str, str] = {
    "starbase": "Starbase",
    "orbital": "Orbital",
    "monolith": "Monolith",
}


class RulesViolation(ValueError):
    """Raised when an attempted action violates the core rulebook."""


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
        if mats >= BUILD_COST["starbase"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "starbase": 1}))

    # Build ships in any controlled hex
    for hx in your_hexes:
        # Try a few affordable bundles
        if mats >= BUILD_COST["dreadnought"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"dreadnought": 1}}))
        if mats >= BUILD_COST["cruiser"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"cruiser": 1}}))
        if mats >= 2 * BUILD_COST["interceptor"]:
            out.append(Action(ActionType.BUILD, {"hex": hx.id, "ships": {"interceptor": 2}}))
        if mats >= BUILD_COST["interceptor"]:
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

# =============================
# Validators
# =============================

def validate_design(player: PlayerState, ship_type: str, blueprint: Any) -> None:
    """Validate and normalise a ship blueprint according to the rulebook."""

    design = _coerce_ship_design(blueprint)
    ship_key = _normalize_ship_class(ship_type)
    if ship_key not in SHIP_BLUEPRINT_SLOTS:
        raise RulesViolation(f"Unknown ship type '{ship_type}' for design validation")

    part_maps = _design_part_maps(design)
    has_explicit_parts = any(part_maps[attr] for attr in part_maps)

    if not has_explicit_parts:
        _validate_legacy_design(player, ship_key, design)
        return

    slot_limit = SHIP_BLUEPRINT_SLOTS[ship_key]
    totals = Counter()
    known_techs = set(player.known_techs or [])

    for attr, category in (
        ("computer_parts", "computer"),
        ("shield_parts", "shield"),
        ("cannon_parts", "cannon"),
        ("missile_parts", "missile"),
        ("drive_parts", "drive"),
        ("energy_sources", "energy"),
        ("hull_parts", "hull"),
    ):
        clean = _sanitize_part_dict(getattr(design, attr, {}), category)
        setattr(design, attr, clean)
        for part_name, count in clean.items():
            part = SHIP_PARTS.get(part_name)
            if not part:
                raise RulesViolation(f"Unknown ship part '{part_name}' on {ship_type}")
            if part.category != category and not (category == "energy" and part.category == "energy"):
                raise RulesViolation(
                    f"Part '{part_name}' cannot be placed in {category} slots"
                )
            if part.requires_tech and part.requires_tech not in known_techs:
                raise RulesViolation(
                    f"{player.player_id} must research {part.requires_tech} before using {part.name}"
                )
            totals["slots"] += part.slots * count
            totals["initiative"] += part.initiative * count
            totals["energy_consumption"] += part.energy_consumption * count
            totals["energy_production"] += part.energy_production * count
            if part.category == "computer":
                totals["computer"] += part.computer * count
            if part.category == "shield":
                totals["shield"] += part.shield * count
            if part.category == "hull":
                totals["hull"] += part.hull * count
            if part.category == "cannon":
                totals["cannon_power"] += part.weapon_strength * count
            if part.category == "missile":
                totals["missiles"] += part.missiles * count
                totals["initiative"] += part.initiative * count
            if part.category == "drive":
                totals["movement"] += part.movement * count
                totals["drive_count"] += count

    if totals["slots"] > slot_limit:
        raise RulesViolation(
            f"{ship_type.title()} blueprint exceeds its {slot_limit}-slot limit"
        )

    if ship_key == "starbase" and totals["drive_count"] > 0:
        raise RulesViolation("Starbases may not equip Drives")

    design.initiative = totals["initiative"]
    design.movement_value = totals["movement"]
    design.energy_consumption = totals["energy_consumption"]
    design.energy_production = totals["energy_production"]
    design.computer = totals["computer"]
    design.shield = totals["shield"]
    design.hull = max(1, totals["hull"])
    design.cannons = totals["cannon_power"]
    design.missiles = totals["missiles"]
    design.drive = totals["drive_count"]

    if design.energy_production - design.energy_consumption < 0:
        raise RulesViolation(
            f"{ship_type.title()} design consumes more energy than it produces"
        )

    if ship_key in MOBILE_SHIPS and design.drive <= 0:
        raise RulesViolation(f"{ship_type.title()} must include at least one Drive")


def _validate_legacy_design(player: PlayerState, ship_key: str, design: ShipDesign) -> None:
    """Fallback validation for older aggregated blueprints with no part data."""

    if ship_key in MOBILE_SHIPS and design.drive <= 0:
        raise RulesViolation(f"{ship_key.title()} must include at least one Drive")
    if ship_key == "starbase" and design.drive > 0:
        raise RulesViolation("Starbases may not equip Drives")
    energy_delta = design.energy_production - design.energy_consumption
    if energy_delta < 0:
        raise RulesViolation(
            f"{player.player_id}'s {ship_key} blueprint is energy negative"
        )
    if ship_key in MOBILE_SHIPS and design.movement_value < design.drive:
        design.movement_value = design.drive


def _coerce_ship_design(blueprint: Any) -> ShipDesign:
    if isinstance(blueprint, ShipDesign):
        return blueprint
    if isinstance(blueprint, dict):
        design = ShipDesign()
        for attr, aliases in (
            ("computer_parts", ["computer_parts", "computers"]),
            ("shield_parts", ["shield_parts", "shields"]),
            ("cannon_parts", ["cannon_parts", "cannons"]),
            ("missile_parts", ["missile_parts", "missiles"]),
            ("drive_parts", ["drive_parts", "drives"]),
            ("energy_sources", ["energy_sources", "sources", "energy"]),
            ("hull_parts", ["hull_parts", "hulls"]),
        ):
            for key in aliases:
                if key in blueprint and isinstance(blueprint[key], dict):
                    setattr(design, attr, dict(blueprint[key]))
                    break
        for key in (
            "computer",
            "shield",
            "initiative",
            "hull",
            "cannons",
            "missiles",
            "drive",
            "movement_value",
            "energy_consumption",
            "energy_production",
        ):
            if key in blueprint:
                setattr(design, key, int(blueprint[key]))
        return design
    raise RulesViolation("Blueprint payload must be a ShipDesign or dict")


def _sanitize_part_dict(parts: Optional[Dict[str, Any]], category: str) -> Dict[str, int]:
    clean: Dict[str, int] = {}
    if not parts:
        return clean
    for name, value in parts.items():
        if value is None:
            continue
        count = int(value)
        if count < 0:
            raise RulesViolation(f"Cannot place a negative number of {category} parts")
        if count == 0:
            continue
        clean[str(name)] = count
    return clean


def _design_part_maps(design: ShipDesign) -> Dict[str, Dict[str, int]]:
    return {
        "computer_parts": design.computer_parts,
        "shield_parts": design.shield_parts,
        "cannon_parts": design.cannon_parts,
        "missile_parts": design.missile_parts,
        "drive_parts": design.drive_parts,
        "energy_sources": design.energy_sources,
        "hull_parts": design.hull_parts,
    }


def _normalize_ship_class(ship_type: str) -> str:
    return str(ship_type or "").strip().lower()


def validate_build(player: PlayerState, thing: Any, hex_id: str) -> None:
    """Validate a build action before applying it."""

    if not isinstance(thing, dict):
        raise RulesViolation("Build payload must be a dict")

    state: Optional[GameState] = thing.get("state") or thing.get("game_state")
    if not isinstance(state, GameState):
        raise RulesViolation("Build validation requires the current GameState under 'state'")

    ships = _sanitize_count_dict(thing.get("ships", {}))
    structures = _sanitize_count_dict(thing.get("structures", {}))

    # Support legacy payloads like {"starbase":1}
    for cls in ("interceptor", "cruiser", "dreadnought", "starbase"):
        if cls in thing:
            ships[cls] = ships.get(cls, 0) + int(thing[cls])
    for struct in ("orbital", "monolith"):
        if struct in thing:
            structures[struct] = structures.get(struct, 0) + int(thing[struct])

    total_builds = sum(ships.values()) + sum(structures.values())
    if total_builds == 0:
        raise RulesViolation("Build action must create at least one ship or structure")
    if total_builds > 2:
        raise RulesViolation("Build action is limited to two ships/structures per action")

    known_techs = set(player.known_techs or [])

    cost = 0
    for cls, count in ships.items():
        key = _normalize_ship_class(cls)
        if key not in BUILD_COST:
            raise RulesViolation(f"Unsupported ship class '{cls}' for building")
        cost += BUILD_COST[key] * count
        if key == "starbase":
            tech = STRUCTURE_TECH_REQUIREMENTS.get("starbase")
            if tech and tech not in known_techs:
                raise RulesViolation("Research Starbase before building one")
    for struct, count in structures.items():
        key = _normalize_ship_class(struct)
        if key not in BUILD_COST:
            raise RulesViolation(f"Unsupported structure '{struct}' for building")
        cost += BUILD_COST[key] * count

    if player.resources.materials < cost:
        raise RulesViolation(
            f"Building these units costs {cost} Materials but only {player.resources.materials} are available"
        )

    hx = state.map.hexes.get(hex_id) if state.map else None
    if not hx:
        raise RulesViolation(f"Hex '{hex_id}' does not exist")
    pieces = hx.pieces.get(player.player_id)
    if not pieces or pieces.discs <= 0:
        raise RulesViolation("You must have an Influence Disc in the chosen hex to build there")

    _enforce_structure_rules(player, hx, structures)

    existing = _count_player_ships_on_board(state, player.player_id)
    for cls, count in ships.items():
        key = _normalize_ship_class(cls)
        cap = FLEET_CAP.get(key)
        if cap is not None and existing.get(key, 0) + count > cap:
            raise RulesViolation(
                f"Building {count} {key}s would exceed the fleet cap of {cap}"
            )
        supply = player.available_components.get(key)
        if supply is not None and count > supply:
            raise RulesViolation(
                f"{player.player_id} has only {supply} {key} miniature(s) remaining"
            )

    for struct, count in structures.items():
        supply = player.available_components.get(_normalize_ship_class(struct))
        if supply is not None and count > supply:
            raise RulesViolation(
                f"{player.player_id} has only {supply} {struct} component(s) remaining"
            )


def _sanitize_count_dict(raw: Any) -> Dict[str, int]:
    clean: Dict[str, int] = {}
    if not isinstance(raw, dict):
        return clean
    for name, value in raw.items():
        if value is None:
            continue
        count = int(value)
        if count < 0:
            raise RulesViolation("Cannot build a negative number of units")
        if count == 0:
            continue
        clean[str(name)] = count
    return clean


def _enforce_structure_rules(player: PlayerState, hx: Hex, structures: Dict[str, int]) -> None:
    for struct, count in structures.items():
        key = _normalize_ship_class(struct)
        if key not in ("orbital", "monolith"):
            continue
        tech = STRUCTURE_TECH_REQUIREMENTS.get(key)
        if tech and tech not in set(player.known_techs or []):
            raise RulesViolation(f"Research {tech} before building {struct}")
        if count > 1:
            raise RulesViolation(f"Only one {struct.title()} may be built in a hex")
        if key == "orbital" and hx.orbital:
            raise RulesViolation("Each hex may only contain one Orbital")
        if key == "monolith" and hx.monolith:
            raise RulesViolation("Each hex may only contain one Monolith")


def _count_player_ships_on_board(state: GameState, player_id: str) -> Dict[str, int]:
    totals: Counter[str] = Counter()
    for hx in state.map.hexes.values():
        pieces = hx.pieces.get(player_id)
        if not pieces:
            continue
        for cls, count in pieces.ships.items():
            totals[_normalize_ship_class(cls)] += int(count)
        if pieces.starbase:
            totals["starbase"] += int(pieces.starbase)
    return dict(totals)

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