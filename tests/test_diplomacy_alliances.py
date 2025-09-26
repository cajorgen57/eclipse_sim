from __future__ import annotations

import pytest

from eclipse_ai.game_models import GameState, MapState, Hex, Pieces, PlayerState
from eclipse_ai.diplomacy import (
    DiplomacyError,
    break_diplomacy,
    can_form_diplomacy,
    form_diplomacy,
    has_diplomatic_relation,
)
from eclipse_ai.alliances import (
    AllianceError,
    are_allied,
    can_found_alliance,
    found_alliance,
    join_alliance,
    leave_alliance,
    merge_combat_sides,
    ship_presence,
)
from eclipse_ai.scoring.endgame import alliance_average_vp, calculate_endgame_vp


def _basic_player(pid: str) -> PlayerState:
    player = PlayerState(player_id=pid, color="color")
    player.population["yellow"] = 5
    return player


def _setup_state(*player_ids: str) -> GameState:
    state = GameState()
    state.players = {pid: _basic_player(pid) for pid in player_ids}
    state.map = MapState(hexes={}, adjacency={})
    state.feature_flags["rotA"] = True
    return state


def _link_hexes(state: GameState, wormholes_a: list[int], wormholes_b: list[int]) -> tuple[Hex, Hex]:
    hex_a = Hex(id="A", ring=1, wormholes=list(wormholes_a), neighbors={0: "B"}, pieces={})
    hex_b = Hex(id="B", ring=1, wormholes=list(wormholes_b), neighbors={3: "A"}, pieces={})
    state.map.hexes = {"A": hex_a, "B": hex_b}
    return hex_a, hex_b


def _force_diplomacy(state: GameState, a_id: str, b_id: str, color: str = "yellow") -> None:
    state.players[a_id].ambassadors[b_id] = True
    state.players[b_id].ambassadors[a_id] = True
    state.players[a_id].diplomacy[b_id] = color
    state.players[b_id].diplomacy[a_id] = color
    state.players[a_id].population[color] -= 1
    state.players[b_id].population[color] -= 1


def test_form_diplomacy_requires_full_wormhole():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    assert not can_form_diplomacy(state, "p1", "p2")

    hex_b.wormholes.append(3)
    assert can_form_diplomacy(state, "p1", "p2")


def test_no_diplomacy_if_ships_cohabit():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    hex_a.pieces["p2"] = Pieces(ships={"interceptor": 1})
    assert not can_form_diplomacy(state, "p1", "p2")

    hex_a.pieces["p2"] = Pieces()
    hex_b.pieces["p1"] = Pieces(ships={"interceptor": 1})
    assert not can_form_diplomacy(state, "p1", "p2")


def test_breaking_relations_on_move_into_enemy_hex():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")

    break_diplomacy(state, "p1", "p2")
    assert not has_diplomatic_relation(state, "p1", "p2")
    assert state.players["p1"].has_traitor
    assert state.players["p1"].population["yellow"] == 5
    assert state.players["p2"].population["yellow"] == 5


def test_ambassador_limits_and_vp():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")

    assert not can_form_diplomacy(state, "p1", "p2")
    with pytest.raises(DiplomacyError):
        form_diplomacy(state, "p1", "p2")

    assert calculate_endgame_vp(state, "p1") == 1
    assert calculate_endgame_vp(state, "p2") == 1


def test_found_alliance_requires_diplomacy_and_capacity():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")

    assert can_found_alliance(state, "p1", "p2")
    assert not can_found_alliance(state, "p1", "p2", third_id="p3")

    alliance = found_alliance(state, "p1", "p2")
    assert alliance.members == ["p1", "p2"]
    assert state.players["p1"].alliance_tile == "+2"

    # Expand to 6 players to allow a third member.
    state.players["p5"] = _basic_player("p5")
    state.players["p6"] = _basic_player("p6")
    _force_diplomacy(state, "p3", "p1")
    _force_diplomacy(state, "p3", "p2")
    join_alliance(state, alliance.id, "p3")
    assert are_allied(state, "p1", "p3")


def test_alliance_effects_on_move_pinning_combat():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1, ships={"interceptor": 1})
    hex_a.pieces["p3"] = Pieces(discs=0, ships={"interceptor": 2})
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")
    hex_a.pieces["p2"] = Pieces(discs=0, ships={"interceptor": 1})
    alliance = found_alliance(state, "p1", "p2")

    friendly, enemy = ship_presence(state, hex_a, "p1")
    assert friendly == 2  # p1 + allied p2 ships
    assert enemy == 2     # hostile p3 ships

    defenders, attackers, defender_tie = merge_combat_sides(state, ["p1"], ["p3"])
    assert set(defenders) == {"p1", "p2"}
    assert attackers == ["p3"]
    assert defender_tie


def test_leave_alliance_sets_betrayer_and_traitor_if_co_located():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")
    hex_b.pieces["p1"] = Pieces(ships={"interceptor": 1})
    alliance = found_alliance(state, "p1", "p2")

    leave_alliance(state, "p1")
    assert state.players["p1"].alliance_tile == "-3"
    assert state.players["p1"].has_traitor
    assert not has_diplomatic_relation(state, "p1", "p2")
    assert alliance.id not in state.alliances or "p1" not in state.alliances[alliance.id].members


def test_last_round_restriction():
    late_state = _setup_state("p1", "p2", "p3", "p4")
    late_state.round = 9
    hex_a, hex_b = _link_hexes(late_state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(late_state, "p1", "p2")

    assert not can_found_alliance(late_state, "p1", "p2")

    active_state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(active_state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(active_state, "p1", "p2")
    found_alliance(active_state, "p1", "p2")
    active_state.round = 9
    with pytest.raises(AllianceError):
        leave_alliance(active_state, "p1")


def test_alliance_tile_vp_and_team_average():
    state = _setup_state("p1", "p2", "p3", "p4")
    hex_a, hex_b = _link_hexes(state, [0], [3])
    hex_a.pieces["p1"] = Pieces(discs=1)
    hex_b.pieces["p2"] = Pieces(discs=1)
    form_diplomacy(state, "p1", "p2")
    alliance = found_alliance(state, "p1", "p2")

    totals = {
        "p1": calculate_endgame_vp(state, "p1", base_vp=5),
        "p2": calculate_endgame_vp(state, "p2", base_vp=7),
        "p3": calculate_endgame_vp(state, "p3", base_vp=4),
    }
    averages = alliance_average_vp(state, totals)
    assert alliance.id in averages
    assert averages[alliance.id] == pytest.approx((totals["p1"] + totals["p2"]) / 2)
