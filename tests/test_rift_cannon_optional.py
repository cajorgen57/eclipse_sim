from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def rift_profile():
    return {"rift": WeaponProfile(base_to_hit=4, damage=2, is_rift=True)}


def rift_ship() -> Ship:
    return Ship(
        cls="ancient",
        initiative=2,
        hull=3,
        max_hull=3,
        computer=0,
        shield=0,
        weapons={"rift": 1},
    )


def target_ship() -> Ship:
    return Ship(
        cls="cruiser",
        initiative=1,
        hull=3,
        max_hull=3,
        computer=0,
        shield=3,
        weapons={},
    )


def test_rift_cannon_requires_flag():
    attacker = Combatant(owner="attacker", ships=[rift_ship()])
    defender = Combatant(owner="defender", ships=[target_ship()])

    disabled_cfg = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=rift_profile(),
        enable_rift_cannons=False,
        seed=19,
    )
    enabled_cfg = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=rift_profile(),
        enable_rift_cannons=True,
        seed=19,
    )

    disabled_result = resolve_combat(disabled_cfg)
    enabled_result = resolve_combat(enabled_cfg)

    assert disabled_result.defender.ships[0].hull == 3
    assert enabled_result.defender.ships[0].hull < 3 or enabled_result.attacker.ships[0].hull < 3
