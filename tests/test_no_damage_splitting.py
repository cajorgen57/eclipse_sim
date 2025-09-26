from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def antimatter_profile():
    return {"antimatter": WeaponProfile(base_to_hit=4, damage=2)}


def attacker_ship() -> Ship:
    return Ship(
        cls="dreadnought",
        initiative=2,
        hull=3,
        max_hull=3,
        computer=2,
        shield=0,
        weapons={"antimatter": 1},
    )


def defenders() -> Combatant:
    return Combatant(
        owner="defender",
        ships=[
            Ship(
                cls="interceptor",
                initiative=1,
                hull=1,
                max_hull=1,
                computer=0,
                shield=0,
                weapons={},
            ),
            Ship(
                cls="interceptor",
                initiative=1,
                hull=1,
                max_hull=1,
                computer=0,
                shield=0,
                weapons={},
            ),
        ],
    )


def base_config(antimatter_splitter: bool):
    return CombatConfig(
        attacker=Combatant(owner="attacker", ships=[attacker_ship()]),
        defender=defenders(),
        weapon_profiles=antimatter_profile(),
        antimatter_splitter_enabled=antimatter_splitter,
        round_cap=1,
        seed=13,
    )


def test_damage_not_split_without_splitter():
    result = resolve_combat(base_config(False))
    destroyed = sum(1 for ship in result.defender.ships if not ship.alive())
    assert destroyed == 1


def test_damage_can_split_with_splitter():
    result = resolve_combat(base_config(True))
    destroyed = sum(1 for ship in result.defender.ships if not ship.alive())
    assert destroyed >= 2
