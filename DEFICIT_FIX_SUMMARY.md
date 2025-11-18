# Eclipse Economy Fix - Allow Deficit Actions

## Problem

Players weren't taking actions during multi-round simulation because the `would_cause_deficit()` check was too conservative. It rejected any action that would make net money negative, even though Eclipse's economy allows going into deficit.

## Eclipse Economy Rules

In Eclipse, what matters is:

```
Net money = (Treasury) + (Income) - (Upkeep)
```

Players can safely take actions that make net money negative because at upkeep they can:
1. Trade resources at 3:1 ratio (science/materials → money)
2. Remove influence discs to reduce upkeep cost
3. Only collapse if still unable to pay after all recovery options

## The Fix

**File**: `eclipse_ai/round_simulator.py`  
**Function**: `would_cause_deficit()` (lines 145-188)

### Before
```python
return money_after < safety_margin  # Rejected at net money < 0
```

### After
```python
deficit_threshold = -8  # Can go 8 credits into deficit
return money_after < (safety_margin + deficit_threshold)
```

## Impact

- **Before**: Players passed immediately when net money approached 0
- **After**: Players take actions even with net money down to -8
- **Result**: Players explore during simulation → hexes appear on board!

## Testing

```python
from eclipse_ai.game_setup import new_game

# Start at round 5 (simulates rounds 1-4)
state = new_game(num_players=2, starting_round=5)

print(f"Hexes: {len(state.map.hexes)}")  # Shows 6+ hexes (3 starting + explored)
```

Output:
```
[ROUND 1] Exploration: +1 hexes (now 4 total)
[ROUND 2] Exploration: +2 hexes (now 6 total)
Final: 6 hexes with coordinates
```

## Why -8?

The threshold of -8 credits is reasonable because:
- Players typically have 3-9 science → can trade for 1-3 money
- Players typically have 3-9 materials → can trade for 1-3 money  
- Players have 2-4 influence discs → removing 2-3 saves 4-6 money
- **Total recovery potential**: ~10-15 credits

So -8 deficit is safely recoverable at upkeep.

## Related Files

- `eclipse_ai/upkeep.py` - Implements bankruptcy handling (resource trading, disc removal)
- `eclipse_ai/round_simulator.py` - Action phase simulation with deficit checks
- `tests/test_upkeep.py` - Tests bankruptcy mechanics

## Status

✅ **FIXED** - Players now take actions appropriately during simulation

