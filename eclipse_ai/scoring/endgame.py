
"""Endgame scoring helpers for diplomacy and alliances."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional
from typing import Dict
from ..models.player_state import EvolutionTile, ReputationTile
from ..game_models import GameState, PlayerState
from ..data.constants import (
    ALLIANCE_TILE_BETRAYER_VP,
    ALLIANCE_TILE_FACEUP_VP,
    ANCIENT_KILL_VP,
    DISCOVERY_TILE_VP,
    MONOLITH_VP,
    TECH_TRACK_VP,
    TRAITOR_PENALTY,
)

def diplomacy_vp(player: PlayerState) -> int:
    if not player:
        return 0
    return sum(1 for active in player.ambassadors.values() if active)


def traitor_penalty(player: PlayerState) -> int:
    if not player:
        return 0
    return -2 if player.has_traitor else 0


def alliance_tile_vp(player: PlayerState) -> int:
    if not player:
        return 0
    if player.alliance_tile == "+2":
        return 2
    if player.alliance_tile == "-3":
        return -3
    return 0


def calculate_endgame_vp(state: GameState, player_id: str, base_vp: int = 0) -> int:
    player = state.players.get(player_id) if state else None
    if player is None:
        return base_vp
    total = base_vp
    total += diplomacy_vp(player)
    total += traitor_penalty(player)
    total += alliance_tile_vp(player)
    return total


def alliance_average_vp(state: GameState, totals: Dict[str, int]) -> Dict[str, float]:
    """Return the per-alliance average VP used for ranking comparisons."""
    if not state:
        return {}
    averages: Dict[str, float] = {}
    for alliance_id, alliance in state.alliances.items():
        if not alliance.members:
            continue
        member_scores = [totals.get(pid, 0) for pid in alliance.members]
        if not member_scores:
            continue
        averages[alliance_id] = sum(member_scores) / float(len(member_scores))
    return averages


def compute_endgame_vp(state: Any, player_id: str, modules: Optional[Mapping[str, Any]] = None) -> Dict[str, int]:
    """Compute the endgame VP breakdown for ``player_id``."""

    modules = modules or {}
    player = _get_player(state, player_id)
    if player is None:
        raise KeyError(f"Unknown player '{player_id}' in state")

    alliances_enabled = _module_enabled(modules, "alliances", "rotA_alliances")
    new_ancients_enabled = _module_enabled(modules, "new_ancients", "rotA_new_ancients")
    sor_enabled = _module_enabled(modules, "sor", "shadows_of_the_rift")

    vp_reputation = _reputation_vp(player)
    vp_ambassadors = int(getattr(player, "ambassadors", 0) or 0)
    vp_hexes = _hex_vp(state, player)
    vp_discoveries = int(getattr(player, "discoveries_kept", 0) or 0) * DISCOVERY_TILE_VP
    vp_monoliths = int(getattr(player, "monolith_count", 0) or 0) * MONOLITH_VP
    vp_tech_tracks = _tech_track_vp(player)
    vp_traitor = TRAITOR_PENALTY if bool(getattr(player, "has_traitor", False)) else 0
    vp_alliance = _alliance_tile_vp(player) if alliances_enabled else 0
    vp_ancients = _ancient_kill_vp(player) if new_ancients_enabled else 0
    vp_evolution = _evolution_vp(state, player) if sor_enabled else 0

    total = (
        vp_reputation
        + vp_ambassadors
        + vp_hexes
        + vp_discoveries
        + vp_monoliths
        + vp_tech_tracks
        + vp_traitor
        + vp_alliance
        + vp_ancients
        + vp_evolution
    )

    return {
        "vp_reputation": vp_reputation,
        "vp_ambassadors": vp_ambassadors,
        "vp_hexes": vp_hexes,
        "vp_discoveries": vp_discoveries,
        "vp_monoliths": vp_monoliths,
        "vp_tech_tracks": vp_tech_tracks,
        "vp_traitor": vp_traitor,
        "vp_rise_alliance_tile": vp_alliance,
        "vp_rise_ancient_kills": vp_ancients,
        "vp_sor_evolution": vp_evolution,
        "total": total,
    }


def score_game(state: Any, modules: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return per-player endgame VP breakdowns and alliance summaries."""

    modules = modules or {}
    players: Mapping[str, Any] = getattr(state, "players", {})
    if not isinstance(players, Mapping):
        raise TypeError("state.players must be a mapping of player_id -> PlayerState")

    player_breakdowns: Dict[str, Dict[str, int]] = {}
    for player_id in players:
        player_breakdowns[player_id] = compute_endgame_vp(state, player_id, modules)

    result: Dict[str, Any] = {"players": player_breakdowns}

    if _module_enabled(modules, "alliances", "rotA_alliances"):
        teams = _extract_alliance_teams(state, players)
        if teams:
            totals = {pid: data["total"] for pid, data in player_breakdowns.items()}
            team_totals: Dict[str, int] = {}
            team_average: Dict[str, int] = {}
            for team_id, members in teams.items():
                team_total = sum(totals.get(pid, 0) for pid in members)
                if not members:
                    continue
                team_totals[team_id] = team_total
                team_average[team_id] = team_total // len(members)
            result["alliances"] = {"team_totals": team_totals, "team_average": team_average}

    return result


def _module_enabled(modules: Mapping[str, Any], *keys: str) -> bool:
    return any(bool(modules.get(key)) for key in keys)


def _get_player(state: Any, player_id: str) -> Optional[Any]:
    players = getattr(state, "players", None)
    if isinstance(players, Mapping):
        return players.get(player_id)
    return None


def _reputation_vp(player: Any) -> int:
    tiles: Iterable[Any] = getattr(player, "reputation_kept", []) or []
    total = 0
    for tile in tiles:
        if tile is None:
            continue
        if isinstance(tile, ReputationTile):
            if tile.is_special:
                continue
            total += int(tile.value)
            continue
        if isinstance(tile, Mapping):
            if tile.get("is_special"):
                continue
            value = tile.get("value", 0)
            total += int(value)
            continue
        value = getattr(tile, "value", tile)
        flag = getattr(tile, "is_special", False)
        if flag:
            continue
        total += int(value)
    return total


def _hex_vp(state: Any, player: Any) -> int:
    hexes = _get_hex_collection(state)
    if not hexes:
        return 0

    player_id = getattr(player, "player_id", None)
    total = 0
    for hex_id in getattr(player, "controlled_hex_ids", []) or []:
        hex_obj = hexes.get(hex_id)
        if hex_obj is None:
            continue
        controller = getattr(hex_obj, "controller", getattr(hex_obj, "controlled_by", None))
        if controller is not None and player_id is not None and controller != player_id:
            continue
        total += int(getattr(hex_obj, "vp_value", 0) or 0)
    return total


def _get_hex_collection(state: Any) -> Mapping[str, Any]:
    map_state = getattr(state, "map", None)
    if map_state is not None:
        hexes = getattr(map_state, "hexes", None)
        if isinstance(hexes, Mapping):
            return hexes
    hexes = getattr(state, "hexes", None)
    if isinstance(hexes, Mapping):
        return hexes
    return {}


def _tech_track_vp(player: Any) -> int:
    counts: Mapping[str, Any] = getattr(player, "tech_track_counts", {}) or {}

    def _vp_from_track(count: Any) -> int:
        try:
            value = int(count)
        except (TypeError, ValueError):
            return 0
        value = min(value, 7)
        return int(TECH_TRACK_VP.get(value, 0))

    return sum(_vp_from_track(count) for count in counts.values())


def _alliance_tile_vp(player: Any) -> int:
    tile = getattr(player, "alliance_tile", None)
    if tile is None:
        return 0
    normalized = str(tile).lower()
    if normalized in {"faceup", "face-up", "face_up", "+2"}:
        return ALLIANCE_TILE_FACEUP_VP
    if normalized in {"betrayer", "-3"}:
        return ALLIANCE_TILE_BETRAYER_VP
    return 0


def _ancient_kill_vp(player: Any) -> int:
    tokens: Mapping[str, Any] = getattr(player, "ancient_kill_tokens", {}) or {}
    total = 0
    for key in ("cruiser", "dreadnought"):
        try:
            total += int(tokens.get(key, 0))
        except (TypeError, ValueError):
            continue
    return total * ANCIENT_KILL_VP


def _evolution_vp(state: Any, player: Any) -> int:
    tiles: Iterable[Any] = getattr(player, "evolution_tiles", []) or []
    if not tiles:
        return 0

    total = 0
    for tile in tiles:
        key, value = _evolution_tile_fields(tile)
        handler = _EVOLUTION_HANDLERS.get(key)
        if handler is None:
            total += int(value)
        else:
            total += handler(state, player, int(value))
    return total


def _evolution_tile_fields(tile: Any) -> tuple[Optional[str], int]:
    if isinstance(tile, EvolutionTile):
        return tile.endgame_key, int(tile.value)
    if isinstance(tile, Mapping):
        key = tile.get("endgame_key") or tile.get("key")
        value = tile.get("value", tile.get("endgame_value", 0))
        return key, int(value)
    key = getattr(tile, "endgame_key", None)
    value = getattr(tile, "value", 0)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 0
    return key, value


def _controlled_hex_count(player: Any) -> int:
    return len(getattr(player, "controlled_hex_ids", []) or [])


def _artifact_count(player: Any) -> int:
    try:
        return int(getattr(player, "artifacts_controlled", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _has_galactic_center(state: Any, player: Any) -> bool:
    flag = getattr(player, "controls_galactic_center", None)
    if flag is not None:
        return bool(flag)
    # Fall back to checking whether a tracked hex is explicitly named.
    for hex_id in getattr(player, "controlled_hex_ids", []) or []:
        if str(hex_id).lower() in {"galactic_center", "galactic-centre", "gc"}:
            return True
    return False


def _per_monolith(_: Any, player: Any, value: int) -> int:
    try:
        return value * int(getattr(player, "monolith_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _per_two_hex(_: Any, player: Any, value: int) -> int:
    return value * (_controlled_hex_count(player) // 2)


def _per_artifact(_: Any, player: Any, value: int) -> int:
    return value * _artifact_count(player)


def _galactic_center(state: Any, player: Any, value: int) -> int:
    return value if _has_galactic_center(state, player) else 0


_EVOLUTION_HANDLERS: Dict[Optional[str], Any] = {
    "per_monolith": _per_monolith,
    "per_two_hex": _per_two_hex,
    "per_artifact": _per_artifact,
    "galactic_center": _galactic_center,
}


def _extract_alliance_teams(state: Any, players: Mapping[str, Any]) -> Dict[str, list[str]]:
    candidate_attrs = ("alliance_teams", "alliances", "teams")
    for attr in candidate_attrs:
        data = getattr(state, attr, None)
        if isinstance(data, Mapping):
            teams: Dict[str, list[str]] = {}
            for team_id, members in data.items():
                if isinstance(members, Iterable) and not isinstance(members, (str, bytes)):
                    teams[str(team_id)] = [str(pid) for pid in members]
            if teams:
                return teams
    teams: Dict[str, list[str]] = {}
    for pid, player in players.items():
        team_id = (
            getattr(player, "alliance_team", None)
            or getattr(player, "team", None)
            or getattr(player, "team_id", None)
        )
        if team_id is None:
            continue
        teams.setdefault(str(team_id), []).append(str(pid))
    return teams
  
  
__all__ = [
    "diplomacy_vp",
    "traitor_penalty",
    "alliance_tile_vp",
    "calculate_endgame_vp",
    "alliance_average_vp",
]
