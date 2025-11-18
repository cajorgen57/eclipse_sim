#!/usr/bin/env python3
"""Test script to verify board renderer integration with new coordinate system."""

import json
from eclipse_ai.game_setup import new_game

# Create a test game with the new coordinate system
state = new_game(num_players=2, species_by_player={'P1': 'terrans', 'P2': 'orion'})

# Extract the map state
map_data = {
    "hexes": {}
}

for hex_id, hex_obj in state.map.hexes.items():
    hex_dict = {
        "id": hex_id,
        "ring": hex_obj.ring,
        "axial_q": hex_obj.axial_q,
        "axial_r": hex_obj.axial_r,
        "rotation": getattr(hex_obj, 'rotation', 0),
        "wormholes": list(hex_obj.wormholes) if hasattr(hex_obj, 'wormholes') else [],
        "explored": getattr(hex_obj, 'explored', True),
        "revealed": getattr(hex_obj, 'revealed', True),
        "has_gcds": getattr(hex_obj, 'has_gcds', False),
        "ancients": getattr(hex_obj, 'ancients', 0),
        "discovery_tile": getattr(hex_obj, 'discovery_tile', None),
    }
    
    # Add pieces if present
    if hex_obj.pieces:
        for player_id, pieces in hex_obj.pieces.items():
            if not "controlled_by" in hex_dict and pieces.discs > 0:
                hex_dict["controlled_by"] = player_id
            
            if pieces.ships:
                hex_dict["ships"] = pieces.ships
            
            if pieces.discs > 0:
                hex_dict["influence_discs"] = pieces.discs
    
    # Add planets if present
    if hex_obj.planets:
        hex_dict["planets"] = []
        for planet in hex_obj.planets:
            hex_dict["planets"].append({
                "type": planet.type,
                "colonized_by": planet.colonized_by,
            })
    
    map_data["hexes"][hex_id] = hex_dict

# Create a minimal game state for testing
test_state = {
    "round": 1,
    "active_player": "P1",
    "phase": "ACTION",
    "map": map_data,
}

# Save to a JSON file for testing
output_path = "eclipse_ai/gui/saved_states/test_coordinate_integration.json"
with open(output_path, 'w') as f:
    json.dump(test_state, f, indent=2)

print("✅ Test state saved to:", output_path)
print(f"\n📊 State summary:")
print(f"   Hexes created: {len(map_data['hexes'])}")
print(f"\n🔍 Hex details:")
for hex_id, hex_data in sorted(map_data['hexes'].items()):
    coords = f"({hex_data['axial_q']}, {hex_data['axial_r']})"
    wormholes = hex_data.get('wormholes', [])
    print(f"   {hex_id}: {coords} ring={hex_data['ring']} wormholes={wormholes}")

print(f"\n✨ All hexes have axial_q and axial_r fields!")
print(f"   The board renderer will now use these coordinates directly.")
print(f"\n🎮 To test in GUI:")
print(f"   1. Start the GUI: ./start_gui.sh")
print(f"   2. Load state: test_coordinate_integration.json")
print(f"   3. Hover over hexes to see coordinate tooltips")
print(f"   4. Verify hexes render at correct positions")

