from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class Snapshot:
    round_idx: int
    # Minimal, robust projection to avoid depending on internal structures.
    sectors_by_player: Dict[int, int]
    ships_by_player: Dict[int, int]
    techs_by_player: Dict[int, int]
    upgrades_by_player: Dict[int, int]
    battles_in_round_by_player: Dict[int, int]
    # Optional: initiative/drive proxies if derivable
    mobility_by_player: Dict[int, float]


def _safe_len(x) -> int:
    try:
        return len(x)
    except Exception:
        return 0


def _count_ships(state: Any, pid: int) -> int:
    # Fallback strategy; try a few common shapes
    for name in ("ships", "fleets", "units"):
        obj = getattr(state, name, None)
        if obj is not None:
            if isinstance(obj, dict):
                return sum(
                    _safe_len(v) for k, v in obj.items() if getattr(k, "owner", k) == pid
                )
            return _safe_len([u for u in obj if getattr(u, "owner", None) == pid])
    return 0


def _count_techs(state: Any, pid: int) -> int:
    for name in ("techs", "technologies", "research"):
        obj = getattr(state, name, None)
        if obj is not None:
            if isinstance(obj, dict):
                return _safe_len(obj.get(pid, ()))
            return _safe_len([t for t in obj if getattr(t, "owner", None) == pid])
    return 0


def _count_upgrades(state: Any, pid: int) -> int:
    # Use ship designs or upgrade logs if available
    designs = getattr(state, "ship_designs", None)
    if isinstance(designs, dict):
        return sum(_safe_len(v) for k, v in designs.items() if k == pid)
    return 0


def _count_sectors(state: Any, pid: int) -> int:
    board = getattr(state, "board", None) or getattr(state, "map", None)
    if board is None:
        return 0
    sec = getattr(board, "sectors", None) or getattr(board, "hexes", None)
    if sec is None:
        return 0
    if isinstance(sec, dict):
        return sum(1 for s in sec.values() if getattr(s, "owner", None) == pid)
    return sum(1 for s in sec if getattr(s, "owner", None) == pid)


def _mobility_proxy(state: Any, pid: int) -> float:
    # Try to infer from techs or ship component averages; fall back to 0.5
    return 0.5


def _player_ids(state: Any) -> List[int]:
    players = getattr(state, "players", None)
    if isinstance(players, dict):
        return list(players.keys())
    if isinstance(players, list):
        return [getattr(p, "id", i) for i, p in enumerate(players)]
    # fallback guess: 0..N-1 if active_player_index exists
    n = getattr(state, "num_players", None)
    if isinstance(n, int):
        return list(range(n))
    return []


def make_snapshot(state: Any, round_idx: int) -> Snapshot:
    pids = _player_ids(state)
    sectors = {pid: _count_sectors(state, pid) for pid in pids}
    ships = {pid: _count_ships(state, pid) for pid in pids}
    techs = {pid: _count_techs(state, pid) for pid in pids}
    upgrades = {pid: _count_upgrades(state, pid) for pid in pids}
    # If state logs battles per round, try to read it; else 0s
    battles = {pid: 0 for pid in pids}
    mobility = {pid: _mobility_proxy(state, pid) for pid in pids}
    return Snapshot(round_idx, sectors, ships, techs, upgrades, battles, mobility)


@dataclass
class OppHistory:
    # Maintain last K snapshots; K default 3 rounds
    snapshots: List[Snapshot] = field(default_factory=list)
    K: int = 3

    def record(self, snap: Snapshot) -> None:
        self.snapshots.append(snap)
        if len(self.snapshots) > self.K:
            self.snapshots.pop(0)

    @property
    def has_window(self) -> bool:
        return len(self.snapshots) >= 2

    def window(self) -> List[Snapshot]:
        return list(self.snapshots)

