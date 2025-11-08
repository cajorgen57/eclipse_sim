from __future__ import annotations

from typing import Dict, List

from .observe import OppHistory, Snapshot
from .types import OpponentMetrics


def _rate(delta: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    x = max(0.0, delta / scale)
    return min(1.0, x)


def compute_metrics(hist: OppHistory) -> Dict[int, OpponentMetrics]:
    """Compute normalized metrics per player from the last window of snapshots."""
    if not hist.has_window:
        return {}
    snaps: List[Snapshot] = hist.window()
    first, last = snaps[0], snaps[-1]
    rounds = max(1, last.round_idx - first.round_idx)
    pids = sorted(set(first.sectors_by_player) | set(last.sectors_by_player))

    # Scales — conservative defaults
    sector_scale = 6.0  # sectors per several rounds
    ship_scale = 12.0  # ships per several rounds
    tech_scale = 5.0  # techs per several rounds
    upgrade_scale = 6.0

    out: Dict[int, OpponentMetrics] = {}
    for pid in pids:
        d_sec = (last.sectors_by_player.get(pid, 0) - first.sectors_by_player.get(pid, 0)) / rounds
        d_ship = (last.ships_by_player.get(pid, 0) - first.ships_by_player.get(pid, 0)) / rounds
        d_tech = (last.techs_by_player.get(pid, 0) - first.techs_by_player.get(pid, 0)) / rounds
        d_upg = (last.upgrades_by_player.get(pid, 0) - first.upgrades_by_player.get(pid, 0)) / rounds

        expansion = _rate(d_sec, sector_scale / rounds)
        build_intensity = _rate(d_ship, ship_scale / rounds)
        tech_pace = _rate(d_tech, tech_scale / rounds)
        upgrade_intensity = _rate(d_upg, upgrade_scale / rounds)

        aggression = min(1.0, 0.5 * build_intensity + 0.2 * expansion)

        mobility = last.mobility_by_player.get(pid, 0.5)
        fleet_power = max(0.0, min(1.0, 0.5 * build_intensity + 0.3 * upgrade_intensity + 0.2 * mobility))

        border_pressure = 0.0
        diplomacy_rate = 0.0
        risk_tolerance = 0.3 + 0.4 * aggression - 0.2 * tech_pace

        out[pid] = OpponentMetrics(
            aggression=aggression,
            expansion=expansion,
            tech_pace=tech_pace,
            build_intensity=build_intensity,
            upgrade_intensity=upgrade_intensity,
            mobility=mobility,
            fleet_power=fleet_power,
            border_pressure=border_pressure,
            diplomacy_rate=diplomacy_rate,
            risk_tolerance=max(0.0, min(1.0, risk_tolerance)),
        )
    return out

