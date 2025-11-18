# Quick Start: Integrated Board System

## TL;DR

The backend and frontend are now fully integrated. Hexes have coordinates, the renderer reads them, everything works.

## Quick Test (30 seconds)

```bash
# 1. Run verification
./verify_integration.sh

# 2. Create test state
./venv/bin/python test_board_renderer_integration.py

# 3. Start GUI
./start_gui.sh

# 4. Load state: test_coordinate_integration.json
# 5. Hover over hexes - you'll see coordinates!
```

## For Developers

### Create a Game with Coordinates

```python
from eclipse_ai.game_setup import new_game

# All hexes automatically have axial_q, axial_r, rotation
state = new_game(num_players=2)

# Check a hex
gc = state.map.hexes["GC"]
print(f"Center at: ({gc.axial_q}, {gc.axial_r})")  # (0, 0)
```

### Generate Explore Actions

```python
from eclipse_ai.action_gen.explore import generate

actions = generate(state)
for action in actions:
    coords = action.payload["target_coords"]
    print(f"Can explore: {coords}")
```

### Validate the Board

```python
from eclipse_ai.map.validation import validate_all

results = validate_all(state)
print(f"Valid: {results['valid']}")
print(f"Errors: {results['geometry_errors']}")
```

## For Frontend

### Hex Data Structure

```json
{
  "id": "201",
  "axial_q": 2,
  "axial_r": 0,
  "ring": 2,
  "rotation": 0,
  "wormholes": [0, 3],
  "planets": [...],
  "ships": {...}
}
```

### Renderer Automatically Uses Coordinates

The renderer in `board-renderer.js` now:
1. Checks for `hexData.axial_q` and `hexData.axial_r`
2. Uses them for positioning
3. Falls back to hardcoded mapping if missing
4. Shows coordinates in hover tooltips

**No changes needed in your code!** Just serialize the game state and the renderer will display it correctly.

## Testing

### Run All Tests
```bash
pytest tests/test_hex_coordinates.py tests/test_tile_placement.py -v
```

### Quick Verification
```bash
./verify_integration.sh
```

## Files to Know

### Backend
- `eclipse_ai/map/coordinates.py` - Coordinate math
- `eclipse_ai/map/placement.py` - Tile placement logic
- `eclipse_ai/game_setup.py` - Creates games with coordinates

### Frontend
- `eclipse_ai/gui/static/js/board-renderer.js` - Reads coordinates from backend

### Tests
- `tests/test_hex_coordinates.py` - 20 coordinate tests
- `tests/test_tile_placement.py` - 14 placement tests

### Documentation
- `INTEGRATION_COMPLETE.md` - Full integration summary
- `BOARD_UPDATE_SUMMARY.md` - Backend details
- `RENDERER_INTEGRATION.md` - Frontend details

## Common Questions

**Q: Do I need to change my code?**  
A: No! If you use `new_game()` or `game_setup.py`, coordinates are automatic.

**Q: Will old saved states work?**  
A: Yes! The renderer falls back to hardcoded mapping.

**Q: How do I see coordinates?**  
A: Hover over any hex in the GUI.

**Q: How do I place a new hex?**  
A: Use `place_explored_tile()` from `placement.py`.

**Q: Do tests pass?**  
A: Yes! 34/34 tests passing.

## What's New

✅ Every hex has `axial_q`, `axial_r`, `rotation`  
✅ Renderer reads these from backend  
✅ Explore actions work with coordinates  
✅ Validation checks geometry  
✅ Tooltips show coordinates  
✅ 100% backwards compatible  

## Status

🎉 **PRODUCTION READY**

All systems tested and integrated. Ready to use!

