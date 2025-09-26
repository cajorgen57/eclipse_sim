# Eclipse AI Toolkit

Tools for reconstructing *Eclipse: New Dawn for the Galaxy* game states from table snapshots,
simulating outcomes, and recommending plans. The code is packaged as `eclipse_ai`, which can be
imported or driven from notebooks and CLI harnesses.

## Quick start

1. **Run the bundled Orion smoke test.** Parse the demo board/tech photos, assemble a game state,
   and execute the Monte Carlo planner. 【F:eclipse_ai/eclipse_test/run_test.py†L1-L12】【F:eclipse_ai/main.py†L35-L74】

   ```bash
   python -m eclipse_ai.eclipse_test.run_test \
       --board eclipse_ai/eclipse_test/board.jpg \
       --tech eclipse_ai/eclipse_test/tech.jpg \
       --sims 400 --depth 2 --topk 5 \
       --output orion_round1.json
   ```

2. **Render a shareable report.** Convert a saved JSON run into an SVG summary card for
   presentation or archival. 【F:eclipse_ai/eclipse_test/render_report.py†L1-L94】

   ```bash
   python -m eclipse_ai.eclipse_test.render_report orion_round1.json \
       --output orion_round1.svg \
       --title "Orion Opening"
   ```

## Repository layout

```text
eclipse_ai/                      ← importable Python package
  board_parser.py                ← translate calibrated board images into map data
  tech_parser.py                 ← extract technology market state from the tech display
  state_assembler.py             ← merge parsed fragments and manual overrides into GameState
  game_models.py                 ← dataclasses for players, hexes, bags, and action payloads
  movement.py                    ← helpers for faction-specific activation limits
  research.py                    ← shared logic for tech availability and cost adjustments
  influence.py                   ← influence disc accounting, diplomacy hooks, upkeep helpers
  map/                           ← sector deck metadata and canonical hex definitions
  simulators/                    ← combat and exploration Monte Carlo kernels
  scoring/                       ← endgame VP calculators and species valuation helpers
  search_policy.py               ← Monte Carlo tree search over enumerated action sequences
  round_flow.py                  ← action/phase management and upkeep resolution
  overlay.py                     ← vector overlay builders for UI/AR consumers
  eclipse_test/                  ← CLI smoke tests, fixtures, and SVG renderer
notebooks & PDFs                 ← exploratory analyses of exploration, combat, and plan trees
scripts/                         ← utilities for development and data wrangling
tests/                           ← pytest suite covering rules, combat, economy, and parsing
```

## Core workflow

1. **Image ingestion.** `load_and_calibrate` rectifies and annotates raw photos (EXIF-aware when
   Pillow/OpenCV are installed) before parsing. 【F:eclipse_ai/image_ingestion.py†L1-L138】
2. **Parsing.** `parse_board` and `parse_tech` translate calibrated images or JSON sidecars into
   structured map and tech display objects. 【F:eclipse_ai/board_parser.py†L1-L146】【F:eclipse_ai/tech_parser.py†L1-L145】
3. **State assembly.** `assemble_state` combines parsed fragments with tech definitions, ensures
   bags/players exist, and applies manual overrides for simulations. 【F:eclipse_ai/state_assembler.py†L38-L114】
4. **Action enumeration.** `rules_engine.legal_actions` produces pragmatic explore/research/build
   move/upgrade/influence/diplomacy options, delegating to helper modules for research pricing and
   other rule nuances. 【F:eclipse_ai/rules_engine.py†L28-L86】【F:eclipse_ai/research.py†L1-L112】
5. **Simulation & scoring.** Exploration and combat Monte Carlo kernels feed
   `evaluator.evaluate_action`, which aggregates risk-aware VP estimates for each candidate action.
   【F:eclipse_ai/simulators/exploration.py†L1-L118】【F:eclipse_ai/simulators/combat.py†L1-L132】【F:eclipse_ai/evaluator.py†L10-L49】
6. **Planning.** `MCTSPlanner.plan` rolls out multi-step action sequences, applying configurable
   simulation counts, depth, and risk aversion to produce ranked plans and overlays. 【F:eclipse_ai/search_policy.py†L1-L112】【F:eclipse_ai/main.py†L75-L115】
7. **Round flow helpers.** `round_flow.begin_round`, `take_action`, `take_reaction`, and upkeep
   utilities maintain action discs, turn order, and economic collapse rules for downstream
   integrations. 【F:eclipse_ai/round_flow.py†L19-L118】【F:eclipse_ai/round_flow.py†L120-L196】

## Running tests

Install dependencies (see `requirements.txt` if present in your environment) and execute the
pytest suite from the repository root:

```bash
pytest
```

The suite covers legality gates, combat solvers, research costs, scoring heuristics, and state
assembly invariants. 【F:tests/test_rules_engine.py†L1-L33】【F:tests/test_scoring.py†L1-L33】【F:tests/test_state_assembler.py†L1-L52】

## Extending the toolkit

* Add new faction perks or movement tweaks via `PlayerState` flags and the helpers in
  `movement.py` / `influence.py`. 【F:eclipse_ai/game_models.py†L90-L200】【F:eclipse_ai/movement.py†L1-L32】【F:eclipse_ai/influence.py†L1-L48】
* Expand research catalogs or alternate scoring heuristics by editing the data files under
  `eclipse_ai/data/` and the modules in `research.py` / `scoring/`. 【F:eclipse_ai/data/tech.json†L1-L40】【F:eclipse_ai/research.py†L1-L112】【F:eclipse_ai/scoring/endgame.py†L1-L76】
* Build richer UIs by consuming the JSON payload from `recommend` and the vector overlays returned
  by `plan_overlays`. 【F:eclipse_ai/main.py†L75-L115】【F:eclipse_ai/overlay.py†L1-L152】

## License

No explicit license has been declared. Treat the contents as proprietary unless you have
permission from the maintainers.
