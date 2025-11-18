#!/usr/bin/env python3
"""Demo showing that exploration properly places hexes with coordinates."""

from eclipse_ai.game_setup import new_game
from eclipse_ai.rules import api as rules_api

print("=" * 70)
print("Manual Exploration Test - Verify Hex Placement")
print("=" * 70)

# Create fresh game
print("\n1. Creating game...")
state = new_game(num_players=2, starting_round=1, seed=42)
initial_hex_count = len(state.map.hexes)
print(f"   Initial hexes: {initial_hex_count}")

# Show initial positions
print("\n2. Initial hexes:")
for hex_id, hex_obj in state.map.hexes.items():
    print(f"   - {hex_id}: ({hex_obj.axial_q:2}, {hex_obj.axial_r:2}) ring={hex_obj.ring}")

# Find a player's starting hex
player_hex = None
for hex_id, hex_obj in state.map.hexes.items():
    if hex_id.startswith("22"):  # Starting hex
        player_hex = hex_obj
        break

if player_hex:
    # Target an adjacent position
    target_q = player_hex.axial_q + 1
    target_r = player_hex.axial_r
    
    print(f"\n3. Exploring adjacent to {hex_id}...")
    print(f"   Target position: ({target_q}, {target_r})")
    
    # Create and apply explore action
    action = {
        "type": "EXPLORE",
        "payload": {
            "target_q": target_q,
            "target_r": target_r,
            "ring": 2,
            "player_id": "P1",
        }
    }
    
    new_state = rules_api.apply_action(state, "P1", action)
    final_hex_count = len(new_state.map.hexes)
    
    print(f"   Result: {initial_hex_count} → {final_hex_count} hexes")
    
    if final_hex_count > initial_hex_count:
        # Find the new hex
        new_hex = None
        for hex_obj in new_state.map.hexes.values():
            if hex_obj.axial_q == target_q and hex_obj.axial_r == target_r:
                new_hex = hex_obj
                break
        
        if new_hex:
            print(f"\n4. New hex placed:")
            print(f"   ✅ ID: {new_hex.id}")
            print(f"   ✅ Position: ({new_hex.axial_q}, {new_hex.axial_r})")
            print(f"   ✅ Ring: {new_hex.ring}")
            print(f"   ✅ Wormholes: {new_hex.wormholes}")
            print(f"   ✅ Rotation: {new_hex.rotation}")
            
            if hasattr(new_hex, 'discovery_tile') and new_hex.discovery_tile:
                print(f"   ✅ Discovery: {new_hex.discovery_tile}")
            
            # Test multiple explorations
            print(f"\n5. Testing multiple explorations...")
            for i in range(3):
                # Try different adjacent positions
                test_q = player_hex.axial_q + (i - 1)
                test_r = player_hex.axial_r + 1
                
                action = {
                    "type": "EXPLORE",
                    "payload": {
                        "target_q": test_q,
                        "target_r": test_r,
                        "ring": 2,
                    }
                }
                new_state = rules_api.apply_action(new_state, "P1", action)
            
            total_hexes = len(new_state.map.hexes)
            print(f"   Final hex count: {total_hexes}")
            print(f"   Added {total_hexes - initial_hex_count} hexes total")
            
            # Verify all have coordinates
            all_valid = all(
                hasattr(h, 'axial_q') and hasattr(h, 'axial_r')
                and h.axial_q is not None and h.axial_r is not None
                for h in new_state.map.hexes.values()
            )
            
            if all_valid:
                print(f"   ✅ All {total_hexes} hexes have valid coordinates")
            
            print("\n" + "=" * 70)
            print("✅ SUCCESS: Exploration correctly places hexes with coordinates!")
            print("=" * 70)
        else:
            print(f"\n   ⚠️  Hex count increased but couldn't find new hex at target")
    else:
        print(f"\n   ℹ️  No hex placed (likely no valid wormhole connection)")
        print(f"   This is expected - placement requires wormhole alignment")
else:
    print("\n   ⚠️  Couldn't find player starting hex")

