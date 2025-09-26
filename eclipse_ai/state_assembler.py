from __future__ import annotations
from typing import Optional, Dict, Any, Set
import csv
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from copy import deepcopy

from .game_models import GameState, PlayerState, Resources, MapState, TechDisplay, Pieces

_ROUND_EXPLORED_FRACTION = 0.33


@dataclass(frozen=True)
class _TileCatalog:
    total_by_ring: Dict[int, int]
    tile_ids_by_ring: Dict[int, Set[str]]
    all_tile_ids: Set[str]


def _load_tile_catalog() -> _TileCatalog:
    """Read the exploration tile CSV and index counts by ring."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "eclipse_tiles.csv")
    totals: Counter[int] = Counter()
    by_ring: Dict[int, Set[str]] = defaultdict(set)
    try:
        with open(os.path.abspath(csv_path), newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                sector = row.get("Sector")
                tile = row.get("TileNumber")
                if not sector or not tile:
                    continue
                try:
                    ring = int(sector)
                except ValueError:
                    continue
                tile_id = str(tile).strip()
                if not tile_id:
                    continue
                totals[ring] += 1
                by_ring[ring].add(tile_id)
    except FileNotFoundError:
        return _TileCatalog(total_by_ring={}, tile_ids_by_ring={}, all_tile_ids=set())
    all_ids = set().union(*by_ring.values()) if by_ring else set()
    return _TileCatalog(
        total_by_ring=dict(totals),
        tile_ids_by_ring={r: set(ids) for r, ids in by_ring.items()},
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
    # Update core
    gs.map = map_state
    gs.tech_display = tech_display

    # Ensure players seen on the board exist
    _reconcile_players_from_map(gs)

    # Ensure bag placeholders for observed rings
    _ensure_bags_for_rings(gs)
    _populate_explore_bags(gs)

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
