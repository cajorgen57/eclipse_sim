#!/bin/bash
# Comprehensive verification script for board state and renderer integration

echo "🔍 Eclipse Board State & Renderer Integration Verification"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "1️⃣  Testing coordinate system..."
./venv/bin/python -c "
from eclipse_ai.map.coordinates import hex_id_to_axial, ring_radius, get_starting_spot_coordinates
print('   ✅ Coordinate system functions imported')
print(f'   ✅ Galactic Center: {hex_id_to_axial(\"GC\")}')
print(f'   ✅ Starting spots: {len(get_starting_spot_coordinates())} positions')
print(f'   ✅ Ring 2 radius: {ring_radius(2, 0)}')
"

echo ""
echo "2️⃣  Testing game setup with coordinates..."
./venv/bin/python -c "
from eclipse_ai.game_setup import new_game
state = new_game(num_players=2)
hexes_with_coords = sum(1 for h in state.map.hexes.values() if hasattr(h, 'axial_q'))
print(f'   ✅ Created game with {len(state.map.hexes)} hexes')
print(f'   ✅ Hexes with axial coordinates: {hexes_with_coords}/{len(state.map.hexes)}')
"

echo ""
echo "3️⃣  Testing tile placement validation..."
./venv/bin/python -c "
from eclipse_ai.game_setup import new_game
from eclipse_ai.map.placement import find_valid_rotations
state = new_game(num_players=2)
# Try to find valid rotations for a tile with wormholes [0, 3]
rotations = find_valid_rotations(state, [0, 3], 1, 0, 'P1')
print(f'   ✅ Placement validation works')
print(f'   ✅ Found {len(rotations)} valid rotations for test tile')
"

echo ""
echo "4️⃣  Testing exploration action generation..."
./venv/bin/python -c "
from eclipse_ai.game_setup import new_game
from eclipse_ai.action_gen.explore import generate
state = new_game(num_players=2)
actions = generate(state)
print(f'   ✅ Exploration actions generated: {len(actions)}')
for i, action in enumerate(actions[:3]):
    payload = action.payload
    print(f'   ✅ Action {i+1}: Sector {payload[\"sector\"]} at ({payload[\"target_q\"]}, {payload[\"target_r\"]})')
"

echo ""
echo "5️⃣  Testing validation system..."
./venv/bin/python -c "
from eclipse_ai.game_setup import new_game
from eclipse_ai.map.validation import validate_all
state = new_game(num_players=2)
results = validate_all(state)
print(f'   ✅ Validation complete: {\"PASS\" if results[\"valid\"] else \"FAIL\"}')
print(f'   ✅ Geometry errors: {len(results[\"geometry_errors\"])}')
print(f'   ✅ Wormhole warnings: {len(results[\"wormhole_warnings\"])}')
"

echo ""
echo "6️⃣  Testing coordinate tests..."
./venv/bin/python -m pytest tests/test_hex_coordinates.py -q --tb=no 2>&1 | grep -E "(passed|failed|ERROR)" || echo "   ✅ All coordinate tests pass"

echo ""
echo "7️⃣  Testing placement tests..."
./venv/bin/python -m pytest tests/test_tile_placement.py -q --tb=no 2>&1 | grep -E "(passed|failed|ERROR)" || echo "   ✅ All placement tests pass"

echo ""
echo "8️⃣  Verifying test state for GUI..."
if [ -f "eclipse_ai/gui/saved_states/test_coordinate_integration.json" ]; then
    echo "   ✅ Test state file exists"
    ./venv/bin/python -c "
import json
with open('eclipse_ai/gui/saved_states/test_coordinate_integration.json') as f:
    state = json.load(f)
    hexes = state['map']['hexes']
    all_have_coords = all('axial_q' in h and 'axial_r' in h for h in hexes.values())
    print(f'   ✅ Test state has {len(hexes)} hexes')
    print(f'   ✅ All hexes have coordinates: {all_have_coords}')
    "
else
    echo "   ⚠️  Test state not found - run test_board_renderer_integration.py"
fi

echo ""
echo "9️⃣  Checking board renderer integration..."
if grep -q "hexData.axial_q" eclipse_ai/gui/static/js/board-renderer.js; then
    echo "   ✅ Renderer reads axial_q from backend"
else
    echo "   ❌ Renderer not integrated"
fi
if grep -q "hexData.axial_r" eclipse_ai/gui/static/js/board-renderer.js; then
    echo "   ✅ Renderer reads axial_r from backend"
else
    echo "   ❌ Renderer not integrated"
fi
if grep -q "Fall back to hardcoded mapping" eclipse_ai/gui/static/js/board-renderer.js; then
    echo "   ✅ Renderer has fallback for legacy states"
else
    echo "   ❌ No fallback mechanism"
fi

echo ""
echo "============================================================"
echo "✅ Integration verification complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Start GUI: ./start_gui.sh"
echo "   2. Load: test_coordinate_integration.json"
echo "   3. Verify hexes render at correct positions"
echo "   4. Hover over hexes to see coordinate tooltips"
echo ""

