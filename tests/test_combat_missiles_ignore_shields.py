from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def basic_profiles():
    return {"ion": WeaponProfile(base_to_hit=6, damage=1)}


def make_ship(shield: int = 0) -> Ship:
    return Ship(
        cls="cruiser",
        initiative=2,
        hull=2,
        max_hull=2,
        computer=0,
        shield=shield,
        weapons={},
        missiles=1,
    )


def test_missiles_ignore_defender_shields():
    attacker = Combatant(owner="attacker", ships=[make_ship(shield=0)])
    defender_no_shield = Combatant(owner="defender", ships=[make_ship(shield=0)])
    defender_shield = Combatant(owner="defender", ships=[make_ship(shield=2)])

    cfg_no_shield = CombatConfig(
        attacker=attacker,
        defender=defender_no_shield,
        weapon_profiles=basic_profiles(),
        seed=11,
    )
    cfg_with_shield = CombatConfig(
        attacker=attacker,
        defender=defender_shield,
        weapon_profiles=basic_profiles(),
        seed=11,
    )

    res_no_shield = resolve_combat(cfg_no_shield)
    res_with_shield = resolve_combat(cfg_with_shield)

    hull_after_no_shield = res_no_shield.defender.ships[0].hull
    hull_after_with_shield = res_with_shield.defender.ships[0].hull

    assert hull_after_no_shield == hull_after_with_shield
