from __future__ import annotations
from typing import Optional, Dict, Any, Set
from copy import deepcopy

from .types import GameState, PlayerState, Resources, MapState, TechDisplay, Pieces

# -----------------------------
# Public API
# -----------------------------

def assemble_state(
    map_state: MapState,
    tech_display: TechDisplay,
    prior_state: Optional[GameState]=None,
    manual_inputs: Optional[Dict[str,Any]]=None
) -> GameState:
    """
    Combine parsed board + tech into a canonical GameState.

    Rules:
      - If prior_state is provided, it is deep-copied then updated in place.
      - Players discovered from the board are auto-added with neutral defaults.
      - Bags are ensured for any rings observed on the map. Existing bag counts are preserved.
      - manual_inputs can be nested dicts or dot-path overrides (e.g., "players.you.resources.money": 12).
    """
    gs = deepcopy(prior_state) if prior_state is not None else _default_state()
    # Update core
    gs.map = map_state
    gs.tech_display = tech_display

    # Ensure players seen on the board exist
    _reconcile_players_from_map(gs)

    # Ensure bag placeholders for observed rings
    _ensure_bags_for_rings(gs)

    # Apply manual inputs
    if manual_inputs:
        _apply_manual_inputs(gs, manual_inputs)

    return gs

# -----------------------------
# Defaults and reconciliation
# -----------------------------

def from_dict(fake_state: Dict[str, Any]) -> GameState:
    """Build a GameState directly from a test dict."""
    return GameState.from_dict(fake_state)


def apply_overrides(state: GameState, manual_inputs: Dict[str, Any]) -> GameState:
    """Apply targeted overrides onto an existing state."""
    if not manual_inputs:
        return state
    # Special-case persisted belief if you use it
    belief = manual_inputs.pop("belief", None)
    state.apply_overrides(manual_inputs)
    if belief is not None:
        # allow full replacement or merge, depending on your belief type
        try:
            state.belief = belief if not hasattr(state.belief, "apply_overrides") else state.belief.apply_overrides(belief)
        except Exception:
            state.belief = belief
    return state

def _default_state() -> GameState:
    players = {
        "you": PlayerState(player_id="you", color="orange", resources=Resources(10,7,6)),
        "blue": PlayerState(player_id="blue", color="blue", resources=Resources(8,6,7))
    }
    gs = GameState(round=6, active_player="you", players=players, map=MapState(), tech_display=TechDisplay())
    # Provide a minimal example bag so exploration math runs. Caller should replace with real counts.
    gs.bags = {"R2": {"ancient":3, "monolith":1, "money2":4, "science2":4, "materials2":4}}
    return gs

def _reconcile_players_from_map(gs: GameState) -> None:
    # Discover player ids present in map pieces
    present: Set[str] = set(gs.players.keys())
    for hx in gs.map.hexes.values():
        for pid in hx.pieces.keys():
            if pid not in present:
                present.add(pid)
                # Neutral defaults
                gs.players[pid] = PlayerState(player_id=pid, color=pid, resources=Resources(6,6,6))
            # Ensure Pieces data structure is well-formed
            p = hx.pieces[pid]
            if p.cubes is None:
                p.cubes = {}
            if p.ships is None:
                p.ships = {}

def _ensure_bags_for_rings(gs: GameState) -> None:
    rings = set()
    for hx in gs.map.hexes.values():
        rings.add(max(1, int(getattr(hx, "ring", 1))))
    if not hasattr(gs, "bags") or gs.bags is None:
        gs.bags = {}
    for r in sorted(rings):
        key = f"R{r}"
        if key not in gs.bags:
            gs.bags[key] = {}  # placeholder; upstream uncertainty module can populate a PF on demand

# -----------------------------
# Manual inputs
# -----------------------------

def _apply_manual_inputs(gs: GameState, manual: Dict[str,Any]) -> None:
    """
    Supports two forms:
      1) Nested dicts mirroring GameState structure for deep merge.
      2) Dot-path keys for targeted sets, e.g. {"players.you.resources.money": 12}
    """
    # Split dot-path keys from nested dict blocks
    dot_items = {k:v for k,v in manual.items() if isinstance(k, str) and "." in k}
    tree_items = {k:v for k,v in manual.items() if k not in dot_items}

    # Deep merge dict-style patches
    if tree_items:
        _deep_merge_object(gs, tree_items)

    # Dot-path sets
    for path, value in dot_items.items():
        _set_by_path(gs, path, value)

def _deep_merge_object(obj: Any, patch: Dict[str,Any]) -> None:
    """
    Recursively merge dictionaries into dataclass-like objects by attribute.
    """
    for key, val in patch.items():
        if not hasattr(obj, key):
            # create attribute if missing
            setattr(obj, key, deepcopy(val))
            continue
        curr = getattr(obj, key)
        if isinstance(val, dict) and not isinstance(curr, (int, float, str, list, tuple, set)):
            _deep_merge_object(curr, val)
        else:
            setattr(obj, key, deepcopy(val))

def _set_by_path(root: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    obj = root
    for p in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj.setdefault(p, {})
        else:
            if not hasattr(obj, p) or getattr(obj, p) is None:
                setattr(obj, p, {})
            obj = getattr(obj, p)
    last = parts[-1]
    if isinstance(obj, dict):
        obj[last] = value
    else:
        setattr(obj, last, value)
