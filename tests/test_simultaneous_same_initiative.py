from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def profiles():
    return {"ion": WeaponProfile(base_to_hit=6, damage=1)}


def ship() -> Ship:
    return Ship(
        cls="interceptor",
        initiative=3,
        hull=1,
        max_hull=1,
        computer=0,
        shield=0,
        weapons={"ion": 1},
    )


def test_same_initiative_volley_is_simultaneous():
    attacker = Combatant(owner="attacker", ships=[ship()])
    defender = Combatant(owner="defender", ships=[ship()])
    config = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=profiles(),
        simul_same_initiative=True,
        seed=13,
    )
    result = resolve_combat(config)
    assert result.attacker.ships[0].hull == 0
    assert result.defender.ships[0].hull == 0
