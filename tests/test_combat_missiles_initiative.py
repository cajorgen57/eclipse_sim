import pytest

from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def basic_profiles():
    return {"ion": WeaponProfile(base_to_hit=6, damage=1)}


def make_ship(cls: str, initiative: int, missiles: int = 0) -> Ship:
    return Ship(
        cls=cls,
        initiative=initiative,
        hull=1,
        max_hull=1,
        computer=0,
        shield=0,
        weapons={},
        missiles=missiles,
    )


def make_side(name: str, ships):
    return Combatant(owner=name, ships=list(ships))


def test_missiles_fire_by_initiative_order():
    attacker = make_side(
        "attacker",
        [make_ship("interceptor", 3, missiles=1), make_ship("cruiser", 2, missiles=1)],
    )
    defender = make_side(
        "defender",
        [make_ship("interceptor", 3, missiles=1), make_ship("cruiser", 2, missiles=1)],
    )
    config = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=basic_profiles(),
        seed=3,
    )
    result = resolve_combat(config, debug=True)
    steps = [(step["initiative"], step["side"]) for step in result.trace["missile_steps"]]
    assert steps == [
        (3, "attacker"),
        (3, "defender"),
        (2, "attacker"),
        (2, "defender"),
    ]
