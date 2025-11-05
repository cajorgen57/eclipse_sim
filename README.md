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
       --planner pw_mcts \
       --output orion_round1.json
   ```

   **Note**: The default planner is now `pw_mcts` (PW_MCTSPlanner). The legacy `MCTSPlanner` is deprecated. See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for migration details.

2. **Render a shareable report.** Convert a saved JSON run into an SVG summary card for
   presentation or archival. 【F:eclipse_ai/eclipse_test/render_report.py†L1-L94】

   ```bash
   python -m eclipse_ai.render_report orion_round1.json \
       --output orion_round1.svg \
       --title "Orion Opening"
   ```

## Repository layout

```text
eclipse_ai/                      ← importable Python package
  # Core parsing & state
  board_parser.py                ← translate calibrated board images into map data
  tech_parser.py                 ← extract technology market state from the tech display
  state_assembler.py             ← merge parsed fragments and manual overrides into GameState
  image_ingestion.py             ← image calibration and preprocessing
  
  # Game models & rules
  game_models.py                 ← dataclasses for players, hexes, bags, and action payloads
  rules_engine.py                ← legacy rules engine (still used)
  rules/                         ← new centralized rules API
    api.py                       ← single source of truth for action enumeration
  action_gen/                   ← action generation modules
    explore.py, research.py, build.py, upgrade.py, move_fight.py, etc.
    legacy.py                    ← compatibility bridge to rules API
  
  # Planning & evaluation
  planners/                      ← planning algorithms
    mcts_pw.py                   ← PW_MCTSPlanner (primary, recommended)
  search_policy.py              ← legacy MCTSPlanner (deprecated)
  evaluator.py                   ← action and state evaluation
  value/                         ← feature extraction and weighted evaluation
    features.py                  ← state feature extraction
    weights.yaml                  ← evaluation weights
  
  # Simulation
  simulators/                    ← combat and exploration Monte Carlo kernels
    combat.py                    ← combat resolution
    exploration.py               ← exploration tile sampling
  explore_eval.py                ← exploration expected value calculations
  
  # Game mechanics
  movement.py                    ← helpers for faction-specific activation limits
  research.py                    ← shared logic for tech availability and cost adjustments
  influence.py                   ← influence disc accounting, diplomacy hooks, upkeep helpers
  technology.py                  ← tech research logic
  round_flow.py                  ← action/phase management and upkeep resolution
  pathing.py                     ← connectivity and reachability
  alliances.py                   ← alliance and diplomacy mechanics
  
  # Opponent modeling
  opponents/                     ← opponent behavior modeling
    model.py, infer.py, observe.py, threat.py, stats.py
  
  # State & economy
  models/                        ← economic and player state models
    economy.py                   ← economy tracking
    player_state.py              ← player state management
  state/                         ← state loading utilities
  uncertainty.py                 ← belief states and hidden information
  
  # Data & configuration
  data/                          ← game data files
    species.json                 ← species definitions
    tech.json                     ← technology definitions
    tech_costs_second_dawn.json  ← expansion tech costs
    constants.py                 ← game constants
    exploration_tiles.py         ← exploration tile data
  config.py                       ← configuration management
  
  # Scoring & reporting
  scoring/                       ← endgame VP calculators and species valuation helpers
    endgame.py                   ← endgame scoring
    species.py                   ← species-specific scoring
  reports/                       ← report generation
    run_report.py                ← planning report builder
  render_report.py                ← SVG report rendering
  
  # UI & visualization
  overlay.py                     ← vector overlay builders for UI/AR consumers
  resource_colors.py             ← resource color normalization
  
  # Utilities
  map/                           ← sector deck metadata and canonical hex definitions
    hex.py, connectivity.py, decks.py
  validators.py                  ← validation utilities
  hashing.py                     ← state hashing
  hidden_info.py                 ← hidden information handling
  diplomacy.py                    ← diplomacy utilities
  ship_parts.py                  ← ship component definitions
  species_data.py                ← species data access
  
  # Entry points
  main.py                        ← main API (recommend function)
  cli.py                         ← command-line interface
  
  # Testing & examples
  eclipse_test/                  ← CLI smoke tests, fixtures, and SVG renderer
    cases/                       ← test cases
tests/                           ← pytest suite covering rules, combat, economy, and parsing
scripts/                         ← utilities for development and data wrangling
notebooks & PDFs                 ← exploratory analyses (Jupyter notebooks)
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
6. **Planning.** `PW_MCTSPlanner.plan` (or legacy `MCTSPlanner.plan` - deprecated) rolls out multi-step action sequences, applying configurable
   simulation counts, depth, and progressive widening to produce ranked plans and overlays. 【F:eclipse_ai/planners/mcts_pw.py†L68-L156】【F:eclipse_ai/main.py†L75-L115】

   **Note**: The legacy `MCTSPlanner` is deprecated. Use `PW_MCTSPlanner` (default) instead. See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).
7. **Round flow helpers.** `round_flow.begin_round`, `take_action`, `take_reaction`, and upkeep
   utilities maintain action discs, turn order, and economic collapse rules for downstream
   integrations. 【F:eclipse_ai/round_flow.py†L19-L118】【F:eclipse_ai/round_flow.py†L120-L196】

## Running tests

Install development dependencies (see `pyproject.toml`) and execute the pytest suite from the
repository root:

```bash
pytest -q
```

Pytest discovers scenarios under `tests/`, which is organized around reusable fixtures, golden plan
outputs, and focused modules for rules legality, combat math, exploration EV checks, planner
reproducibility, species traits, and performance guards. 【F:Agents_Testing.md†L19-L110】

Common focused runs include:

```bash
pytest -q --maxfail=1 -m "golden"
pytest -q -k combat --durations=10
pytest -q -m "not slow"
```

These targets keep heavy simulations behind opt-in markers while preserving fast feedback loops for
the default CI configuration. 【F:Agents_Testing.md†L216-L224】

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
