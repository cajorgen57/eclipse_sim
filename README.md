# Quick start

1. **Run the Orion smoke test from the CLI.** Sample Orion round-one images and annotations live in `eclipse_ai/eclipse_test/`. Execute the bundled harness to parse those assets, run Monte Carlo planning, and persist a JSON summary.【F:eclipse_ai/eclipse_test/run_test.py†L12-L270】

   ```bash
   python -m eclipse_ai.eclipse_test.run_test \
       --board eclipse_ai/eclipse_test/board.jpg \
       --tech eclipse_ai/eclipse_test/tech.jpg \
       --sims 400 --depth 2 --topk 5 \
       --output orion_round1.json
   ```

2. **Render a shareable report.** Convert the saved JSON into an SVG card that summarizes the recommended plans and their risk profile.【F:eclipse_ai/eclipse_test/render_report.py†L1-L162】

   ```bash
   python -m eclipse_ai.eclipse_test.render_report orion_round1.json \
       --output orion_round1.svg \
       --title "Orion Opening"
   ```

   The SVG embeds the EV/risk details for the top plans and can be opened directly in a browser or vector editor. Re-run the CLI with different planner settings or manual overrides to generate alternative scenarios.

# Eclipse AI Toolkit

This repository contains an experimental toolkit for parsing snapshots of an *Eclipse: New Dawn for the Galaxy* board, reconstructing a game state, simulating likely outcomes, and producing turn recommendations. The code is structured as a lightweight Python package (`eclipse_ai`) that can be imported into downstream projects or used from notebooks that orchestrate camera input, state overrides, and plan visualizations.

## High-level workflow

1. **Image ingestion** – Raw board or tech display photos are rectified, white-balanced, and annotated with metadata (e.g., a projected hex grid) to make downstream parsing easier. Optional dependencies such as OpenCV, Pillow, and ArUco marker detection power these corrections, with graceful degradation when they are unavailable.【F:eclipse_ai/image_ingestion.py†L1-L218】【F:eclipse_ai/image_ingestion.py†L219-L301】
2. **Board & tech parsing** – Calibrated images are converted into structured data:
   * `board_parser.parse_board` prefers JSON sidecars but can fall back to HSV-based token detection or a demo map if computer vision fails.【F:eclipse_ai/board_parser.py†L1-L176】【F:eclipse_ai/board_parser.py†L177-L278】
   * `tech_parser.parse_tech` reads available technologies from sidecar files or OCR, normalizing noisy text into canonical names.【F:eclipse_ai/tech_parser.py†L1-L121】【F:eclipse_ai/tech_parser.py†L122-L229】
3. **State assembly & overrides** – Parsed fragments are merged into a canonical `GameState` dataclass. Helpers ensure discovered players exist, tile bags are instantiated, and manual overrides (nested dicts or dotted paths) can patch any portion of the state.【F:eclipse_ai/state_assembler.py†L1-L118】【F:eclipse_ai/game_models.py†L1-L168】
4. **Belief tracking** – `uncertainty.BeliefState` maintains opponent tech archetype posteriors via discrete HMMs and tracks exploration bag uncertainty with a particle filter. Observations from parsed tech automatically update these models before planning.【F:eclipse_ai/uncertainty.py†L1-L232】【F:eclipse_ai/main.py†L32-L83】
5. **Action generation & evaluation** – `rules_engine.legal_actions` enumerates plausible moves for the active player, covering explore, research, build, move, upgrade, influence, diplomacy, and pass actions.【F:eclipse_ai/rules_engine.py†L1-L206】 Each candidate is scored by `evaluator.evaluate_action`, which fuses heuristics with Monte Carlo exploration and combat simulators to estimate VP delta and risk.【F:eclipse_ai/evaluator.py†L1-L241】【F:eclipse_ai/simulators/exploration.py†L1-L224】【F:eclipse_ai/simulators/combat.py†L1-L210】
6. **Search & planning** – `search_policy.MCTSPlanner` runs a single-player Monte Carlo Tree Search (P-UCT) over the enumerated actions, assembling top-ranked plans with risk-adjusted values and optional rollouts for deeper horizons.【F:eclipse_ai/search_policy.py†L1-L217】
7. **Visualization & packaging** – Results include serialized plan steps, belief summaries, expected bag compositions, and optional vector overlays for front-end rendering or augmented reality prototypes.【F:eclipse_ai/main.py†L92-L114】【F:eclipse_ai/overlay.py†L1-L185】

The notebooks and PDFs in the repository capture prototype experiments for exploration heuristics, combat simulations, and state tree visualizations; they illustrate how to orchestrate the Python package in interactive settings.

## Repository layout

```
Eclipse Exploration Simulation.ipynb   ← notebook exploring the end-to-end pipeline
Eclpise Combat Simulator.ipynb         ← combat tuning & validation notebook
state_tree_sim.ipynb                   ← experiments with plan trees / uncertainty
Eclipse Exploration Simulation.pdf     ← exported reference for the exploration notebook
Eclpise Combat Simulator.pdf           ← exported combat notebook reference
eclipse_tiles.csv                      ← sample tile bag data for exploration sims
eclipse_tiles.pdf                      ← annotated tile reference sheet

eclipse_ai/                            ← importable package
  ├── main.py                          ← `recommend` orchestration entry point
  ├── image_ingestion.py               ← photo calibration & metadata extraction
  ├── board_parser.py                  ← board token detection & sidecar loading
  ├── tech_parser.py                   ← tech display parsing via OCR/sidecars
  ├── state_assembler.py               ← merge map & tech into a `GameState`
  ├── game_models.py                   ← dataclasses and helpers for canonical state
  ├── rules_engine.py                  ← pragmatic action enumerators
  ├── evaluator.py                     ← action scoring (exploration/combat EV)
  ├── search_policy.py                 ← MCTS planner & plan data structures
  ├── overlay.py                       ← plan overlay generation helpers
  ├── uncertainty.py                   ← belief state & particle filters
  ├── validators.py                    ← rule conformance and state validation checks
  ├── simulators/                      ← Monte Carlo combat & exploration engines
  └── eclipse_test/                    ← CLI harnesses, fixtures, and report renderer
```

## Using the planner

```python
from eclipse_ai import recommend

result = recommend(
    board_image_path="board.jpg",      # or None if providing prior state
    tech_image_path="tech.jpg",
    prior_state=None,                   # optional cached GameState
    manual_inputs={                     # optional overrides (state + planner knobs)
        "players.you.resources.money": 12,
        "_planner": {"simulations": 800, "depth": 3, "risk_aversion": 0.3},
    },
    top_k=3,
)

for plan in result["plans"]:
    print(plan["score"], plan["risk"], plan["steps"])
```

`recommend` automatically calibrates photos, parses board/tech state, applies manual overrides, updates opponent beliefs, runs MCTS, and returns JSON-serializable structures ready for UIs or reporting.【F:eclipse_ai/main.py†L32-L114】 The helper functions in `overlay.py` can turn each plan into vector annotations for an AR overlay or web front-end.【F:eclipse_ai/overlay.py†L1-L185】

## Optional dependencies

The package is designed to degrade gracefully when computer-vision libraries are absent. If you install the following extras, more automation becomes available:

* **OpenCV + NumPy** – Required for token detection, image rectification, and computer vision-assisted tech parsing.【F:eclipse_ai/board_parser.py†L1-L176】【F:eclipse_ai/image_ingestion.py†L1-L218】
* **Pillow** – Used for EXIF-aware image loading when OpenCV is available.【F:eclipse_ai/image_ingestion.py†L1-L218】
* **pytesseract** – Enables OCR of the tech display when sidecar data is missing.【F:eclipse_ai/tech_parser.py†L1-L121】

Without these packages the system falls back to sidecar JSON or demo data, ensuring the rest of the pipeline (state assembly, action generation, planning, and visualization) remains testable.

## Extending the toolkit

* Add richer rule handling or faction-specific logic by extending `rules_engine` and the dataclasses in `game_models`.【F:eclipse_ai/rules_engine.py†L1-L206】【F:eclipse_ai/game_models.py†L1-L168】
* Plug in alternative evaluation heuristics by modifying or augmenting `evaluator`—for example, add economic simulators or alliance modeling.【F:eclipse_ai/evaluator.py†L1-L236】
* Persist and hydrate belief state particles via `BeliefState.to_dict()` / `from_dict()` to maintain continuity across turns.【F:eclipse_ai/uncertainty.py†L151-L232】
* The MCTS planner accepts configuration overrides (simulation count, depth, risk aversion) through the `_planner` manual input to experiment with different planning tempos.【F:eclipse_ai/main.py†L83-L103】【F:eclipse_ai/search_policy.py†L1-L217】

## License

This repository is provided for experimentation with Eclipse strategy aids. No explicit license has been declared; treat the contents as proprietary unless you have permission from the maintainers.
