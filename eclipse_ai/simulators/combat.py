"""Combat resolution for Eclipse.

This module implements deterministic single-combat resolution that respects the
published timing structure: missiles by initiative, then engagement rounds with
initiative ordered cannon volleys.  The driver is :func:`resolve_combat`, while
:func:`score_combat` keeps the legacy Monte-Carlo EV wrapper used by other
modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
import random

# =============================
# Basic data structures
# =============================


@dataclass
class WeaponProfile:
    """Static information about a weapon line."""

    base_to_hit: int
    damage: int = 1
    is_rift: bool = False


@dataclass
class Ship:
    """Runtime representation of a single ship in combat."""

    cls: str
    initiative: int
    hull: int
    max_hull: int
    computer: int
    shield: int
    weapons: Dict[str, int] = field(default_factory=dict)
    missiles: int = 0
    missile_damage: int = 1

    def alive(self) -> bool:
        return self.hull > 0

    def copy(self) -> "Ship":
        return Ship(
            cls=self.cls,
            initiative=self.initiative,
            hull=self.hull,
            max_hull=self.max_hull,
            computer=self.computer,
            shield=self.shield,
            weapons=dict(self.weapons),
            missiles=self.missiles,
            missile_damage=self.missile_damage,
        )


@dataclass
class Combatant:
    """State for one side of the battle."""

    owner: str
    ships: List[Ship] = field(default_factory=list)
    has_point_defense: bool = False
    point_defense_dice: int = 0
    point_defense_base: int = 6
    point_defense_computer: int = 0
    retreat_requested: bool = False
    pinned: bool = False

    def alive(self) -> bool:
        return any(s.alive() for s in self.ships)

    def total_ships(self) -> int:
        return sum(1 for s in self.ships if s.alive())

    def copy(self) -> "Combatant":
        return Combatant(
            owner=self.owner,
            ships=[s.copy() for s in self.ships],
            has_point_defense=self.has_point_defense,
            point_defense_dice=self.point_defense_dice,
            point_defense_base=self.point_defense_base,
            point_defense_computer=self.point_defense_computer,
            retreat_requested=self.retreat_requested,
            pinned=self.pinned,
        )


@dataclass
class CombatConfig:
    attacker: Combatant
    defender: Combatant
    weapon_profiles: Dict[str, WeaponProfile]
    simul_same_initiative: bool = True
    enable_point_defense: bool = False
    enable_rift_cannons: bool = False
    antimatter_splitter_enabled: bool = False
    targeting: str = "focus_fire"
    round_cap: int = 20
    seed: Optional[int] = None


@dataclass
class CombatResolution:
    winner: Optional[str]
    attacker: Combatant
    defender: Combatant
    retreating_side: Optional[str] = None
    rounds_completed: int = 0
    trace: Optional[Dict[str, List[Dict[str, Any]]]] = None


# =============================
# Dice helpers
# =============================


def missile_hit(die: int) -> bool:
    """Missiles hit only on a natural six."""

    return die == 6


def cannon_threshold(att_computers: int, def_shields: int, base: int) -> int:
    """Compute the to-hit threshold for cannons, bounded to 2..6."""

    thr = base - att_computers + def_shields
    if thr < 2:
        return 2
    if thr > 6:
        return 6
    return thr


# =============================
# Core combat driver
# =============================


class CombatResolver:
    def __init__(self, config: CombatConfig, debug: bool = False):
        self.cfg = config
        self.debug = debug
        self.rng = random.Random(config.seed)
        self.attacker = config.attacker.copy()
        self.defender = config.defender.copy()
        self.weapon_profiles = dict(config.weapon_profiles)
        self.trace: Optional[Dict[str, List[Dict[str, Any]]]] = (
            {"missile_steps": [], "pd_steps": [], "cannon_volleys": []}
            if debug
            else None
        )
        self.retreating_side: Optional[str] = None
        self.rounds_completed = 0

    # ----- Public API -----

    def resolve(self) -> CombatResolution:
        self._resolve_missiles()
        if self.attacker.alive() and self.defender.alive():
            self._engagement_loop()
        winner = self._determine_winner()
        return CombatResolution(
            winner=winner,
            attacker=self.attacker,
            defender=self.defender,
            retreating_side=self.retreating_side,
            rounds_completed=self.rounds_completed,
            trace=self.trace,
        )

    # ----- Missile phase -----

    def _resolve_missiles(self) -> None:
        max_ini = self._max_initiative()
        for ini in range(max_ini, -1, -1):
            if self.attacker.alive():
                self._fire_missiles_for_initiative(self.attacker, self.defender, ini)
            if self.defender.alive():
                self._fire_missiles_for_initiative(self.defender, self.attacker, ini)
            if not (self.attacker.alive() and self.defender.alive()):
                break

    def _fire_missiles_for_initiative(
        self, side: Combatant, opponent: Combatant, ini: int
    ) -> None:
        ships = [s for s in side.ships if s.alive() and s.initiative == ini and s.missiles > 0]
        if not ships or not opponent.alive():
            return
        ships_by_cls: Dict[str, List[Ship]] = {}
        for ship in ships:
            ships_by_cls.setdefault(ship.cls, []).append(ship)
        for cls, cls_ships in ships_by_cls.items():
            assignments: List[Dict[str, Any]] = []
            for ship in cls_ships:
                for _ in range(ship.missiles):
                    target_index = self._select_target_index(opponent, self.cfg.targeting)
                    die = self._roll_die()
                    assignments.append(
                        {
                            "target_index": target_index,
                            "die": die,
                            "hit": missile_hit(die),
                            "damage": ship.missile_damage,
                            "ship_class": cls,
                            "side": side.owner,
                            "initiative": ini,
                        }
                    )
                ship.missiles = 0
            hits_before_pd = sum(1 for a in assignments if a["hit"])
            if (
                hits_before_pd
                and self.cfg.enable_point_defense
                and opponent.has_point_defense
                and opponent.point_defense_dice > 0
            ):
                pd_hits = self._resolve_point_defense(
                    defender=opponent,
                    incoming_hits=hits_before_pd,
                    context={"side": side.owner, "ship_class": cls, "initiative": ini},
                )
                for assignment in assignments:
                    if pd_hits <= 0:
                        break
                    if assignment["hit"]:
                        assignment["hit"] = False
                        pd_hits -= 1
            self._apply_missile_assignments(assignments, opponent)
            if self.trace is not None:
                self.trace["missile_steps"].append(
                    {
                        "side": side.owner,
                        "initiative": ini,
                        "ship_class": cls,
                        "assignments": assignments,
                    }
                )

    def _resolve_point_defense(
        self,
        defender: Combatant,
        incoming_hits: int,
        context: Dict[str, Any],
    ) -> int:
        threshold = cannon_threshold(
            att_computers=defender.point_defense_computer,
            def_shields=0,
            base=defender.point_defense_base,
        )
        prevented = 0
        rolls: List[int] = []
        for _ in range(defender.point_defense_dice):
            die = self._roll_die()
            rolls.append(die)
            if die == 6 or die >= threshold:
                prevented += 1
        prevented = min(prevented, incoming_hits)
        if self.trace is not None:
            data = dict(context)
            data.update(
                {
                    "defender": defender.owner,
                    "prevented": prevented,
                    "rolls": rolls,
                }
            )
            self.trace["pd_steps"].append(data)
        return prevented

    def _apply_missile_assignments(
        self, assignments: Iterable[Dict[str, Any]], opponent: Combatant
    ) -> None:
        for assignment in assignments:
            if not assignment.get("hit"):
                continue
            target_index = assignment["target_index"]
            damage = assignment["damage"]
            self._apply_damage_to_index(opponent, target_index, damage)

    # ----- Engagement rounds -----

    def _engagement_loop(self) -> None:
        for round_index in range(1, self.cfg.round_cap + 1):
            if not (self.attacker.alive() and self.defender.alive()):
                break
            self._engagement_round(round_index)
            self.rounds_completed = round_index
            if self.retreating_side:
                break
            if not (self.attacker.alive() and self.defender.alive()):
                break
            self._handle_retreats()
            if self.retreating_side:
                break

    def _engagement_round(self, round_index: int) -> None:
        max_ini = self._max_initiative()
        for ini in range(max_ini, -1, -1):
            if not (self.attacker.alive() and self.defender.alive()):
                break
            att_hits = self._prepare_cannon_volley(self.attacker, self.defender, ini)
            def_hits = self._prepare_cannon_volley(self.defender, self.attacker, ini)
            if self.trace is not None and (att_hits or def_hits):
                self.trace["cannon_volleys"].append(
                    {
                        "round": round_index,
                        "initiative": ini,
                        "attacker_hits": att_hits,
                        "defender_hits": def_hits,
                    }
                )
            if self.cfg.simul_same_initiative:
                self._apply_hits(self.defender, att_hits)
                self._apply_hits(self.attacker, def_hits)
            else:
                self._apply_hits(self.defender, att_hits)
                if self.defender.alive():
                    self._apply_hits(self.attacker, def_hits)

    def _prepare_cannon_volley(
        self, side: Combatant, opponent: Combatant, ini: int
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        if not opponent.alive():
            return hits
        for ship_index, ship in enumerate(side.ships):
            if not ship.alive() or ship.initiative != ini:
                continue
            for weapon_name, dice in ship.weapons.items():
                profile = self.weapon_profiles.get(weapon_name)
                if profile is None:
                    continue
                if profile.is_rift and not self.cfg.enable_rift_cannons:
                    continue
                for _ in range(dice):
                    if profile.is_rift:
                        self._resolve_rift_die(
                            hits,
                            side,
                            opponent,
                            ship_index,
                            weapon_name,
                            profile,
                        )
                    else:
                        self._resolve_cannon_die(
                            hits,
                            side,
                            opponent,
                            ship_index,
                            weapon_name,
                            profile,
                        )
        return hits

    def _resolve_cannon_die(
        self,
        hits: List[Dict[str, Any]],
        side: Combatant,
        opponent: Combatant,
        ship_index: int,
        weapon_name: str,
        profile: WeaponProfile,
    ) -> None:
        if not opponent.alive():
            return
        target_index = self._select_target_index(opponent, self.cfg.targeting)
        die = self._roll_die()
        threshold = cannon_threshold(
            att_computers=side.ships[ship_index].computer,
            def_shields=opponent.ships[target_index].shield,
            base=profile.base_to_hit,
        )
        hit = die == 6 or die >= threshold
        if hit:
            if self.cfg.antimatter_splitter_enabled and profile.damage > 1:
                ordered_targets = self._ordered_target_indices(
                    opponent, self.cfg.targeting
                )
                if not ordered_targets:
                    return
                assigned = 0
                for idx in ordered_targets:
                    hits.append(
                        {
                            "target_index": idx,
                            "damage": 1,
                            "weapon": weapon_name,
                            "side": side.owner,
                            "die": die,
                            "split": True,
                        }
                    )
                    assigned += 1
                    if assigned >= profile.damage:
                        break
                while assigned < profile.damage and ordered_targets:
                    hits.append(
                        {
                            "target_index": ordered_targets[0],
                            "damage": 1,
                            "weapon": weapon_name,
                            "side": side.owner,
                            "die": die,
                            "split": True,
                        }
                    )
                    assigned += 1
            else:
                hits.append(
                    {
                        "target_index": target_index,
                        "damage": profile.damage,
                        "weapon": weapon_name,
                        "side": side.owner,
                        "die": die,
                        "split": False,
                    }
                )

    def _resolve_rift_die(
        self,
        hits: List[Dict[str, Any]],
        side: Combatant,
        opponent: Combatant,
        ship_index: int,
        weapon_name: str,
        profile: WeaponProfile,
    ) -> None:
        die = self._roll_die()
        outcome: Dict[str, Any]
        if die <= 2:
            outcome = {
                "target_index": ship_index,
                "damage": 0,
                "weapon": weapon_name,
                "side": side.owner,
                "die": die,
                "self_hit": True,
                "self_damage": profile.damage,
            }
            self._apply_damage_to_index(side, ship_index, profile.damage)
        elif die in (3, 4):
            outcome = {
                "target_index": None,
                "damage": 0,
                "weapon": weapon_name,
                "side": side.owner,
                "die": die,
                "self_hit": False,
            }
        else:
            target_index = self._select_target_index(opponent, self.cfg.targeting)
            outcome = {
                "target_index": target_index,
                "damage": profile.damage if die == 5 else profile.damage + 1,
                "weapon": weapon_name,
                "side": side.owner,
                "die": die,
                "self_hit": False,
            }
            hits.append(outcome)
            return
        hits.append(outcome)

    def _apply_hits(self, target: Combatant, hits: Iterable[Dict[str, Any]]) -> None:
        for hit in hits:
            damage = hit.get("damage", 0)
            target_index = hit.get("target_index")
            if damage <= 0 or target_index is None:
                continue
            self._apply_damage_to_index(target, target_index, damage)

    # ----- Retreat -----

    def _handle_retreats(self) -> None:
        attacker_retreats = (
            self.attacker.retreat_requested and not self.attacker.pinned
        )
        defender_retreats = (
            self.defender.retreat_requested and not self.defender.pinned
        )
        if attacker_retreats and defender_retreats:
            self.retreating_side = "both"
        elif attacker_retreats:
            self.retreating_side = "attacker"
        elif defender_retreats:
            self.retreating_side = "defender"

    # ----- Utility -----

    def _determine_winner(self) -> Optional[str]:
        if self.retreating_side == "attacker":
            return "defender"
        if self.retreating_side == "defender":
            return "attacker"
        if not self.attacker.alive() and not self.defender.alive():
            return None
        if self.attacker.alive() and not self.defender.alive():
            return "attacker"
        if self.defender.alive() and not self.attacker.alive():
            return "defender"
        return None

    def _apply_damage_to_index(self, fleet: Combatant, idx: int, dmg: int) -> None:
        if idx >= len(fleet.ships):
            return
        ship = fleet.ships[idx]
        if not ship.alive():
            return
        ship.hull -= dmg
        if ship.hull < 0:
            ship.hull = 0

    def _max_initiative(self) -> int:
        max_ini = 0
        for ship in self.attacker.ships + self.defender.ships:
            if ship.alive():
                if ship.initiative > max_ini:
                    max_ini = ship.initiative
        return max_ini

    def _roll_die(self) -> int:
        return self.rng.randint(1, 6)

    def _ordered_target_indices(self, fleet: Combatant, policy: str) -> List[int]:
        alive_indices = [i for i, ship in enumerate(fleet.ships) if ship.alive()]
        if not alive_indices:
            return []
        if policy == "random":
            indices = alive_indices[:]
            self.rng.shuffle(indices)
            return indices

        def key_focus(i: int) -> Tuple[int, int, str]:
            ship = fleet.ships[i]
            return (ship.hull, ship.initiative, ship.cls)

        def key_lowest_ini(i: int) -> Tuple[int, int, str]:
            ship = fleet.ships[i]
            return (ship.initiative, ship.hull, ship.cls)

        def key_highest_ini(i: int) -> Tuple[int, int, str]:
            ship = fleet.ships[i]
            return (-ship.initiative, ship.hull, ship.cls)

        if policy == "lowest_initiative":
            return sorted(alive_indices, key=key_lowest_ini)
        if policy == "highest_initiative":
            return sorted(alive_indices, key=key_highest_ini)
        return sorted(alive_indices, key=key_focus)

    def _select_target_index(self, fleet: Combatant, policy: str) -> int:
        ordered = self._ordered_target_indices(fleet, policy)
        if not ordered:
            return 0
        return ordered[0]


# =============================
# Legacy Monte Carlo wrapper
# =============================


@dataclass
class CombatResult:
    win_prob: float
    expected_vp_swing: float
    expected_losses_attacker: float
    expected_losses_defender: float


@dataclass
class _SimConfig:
    weapon_profiles: Dict[str, WeaponProfile]
    n_sims: int
    seed: int
    rep_tile_ev: float
    ship_vp: Dict[str, float]
    round_cap: int
    simul_same_initiative: bool
    targeting: str
    enable_point_defense: bool
    enable_rift_cannons: bool
    antimatter_splitter_enabled: bool
    attacker: Combatant = field(default_factory=lambda: Combatant(owner="attacker"))
    defender: Combatant = field(default_factory=lambda: Combatant(owner="defender"))
    attacker_initial_counts: Dict[str, int] = field(default_factory=dict)
    defender_initial_counts: Dict[str, int] = field(default_factory=dict)

    @staticmethod
    def _default_weapon_profiles() -> Dict[str, WeaponProfile]:
        return {
            "ion": WeaponProfile(base_to_hit=6, damage=1),
            "plasma": WeaponProfile(base_to_hit=5, damage=1),
            "gauss": WeaponProfile(base_to_hit=4, damage=1),
            "antimatter": WeaponProfile(base_to_hit=4, damage=2),
            "rift": WeaponProfile(base_to_hit=4, damage=2, is_rift=True),
        }

    @classmethod
    def from_query(cls, query: Dict[str, Any]) -> "_SimConfig":
        weapon_profiles = cls._default_weapon_profiles()
        for name, info in query.get("weapon_profiles", {}).items():
            weapon_profiles[name] = WeaponProfile(
                base_to_hit=int(info.get("base_to_hit", 6)),
                damage=int(info.get("damage", 1)),
                is_rift=bool(info.get("is_rift", False)),
            )
        n_sims = int(query.get("n_sims", 4000))
        seed = int(query.get("seed", 12345))
        rep_tile_ev = float(query.get("rep_tile_ev", 1.0))
        ship_vp = {
            "interceptor": 0.5,
            "cruiser": 1.0,
            "dreadnought": 2.0,
            "starbase": 1.0,
            "ancient": 1.0,
        }
        ship_vp.update(query.get("ship_vp", {}))
        round_cap = int(query.get("round_cap", 20))
        simul = bool(query.get("simultaneous_at_same_initiative", True))
        targeting = str(query.get("targeting", "focus_fire"))
        enable_pd = bool(query.get("enable_point_defense", False))
        enable_rift = bool(query.get("enable_rift_cannons", False))
        splitter = bool(query.get("antimatter_splitter_enabled", False))

        atk = query.get("attacker", {})
        dfd = query.get("defender", {})
        atk_fleet, atk_init = _build_fleet("attacker", atk)
        dfd_fleet, dfd_init = _build_fleet("defender", dfd)

        atk_pd = atk.get("point_defense", {})
        dfd_pd = dfd.get("point_defense", {})
        atk_fleet.has_point_defense = bool(atk_pd.get("enabled", False))
        atk_fleet.point_defense_dice = int(atk_pd.get("dice", 0))
        atk_fleet.point_defense_base = int(atk_pd.get("base", 6))
        atk_fleet.point_defense_computer = int(atk_pd.get("computer", 0))
        dfd_fleet.has_point_defense = bool(dfd_pd.get("enabled", False))
        dfd_fleet.point_defense_dice = int(dfd_pd.get("dice", 0))
        dfd_fleet.point_defense_base = int(dfd_pd.get("base", 6))
        dfd_fleet.point_defense_computer = int(dfd_pd.get("computer", 0))

        atk_fleet.retreat_requested = bool(atk.get("retreat", False))
        atk_fleet.pinned = bool(atk.get("pinned", False))
        dfd_fleet.retreat_requested = bool(dfd.get("retreat", False))
        dfd_fleet.pinned = bool(dfd.get("pinned", False))

        return cls(
            weapon_profiles=weapon_profiles,
            n_sims=n_sims,
            seed=seed,
            rep_tile_ev=rep_tile_ev,
            ship_vp=ship_vp,
            round_cap=round_cap,
            simul_same_initiative=simul,
            targeting=targeting,
            enable_point_defense=enable_pd,
            enable_rift_cannons=enable_rift,
            antimatter_splitter_enabled=splitter,
            attacker=atk_fleet,
            defender=dfd_fleet,
            attacker_initial_counts=atk_init,
            defender_initial_counts=dfd_init,
        )


def _build_fleet(owner: str, side: Dict[str, Any]) -> Tuple[Combatant, Dict[str, int]]:
    ships_by_class: Dict[str, int] = {k: int(v) for k, v in side.get("ships", {}).items()}
    designs_by_class: Dict[str, Dict[str, Any]] = dict(side.get("designs", {}))

    if not designs_by_class:
        aggregate = {
            "computer": int(side.get("computer", 0)),
            "shield": int(side.get("shield", 0)),
            "weapons": dict(side.get("weapons", {})),
            "missiles": int(side.get("missiles", 0)),
            "hull": int(side.get("hull", 1)),
            "initiative": int(side.get("initiative", 2)),
        }
        designs_by_class = {
            cls: _generic_design_for(cls, aggregate) for cls in ships_by_class
        }
        if not designs_by_class and not ships_by_class:
            ships_by_class = {"interceptor": 1}
            designs_by_class = {
                "interceptor": _generic_design_for("interceptor", aggregate)
            }

    fleet = Combatant(owner=owner)
    for cls_name, count in ships_by_class.items():
        design = designs_by_class.get(cls_name, _generic_design_for(cls_name, {}))
        for _ in range(count):
            fleet.ships.append(
                Ship(
                    cls=cls_name,
                    initiative=int(design.get("initiative", 2)),
                    hull=int(design.get("hull", 1)),
                    max_hull=int(design.get("hull", 1)),
                    computer=int(design.get("computer", 0)),
                    shield=int(design.get("shield", 0)),
                    weapons=dict(design.get("weapons", {"ion": 1})),
                    missiles=int(design.get("missiles", 0)),
                    missile_damage=int(design.get("missile_damage", 1)),
                )
            )
    initial_counts = {k: int(v) for k, v in ships_by_class.items()}
    return fleet, initial_counts


def _generic_design_for(cls: str, aggregate: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "interceptor": {
            "initiative": 3,
            "hull": 1,
            "computer": aggregate.get("computer", 0),
            "shield": aggregate.get("shield", 0),
            "weapons": aggregate.get("weapons", {"ion": 1}),
            "missiles": aggregate.get("missiles", 0),
        },
        "cruiser": {
            "initiative": 2,
            "hull": 2,
            "computer": aggregate.get("computer", 0),
            "shield": aggregate.get("shield", 0),
            "weapons": aggregate.get("weapons", {"ion": 2}),
            "missiles": aggregate.get("missiles", 0),
        },
        "dreadnought": {
            "initiative": 1,
            "hull": 3,
            "computer": aggregate.get("computer", 0),
            "shield": aggregate.get("shield", 0),
            "weapons": aggregate.get("weapons", {"ion": 3}),
            "missiles": aggregate.get("missiles", 0),
        },
        "starbase": {
            "initiative": 4,
            "hull": 2,
            "computer": aggregate.get("computer", 0),
            "shield": aggregate.get("shield", 0),
            "weapons": aggregate.get("weapons", {"ion": 2}),
            "missiles": aggregate.get("missiles", 0),
        },
        "ancient": {
            "initiative": 2,
            "hull": 2,
            "computer": 1,
            "shield": 1,
            "weapons": {"ion": 2},
            "missiles": 0,
        },
    }
    return base.get(
        cls,
        {
            "initiative": aggregate.get("initiative", 2),
            "hull": aggregate.get("hull", 1),
            "computer": aggregate.get("computer", 0),
            "shield": aggregate.get("shield", 0),
            "weapons": aggregate.get("weapons", {"ion": 1}),
            "missiles": aggregate.get("missiles", 0),
        },
    )


class _CombatSim:
    def __init__(self, cfg: _SimConfig, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self.attacker_start = sum(1 for s in cfg.attacker.ships if s.alive())
        self.defender_start = sum(1 for s in cfg.defender.ships if s.alive())

    def run(self) -> CombatResolution:
        seed = self.rng.randint(1, 10_000_000)
        resolver = CombatResolver(
            CombatConfig(
                attacker=self.cfg.attacker,
                defender=self.cfg.defender,
                weapon_profiles=self.cfg.weapon_profiles,
                simul_same_initiative=self.cfg.simul_same_initiative,
                enable_point_defense=self.cfg.enable_point_defense,
                enable_rift_cannons=self.cfg.enable_rift_cannons,
                antimatter_splitter_enabled=self.cfg.antimatter_splitter_enabled,
                targeting=self.cfg.targeting,
                round_cap=self.cfg.round_cap,
                seed=seed,
            )
        )
        return resolver.resolve()


def score_combat(query: Dict[str, Any]) -> CombatResult:
    cfg = _SimConfig.from_query(query)
    rng = random.Random(cfg.seed)
    wins = 0
    att_losses = 0.0
    def_losses = 0.0
    vp_swing_total = 0.0

    for _ in range(cfg.n_sims):
        sim = _CombatSim(cfg, rng)
        outcome = sim.run()
        if outcome.winner == "attacker":
            wins += 1
            vp_swing_total += cfg.rep_tile_ev
        elif outcome.winner == "defender":
            vp_swing_total -= cfg.rep_tile_ev
        att_losses += _losses(cfg.attacker_initial_counts, outcome.attacker)
        def_losses += _losses(cfg.defender_initial_counts, outcome.defender)
        vp_swing_total += _vp_delta(cfg, outcome)

    n = max(1, cfg.n_sims)
    return CombatResult(
        win_prob=wins / n,
        expected_vp_swing=vp_swing_total / n,
        expected_losses_attacker=att_losses / n,
        expected_losses_defender=def_losses / n,
    )


def _losses(initial_counts: Dict[str, int], fleet: Combatant) -> int:
    destroyed = 0
    for cls, start in initial_counts.items():
        alive = sum(1 for s in fleet.ships if s.alive() and s.cls == cls)
        destroyed += max(0, start - alive)
    return destroyed


def _vp_delta(cfg: _SimConfig, outcome: CombatResolution) -> float:
    attacker_vp = 0.0
    defender_vp = 0.0
    for cls, start in cfg.defender_initial_counts.items():
        alive = sum(1 for s in outcome.defender.ships if s.alive() and s.cls == cls)
        destroyed = max(0, start - alive)
        attacker_vp += cfg.ship_vp.get(cls, 0.0) * destroyed
    for cls, start in cfg.attacker_initial_counts.items():
        alive = sum(1 for s in outcome.attacker.ships if s.alive() and s.cls == cls)
        destroyed = max(0, start - alive)
        defender_vp += cfg.ship_vp.get(cls, 0.0) * destroyed
    return attacker_vp - defender_vp


__all__ = [
    "CombatConfig",
    "CombatResolution",
    "CombatResult",
    "Combatant",
    "CombatResolver",
    "Ship",
    "WeaponProfile",
    "cannon_threshold",
    "missile_hit",
    "resolve_combat",
    "score_combat",
]


def resolve_combat(config: CombatConfig, debug: bool = False) -> CombatResolution:
    resolver = CombatResolver(config, debug=debug)
    return resolver.resolve()
