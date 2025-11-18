# Agents_Testing.md

## Goal

Prove every agent decision respects Eclipse rules and expansion toggles. Lock behavior with fixtures, golden outputs, and seeded sims.

## Test types

* Unit: validate rule atoms (movement edges, energy checks, discounts).
* Integration: full actions across phases.
* Simulation: combat/exploration with fixed RNG seeds.
* Property: invariants across many randomized states.
* Golden: stable plan outputs for known positions.
* Performance: time and memory budgets per call.

## Directory layout

```
eclipse_ai/
  tests/
    fixtures/                # JSON states and tech displays
      base_*.json
      rotA_*.json
      sotR_*.json
    goldens/
      plan_*.json
    test_rules_engine.py
    test_combat.py
    test_exploration.py
    test_planner.py
    test_species.py
    test_performance.py
```

## Fixture schema (minimal)

```json
{
  "round": 3,
  "feature_flags": {"rotA": true, "sotR": false, "warp_portals": true, "anomalies": false},
  "map": {
    "hexes": {
      "101": {"owner": "P1", "wormholes": [0,2,3,5], "portals": []},
      "201": {"owner": null, "wormholes": [1,4], "portals": []}
    },
    "edges": [["101","201"]]
  },
  "players": {
    "P1": {
      "species": "Terran",
      "discs_free": 3, "upkeep_cost": 6,
      "money": 9, "science": 5, "materials": 6,
      "tracks": {"money":2,"science":2,"materials":2,"discounts":{"grid":0,"nano":0,"military":0,"rare":0}},
      "ships": {"interceptor": {}, "cruiser": {}, "dreadnought": {}, "starbase": {}},
      "blueprints": {"interceptor":{"weapons":[],"hull":1,"computer":0,"shield":0,"drive":1,"energy":1}},
      "colonies": {"101":{"money":1,"science":1,"materials":1}},
      "techs": ["Plasma Cannon"], "rares": [], "developments": [],
      "passed": false
    },
    "P2": { "...": "similar" }
  },
  "tech_supply": ["Fusion Drive","Plasma Cannon","Positron Computer"],
  "rare_supply": [], "developments": [],
  "bags": {"discovery":["+2 vp"], "reputation":[1,2,3]}
}
```

## Species start packs and traits

Represent as data not logic. One JSON per species. Agents load these into `state_assembler` overlays for tests.

```json
// fixtures/species/terrans.json
{
  "name": "Terran",
  "starting_hex": "home",
  "starting_resources": {"money": 2, "science": 2, "materials": 2},
  "starting_colonies": {"home": {"money":1,"science":1,"materials":1}},
  "starting_ships": {"interceptor":1, "dreadnought":0, "cruiser":0, "starbase":0},
  "starting_techs": [],
  "traits": {"special": []}
}
```

```json
// fixtures/species/planta.json
{
  "name": "Planta",
  "starting_hex": "home",
  "starting_resources": {"money": 2, "science": 2, "materials": 2},
  "starting_colonies": {"home": {"materials":2}},
  "starting_ships": {"interceptor":1},
  "starting_techs": [],
  "traits": {
    "influence_rules": "may place additional influence discs on connected hexes per Planta rules",
    "movement_rules": "treats own roots as adjacency",
    "other": []
  }
}
```

> Add one file per species you use. Keep them declarative. Expansion species go under `fixtures/species/rotA/` and `fixtures/species/sotR/`. The rules engine consumes these to create legal-action expectations.

## Test matrix (sample)

| Area      | Case                           | Flags | Species | Purpose                   |
| --------- | ------------------------------ | ----- | ------- | ------------------------- |
| Explore   | Draws from correct stack       | base  | Terran  | Enforce sector ring rules |
| Move      | Wormhole adjacency only        | base  | Any     | Disallow illegal hops     |
| Move      | Jump Drive once per activation | base  | Any     | Special movement          |
| Influence | Upkeep changes correct         | base  | Any     | Disc accounting           |
| Research  | Track discounts apply          | base  | Any     | Cost correctness          |
| Research  | Rare tech uniqueness           | rotA  | Any     | Supply constraints        |
| Combat    | Missiles before cannons        | base  | Any     | Phase order               |
| Combat    | Computers vs shields math      | base  | Any     | To-hit math               |
| Combat    | Rift Cannon ignores mods       | sotR  | Any     | Special weapon            |
| Portals   | Warp network adjacency         | rotA  | Any     | Graph overlay             |
| Deep Warp | Separate network               | sotR  | Any     | Graph overlay             |
| Anomalies | Cleanup die only               | sotR  | Any     | Timing                    |
| Species   | Planta influence exceptions    | rotA  | Planta  | Trait enforcement         |
| Planner   | Plan reproducibility           | all   | Any     | Golden outputs            |

## Assertions cookbook

### Rules engine

```python
def test_move_requires_wormhole(state_factory):
    s = state_factory("base_move_simple.json")
    acts = rules_engine.legal_actions(s, "P1")
    illegal = [a for a in acts if a["type"]=="Move" and a["payload"]["path"]==["101","201"]]
    assert illegal == [], "no wormhole edge between 101 and 201"
```

### Research cost

```python
def test_research_discounts_apply(state_factory):
    s = state_factory("base_research_grid_discount.json")
    act = next(a for a in rules_engine.legal_actions(s,"P1") if a["type"]=="Research" and a["payload"]["tech"]=="Fusion Drive")
    assert act["payload"]["cost"]["science"] == 4  # example after discount
```

### Combat order and math

```python
def test_combat_phase_order(seed_rng, combat_builder):
    battle = combat_builder("missile_then_cannons.json")
    log = combat.resolve(battle, seed=42)
    i_missile = log.index("MISSILE_PHASE_START")
    i_cannon  = log.index("CANNON_PHASE_START")
    assert i_missile < i_cannon
```

### Exploration EV vs sampling

```python
def test_exploration_ev_matches_sampling():
    bag = exploration.Bag(["good","bad","blank"])
    ev = exploration.expected_value(bag, policy="colonize_science")
    sample = exploration.sample_value(bag, policy="colonize_science", n=5000, seed=7)
    assert abs(ev - sample.mean) < 0.1
```

### Golden plan

```python
def test_planner_golden(tmp_path, load_fixture, load_golden):
    s = load_fixture("golden_state.json")
    out = recommend(None, None, prior_state=s, manual_inputs={"_planner":{"simulations":200,"depth":2,"risk_aversion":0.25}}, top_k=3)
    assert out["plans"] == load_golden("plan_golden_round3.json")
```

### Species trait enforcement

```python
def test_planta_extra_influence(state_factory):
    s = state_factory("rotA_planta_influence.json")
    acts = [a for a in rules_engine.legal_actions(s,"P1") if a["type"]=="Influence"]
    assert any(a["payload"].get("planta_extra")==True for a in acts)
```

## Utilities

### `state_factory`

* Loads a base fixture.
* Applies species pack overlay.
* Applies manual edits for the test.
* Verifies internal consistency (e.g., discs, upkeep, energy).

### Seeded RNG

* All sims accept `seed`. Tests pass seed through `combat.resolve`, `exploration.sample`, and planner rollout.

### Graph helpers

* Build map adjacency from wormholes.
* Portal overlay injects virtual edges per flags.

## Properties to check

* Conservation: resources never negative after any legal action.
* Energy: blueprint energy ≥ 0 after any `Upgrade`.
* Movement: every step lies on wormhole edge unless Jump Drive used and available.
* Turn order: once `passed`, only `Reaction` actions allowed.
* Supply: cannot research a tech not present in supply unless rules allow.
* Uniqueness: rare techs and developments unique per ruleset.
* Bags: draws reduce counts; returning tokens restores counts.

## Performance budgets

* `rules_engine.legal_actions`: ≤ 10 ms on small states, ≤ 50 ms on mid.
* `combat.resolve` with ≤ 10 ships per side and 2,000 sims: ≤ 150 ms.
* `recommend` with depth=2, sims=400: ≤ 500 ms on fixtures.
  Gate with `pytest -q -m "not slow"` and `-m slow` for heavier sims.

## CI recipe

```
pytest -q
pytest -q --maxfail=1 -m "golden"
pytest -q -k combat --durations=10
```

## Adding a new test case

1. Create or copy a base fixture under `tests/fixtures/`.
2. Overlay species pack(s) if needed.
3. Set flags to isolate the rule you are testing.
4. Write one assertion that pinpoints the rule.
5. If planner behavior is important, generate a golden and commit it.

## Notes

* Do not invent state. Use fixtures or parsed images plus explicit overrides.
* Keep species packs declarative so rules remain centralized in `rules_engine.py`.
* When rules change, update packs and goldens together.
