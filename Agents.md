## TBD agents MD file, needs to be reviewed for accuracy

# Agents.md

## Canonical guidance for agents

This document is the **authoritative reference** for every autonomous agent that interacts with
this repository. When a workflow mentions any other `.md` file, interpret its instructions through
the lens of this file.

### How to use the supporting documents

* `README.md` &mdash; project overview for humans. Agents should only consult it for repository
  layout and command references after first checking this file for rule interpretations or
  overrides.
* `Agents_Testing.md` &mdash; expands on the testing philosophy defined here. Treat it as the
  canonical checklist for verification steps once you have aligned on rules and behaviors from
  `Agents.md`.
* `Species_Starts.md` &mdash; declarative data to seed fixtures. Use it as a lookup table when
  assembling player starts during simulations or tests; do not derive rules logic from it.

If additional markdown references are added, link them back into this section so future agents know
their scope. Unless another document explicitly supersedes these instructions, defer to
`Agents.md`.

## Purpose

Define Eclipse rules your AI must follow. Map rules to code paths for action generation, simulation,
and evaluation.

## Scope

Base game round flow and actions, plus modular support for Rise of the Ancients and Shadows of the
Rift. Core round structure and actions: Action → Combat → Upkeep → Cleanup【turn1file2†】【turn1file2†】.

---

## Rules summary (authoritative)

### Map and movement

* Movement uses wormholes. Exploration is only through a wormhole edge【turn1file2†】.
* Hex stacks: Inner (101–108), Middle (201–211), Outer (301–318)【turn1file2†】.
* Warp Portals (RotA): all warp-portal hexes are mutually adjacent; you may Move, Influence, and form Diplomatic Relations through them【turn1file11†】. Deep Warp Portals and Warp Nexus (SotR) are separate network; link rules differ【turn1file8†】.

### Action phase (repeat 1 action per turn until all pass)

Available actions: Explore, Influence, Research, Upgrade, Build, Move. Reactions are weaker Build/Upgrade/Move after passing【turn1file2†】【turn1file2†】.

### Combat (high level)

Resolve battles in Combat phase. Missiles, then engagement rounds by initiative; computers modify to-hit; shields reduce hits; retreats may occur (per player rules). (Use engine below for exact dice order and allocation.)

### Upkeep and Cleanup

Pay upkeep, produce resources in Upkeep. In Cleanup, return action discs and draw new Technology tiles【turn1file2†】.

### Expansion elements (toggleable)

* Rare Technologies and Developments are researched like techs; rares are unique and drawn/placed specially during setup/cleanup【turn1file0†】【turn1file0†】.
* Example rare parts and effects: Conifold Field (+3 hull), Sentient Hull (+1 comp +1 hull), Flux Missile (+2 initiative), Zero-Point Source (+12 energy), Point Defense vs missiles【turn1file5†】【turn1file5†】【turn1file5†】.
* Jump Drive: move to any neighboring hex regardless of wormholes, once per activation【turn1file6†】.
* Ancient Hives/Homeworlds, alliances, anomalies, deep warp, etc., are modular and should be feature-flagged【turn1file0†】【turn1file11†】【turn1file3†】.
* Anomalies act and destroy planets via an Anomaly die in Cleanup; they fight using Rift Cannons and ignore pinning【turn1file8†】【turn1file10†】【turn1file10†】.

---

## Code architecture (this repo)

### Key modules

* `board_parser.py`, `tech_parser.py`, `state_assembler.py`: build `GameState`.
* `rules_engine.py`: legal action generation.
* `combat.py`: Monte-Carlo resolution aligned with missile → engagement rounds, initiative and computers/shields handling.
* `exploration.py`: expected values and sampling for exploration tiles.
* `evaluator.py`: scoring of states and plans.
* `overlay.py`: UI overlays for steps and annotations.
* Entry point for planning: `from eclipse_ai import recommend`.

### State model

Minimal fields your agent needs per round:

```
GameState {
  round: int
  players: {id -> PlayerState}
  map: HexGraph  # wormholes, portals, ownership
  tech_supply: [TechnologyTile], rare_supply: [RareTech], developments: [Development]
  discovery_bag, reputation_bag
  feature_flags: {rotA: bool, sotR: bool, warp_portals: bool, anomalies: bool}
}
PlayerState {
  species, discs_free, upkeep_cost, money, science, materials
  tracks: {money/science/materials: int, discounts: {grid,nano,military,rare}}
  ships: {interceptor, cruiser, dreadnought, starbase} with blueprints
  colonies: {hex_id -> {pop_cubes}}
  techs: set, rares: set, developments: set
  passed: bool
}
```

### Legal action generator (`rules_engine.py`)

Implement per rules:

* `Explore`: allowed only across a wormhole edge; draw from the correct sector stack【turn1file2†】【turn1file2†】.
* `Influence`: move discs and adjust upkeep; obey adjacency and control.
* `Research`: buy tech; apply track discounts; allow Rare Tech/Development when flags on【turn1file0†】【turn1file7†】.
* `Upgrade`: modify ship blueprints; enforce energy balance and slot limits; include rare parts if owned.
* `Build`: pay Materials; respect capacity.
* `Move`: resolve activations per icon count; drives limit range; Jump Drive ignores wormholes once per activation【turn1file7†】【turn1file6†】.
* `Reaction`: limited versions after passing【turn1file2†】.
* Expansion toggles:

  * Warp Portals adjacency injection【turn1file11†】 and Deep Warp network (separate)【turn1file8†】.
  * Anomalies: spawn on exploring Deep Warp; act in Cleanup【turn1file3†】【turn1file8†】.
  * Hives: Ancients move on dice in Cleanup【turn1file11†】.

### Simulation kernels

* **Combat** (`combat.py`): Use the included missile phase → initiative-ordered volleys → regeneration. Computers add to-hit; shields raise target threshold; special weapons like Rift Cannons ignore both comps and shields【turn1file12†】.
* **Exploration** (`exploration.py`): Expected sector EV and sampling for full game; honor sector limits; feature-flag Draco/Planta hooks (stubs).

### Evaluation

`evaluator.py` should compute plan scores as:

* VP delta estimate (reputation, discoveries, hex VP, developments).
* Production swing at next Upkeep.
* Threat/tempo: initiative edges, pinning, reachable targets through wormholes/portals.
* Risk: combat Monte-Carlo loss probabilities and variance.

---

## Agent loop

### Entry point

```python
from eclipse_ai import recommend

plans = recommend(
  board_image_path, tech_image_path,
  prior_state=None,
  manual_inputs={"_planner":{"simulations":400,"depth":2,"risk_aversion":0.25}},
  top_k=5
)
```

### Internal flow

1. `state_assembler.build(board, tech, overrides)` → `GameState`
2. `rules_engine.legal_actions(state, player)`
3. `search_policy.rollout(state, action)`
4. `combat.resolve()` and `exploration.sample()` during rollouts
5. `evaluator.score(plan)`
6. Return `plans` with `score`, `risk`, `steps` and `overlays`, plus `belief` and `expected_bags`.

### Pseudocode

```python
def agent_decide(state, player_id):
    actions = rules_engine.legal_actions(state, player_id)
    scored = []
    for a in actions:
        sims = simulate_consequences(state, a, n=K)  # uses combat.py, exploration.py
        scored.append((a, evaluator.aggregate(sims)))
    return top_k(scored, k=5)
```

---

## Rule conformance checks

* **Movement validity**: wormhole or Jump Drive exception【turn1file2†】【turn1file6†】.
* **Tech purchase legality**: discounts by track; rare tech uniqueness and draw handling【turn1file0†】【turn1file0†】.
* **Portal graphs**: standard Warp Portal all-to-all adjacency vs Deep Warp/Nexus network separation【turn1file11†】【turn1file8†】.
* **Anomaly and Hive timers**: Cleanup triggers only【turn1file8†】【turn1file11†】.

---

## Testing

### Smoke tests

* Deterministic move legality across wormholes and Jump Drive.
* Research rare tech availability and uniqueness.
* Combat seed test: missiles before cannons; initiative ordering; Rift Cannon behavior.
* Exploration EV vs sampling consistency on sector stacks.

### CLI example

```
python -m eclipse_ai.run_test --mode=direct --state fixtures/state_minimal.json
```

Override pieces with `--manual` JSON to test edge cases.

---

## Notes

Keep expansions behind feature flags. Cite rule text in code comments using the page snippets above for traceability.
