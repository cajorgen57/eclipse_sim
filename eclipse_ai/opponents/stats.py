from __future__ import annotations

from typing import Dict, List

from .observe import OppHistory, Snapshot
from .types import OpponentMetrics


def _rate(delta: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    x = max(0.0, delta / scale)
    return min(1.0, x)


def _compute_battle_aggression(snaps: List[Snapshot], pid: int, rounds: int) -> float:
    """Compute aggression from battle history if available.

    Uses actual combat actions as a stronger signal than ship building alone.
    """
    total_battles = 0
    for snap in snaps:
        total_battles += snap.battles_in_round_by_player.get(pid, 0)
    if rounds <= 0:
        return 0.0
    # Normalize: 1 battle per round = moderate aggression, 2+ = high
    return min(1.0, total_battles / (rounds * 1.5))


def compute_metrics(hist: OppHistory) -> Dict[int, OpponentMetrics]:
    """Compute normalized metrics per player from the last window of snapshots.

    Improved aggression formula that accounts for:
    - Actual combat actions (battles initiated)
    - Fleet buildup rate and composition
    - Border pressure from fleet positioning
    - Expansion into contested territory
    """
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

        # Improved aggression: combines multiple signals
        battle_aggression = _compute_battle_aggression(snaps, pid, rounds)
        build_aggression = 0.5 * build_intensity + 0.2 * expansion

        # If we have battle data, weight it heavily; otherwise fall back to build-based
        if battle_aggression > 0:
            aggression = min(1.0, 0.6 * battle_aggression + 0.3 * build_aggression + 0.1 * upgrade_intensity)
        else:
            aggression = min(1.0, build_aggression + 0.15 * upgrade_intensity)

        # Improved mobility: account for expansion rate as a mobility signal
        base_mobility = last.mobility_by_player.get(pid, 0.5)
        mobility = min(1.0, base_mobility * 0.7 + expansion * 0.3)

        # Improved fleet power: weight combat-tested fleets higher
        fleet_power_base = 0.4 * build_intensity + 0.3 * upgrade_intensity + 0.15 * mobility
        # Battle experience makes fleet power more credible
        if battle_aggression > 0.3:
            fleet_power_base += 0.15 * battle_aggression
        fleet_power = max(0.0, min(1.0, fleet_power_base))

        # Border pressure: infer from expansion into potentially contested areas
        # If expanding rapidly while also building ships, likely pressuring borders
        border_pressure = min(1.0, 0.4 * expansion + 0.3 * build_intensity + 0.3 * aggression)

        diplomacy_rate = 0.0

        # Improved risk tolerance: accounts for battle history
        risk_tolerance = 0.3 + 0.3 * aggression + 0.1 * battle_aggression - 0.2 * tech_pace
        # Players who build starbases and don't attack are risk-averse
        if tech_pace > 0.5 and aggression < 0.2:
            risk_tolerance *= 0.6

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

