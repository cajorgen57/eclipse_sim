"""Forward state model and planning data structures for Eclipse.

This module provides:
- Data structures for representing action plans (Plan, PlanStep)
- Forward state model (_forward_model) for simulating action effects
- Movement validation and execution helpers
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Mapping
import copy

from .game_models import GameState, Action, Score, ActionType, PlayerState, Hex, Pieces, ShipDesign
from .alliances import ship_presence
from .movement import LEGAL_CONNECTION_TYPES, classify_connection, max_ship_activations_per_action
from .resource_colors import canonical_resource_counts
from .technology import do_research, ResearchError, load_tech_definitions
from .pathing import compute_connectivity
from .models.economy import Economy, count_action_discs, count_influence_discs

# =============================
# Public data structures
# =============================

@dataclass
class PlanStep:
    action: Action
    score: Score

@dataclass
class Plan:
    steps: List[PlanStep] = field(default_factory=list)
    total_score: float = 0.0
    risk: float = 0.0
    state_summary: Dict[str, Any] = field(default_factory=dict)
    result_state: Optional[GameState] = None

# =============================
# Forward model (lightweight)
# =============================

# Local cost table to keep forward model self-contained
_SHIP_COSTS = {"interceptor": 3, "cruiser": 5, "dreadnought": 8}
_STARBASE_COST = 3
_SCIENCE_COST_BASE = 3  # rough


def _refresh_connectivity(state: GameState, pid: str) -> None:
    try:
        reach = compute_connectivity(state, pid)
        state.connectivity_metrics[pid] = {
            "reachable": sorted(reach),
            "count": len(reach),
        }
    except Exception:
        pass


def _ensure_player_economy(player: PlayerState) -> Economy:
    econ = getattr(player, "economy", None)
    if isinstance(econ, Economy):
        return econ
    econ_obj = Economy()
    if isinstance(econ, Mapping):
        try:
            econ_obj = Economy(**econ)  # type: ignore[arg-type]
        except Exception:
            econ_obj = Economy()
    player.economy = econ_obj
    return econ_obj


def _update_economy_snapshot(state: GameState, player: PlayerState) -> None:
    econ = _ensure_player_economy(player)
    board_slots = count_action_discs(player)
    if board_slots > econ.action_slots_filled:
        econ.action_slots_filled = board_slots
    econ.refresh(
        bank=int(getattr(player.resources, "money", 0) or 0),
        income=int(getattr(player.income, "money", 0) or 0),
        upkeep_fixed=count_influence_discs(state, player.player_id),
        action_slots_filled=econ.action_slots_filled,
    )


def _finalise_forward_state(state: GameState, player: PlayerState, *, increment_slot: bool) -> GameState:
    econ = _ensure_player_economy(player)
    if increment_slot:
        econ.action_slots_filled = max(0, econ.action_slots_filled + 1)
    _update_economy_snapshot(state, player)
    _refresh_connectivity(state, player.player_id)
    return state

def _forward_model(state: GameState, pid: str, action: Action) -> GameState:
    """Very small deterministic forward model sufficient for short planning.
    Applies optimistic but resource-aware state changes. Non-destructive via deepcopy.
    """
    s = copy.deepcopy(state)

    # Safety checks
    if pid not in s.players:
        return s
    you = s.players[pid]

    t = action.type
    p = action.payload or {}

    if t == ActionType.PASS:
        # Terminal in our single-player horizon; no change
        you.passed = True
        return _finalise_forward_state(s, you, increment_slot=False)

    if t == ActionType.RESEARCH:
        tech = str(p.get("tech", ""))
        if tech:
            if not s.tech_definitions:
                s.tech_definitions = load_tech_definitions()
            try:
                do_research(s, you, tech)
            except ResearchError:
                pass
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.BUILD:
        hex_id = p.get("hex")
        ships: Dict[str,int] = dict(p.get("ships", {}))
        starbase = int(p.get("starbase", 0))
        hx = s.map.hexes.get(hex_id)
        if hx is None:
            # create a placeholder hex if needed
            hx = Hex(id=str(hex_id), ring=2, wormholes=[], planets=[], pieces={})
            s.map.place_hex(hx)
        if pid not in hx.pieces:
            hx.pieces[pid] = Pieces(ships={}, starbase=0, discs=hx.pieces.get(pid, Pieces()).discs if pid in hx.pieces else 0, cubes={})

        # Apply ship builds constrained by materials
        mats = you.resources.materials
        for cls, n in ships.items():
            for _ in range(int(n)):
                c = _SHIP_COSTS.get(cls, 3)
                if mats >= c:
                    mats -= c
                    hx.pieces[pid].ships[cls] = hx.pieces[pid].ships.get(cls, 0) + 1
        if starbase > 0 and mats >= _STARBASE_COST:
            mats -= _STARBASE_COST
            hx.pieces[pid].starbase += 1
        you.resources.materials = mats
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.MOVE:
        try:
            _apply_move_action(s, pid, p)
        except ValueError:
            _refresh_connectivity(state, pid)
            return state  # illegal move payloads are ignored in the forward model
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.EXPLORE:
        # Optimistic: reduce bag mass slightly to reflect drawing; do not place new hex
        ring = int(p.get("ring", 2))
        bag_key = f"R{ring}"
        if bag_key in s.bags:
            # Reduce the heaviest category by 1 as a placeholder draw
            bag = s.bags[bag_key]
            if bag:
                key = max(bag, key=lambda k: bag[k])
                if bag[key] > 0:
                    bag[key] -= 1
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.INFLUENCE:
        # Adjust income proxy via cubes; not modeling discs inventory
        hex_id = p.get("hex")
        inc = canonical_resource_counts(p.get("income_delta", {}), include_zero=False)
        # store a marker by adding cubes to the hex
        hx = s.map.hexes.get(hex_id)
        if hx:
            if pid not in hx.pieces:
                hx.pieces[pid] = Pieces(ships={}, starbase=0, discs=1, cubes={})
            for color, dv in inc.items():
                hx.pieces[pid].cubes[color] = hx.pieces[pid].cubes.get(color, 0) + max(0, int(dv))
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.DIPLOMACY:
        # Store alliance in player state
        target = p.get("with")
        if target:
            you.diplomacy[target] = "ally"
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.UPGRADE:
        # Apply incremental design changes
        apply = p.get("apply", {})
        for cls, mods in apply.items():
            sd = you.ship_designs.get(cls, ShipDesign())
            for k, dv in mods.items():
                if hasattr(sd, k):
                    setattr(sd, k, max(0, getattr(sd, k) + int(dv)))
            you.ship_designs[cls] = sd
        return _finalise_forward_state(s, you, increment_slot=True)

    if t == ActionType.REACTION:
        return _finalise_forward_state(s, you, increment_slot=True)

    # Unknown action -> treat as consuming an action slot with no other changes
    return _finalise_forward_state(s, you, increment_slot=True)

# =============================
# Movement helpers and executor
# =============================

def _apply_move_action(state: GameState, pid: str, payload: Dict[str, Any]) -> None:
    """Validate and apply a MOVE action with full Eclipse legality checks."""
    working = copy.deepcopy(state)

    activations = list(payload.get("activations", []))
    if not activations:
        raise ValueError("MOVE requires activations payload")

    player = working.players.get(pid)
    if player is None:
        raise ValueError("Unknown player for MOVE")

    is_reaction = bool(payload.get("is_reaction") or payload.get("reaction"))
    max_activations = max_ship_activations_per_action(player, is_reaction=is_reaction)
    if len(activations) > max_activations:
        raise ValueError("Too many ship activations for this action")

    for activation in activations:
        _execute_activation(working, player, activation, is_reaction=is_reaction)

    # Commit the simulated changes back to the real state only after validation succeeds.
    state.players = working.players
    state.map = working.map


def _execute_activation(
    state: GameState,
    player: PlayerState,
    activation: Dict[str, Any],
    *,
    is_reaction: bool = False,
) -> None:
    ship_class = str(activation.get("ship_class", ""))
    if not ship_class:
        raise ValueError("Activation missing ship class")
    start_hex_id = str(activation.get("from", ""))
    if not start_hex_id:
        raise ValueError("Activation missing starting hex")

    path = list(activation.get("path", []))
    if not path:
        raise ValueError("Activation requires explicit path including start")
    if path[0] != start_hex_id:
        raise ValueError("Path must begin at starting hex")

    count = int(activation.get("count", 1))
    if count <= 0:
        raise ValueError("Activation must move at least one ship")
    if is_reaction and count != 1:
        raise ValueError("Reaction MOVE may activate exactly one ship")

    for _ in range(count):
        _activate_single_ship(state, player, ship_class, path, activation)


def _activate_single_ship(state: GameState, player: PlayerState, ship_class: str, path: List[str], activation: Dict[str, Any]) -> None:
    you = player.player_id
    current_hex = _require_hex(state, path[0])
    pieces = current_hex.pieces.get(you)
    if pieces is None or pieces.ships.get(ship_class, 0) <= 0:
        raise ValueError("No ship of requested class in starting hex")

    friendly_start, enemy_start = ship_presence(state, current_hex, you)
    pinned_at_start = enemy_start > 0

    design = player.ship_designs.get(ship_class, ShipDesign())
    if ship_class == "starbase":
        if len(path) > 1:
            raise ValueError("Starbases cannot move")
        return

    movement_points = design.movement_value()
    has_jump = bool(design.has_jump_drive)
    if len(path) > 1 and movement_points <= 0 and not has_jump:
        if ship_class in {"interceptor", "cruiser", "dreadnought"}:
            raise ValueError("Ship lacks drives and cannot move")

    bay_payload = activation.get("bay") if design.interceptor_bays > 0 else None
    carried_interceptors = 0
    if bay_payload:
        carried_interceptors = int(bay_payload.get("interceptors", 0))
        if carried_interceptors < 0:
            raise ValueError("Cannot load negative interceptors")
        capacity = min(2, design.interceptor_bays)
        if carried_interceptors > capacity:
            raise ValueError("Interceptor Bay capacity exceeded")
        available = pieces.ships.get("interceptor", 0)
        if carried_interceptors > available:
            raise ValueError("Not enough interceptors to load into bay")

    # Enforce pinning when leaving the starting hex, including any interceptors we plan to carry.
    if pinned_at_start:
        activation.setdefault("pinned", True)
    _enforce_exit_pinning(state, current_hex, you, 1 + carried_interceptors)

    if carried_interceptors:
        _remove_ships_from_hex(current_hex, you, "interceptor", carried_interceptors)

    jump_used = False
    steps_remaining = movement_points
    current_hex_id = path[0]

    for idx, next_hex_id in enumerate(path[1:], start=1):
        next_hex = _require_hex(state, next_hex_id)
        if not next_hex.explored:
            raise ValueError("Cannot move into unexplored hex")

        src_hex = _require_hex(state, current_hex_id)
        if src_hex.has_gcds:
            raise ValueError("GCDS blocks movement through the Galactic Center")

        connection_type = classify_connection(
            state,
            player,
            current_hex_id,
            next_hex_id,
            ship_design=design,
            ship_class=ship_class,
        )
        if connection_type not in LEGAL_CONNECTION_TYPES:
            raise ValueError("No legal connection between hexes")

        if connection_type == "jump":
            if not has_jump or jump_used:
                raise ValueError("Jump Drive already used this activation")
            jump_used = True
        else:
            if steps_remaining <= 0:
                raise ValueError("Movement exceeds drive allowance")
            steps_remaining -= 1

        # Leaving current hex after validating movement points.
        _enforce_exit_pinning(state, src_hex, you, 1)
        _move_ship_between_hexes(state, you, ship_class, current_hex_id, next_hex_id)

        dst_hex = _require_hex(state, next_hex_id)
        enemy_in_dst = _count_enemy_ships(state, dst_hex, you)
        if idx < len(path) - 1:
            if dst_hex.has_gcds:
                raise ValueError("Cannot move through the Galactic Center while GCDS is active")
            if enemy_in_dst > 0:
                friendly_total = _count_friendly_ships(state, dst_hex, you)
                if friendly_total <= enemy_in_dst:
                    raise ValueError("Pinned upon entering contested hex")

        current_hex_id = next_hex_id

    # Re-add any interceptors transported in the bay to the final destination.
    if carried_interceptors:
        dest_hex = _require_hex(state, current_hex_id)
        dest_pieces = dest_hex.pieces.setdefault(you, Pieces())
        dest_pieces.ships["interceptor"] = dest_pieces.ships.get("interceptor", 0) + carried_interceptors


def _require_hex(state: GameState, hex_id: str) -> Hex:
    hx = state.map.hexes.get(hex_id)
    if hx is None:
        raise ValueError(f"Hex {hex_id} is not on the map")
    return hx


def _move_ship_between_hexes(state: GameState, pid: str, ship_class: str, src_id: str, dst_id: str) -> None:
    src_hex = _require_hex(state, src_id)
    dst_hex = _require_hex(state, dst_id)
    _remove_ships_from_hex(src_hex, pid, ship_class, 1)
    dst_pieces = dst_hex.pieces.setdefault(pid, Pieces())
    dst_pieces.ships[ship_class] = dst_pieces.ships.get(ship_class, 0) + 1


def _remove_ships_from_hex(hex_obj: Hex, pid: str, ship_class: str, count: int) -> None:
    if count <= 0:
        return
    pieces = hex_obj.pieces.get(pid)
    if pieces is None:
        raise ValueError("Player has no ships to remove")
    have = pieces.ships.get(ship_class, 0)
    if have < count:
        raise ValueError("Attempting to move more ships than present")
    pieces.ships[ship_class] = have - count
    if pieces.ships[ship_class] <= 0:
        del pieces.ships[ship_class]


def _count_enemy_ships(state: GameState, hex_obj: Hex, pid: str) -> int:
    if not hex_obj:
        return 0
    _, enemy = ship_presence(state, hex_obj, pid)
    return enemy


def _count_friendly_ships(state: GameState, hex_obj: Hex, pid: str) -> int:
    if not hex_obj:
        return 0
    friendly, _ = ship_presence(state, hex_obj, pid)
    return friendly


def _enforce_exit_pinning(state: GameState, hex_obj: Hex, pid: str, leaving: int) -> None:
    enemy = _count_enemy_ships(state, hex_obj, pid)
    if enemy <= 0:
        return
    friendly = _count_friendly_ships(state, hex_obj, pid)
    if friendly - leaving < enemy:
        raise ValueError("Cannot leave contested hex without leaving pinned ships")
