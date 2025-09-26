from __future__ import annotations
from typing import Optional, Dict, Any, Set
from collections import Counter
from dataclasses import dataclass
from copy import deepcopy

from .game_models import GameState, PlayerState, Resources, MapState, TechDisplay, Pieces
from .technology import load_tech_definitions
from .data.exploration_tiles import tile_counts_by_ring, tile_numbers_by_ring

_ROUND_EXPLORED_FRACTION = 0.33


@dataclass(frozen=True)
class _TileCatalog:
    total_by_ring: Dict[int, int]
    tile_ids_by_ring: Dict[int, Set[str]]
    all_tile_ids: Set[str]


def _load_tile_catalog() -> _TileCatalog:
    """Read the exploration tile CSV and index counts by ring."""
    totals_map = tile_counts_by_ring()
    numbers_map = tile_numbers_by_ring()
    if not totals_map:
        return _TileCatalog(total_by_ring={}, tile_ids_by_ring={}, all_tile_ids=set())

    all_ids = set().union(*(set(ids) for ids in numbers_map.values())) if numbers_map else set()
    return _TileCatalog(
        total_by_ring=dict(totals_map),
        tile_ids_by_ring={ring: set(ids) for ring, ids in numbers_map.items()},
        all_tile_ids=all_ids,
    )


_TILE_CATALOG = _load_tile_catalog()

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
    if not gs.tech_definitions:
        gs.tech_definitions = load_tech_definitions()
    # Update core
    gs.map = map_state
    gs.tech_display = tech_display

    # Ensure players seen on the board exist
    _reconcile_players_from_map(gs)

    # Ensure bag placeholders for observed rings
    _ensure_bags_for_rings(gs)
    _populate_explore_bags(gs)

    # Ensure player tech state derived from any known tech lists remains consistent.
    for p in gs.players.values():
        _initialise_player_state(p, gs.tech_definitions)

    # Apply manual inputs
    if manual_inputs:
        _apply_manual_inputs(gs, manual_inputs)
        for p in gs.players.values():
            _initialise_player_state(p, gs.tech_definitions)

    _validate_existing_designs(gs)

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
        "you": PlayerState(player_id="you", color="orange", resources=Resources(10,7,6), influence_discs=3),
        "blue": PlayerState(player_id="blue", color="blue", resources=Resources(8,6,7), influence_discs=3)
    }
    gs = GameState(round=6, active_player="you", players=players, map=MapState(), tech_display=TechDisplay())
    for p in gs.players.values():
        _initialise_player_state(p, gs.tech_definitions)
    gs.tech_definitions = load_tech_definitions()
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
                new_player = PlayerState(player_id=pid, color=pid, resources=Resources(6,6,6))
                _initialise_player_state(new_player, gs.tech_definitions)
                gs.players[pid] = new_player
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


def _populate_explore_bags(gs: GameState) -> None:
    """Backfill exploration bag sizes using CSV totals and board state."""
    if not _TILE_CATALOG.total_by_ring:
        return
    round_num = max(1, int(getattr(gs, "round", 1)))
    player_count = max(1, len(getattr(gs, "players", {}) or {}))
    explored_by_ring = _count_explored_tiles(gs, player_count)

    for ring, total in _TILE_CATALOG.total_by_ring.items():
        key = f"R{ring}"
        bag = gs.bags.setdefault(key, {})
        if bag and sum(bag.values()) > 0:
            # Caller already supplied explicit bag contents; trust it.
            continue

        # Estimate explored tiles either from the board or heuristic round progression.
        heuristic = int(total * min(1.0, max(0.0, (round_num - 1) * _ROUND_EXPLORED_FRACTION)))
        explored = max(explored_by_ring.get(ring, 0), heuristic)
        remaining = max(0, total - explored)

        if remaining > 0:
            gs.bags[key] = {"unknown": remaining}
        else:
            gs.bags[key] = {}


def _count_explored_tiles(gs: GameState, player_count: int) -> Counter[int]:
    counts: Counter[int] = Counter()
    fallback: Counter[int] = Counter()
    for hx in gs.map.hexes.values():
        ring = max(1, int(getattr(hx, "ring", 1)))
        fallback[ring] += 1
        hid = str(getattr(hx, "id", "")).strip()
        if hid and hid in _TILE_CATALOG.tile_ids_by_ring.get(ring, set()):
            counts[ring] += 1

    for ring, fallback_count in fallback.items():
        if counts[ring] >= fallback_count:
            continue
        additional = fallback_count - counts[ring]
        if ring == 1:
            additional = max(0, additional - player_count)
        if additional > 0:
            counts[ring] += additional

    return counts


def _initialise_player_state(player: PlayerState, definitions: Optional[Dict[str, "Tech"]]=None) -> None:
    from .technology import load_tech_definitions  # local import to avoid cycles

    tech_defs = definitions or load_tech_definitions()
    player.science = int(player.science or player.resources.science)
    if player.influence_discs is None:
        player.influence_discs = 0
    player.influence_discs = int(player.influence_discs)
    player.owned_tech_ids = set(player.owned_tech_ids or set())
    player.tech_count_by_category = dict(player.tech_count_by_category or {})
    player.unlocked_parts = set(player.unlocked_parts or set())
    player.unlocked_structures = set(player.unlocked_structures or set())
    player.species_flags = dict(player.species_flags or {})
    player.action_overrides = dict(player.action_overrides or {})
    player.build_overrides = dict(player.build_overrides or {})
    player.move_overrides = dict(player.move_overrides or {})
    player.explore_overrides = dict(player.explore_overrides or {})
    player.cannot_build = set(player.cannot_build or set())
    player.vp_bonuses = dict(player.vp_bonuses or {})
    player.species_pools = dict(player.species_pools or {})
    player.special_resources = dict(player.special_resources or {})

    name_to_id = {t.name.lower(): tid for tid, t in tech_defs.items()}
    for entry in list(player.known_techs or []):
        tid = name_to_id.get(entry.lower())
        if tid:
            player.owned_tech_ids.add(tid)

    # Recompute caches from owned techs
    player.tech_count_by_category.clear()
    player.unlocked_parts.clear()
    player.unlocked_structures.clear()
    for tid in list(player.owned_tech_ids):
        tech = tech_defs.get(tid)
        if not tech:
            continue
        player.tech_count_by_category[tech.category] = player.tech_count_by_category.get(tech.category, 0) + 1
        player.unlocked_parts.update(tech.grants_parts)
        player.unlocked_structures.update(tech.grants_structures)
        if tech.name not in player.known_techs:
            player.known_techs.append(tech.name)
            
def _validate_existing_designs(gs: GameState) -> None:
    try:
        from .rules_engine import validate_design
    except ImportError:
        return

    for player in gs.players.values():
        for ship_type, design in (player.ship_designs or {}).items():
            try:
                validate_design(player, ship_type, design)
            except Exception:
                raise

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
