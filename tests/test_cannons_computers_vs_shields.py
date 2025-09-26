from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def cannon_profiles():
    return {"ion": WeaponProfile(base_to_hit=6, damage=1)}


def shooter(computer: int) -> Ship:
    return Ship(
        cls="interceptor",
        initiative=3,
        hull=1,
        max_hull=1,
        computer=computer,
        shield=0,
        weapons={"ion": 1},
    )


def target(shield: int) -> Ship:
    return Ship(
        cls="interceptor",
        initiative=3,
        hull=1,
        max_hull=1,
        computer=0,
        shield=shield,
        weapons={},
    )


def test_cannon_threshold_uses_computers_and_shields():
    base_cfg = dict(
        weapon_profiles=cannon_profiles(),
        simul_same_initiative=True,
        seed=34,
    )

    res_low = resolve_combat(
        CombatConfig(
            attacker=Combatant(owner="attacker", ships=[shooter(computer=2)]),
            defender=Combatant(owner="defender", ships=[target(shield=0)]),
            **base_cfg,
        )
    )
    res_high = resolve_combat(
        CombatConfig(
            attacker=Combatant(owner="attacker", ships=[shooter(computer=2)]),
            defender=Combatant(owner="defender", ships=[target(shield=2)]),
            **base_cfg,
        )
    )

    low_alive = res_low.defender.ships[0].alive()
    high_alive = res_high.defender.ships[0].alive()

    assert low_alive is False
    assert high_alive is True
