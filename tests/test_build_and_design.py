from __future__ import annotations

import pytest

from eclipse_ai.game_models import (
    GameState,
    MapState,
    PlayerState,
    Resources,
    Hex,
    Pieces,
    ShipDesign as LegacyShipDesign,
)
from eclipse_ai.rules_engine import (
    BUILD_COST,
    FLEET_CAP,
    RulesViolation,
    validate_build,
    validate_design,
)
from eclipse_ai.types import ShipDesign


def _base_player() -> PlayerState:
    player = PlayerState(
        player_id="P1",
        color="orange",
        known_techs=[],
        resources=Resources(money=5, science=5, materials=20),
    )
    player.available_components = {
        "interceptor": 8,
        "cruiser": 4,
        "dreadnought": 2,
        "starbase": 4,
        "orbital": 4,
        "monolith": 4,
    }
    return player


def _state_with_hex(player: PlayerState, hex_id: str = "H1") -> GameState:
    hx = Hex(
        id=hex_id,
        ring=1,
        pieces={
            player.player_id: Pieces(ships={}, starbase=0, discs=1, cubes={})
        },
    )
    state = GameState(
        round=1,
        active_player=player.player_id,
        players={player.player_id: player},
        map=MapState(hexes={hex_id: hx}),
    )
    return state


def test_upgrade_requires_researched_tech():
    player = _base_player()
    design = ShipDesign(
        computer_parts={"Electron Computer": 1},
        cannon_parts={"Ion Cannon": 1},
        drive_parts={"Fusion Drive": 1},
        energy_sources={"Nuclear Source": 1},
        hull_parts={"Hull": 1},
    )

    with pytest.raises(RulesViolation):
        validate_design(player, "interceptor", design)

    player.known_techs.append("Fusion Drive")
    validate_design(player, "interceptor", design)
    assert design.drive == 1
    assert design.movement_value == 2


def test_energy_balance_enforced():
    player = _base_player()
    player.known_techs.extend(["Plasma Cannon"])
    design = ShipDesign(
        cannon_parts={"Plasma Cannon": 1},
        drive_parts={"Nuclear Drive": 1},
        hull_parts={"Hull": 1},
    )

    with pytest.raises(RulesViolation):
        validate_design(player, "cruiser", design)

    design.energy_sources["Nuclear Source"] = 1
    validate_design(player, "cruiser", design)
    assert design.energy_production >= design.energy_consumption


def test_drive_required_mobile_starbase_no_drive():
    player = _base_player()
    player.known_techs.extend(["Nuclear Drive", "Starbase"])

    mobile = ShipDesign(hull_parts={"Hull": 1}, energy_sources={"Nuclear Source": 1})
    with pytest.raises(RulesViolation):
        validate_design(player, "interceptor", mobile)

    mobile.drive_parts["Nuclear Drive"] = 1
    validate_design(player, "interceptor", mobile)

    starbase = ShipDesign(
        cannon_parts={"Ion Cannon": 1},
        drive_parts={"Nuclear Drive": 1},
        energy_sources={"Nuclear Source": 1},
        hull_parts={"Hull": 1},
    )
    with pytest.raises(RulesViolation):
        validate_design(player, "starbase", starbase)

    starbase.drive_parts.clear()
    validate_design(player, "starbase", starbase)


def test_values_cumulative():
    player = _base_player()
    player.known_techs.extend(["Fusion Drive"])
    design = ShipDesign(
        drive_parts={"Fusion Drive": 2},
        energy_sources={"Nuclear Source": 2},
        hull_parts={"Hull": 1},
    )

    validate_design(player, "cruiser", design)
    assert design.drive == 2
    assert design.movement_value == 4
    assert design.initiative == 4
    assert design.energy_consumption == 4


def test_legacy_game_model_design_supported():
    player = _base_player()
    legacy = LegacyShipDesign(drive=1, drives=1)

    # Should not raise for pre-part aggregated blueprints.
    validate_design(player, "interceptor", legacy)
    assert legacy.drive == 1
    assert legacy.movement_value() == 1


def test_build_caps():
    player = _base_player()
    player.known_techs.append("Starbase")
    state = _state_with_hex(player)
    hx = state.map.hexes["H1"]
    hx.pieces[player.player_id].ships["dreadnought"] = FLEET_CAP["dreadnought"]

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"dreadnought": 1}}, "H1")

    # Fill interceptors to the cap across two hexes
    hx2 = Hex(
        id="H2",
        ring=1,
        pieces={player.player_id: Pieces(ships={"interceptor": 4}, discs=1)},
    )
    state.map.hexes["H2"] = hx2
    hx.pieces[player.player_id].ships["interceptor"] = 4

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"interceptor": 1}}, "H1")


def test_build_costs_and_limit_two_per_action():
    player = _base_player()
    state = _state_with_hex(player)

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"interceptor": 3}}, "H1")

    player.resources.materials = BUILD_COST["cruiser"] + BUILD_COST["interceptor"] - 1
    with pytest.raises(RulesViolation):
        validate_build(
            player,
            {"state": state, "ships": {"cruiser": 1, "interceptor": 1}},
            "H1",
        )

    player.resources.materials = BUILD_COST["cruiser"] + BUILD_COST["interceptor"]
    validate_build(
        player,
        {"state": state, "ships": {"cruiser": 1, "interceptor": 1}},
        "H1",
    )


def test_build_requires_influence_disc_in_hex():
    player = _base_player()
    state = _state_with_hex(player)
    state.map.hexes["H1"].pieces[player.player_id].discs = 0

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"interceptor": 1}}, "H1")


def test_structure_prereqs_and_per_hex_limits():
    player = _base_player()
    state = _state_with_hex(player)
    hx = state.map.hexes["H1"]

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"starbase": 1}}, "H1")

    player.known_techs.append("Starbase")
    validate_build(player, {"state": state, "ships": {"starbase": 1}}, "H1")

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "structures": {"orbital": 1}}, "H1")

    player.known_techs.append("Orbital")
    validate_build(player, {"state": state, "structures": {"orbital": 1}}, "H1")
    hx.orbital = True
    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "structures": {"orbital": 1}}, "H1")

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "structures": {"monolith": 1}}, "H1")

    player.known_techs.append("Monolith")
    validate_build(player, {"state": state, "structures": {"monolith": 1}}, "H1")
    hx.monolith = True
    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "structures": {"monolith": 1}}, "H1")


def test_component_availability_limits():
    player = _base_player()
    player.available_components["dreadnought"] = 0
    state = _state_with_hex(player)

    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "ships": {"dreadnought": 1}}, "H1")

    player.available_components["dreadnought"] = 2
    player.available_components["orbital"] = 0
    with pytest.raises(RulesViolation):
        validate_build(player, {"state": state, "structures": {"orbital": 1}}, "H1")
