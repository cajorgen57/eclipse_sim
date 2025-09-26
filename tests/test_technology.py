from __future__ import annotations

import pytest

from eclipse_ai.game_models import GameState, PlayerState, Resources, MapState
from eclipse_ai.technology import (
    ResearchError,
    can_research,
    cleanup_refresh_market,
    discounted_cost,
    do_research,
    ensure_part_allowed,
    ensure_structure_allowed,
    load_tech_definitions,
    MARKET_SIZES_BY_PLAYER_COUNT,
)


def _make_state(player_count: int = 1) -> GameState:
    defs = load_tech_definitions()
    players = {}
    for idx in range(player_count):
        pid = f"P{idx + 1}"
        resources = Resources(money=5, science=10, materials=5)
        players[pid] = PlayerState(
            player_id=pid,
            color="orange",
            resources=resources,
            science=resources.science,
            influence_discs=3,
        )
        players[pid].tech_count_by_category = {}
        players[pid].owned_tech_ids = set()
        players[pid].unlocked_parts = set()
        players[pid].unlocked_structures = set()
    return GameState(
        round=1,
        active_player="P1",
        phase="action",
        players=players,
        map=MapState(),
        tech_bags={},
        market=[],
        tech_definitions=defs,
    )


def test_research_spends_disc_and_science():
    state = _make_state()
    player = state.players["P1"]
    state.market = ["advanced_labs"]
    player.science = 6
    player.resources.science = 6
    player.influence_discs = 2

    do_research(state, player, "advanced_labs")

    assert player.influence_discs == 1
    # pay 6, immediate effect refunds +2 science
    assert player.science == 2
    assert "advanced_labs" in player.owned_tech_ids


def test_category_discount_applies_only_within_category():
    state = _make_state()
    player = state.players["P1"]
    player.owned_tech_ids.update({"plasma_cannon", "improved_hull"})
    player.tech_count_by_category = {"grid": 2}
    player.science = 10
    player.resources.science = 10

    defs = state.tech_definitions
    military_cost = discounted_cost(player, defs["gauss_shield"])
    grid_cost = discounted_cost(player, defs["advanced_labs"])

    assert military_cost == 1
    assert grid_cost == defs["advanced_labs"].base_cost


def test_no_research_as_reaction():
    state = _make_state()
    player = state.players["P1"]
    state.market = ["nanorobots"]
    player.science = 5
    player.resources.science = 5
    state.phase = "reaction"

    assert not can_research(state, player, "nanorobots")
    with pytest.raises(ResearchError, match="cannot research during Reaction"):
        do_research(state, player, "nanorobots")


def test_rare_uniqueness_and_starting_rare():
    state = _make_state(player_count=2)
    p1 = state.players["P1"]
    p2 = state.players["P2"]
    p1.owned_tech_ids.add("zero_point_source")
    p1.tech_count_by_category = {"rare": 1}
    state.market = ["zero_point_source"]
    state.tech_bags = {"III": ["zero_point_source", "quantum_grid"]}

    cleanup_refresh_market(state)

    assert "zero_point_source" not in state.market
    assert "zero_point_source" not in state.tech_bags["III"]

    state.market.append("quantum_grid")
    p2.science = 8
    p2.resources.science = 8
    p2.influence_discs = 2
    do_research(state, p2, "quantum_grid")

    assert "quantum_grid" not in state.market
    assert all("quantum_grid" not in bag for bag in state.tech_bags.values())
    with pytest.raises(ResearchError, match="tech not available in market"):
        do_research(state, p1, "zero_point_source")


def test_grants_parts_and_structures_gated():
    state = _make_state()
    player = state.players["P1"]

    with pytest.raises(ResearchError, match="required technology not owned"):
        ensure_structure_allowed(player, "starbase")
    with pytest.raises(ResearchError, match="required technology not owned"):
        ensure_part_allowed(player, "plasma_cannon")

    state.market = ["starbase", "plasma_cannon"]
    player.science = 12
    player.resources.science = 12

    do_research(state, player, "starbase")
    ensure_structure_allowed(player, "starbase")

    state.market.append("plasma_cannon")
    do_research(state, player, "plasma_cannon")
    ensure_part_allowed(player, "plasma_cannon")


def test_cleanup_refills_market_only_in_cleanup():
    state = _make_state(player_count=2)
    player = state.players["P1"]
    player.science = 8
    player.resources.science = 8
    player.influence_discs = 2
    state.market = ["plasma_cannon", "advanced_labs", "nanorobots"]
    state.tech_bags = {"I": ["gauss_shield", "improved_hull"]}

    do_research(state, player, "plasma_cannon")
    assert state.market == ["advanced_labs", "nanorobots"]

    cleanup_refresh_market(state)
    target = MARKET_SIZES_BY_PLAYER_COUNT[len(state.players)]
    assert len(state.market) <= target
    assert "gauss_shield" in state.market or "improved_hull" in state.market
