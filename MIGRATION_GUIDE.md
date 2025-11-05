# Migration Guide: Legacy Planner Deprecation

This guide explains how to migrate from the deprecated `MCTSPlanner` to the new `PW_MCTSPlanner`.

## Overview

The legacy `MCTSPlanner` has been deprecated in favor of `PW_MCTSPlanner`, which provides:
- **Progressive widening** for better exploration of the action space
- **Opponent awareness** capabilities for more strategic play
- **Improved evaluation** with feature-based scoring
- **Better diagnostics** for understanding plan decisions

## Timeline

- **Now**: Legacy planner is deprecated but still functional (with warnings)
- **Future**: Legacy planner will be removed in a future major version

## Quick Migration

### Command Line Interface

**Before:**
```bash
python -m eclipse_ai.main --board board.jpg --tech tech.jpg --planner legacy
```

**After:**
```bash
python -m eclipse_ai.main --board board.jpg --tech tech.jpg --planner pw_mcts
```

Or simply omit `--planner` (default is now `pw_mcts`):
```bash
python -m eclipse_ai.main --board board.jpg --tech tech.jpg
```

### Programmatic API

**Before:**
```python
from eclipse_ai import recommend

plans = recommend(
    board_image_path="board.jpg",
    tech_image_path="tech.jpg",
    planner="legacy",
    top_k=5
)
```

**After:**
```python
from eclipse_ai import recommend

plans = recommend(
    board_image_path="board.jpg",
    tech_image_path="tech.jpg",
    planner="pw_mcts",  # or omit (default)
    top_k=5,
    pw_alpha=0.6,      # Progressive widening alpha
    pw_c=1.5,          # Progressive widening constant
    prior_scale=0.5,   # Prior scale factor
    seed=0             # Random seed
)
```

### Direct Planner Usage

**Before:**
```python
from eclipse_ai.search_policy import MCTSPlanner

planner = MCTSPlanner(
    simulations=400,
    risk_aversion=0.25
)
plans = planner.plan(state, player_id, depth=2, top_k=5)
```

**After:**
```python
from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner

planner = PW_MCTSPlanner(
    sims=400,
    depth=2,
    pw_alpha=0.6,
    pw_c=1.5,
    prior_scale=0.5,
    seed=0
)
ranked = planner.plan(state)
```

## Parameter Mapping

| Legacy MCTSPlanner | PW_MCTSPlanner | Notes |
|-------------------|----------------|-------|
| `simulations=400` | `sims=400` | Same meaning |
| `risk_aversion=0.25` | N/A | Risk handled via priors |
| `depth=2` | `depth=2` | Same meaning |
| `c_puct=1.4` | `pw_c=1.5` | Similar exploration constant |
| `dirichlet_alpha=0.3` | `pw_alpha=0.6` | Progressive widening parameter |
| N/A | `prior_scale=0.5` | New: scales prior probabilities |
| `seed=None` | `seed=0` | Explicit seed support |

## Advanced Features

### Opponent Awareness

PW_MCTSPlanner supports opponent-aware planning:

```python
from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner

planner = PW_MCTSPlanner(sims=400, depth=2, seed=0)
planner.opponent_awareness = True  # Enable opponent modeling
ranked = planner.plan(state)
```

### Diagnostics

Get detailed diagnostics about the planning process:

```python
ranked, diagnostics = planner.plan_with_diagnostics(state)

# diagnostics contains:
# - children: stats for each action considered
# - params: planner parameters used
# - sims: number of simulations run
```

## CLI Migration

### Using eclipse_ai.cli

**Before:**
```bash
python -m eclipse_ai.cli plan --board board.jpg --tech tech.jpg --planner legacy
```

**After:**
```bash
python -m eclipse_ai.cli plan --board board.jpg --tech tech.jpg --planner pw_mcts
```

Or with additional PW-MCTS parameters:
```bash
python -m eclipse_ai.cli plan \
    --board board.jpg \
    --tech tech.jpg \
    --planner pw_mcts \
    --pw-alpha 0.6 \
    --pw-c 1.5 \
    --prior-scale 0.5 \
    --opponent-awareness
```

## Troubleshooting

### Deprecation Warnings

If you see deprecation warnings, you're still using the legacy planner. Update your code to use `pw_mcts`:

```
DeprecationWarning: MCTSPlanner is deprecated. Use PW_MCTSPlanner from eclipse_ai.planners.mcts_pw instead.
```

### Different Results

PW_MCTSPlanner uses a different algorithm, so results may differ:
- **Progressive widening** explores more actions initially
- **Feature-based evaluation** may score actions differently
- Use `--seed` for reproducible results

### Performance

PW_MCTSPlanner may be slightly slower due to:
- More sophisticated evaluation
- Opponent modeling (if enabled)
- Progressive widening overhead

Adjust `--sims` if needed for your use case.

## Backward Compatibility

The legacy planner is still available for now:
- Pass `--planner legacy` explicitly
- Import `MCTSPlanner` from `eclipse_ai.search_policy`
- Expect deprecation warnings

This will be removed in a future major version.

## Questions?

See the main [README.md](README.md) or [Agents.md](Agents.md) for more details.

