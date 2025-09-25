# Overwrite the combat simulator with a full Monte Carlo implementation.
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import random
import math

# =============================
# Public API
# =============================

@dataclass
class CombatResult:
    win_prob: float
    expected_vp_swing: float
    expected_losses_attacker: float
    expected_losses_defender: float

def score_combat(query: Dict[str, Any]) -> CombatResult:
    """
    Monte Carlo combat simulator for Eclipse-like battles with initiative, computers, shields,
    multiple weapon lines, and missiles. Accepts flexible input. Examples at bottom.
    Required (minimum) fields:
        query = {
        "attacker": {
            "ships": {"interceptor":2,"cruiser":1},
            # either provide per-class designs...
            "designs": {
            "interceptor": {"initiative":3,"hull":1,"computer":1,"shield":0,"weapons":{"ion":1},"missiles":0},
            "cruiser":     {"initiative":2,"hull":2,"computer":1,"shield":0,"weapons":{"ion":2},"missiles":0},
            }
            # ...or a fleet-wide aggregate (fallback) used to generate generic ships
            # "computer": 1, "shield": 0, "weapons": {"ion":2}, "hull": 1, "initiative": 3
        },
        "defender": {
            "ships": {"cruiser":2},
            "designs": {"cruiser":{"initiative":2,"hull":2,"computer":0,"shield":1,"weapons":{"ion":2},"missiles":0}},
        },
        # optional knobs
        "weapon_thresholds": {"ion":6,"plasma":5,"gauss":4,"antimatter":4,"missiles":5},
        "n_sims": 4000,
        "seed": 42,
        "rep_tile_ev": 1.0,           # EV for winning the battle (reputation etc)
        "ship_vp": {"interceptor":0.5,"cruiser":1.0,"dreadnought":2.0,"starbase":1.0},
        "round_cap": 20,
        "simultaneous_at_same_initiative": True,
        "targeting": "focus_fire"      # focus_fire | lowest_initiative | highest_initiative | random
        }
    Returns:
        CombatResult with aggregate statistics.
    """
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
        # ship VP delta
        vp_swing_total += outcome.vp_delta_attacker_minus_defender
        att_losses += outcome.attacker_losses
        def_losses += outcome.defender_losses

    n = max(1, cfg.n_sims)
    return CombatResult(
        win_prob = wins / n,
        expected_vp_swing = vp_swing_total / n,
        expected_losses_attacker = att_losses / n,
        expected_losses_defender = def_losses / n,
    )

# =============================
# Data model
# =============================

@dataclass
class Ship:
    cls: str
    hull: int
    max_hull: int
    initiative: int
    computer: int
    shield: int
    weapons: Dict[str, int]  # e.g., {"ion":2,"plasma":1}
    missiles: int = 0

def alive(self) -> bool:
    return self.hull > 0

@dataclass
class Fleet:
    owner: str
    ships: List[Ship] = field(default_factory=list)

    def alive(self) -> bool:
        return any(s.alive() for s in self.ships)

    def total_ships(self) -> int:
        return sum(1 for s in self.ships if s.alive())

    def losses(self, initial_count: int) -> int:
        return max(0, initial_count - self.total_ships())

    def vp_value_of_destroyed(self, initial_counts: Dict[str,int], ship_vp: Dict[str,float]) -> float:
        # initial per-class counts minus survivors times VP per class
        destroyed = {}
        for sclass, start in initial_counts.items():
            alive_now = sum(1 for s in self.ships if s.alive() and s.cls == sclass)
            destroyed[sclass] = max(0, start - alive_now)
        return sum(ship_vp.get(k, 0.0) * v for k, v in destroyed.items())

@dataclass
class _Outcome:
    winner: Optional[str]  # "attacker"|"defender"|None
    attacker_losses: int
    defender_losses: int
    vp_delta_attacker_minus_defender: float

@dataclass
class _SimConfig:
    weapon_thresholds: Dict[str,int]
    n_sims: int
    seed: int
    rep_tile_ev: float
    ship_vp: Dict[str,float]
    round_cap: int
    simultaneous_at_same_initiative: bool
    targeting: str

    # pre-built fleets + initial counts for VP
    attacker: Fleet = field(default_factory=lambda: Fleet(owner="attacker"))
    defender: Fleet = field(default_factory=lambda: Fleet(owner="defender"))
    attacker_initial_counts: Dict[str,int] = field(default_factory=dict)
    defender_initial_counts: Dict[str,int] = field(default_factory=dict)

@staticmethod
def _default_weapon_thresholds() -> Dict[str,int]:
    # These defaults are plausible for Eclipse 2E style combat but configurable.
    return {"ion":6, "plasma":5, "gauss":4, "antimatter":4, "missiles":5}

@staticmethod
def _generic_design_for(cls: str, aggregate: Dict[str,Any]) -> Dict[str,Any]:
    # Fallback if per-class designs are not supplied. Tunable placeholders.
    base = {
        "interceptor": {"initiative":3,"hull":1,"computer":aggregate.get("computer",0),"shield":aggregate.get("shield",0),"weapons":aggregate.get("weapons",{"ion":1}),"missiles":aggregate.get("missiles",0)},
        "cruiser":     {"initiative":2,"hull":2,"computer":aggregate.get("computer",0),"shield":aggregate.get("shield",0),"weapons":aggregate.get("weapons",{"ion":2}),"missiles":aggregate.get("missiles",0)},
        "dreadnought": {"initiative":1,"hull":3,"computer":aggregate.get("computer",0),"shield":aggregate.get("shield",0),"weapons":aggregate.get("weapons",{"ion":3}),"missiles":aggregate.get("missiles",0)},
        "starbase":    {"initiative":4,"hull":2,"computer":aggregate.get("computer",0),"shield":aggregate.get("shield",0),"weapons":aggregate.get("weapons",{"ion":2}),"missiles":0},
        "ancient":     {"initiative":2,"hull":2,"computer":1,"shield":1,"weapons":{"ion":2},"missiles":0},
    }
    return base.get(cls, {"initiative":2,"hull":1,"computer":0,"shield":0,"weapons":{"ion":1},"missiles":0})

@classmethod
def from_query(cls, query: Dict[str,Any]) -> "_SimConfig":
    weapon_thresholds = dict(cls._default_weapon_thresholds())
    weapon_thresholds.update(query.get("weapon_thresholds", {}))

    n_sims = int(query.get("n_sims", 4000))
    seed = int(query.get("seed", 12345))
    rep_tile_ev = float(query.get("rep_tile_ev", 1.0))
    ship_vp = {"interceptor":0.5, "cruiser":1.0, "dreadnought":2.0, "starbase":1.0, "ancient":1.0}
    ship_vp.update(query.get("ship_vp", {}))
    round_cap = int(query.get("round_cap", 20))
    simultaneous = bool(query.get("simultaneous_at_same_initiative", True))
    targeting = str(query.get("targeting", "focus_fire"))

    atk = query.get("attacker", {})
    dfd = query.get("defender", {})
    atk_fleet, atk_init = _build_fleet("attacker", atk)
    dfd_fleet, dfd_init = _build_fleet("defender", dfd)

    return cls(
        weapon_thresholds=weapon_thresholds,
        n_sims=n_sims,
        seed=seed,
        rep_tile_ev=rep_tile_ev,
        ship_vp=ship_vp,
        round_cap=round_cap,
        simultaneous_at_same_initiative=simultaneous,
        targeting=targeting,
        attacker=atk_fleet,
        defender=dfd_fleet,
        attacker_initial_counts=atk_init,
        defender_initial_counts=dfd_init,
    )

# =============================
# Fleet building
# =============================

def _build_fleet(owner: str, side: Dict[str,Any]) -> Tuple[Fleet, Dict[str,int]]:
    ships_by_class: Dict[str,int] = dict(side.get("ships", {}))
    designs_by_class: Dict[str,Dict[str,Any]] = dict(side.get("designs", {}))

    # If no per-class designs, synthesize from aggregate
    if not designs_by_class:
        aggregate = {
            "computer": int(side.get("computer", 0)),
            "shield": int(side.get("shield", 0)),
            "weapons": dict(side.get("weapons", {})),
            "missiles": int(side.get("missiles", 0))
        }
        designs_by_class = {cls: _SimConfig._generic_design_for(cls, aggregate) for cls in ships_by_class}

        # If still empty (no ships), allow a single generic interceptor for robustness
        if not designs_by_class and not ships_by_class:
            ships_by_class = {"interceptor":1}
            designs_by_class = {"interceptor": _SimConfig._generic_design_for("interceptor", aggregate)}

    fleet = Fleet(owner=owner)
    for cls_name, count in ships_by_class.items():
        d = designs_by_class.get(cls_name, _SimConfig._generic_design_for(cls_name, {}))
        for _ in range(int(count)):
            fleet.ships.append(
                Ship(
                    cls=cls_name,
                    hull=int(d.get("hull", 1)),
                    max_hull=int(d.get("hull", 1)),
                    initiative=int(d.get("initiative", 2)),
                    computer=int(d.get("computer", 0)),
                    shield=int(d.get("shield", 0)),
                    weapons=dict(d.get("weapons", {"ion":1})),
                    missiles=int(d.get("missiles", 0)),
                )
            )
    initial_counts = {k:int(v) for k,v in ships_by_class.items()}
    return fleet, initial_counts

# =============================
# Core simulation
# =============================

class _CombatSim:
    def __init__(self, cfg: _SimConfig, rng: random.Random):
        # Deep-copy fleets without importing copy module
        self.rng = rng
        self.cfg = cfg
        self.attacker = Fleet(owner="attacker", ships=[_copy_ship(s) for s in cfg.attacker.ships])
        self.defender = Fleet(owner="defender", ships=[_copy_ship(s) for s in cfg.defender.ships])
        self.start_attacker_count = self.attacker.total_ships()
        self.start_defender_count = self.defender.total_ships()

    def run(self) -> _Outcome:
        # Pre-combat missiles (both sides fire before any casualties are removed)
        self._missile_step()

        # Initiative rounds
        for _ in range(self.cfg.round_cap):
            if not self.attacker.alive() or not self.defender.alive():
                break
            self._initiative_round()
        winner: Optional[str] = None
        if self.attacker.alive() and not self.defender.alive():
            winner = "attacker"
        elif self.defender.alive() and not self.attacker.alive():
            winner = "defender"

        att_losses = self.start_attacker_count - self.attacker.total_ships()
        def_losses = self.start_defender_count - self.defender.total_ships()
        vp_delta = (
            self.attacker.vp_value_of_destroyed(self.cfg.defender_initial_counts, self.cfg.ship_vp)
            - self.defender.vp_value_of_destroyed(self.cfg.attacker_initial_counts, self.cfg.ship_vp)
        )
        return _Outcome(
            winner=winner,
            attacker_losses=att_losses,
            defender_losses=def_losses,
            vp_delta_attacker_minus_defender=vp_delta,
        )

    # ----- Steps -----

    def _missile_step(self):
        if not (self.attacker.alive() and self.defender.alive()):
            return
        # Snapshot for simultaneous application
        att_hits = self._compute_salvo_hits(self.attacker, self.defender, missile_only=True)
        def_hits = self._compute_salvo_hits(self.defender, self.attacker, missile_only=True)
        self._apply_recorded_hits(att_hits, self.defender)
        self._apply_recorded_hits(def_hits, self.attacker)

    def _initiative_round(self):
        max_ini = 0
        for s in self.attacker.ships + self.defender.ships:
            if s.alive():
                max_ini = max(max_ini, s.initiative)
        # Descending initiative
        for ini in range(max_ini, -1, -1):
            if not (self.attacker.alive() and self.defender.alive()):
                return
            # Gather hits for both sides at this initiative without removing casualties if simultaneous
            if self.cfg.simultaneous_at_same_initiative:
                att_hits = self._compute_salvo_hits(self.attacker, self.defender, initiative=ini)
                def_hits = self._compute_salvo_hits(self.defender, self.attacker, initiative=ini)
                self._apply_recorded_hits(att_hits, self.defender)
                self._apply_recorded_hits(def_hits, self.attacker)
            else:
                # Randomize firing order at same initiative
                if self.rng.random() < 0.5:
                    self._apply_recorded_hits(self._compute_salvo_hits(self.attacker, self.defender, initiative=ini), self.defender)
                    if self.defender.alive():
                        self._apply_recorded_hits(self._compute_salvo_hits(self.defender, self.attacker, initiative=ini), self.attacker)
                else:
                    self._apply_recorded_hits(self._compute_salvo_hits(self.defender, self.attacker, initiative=ini), self.attacker)
                    if self.attacker.alive():
                        self._apply_recorded_hits(self._compute_salvo_hits(self.attacker, self.defender, initiative=ini), self.defender)

    # ----- Firing helpers -----

    def _compute_salvo_hits(self, shooter: Fleet, target: Fleet, initiative: Optional[int]=None, missile_only: bool=False) -> List[Tuple[int,int]]:
        """
        Returns a list of (target_index, hits) to apply.
        If missile_only=True, only missile dice are fired. Otherwise, only ships with initiative==initiative fire cannons.
        """
        records: List[Tuple[int,int]] = []  # (idx_in_target_list, hits)
        if not (shooter.alive() and target.alive()):
            return records

        # Build indexable list of targets
        target_indices = [i for i, s in enumerate(target.ships) if s.alive()]
        if not target_indices:
            return records

        for i, ship in enumerate(shooter.ships):
            if not ship.alive():
                continue
            if missile_only:
                # Missiles fire once at start; assume all on ship are expended now
                dice = ship.missiles
                if dice <= 0:
                    continue
                # choose targets per die according to targeting policy
                for _d in range(dice):
                    tgt_idx = _select_target_index(self.rng, target, self.cfg.targeting)
                    tgt = target.ships[tgt_idx]
                    thr = _to_hit_threshold(self.cfg.weapon_thresholds["missiles"], ship.computer, tgt.shield)
                    hits = _roll_hits(self.rng, 1, thr)
                    if hits > 0:
                        records.append((tgt_idx, hits))
                # missiles are one-shot
                ship.missiles = 0
            else:
                if initiative is None or ship.initiative != initiative:
                    continue
                # fire all cannon-type weapons
                for wname, dice in ship.weapons.items():
                    base_thr = self.cfg.weapon_thresholds.get(wname, 6)
                    for _ in range(dice):
                        tgt_idx = _select_target_index(self.rng, target, self.cfg.targeting)
                        tgt = target.ships[tgt_idx]
                        thr = _to_hit_threshold(base_thr, ship.computer, tgt.shield)
                        hits = _roll_hits(self.rng, 1, thr)
                        if hits > 0:
                            records.append((tgt_idx, hits))
        return records

    def _apply_recorded_hits(self, records: List[Tuple[int,int]], target: Fleet):
        # Aggregate hits per target index to minimize order effects
        agg: Dict[int,int] = {}
        for idx, h in records:
            if idx < len(target.ships) and target.ships[idx].alive():
                agg[idx] = agg.get(idx, 0) + h
        # Apply damage
        # Prioritize applying to same targeted ships first; surplus spills to other lowest-hull ships
        # to reduce oddities when overkilling.
        for idx, h in agg.items():
            if idx >= len(target.ships):
                continue
            _apply_damage_to_index(target, idx, h)
        # Any overflow due to destroyed targets not existing anymore? Already handled by alive() check.

    # =============================
    # Dice mechanics and targeting
    # =============================

    def _to_hit_threshold(base: int, computer: int, shield: int) -> int:
        # Clamp between 2 and 6; 6 always hits only if base<=6 and mods not pushing above 6.
        thr = base - (computer - shield)
        if thr < 2: thr = 2
        if thr > 6: thr = 6
        return thr

    def _roll_hits(rng: random.Random, dice: int, threshold: int) -> int:
        hits = 0
        for _ in range(dice):
            d = rng.randint(1, 6)
            if d >= threshold:
                hits += 1
        return hits

    def _select_target_index(rng: random.Random, fleet: Fleet, policy: str) -> int:
        # Choose among alive ships according to policy
        alive_indices = [i for i, s in enumerate(fleet.ships) if s.alive()]
        if not alive_indices:
            return 0
        if policy == "random":
            return rng.choice(alive_indices)
        # compute keys
        def key_focus(i):  # lowest hull to secure kills
            s = fleet.ships[i]
            return (s.hull, s.initiative, s.cls)
        def key_lowest_ini(i):
            s = fleet.ships[i]
            return (s.initiative, s.hull, s.cls)
        def key_highest_ini(i):
            s = fleet.ships[i]
            return (-s.initiative, s.hull, s.cls)
        if policy == "lowest_initiative":
            return min(alive_indices, key=key_lowest_ini)
        if policy == "highest_initiative":
            return min(alive_indices, key=key_highest_ini)
        # default: focus_fire
        return min(alive_indices, key=key_focus)

    def _apply_damage_to_index(fleet: Fleet, idx: int, dmg: int):
        if idx >= len(fleet.ships):
            return
        s = fleet.ships[idx]
        if not s.alive():  # if already dead, spill to next lowest hull
            other_idx = _next_lowest_hull_index(fleet)
            if other_idx is None:
                return
            _apply_damage_to_index(fleet, other_idx, dmg)
            return
        s.hull -= dmg
        if s.hull <= 0:
            s.hull = 0

    def _next_lowest_hull_index(fleet: Fleet) -> Optional[int]:
        alive = [(i, s.hull) for i, s in enumerate(fleet.ships) if s.alive()]
        if not alive:
            return None
        alive.sort(key=lambda t: (t[1], fleet.ships[t[0]].initiative))
        return alive[0][0]

    def _copy_ship(s: Ship) -> Ship:
        return Ship(
            cls=s.cls,
            hull=s.hull,
            max_hull=s.max_hull,
            initiative=s.initiative,
            computer=s.computer,
            shield=s.shield,
            weapons=dict(s.weapons),
            missiles=s.missiles,
        )


