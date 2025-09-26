from __future__ import annotations

import pytest

from eclipse_ai.game_models import (
    GameState,
    Hex,
    MapState,
    Pieces,
    Planet,
    PlayerState,
    Resources,
    Disc,
)
from eclipse_ai import round_flow


def _make_player(pid: str, money: int = 5, science: int = 0, materials: int = 0, discs: int = 5) -> PlayerState:
    player = PlayerState(player_id=pid, color="test")
    player.resources = Resources(money=money, science=science, materials=materials)
    player.income = Resources(money=0, science=0, materials=0)
    player.influence_track = [Disc(f"{pid}-d{i}") for i in range(discs)]
    return player


def _basic_state(players: dict[str, PlayerState]) -> GameState:
    state = GameState(
        round=1,
        players=players,
        map=MapState(hexes={}),
        starting_player=next(iter(players)),
        turn_order=list(players.keys()),
    )
    round_flow.begin_round(state)
    return state


def test_turn_loop_until_all_pass():
    players = {pid: _make_player(pid) for pid in ("P1", "P2", "P3")}
    state = _basic_state(players)

    round_flow.take_action(state, "P1", "Explore")
    assert state.active_player == "P2"

    round_flow.pass_action(state, "P2")
    assert players["P2"].passed is True
    assert state.pending_starting_player == "P2"
    assert state.active_player == "P3"

    round_flow.take_action(state, "P3", "Build")
    assert state.active_player == "P1"

    round_flow.pass_action(state, "P1")
    assert state.active_player == "P2"

    # Passing again simply advances the turn without changing the marker.
    round_flow.pass_action(state, "P2")
    assert state.active_player == "P3"

    round_flow.pass_action(state, "P3")
    assert round_flow.end_action_phase_if_all_passed(state) is True
    assert state.phase == "COMBAT"

    # Advance through upkeep/cleanup so the starting player marker moves.
    state.phase = "UPKEEP"
    round_flow.run_upkeep(state)
    state.phase = "CLEANUP"
    round_flow.run_cleanup(state)

    assert state.starting_player == "P2"
    assert state.active_player == "P2"
    assert state.phase == "ACTION"


def test_action_spends_disc_and_cleanup_returns():
    player = _make_player("P1", discs=4)
    state = _basic_state({"P1": player})

    round_flow.take_action(state, "P1", "Build")
    round_flow.take_action(state, "P1", "Research")

    assert len(player.influence_track) == 2
    assert len(player.action_spaces["build"]) == 1
    assert len(player.action_spaces["research"]) == 1

    round_flow.pass_action(state, "P1")
    assert round_flow.end_action_phase_if_all_passed(state) is True

    state.phase = "UPKEEP"
    round_flow.run_upkeep(state)
    state.phase = "CLEANUP"
    round_flow.run_cleanup(state)

    assert len(player.influence_track) == 4
    assert all(len(player.action_spaces[key]) == 0 for key in round_flow.ACTION_SPACE_KEYS)


def test_reaction_limits_after_pass():
    player = _make_player("P1", discs=5)
    player.known_techs.append("Nanorobots")
    state = _basic_state({"P1": player})

    round_flow.pass_action(state, "P1")
    assert round_flow.can_take_reaction(state, "P1") is True

    round_flow.take_reaction(state, "P1", "Build", {"ships": {"interceptor": 1}})
    assert len(player.action_spaces["reaction"]) == 1
    assert len(player.influence_track) == 4

    with pytest.raises(ValueError):
        round_flow.take_reaction(state, "P1", "Research", {})

    with pytest.raises(ValueError):
        round_flow.take_reaction(state, "P1", "Build", {"ships": {"interceptor": 2}})

    with pytest.raises(round_flow.PhaseError):
        round_flow.take_action(state, "P1", "Explore")

    # Move reaction still allowed with one ship
    round_flow.take_reaction(state, "P1", "Move", {"ships": {"interceptor": 1}})


def test_upkeep_shortfall_removes_discs_only_then():
    player = _make_player("P1", money=0, discs=2)
    hex_state = Hex(
        id="H1",
        ring=2,
        planets=[Planet(type="yellow", colonized_by="P1")],
        pieces={
            "P1": Pieces(ships={}, starbase=0, discs=1, cubes={"yellow": 1}),
        },
    )
    state = GameState(
        round=1,
        players={"P1": player},
        map=MapState(hexes={"H1": hex_state}),
        starting_player="P1",
        turn_order=["P1"],
    )
    round_flow.begin_round(state)

    with pytest.raises(round_flow.InfluenceError):
        round_flow._remove_disc_from_hex(
            state, player, "H1", reason="shortfall"
        )

    state.phase = "UPKEEP"
    round_flow.run_upkeep(state)
    assert player.population["yellow"] == 1
    assert player.influence_track  # disc returned to track
    assert "P1" not in state.map.hexes["H1"].pieces
    assert state.map.hexes["H1"].planets[0].colonized_by is None


def test_extra_discs_stack_rightmost():
    player = _make_player("P1", discs=2)
    extras = [Disc("extra-1", extra=True), Disc("extra-2", extra=True)]
    player.influence_track.extend(extras)
    state = _basic_state({"P1": player})

    round_flow.take_action(state, "P1", "Explore")
    assert player.action_spaces["explore"][0].id == "extra-2"
    assert player.action_spaces["explore"][0].extra is True

    round_flow.take_action(state, "P1", "Move")
    assert player.action_spaces["move"][0].id == "extra-1"

    round_flow.pass_action(state, "P1")
    assert round_flow.end_action_phase_if_all_passed(state)

    state.phase = "UPKEEP"
    round_flow.run_upkeep(state)
    state.phase = "CLEANUP"
    round_flow.run_cleanup(state)

    assert len(player.influence_track) == 4
    assert player.influence_track[-1].extra is True
    assert player.influence_track[-2].extra is True
