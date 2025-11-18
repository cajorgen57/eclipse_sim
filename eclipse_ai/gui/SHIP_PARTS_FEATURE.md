# Ship Parts Display Feature

## Summary
The player board now displays individual ship parts on ship blueprints, not just aggregate stats.

## Implementation Details

### Files Modified
- `eclipse_ai/gui/static/js/player-panel.js`
  - Updated `createEnhancedShipBlueprint()` method to include ship parts section
  - Added new `renderShipParts()` method to display detailed parts breakdown

### How It Works

The `renderShipParts()` method checks for the following part categories in ship designs:
- **cannon_parts**: Ion Cannon, Plasma Cannon, etc.
- **missile_parts**: Plasma Missile, etc.
- **computer_parts**: Electron Computer, Positron Computer, etc.
- **shield_parts**: Gauss Shield, Phase Shield, etc.
- **drive_parts**: Nuclear Drive, Fusion Drive, Antimatter Drive, etc.
- **energy_sources**: Nuclear Source, Fusion Source, etc.
- **hull_parts**: Hull, Improved Hull, etc.

### Display Format

When ship parts data is available, they are displayed below the stats grid:

```
🔧 Installed Parts
💥 Ion Cannon ×2, Plasma Cannon
🎯 Electron Computer
🛡 Gauss Shield
🔧 Nuclear Drive
⚡ Nuclear Source
❤️ Hull ×2
```

### Backward Compatibility

The feature is **fully backward compatible**:
- If ship designs only have aggregate stats (current state), the parts section is hidden
- If ship designs include detailed parts data, they are displayed
- No breaking changes to existing functionality

### Example Ship Design Data

**With detailed parts** (new format):
```json
{
  "initiative": 3,
  "hull": 2,
  "computer": 1,
  "cannons": 2,
  "cannon_parts": {
    "Ion Cannon": 2
  },
  "computer_parts": {
    "Electron Computer": 1
  },
  "drive_parts": {
    "Nuclear Drive": 1
  },
  "energy_sources": {
    "Nuclear Source": 1
  },
  "hull_parts": {
    "Hull": 2
  }
}
```

**Without detailed parts** (current format):
```json
{
  "initiative": 3,
  "hull": 2,
  "computer": 1,
  "cannons": 2
}
```

Both formats work correctly - the second one simply won't show the "Installed Parts" section.

## Future Enhancements

To populate ship parts data, you can:

1. **Update initial ship designs** in `eclipse_ai/game_setup.py` to include default parts
2. **Track parts in upgrade actions** in `eclipse_ai/action_gen/upgrade.py`
3. **Serialize parts data** when saving/loading game states

## Testing

To test the feature:
1. Start the GUI: `./start_gui.sh` or `python -m eclipse_ai.gui.run`
2. Load a state with ship designs
3. View the player panel - ship blueprints will show:
   - Stats badges (as before)
   - **New**: Installed parts section (when data is available)
   - Special features (Jump Drive, Bays) (as before)

## Visual Style

The parts are displayed with:
- Color-coded icons matching the stat badges
- Compact text format with counts (×N for multiple)
- Separated by category for easy reading
- Clean border separation from stats above

