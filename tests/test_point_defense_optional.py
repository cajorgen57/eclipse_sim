from eclipse_ai.simulators.combat import (
    CombatConfig,
    Combatant,
    Ship,
    WeaponProfile,
    resolve_combat,
)


def basic_profiles():
    return {"ion": WeaponProfile(base_to_hit=6, damage=1)}


def missile_boat() -> Ship:
    return Ship(
        cls="interceptor",
        initiative=3,
        hull=1,
        max_hull=1,
        computer=0,
        shield=0,
        weapons={},
        missiles=3,
    )


def target_ship(shield: int = 0) -> Ship:
    return Ship(
        cls="cruiser",
        initiative=2,
        hull=3,
        max_hull=3,
        computer=0,
        shield=shield,
        weapons={},
    )


def test_point_defense_absent_when_disabled():
    attacker = Combatant(owner="attacker", ships=[missile_boat()])
    defender = Combatant(owner="defender", ships=[target_ship()])
    config = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=basic_profiles(),
        seed=7,
    )
    result = resolve_combat(config, debug=True)
    assert result.trace["pd_steps"] == []


def test_point_defense_intercepts_when_enabled():
    attacker = Combatant(owner="attacker", ships=[missile_boat()])
    defender = Combatant(
        owner="defender",
        ships=[target_ship()],
        has_point_defense=True,
        point_defense_dice=2,
        point_defense_base=6,
        point_defense_computer=1,
    )
    config = CombatConfig(
        attacker=attacker,
        defender=defender,
        weapon_profiles=basic_profiles(),
        enable_point_defense=True,
        seed=5,
    )
    result = resolve_combat(config, debug=True)
    assert result.trace["pd_steps"], "Expected PD trace entries"
    prevented = result.trace["pd_steps"][0]["prevented"]
    assert prevented > 0

    shielded_attacker = Combatant(owner="attacker", ships=[missile_boat()])
    shielded_attacker.ships[0].shield = 2
    defender_again = Combatant(
        owner="defender",
        ships=[target_ship()],
        has_point_defense=True,
        point_defense_dice=2,
        point_defense_base=6,
        point_defense_computer=1,
    )
    config_with_shield = CombatConfig(
        attacker=shielded_attacker,
        defender=defender_again,
        weapon_profiles=basic_profiles(),
        enable_point_defense=True,
        seed=5,
    )
    result_with_shield = resolve_combat(config_with_shield, debug=True)
    assert result_with_shield.trace["pd_steps"][0]["prevented"] == prevented
