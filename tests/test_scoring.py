from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from eclipse_ai.models.player_state import EvolutionTile, PlayerState, ReputationTile
from eclipse_ai.scoring import compute_endgame_vp, score_game


@dataclass
class Hex:
    id: str
    vp_value: int = 0
    controller: Optional[str] = None


@dataclass
class MapState:
    hexes: Dict[str, Hex] = field(default_factory=dict)


@dataclass
class StubState:
    players: Dict[str, PlayerState]
    map: MapState = field(default_factory=MapState)
    alliance_teams: Optional[Dict[str, List[str]]] = None


def test_base_example() -> None:
    hexes = {
        "A": Hex(id="A", vp_value=2, controller="p1"),
        "B": Hex(id="B", vp_value=3, controller="p1"),
    }
    player = PlayerState(
        player_id="p1",
        reputation_kept=[
            ReputationTile(value=3),
            ReputationTile(value=2),
            ReputationTile(value=5, is_special=True),
        ],
        ambassadors=2,
        controlled_hex_ids=["A", "B"],
        discoveries_kept=1,
        monolith_count=2,
        tech_track_counts={"military": 4, "grid": 5, "nano": 6},
    )
    state = StubState(players={"p1": player}, map=MapState(hexes=hexes))

    result = compute_endgame_vp(state, "p1", modules={})

    assert result["vp_reputation"] == 5
    assert result["vp_ambassadors"] == 2
    assert result["vp_hexes"] == 5
    assert result["vp_discoveries"] == 2
    assert result["vp_monoliths"] == 6
    assert result["vp_tech_tracks"] == 6
    assert result["vp_traitor"] == 0
    assert result["total"] == 26


def test_tech_track_piecewise() -> None:
    player = PlayerState(
        player_id="p2",
        tech_track_counts={
            "military": 3,
            "grid": 4,
            "nano": 5,
            "quantum": 6,
            "biotech": 7,
            "economy": 8,
        },
    )
    state = StubState(players={"p2": player})

    result = compute_endgame_vp(state, "p2", modules={})

    assert result["vp_tech_tracks"] == 16
    assert result["total"] == 16


def test_traitor_penalty() -> None:
    state = StubState(
        players={
            "p1": PlayerState(player_id="p1", has_traitor=True),
            "p2": PlayerState(player_id="p2", has_traitor=False),
        }
    )

    result_with_traitor = compute_endgame_vp(state, "p1", modules={})
    result_without_traitor = compute_endgame_vp(state, "p2", modules={})

    assert result_with_traitor["vp_traitor"] == -2
    assert result_with_traitor["total"] == -2
    assert result_without_traitor["vp_traitor"] == 0
    assert result_without_traitor["total"] == 0


def test_discoveries_vp_kept_only() -> None:
    player = PlayerState(player_id="p3", discoveries_kept=3)
    state = StubState(players={"p3": player})

    result = compute_endgame_vp(state, "p3", modules={})

    assert result["vp_discoveries"] == 6
    assert result["total"] == 6


def test_alliance_tile_values_and_team_average() -> None:
    players = {
        "p1": PlayerState(player_id="p1", alliance_tile="faceup"),
        "p2": PlayerState(player_id="p2", alliance_tile="betrayer"),
    }
    state = StubState(players=players, alliance_teams={"team-alpha": ["p1", "p2"]})

    result = score_game(state, modules={"alliances": True})

    assert result["players"]["p1"]["vp_rise_alliance_tile"] == 2
    assert result["players"]["p2"]["vp_rise_alliance_tile"] == -3
    alliance_summary = result["alliances"]
    assert alliance_summary["team_totals"]["team-alpha"] == -1
    assert alliance_summary["team_average"]["team-alpha"] == -1


def test_ancient_kill_tokens_vp() -> None:
    tokens = {"cruiser": 2, "dreadnought": 1}
    player = PlayerState(player_id="p4", ancient_kill_tokens=tokens)
    state = StubState(players={"p4": player})

    result = compute_endgame_vp(state, "p4", modules={"new_ancients": True})

    assert result["vp_rise_ancient_kills"] == 3
    assert result["total"] == 3


def test_sor_evolution_examples() -> None:
    player = PlayerState(
        player_id="p5",
        monolith_count=2,
        controlled_hex_ids=["A", "B", "C", "D"],
        artifacts_controlled=3,
        controls_galactic_center=True,
        evolution_tiles=[
            EvolutionTile(endgame_key="per_monolith", value=1),
            EvolutionTile(endgame_key="per_two_hex", value=1),
            EvolutionTile(endgame_key="per_artifact", value=1),
            EvolutionTile(endgame_key="galactic_center", value=3),
            EvolutionTile(endgame_key=None, value=4),
        ],
    )
    state = StubState(players={"p5": player})

    modules_on = {"sor": True}
    modules_off = {}

    result_on = compute_endgame_vp(state, "p5", modules=modules_on)
    result_off = compute_endgame_vp(state, "p5", modules=modules_off)

    assert result_on["vp_sor_evolution"] == 14
    assert result_off["vp_sor_evolution"] == 0
    assert result_on["total"] - result_off["total"] == 14
