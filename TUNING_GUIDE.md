# Eclipse AI Tuning Guide

This guide explains how to customize and improve Eclipse AI's decision-making for your specific needs.

## Table of Contents
1. [Quick Improvements](#quick-improvements)
2. [Strategy Profiles](#strategy-profiles)
3. [Parameter Tuning](#parameter-tuning)
4. [Custom Weights](#custom-weights)
5. [Advanced Configuration](#advanced-configuration)

---

## Quick Improvements

### Better Decisions in 30 Seconds

The fastest way to improve AI performance is to increase computation:

```python
from eclipse_ai import recommend

result = recommend(
    board_path,
    tech_path,
    manual_inputs={
        "_planner": {
            "simulations": 1000,  # Default: 600. More = better (but slower)
            "depth": 4,           # Default: 3. Look further ahead
        }
    }
)
```

**Performance guide:**
- **Fast (< 5s)**: `simulations=300, depth=2`
- **Balanced (10-15s)**: `simulations=600, depth=3` (default)
- **High Quality (30-60s)**: `simulations=1000, depth=4`
- **Maximum (2-5min)**: `simulations=2000, depth=5`

---

## Strategy Profiles

Strategy profiles let you bias the AI toward specific playstyles without manual tuning.

### Available Profiles

```python
from eclipse_ai.value import list_profiles, print_profile_summary

# See all available profiles
list_profiles()

# Get details about a specific profile
print_profile_summary("aggressive")
```

**Built-in profiles:**

| Profile | Best For | Key Characteristics |
|---------|----------|---------------------|
| `balanced` | Default | No biases, uses base weights |
| `aggressive` | Military species, high-conflict games | Prioritizes fleet strength and combat |
| `economic` | Peaceful games, long games | Maximizes resources and planets |
| `tech_rush` | Tech-focused species | Rapid technology acquisition |
| `defensive` | Surrounded positions, early safety | Starbases and secure borders |
| `expansion` | Early game, exploration bonuses | Rapid territorial growth |
| `late_game` | Rounds 7+, closing victories | VP maximization |
| `turtle` | Difficult positions, rebuilding | Extreme defense, minimal expansion |

### Using Profiles

**In Python:**

```python
from eclipse_ai import recommend

# Use aggressive profile
result = recommend(
    board_path,
    tech_path,
    manual_inputs={"_profile": "aggressive"}
)
```

**Via CLI:**

```bash
python -m eclipse_ai.main \
    --board board.jpg \
    --tech tech.jpg \
    --manual '{"_profile": "aggressive"}' \
    --sims 1000
```

**Set globally:**

```python
from eclipse_ai import evaluator

# Set for all subsequent evaluations
evaluator.set_evaluation_profile("aggressive")

# Later, reset to default
evaluator.set_evaluation_profile(None)
```

---

## Parameter Tuning

### Progressive Widening MCTS Parameters

The PW-MCTS planner has three key parameters:

```python
result = recommend(
    board_path,
    tech_path,
    pw_alpha=0.65,      # Exploration rate (0.5-0.8)
    pw_c=1.8,           # Action diversity (1.0-2.5)
    prior_scale=0.6,    # Heuristic trust (0.3-1.0)
)
```

**Parameter Effects:**

1. **`pw_alpha` (Exploration Rate)**
   - Controls how quickly the search explores new actions
   - Lower (0.5): More focused, exploits good actions faster
   - Higher (0.75): More exploratory, considers more options
   - **Default: 0.65** (balanced)

2. **`pw_c` (Action Diversity)**
   - Controls how many different actions to consider
   - Lower (1.0): Narrow search, faster convergence
   - Higher (2.5): Wider search, more creative solutions
   - **Default: 1.8** (good diversity)

3. **`prior_scale` (Heuristic Trust)**
   - How much to trust evaluation heuristics vs learned values
   - Lower (0.3): Trust search tree more, heuristics less
   - Higher (1.0): Trust heuristics more, useful when search is limited
   - **Default: 0.6** (balanced trust)

### Recommended Configurations

**For Aggressive Play:**
```python
pw_alpha=0.60,      # Focus on strong actions
pw_c=1.5,           # Fewer but better options
prior_scale=0.65    # Trust combat heuristics
```

**For Complex Positions:**
```python
pw_alpha=0.70,      # Explore more options
pw_c=2.0,           # Maximum diversity
prior_scale=0.55    # Let search find subtle moves
```

**For Fast Decisions:**
```python
pw_alpha=0.60,      # Quick convergence
pw_c=1.3,           # Narrow search
prior_scale=0.70,   # Trust heuristics heavily
simulations=300     # Fewer iterations
```

---

## Custom Weights

You can create custom evaluation weights by modifying `eclipse_ai/value/weights.yaml` or providing overrides.

### Understanding Weights

Weights determine how much the AI values each game state feature:

```yaml
# Higher = more valuable
science_income: 0.25    # Science generation is important
fleet_power: 0.08       # Fleet strength matters

# Negative = penalty
threat_ratio: -0.30     # Being outnumbered is bad
contested_hexes: -0.15  # Conflict is risky
```

### Custom Weight Overrides

```python
custom_weights = {
    # Boost specific features
    "pink_planets": 0.80,       # vs 0.45 default (want science planets!)
    "wormhole_generator": 1.0,  # vs 0.60 default (critical for strategy)
    
    # Reduce others
    "fleet_dreadnoughts": 0.40, # vs 0.60 default (less military focus)
    "contested_hexes": -0.05,   # vs -0.15 default (less risk-averse)
}

# Apply via manual_inputs
result = recommend(
    board_path,
    tech_path,
    manual_inputs={"_weights": custom_weights}
)
```

### Weight Categories

**VP & Scoring** (Direct value):
- `vp_now`: Current victory points
- `reputation_tiles`, `discoveries`, `monoliths`: VP sources
- Typical range: 0.5-2.0

**Economy** (Resource generation):
- `science_income`, `materials_income`, `money_income`: Per-turn resources
- `orange_net_income`: Action economy
- Typical range: 0.15-0.40

**Military** (Combat capability):
- `fleet_power`: Overall strength
- `fleet_dreadnoughts`, `cruisers`, `interceptors`: Ship counts
- `[ship]_firepower`, `[ship]_defense`: Design quality
- Typical range: 0.05-0.80

**Territory** (Map control):
- `controlled_hexes`, `colonized_planets`: Territorial presence
- `planet_diversity`: Balanced economy
- Typical range: 0.20-0.60

**Threats** (Risk assessment):
- `danger_max`, `threat_ratio`: Enemy pressure
- `contested_hexes`: Conflict zones
- Typical range: -0.50 to 0.0 (usually negative)

---

## Advanced Configuration

### Per-Action Tuning

You can customize how specific actions are evaluated:

```python
manual_inputs = {
    # Exploration settings
    "exploration": {
        "risk_tolerance": 0.3,      # How much risk to accept (0-1)
        "ancient_combat_boost": 1.2, # Multiplier when can fight ancients
    },
    
    # Research priorities
    "research": {
        "early_game_econ_boost": 1.5,  # Economy tech value rounds 1-3
        "late_game_military_boost": 1.3, # Military tech value rounds 7+
    },
    
    # Combat evaluation
    "combat": {
        "win_probability_threshold": 0.60,  # Minimum for "good" attack
        "simulation_count": 100,            # Combat Monte Carlo samples
    }
}

result = recommend(board_path, tech_path, manual_inputs=manual_inputs)
```

### Context-Aware Evaluation

The evaluator automatically adjusts to game context, but you can influence it:

```python
from eclipse_ai import recommend
from eclipse_ai.context import Context

# Create custom context
context = Context(
    round_index=5,              # Current round
    aggressive_opponents=True,   # Enemy behavior
)

# The evaluator will:
# - Value defensive tech more (aggressive opponents)
# - Consider remaining game length (round 5/9)
# - Adjust risk tolerance accordingly
```

### Debugging Decisions

To understand why the AI chose a specific action:

```python
result = recommend(board_path, tech_path, top_k=10)

# Examine top plans
for i, plan in enumerate(result["plans"][:5]):
    print(f"\nPlan {i+1}:")
    for step in plan["steps"]:
        action = step["action"]
        details = step.get("details", {})
        print(f"  {action}: score={step['score']:.2f}, risk={step['risk']:.2f}")
        print(f"    Details: {details}")
```

### Species-Specific Tuning

For species with unique abilities:

```python
# Example: Eridani Empire (focuses on ancient technology)
eridani_weights = {
    "discoveries": 1.8,         # vs 1.2 default (ancient sites valuable)
    "monoliths": 2.2,           # vs 1.5 default (ancient monoliths)
    "tech_count": 0.30,         # vs 0.20 default (benefit from ancient tech)
    "fleet_power": 0.10,        # vs 0.08 default (need to fight guardians)
}

result = recommend(
    board_path,
    tech_path,
    manual_inputs={"_weights": eridani_weights}
)
```

---

## Troubleshooting

### AI Makes Overly Aggressive Moves

**Solution 1:** Increase defensive weights
```python
manual_inputs = {"_weights": {
    "threat_ratio": -0.50,      # vs -0.30 default
    "contested_hexes": -0.30,   # vs -0.15 default
    "fleet_starbases": 0.60,    # vs 0.40 default
}}
```

**Solution 2:** Use defensive profile
```python
manual_inputs = {"_profile": "defensive"}
```

### AI Ignores Economy

**Solution:** Boost economic weights
```python
manual_inputs = {"_weights": {
    "science_income": 0.40,     # vs 0.25 default
    "orange_net_income": 0.35,  # vs 0.22 default
    "colonized_planets": 0.60,  # vs 0.40 default
}}
```

**Or use economic profile:**
```python
manual_inputs = {"_profile": "economic"}
```

### AI Too Passive

**Solution:** Use aggressive profile or boost military
```python
manual_inputs = {
    "_profile": "aggressive",
    "_weights": {
        "fleet_power": 0.15,      # vs 0.08 default
        "contested_hexes": 0.10,  # vs -0.15 default (positive = seek it)
    }
}
```

### Slow Performance

**Solutions:**
1. Reduce simulations: `"simulations": 300` (vs 600 default)
2. Reduce depth: `"depth": 2` (vs 3 default)
3. Tighten progressive widening: `pw_c=1.3` (vs 1.8 default)

---

## Examples

### Complete Example: Tech-Focused Hydran

```python
from eclipse_ai import recommend

# Hydran Progress benefits from technology diversity
hydran_config = {
    "_profile": "tech_rush",
    "_weights": {
        "tech_count": 0.50,         # Even higher than tech_rush default
        "pink_planets": 0.85,       # Science planets crucial
        "science_income": 0.50,     # Maximum science generation
        "tech_diversity": 0.40,     # Want different categories
    },
    "_planner": {
        "simulations": 800,         # High quality for tech decisions
        "depth": 4,                 # Long-term planning
    }
}

result = recommend(
    "board.jpg",
    "tech.jpg",
    manual_inputs=hydran_config,
    pw_alpha=0.68,    # Explore tech options thoroughly
    pw_c=2.0,         # Consider many research paths
)

# Print recommendations
for i, plan in enumerate(result["plans"][:3], 1):
    print(f"\nOption {i}:")
    for step in plan["steps"]:
        print(f"  {step['action']}: {step['payload']}")
```

### Complete Example: Aggressive Orion

```python
# Orion Hegemony excels at combat
orion_config = {
    "_profile": "aggressive",
    "_weights": {
        "fleet_dreadnoughts": 1.0,   # Maximum dread value
        "dreadnought_firepower": 0.50, # Upgraded dreads
        "threat_ratio": -0.15,       # Not very risk-averse
        "contested_hexes": 0.15,     # Seek combat
        "reputation_tiles": 1.2,     # VP from victories
    },
    "_planner": {
        "simulations": 600,
        "depth": 3,
    }
}

result = recommend(
    "board.jpg",
    "tech.jpg",
    manual_inputs=orion_config,
    pw_alpha=0.62,    # Focus on strong military actions
    pw_c=1.6,         # Moderate diversity
    prior_scale=0.70, # Trust combat heuristics
)
```

---

## Further Reading

- `eclipse_ai/value/weights.yaml` - Base weight definitions
- `eclipse_ai/value/profiles.yaml` - Strategy profile configurations
- `eclipse_ai/value/features.py` - Feature extraction details
- `eclipse_ai/evaluator.py` - Action-specific heuristics

For questions or custom configurations, consult the source code or create custom profiles.

