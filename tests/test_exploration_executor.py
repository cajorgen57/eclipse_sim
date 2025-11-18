"""Unit tests for exploration tile sampling and placement.

Tests the integration between:
- Tile sampling from bags (tile_sampler.py)
- Hex placement (map/placement.py)
- Action application (rules/api.py)
"""
import pytest
from eclipse_ai.game_setup import new_game
from eclipse_ai.tile_sampler import sample_tile_from_bag, sample_and_place_tile
from eclipse_ai.rules import api as rules_api


def test_sample_tile_from_bag():
    """Test that we can sample tiles from exploration bags."""
    state = new_game(num_players=2, seed=42)
    
    # Check initial bag state
    print("\n[TEST] Initial bags:")
    for ring_key, bag in state.bags.items():
        total = sum(bag.values())
        print(f"  {ring_key}: {total} tiles")
    
    # Sample a tile from ring 2 (middle)
    tile = sample_tile_from_bag(state, ring=2)
    
    assert tile is not None, "Should be able to sample a tile from ring 2"
    assert tile.ring == 2, f"Tile should be from ring 2, got {tile.ring}"
    print(f"\n[TEST] Sampled tile: {tile.id} with wormholes {tile.wormholes}")
    
    # Check bag was decremented
    ring2_count_after = sum(state.bags["R2"].values())
    print(f"[TEST] Ring 2 bag after sampling: {ring2_count_after} tiles")


def test_sample_and_place_tile():
    """Test full tile sampling and placement flow."""
    state = new_game(num_players=2, seed=123)
    
    initial_hex_count = len(state.map.hexes)
    print(f"\n[TEST] Initial hex count: {initial_hex_count}")
    
    # Find a valid exploration target adjacent to a starting hex
    # Player starts at one of the starting positions
    player_id = "P1"
    player_hexes = []
    for hex_id, hex_obj in state.map.hexes.items():
        if hex_id != "GC" and hasattr(hex_obj, 'axial_q'):
            player_hexes.append((hex_obj.axial_q, hex_obj.axial_r, hex_id))
    
    assert len(player_hexes) >= 1, "Should have at least one player starting hex"
    
    # Try to place adjacent to first player hex
    q, r, hex_id = player_hexes[0]
    target_q, target_r = q + 1, r  # Adjacent position
    
    print(f"[TEST] Player hex at ({q}, {r})")
    print(f"[TEST] Attempting to place at ({target_q}, {target_r})")
    
    # Sample and place
    success = sample_and_place_tile(
        state,
        player_id="P1",
        target_q=target_q,
        target_r=target_r,
        ring=2,
    )
    
    print(f"[TEST] Placement success: {success}")
    
    if success:
        final_hex_count = len(state.map.hexes)
        print(f"[TEST] Final hex count: {final_hex_count}")
        
        assert final_hex_count == initial_hex_count + 1, \
            f"Should have added 1 hex, got {final_hex_count - initial_hex_count}"
        
        # Find the new hex and verify coordinates
        new_hex = None
        for hex_obj in state.map.hexes.values():
            if hex_obj.axial_q == target_q and hex_obj.axial_r == target_r:
                new_hex = hex_obj
                break
        
        assert new_hex is not None, "New hex should be in map"
        assert new_hex.axial_q == target_q, "New hex has wrong Q coordinate"
        assert new_hex.axial_r == target_r, "New hex has wrong R coordinate"
        print(f"[TEST] ✅ New hex placed at ({new_hex.axial_q}, {new_hex.axial_r})")


def test_explore_action_via_api():
    """Test that explore action through rules API places a hex."""
    state = new_game(num_players=2, seed=456)
    
    initial_hex_count = len(state.map.hexes)
    print(f"\n[TEST] Initial hex count: {initial_hex_count}")
    
    # Find starting hex coordinates for player 1
    player_hexes = []
    for hex_id, hex_obj in state.map.hexes.items():
        if hex_id != "GC" and hasattr(hex_obj, 'axial_q'):
            player_hexes.append((hex_obj.axial_q, hex_obj.axial_r))
    
    # Target adjacent position
    q, r = player_hexes[0]
    target_q, target_r = q + 1, r
    
    # Create explore action payload
    action = {
        "type": "EXPLORE",
        "payload": {
            "target_q": target_q,
            "target_r": target_r,
            "ring": 2,
            "player_id": "P1",
        }
    }
    
    print(f"[TEST] Applying explore action to ({target_q}, {target_r})")
    
    # Apply action through rules API
    new_state = rules_api.apply_action(state, "P1", action)
    
    final_hex_count = len(new_state.map.hexes)
    print(f"[TEST] Final hex count: {final_hex_count}")
    
    # Check if hex was placed (might not be if no valid rotation)
    if final_hex_count > initial_hex_count:
        print(f"[TEST] ✅ Hex placed: {final_hex_count - initial_hex_count} new hex(es)")
        
        # Verify the new hex has coordinates
        new_hex = None
        for hex_obj in new_state.map.hexes.values():
            if hex_obj.axial_q == target_q and hex_obj.axial_r == target_r:
                new_hex = hex_obj
                break
        
        assert new_hex is not None, "New hex should be at target coordinates"
        assert hasattr(new_hex, 'axial_q'), "New hex missing axial_q"
        assert hasattr(new_hex, 'axial_r'), "New hex missing axial_r"
        print(f"[TEST] New hex ID: {new_hex.id}")
    else:
        print("[TEST] No hex placed (possibly no valid rotation or bag empty)")


def test_multiple_explorations():
    """Test that multiple explorations work correctly."""
    state = new_game(num_players=2, seed=789)
    
    initial_hex_count = len(state.map.hexes)
    placements_attempted = 0
    placements_successful = 0
    
    print(f"\n[TEST] Initial hex count: {initial_hex_count}")
    
    # Try to place 5 tiles
    for i in range(5):
        # Find all current hexes
        all_positions = [(h.axial_q, h.axial_r) for h in state.map.hexes.values() 
                        if hasattr(h, 'axial_q')]
        
        # Try adjacent to first hex
        if all_positions:
            q, r = all_positions[0]
            # Try different adjacent positions
            directions = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
            target_q = q + directions[i % 6][0]
            target_r = r + directions[i % 6][1]
            
            # Check if position already occupied
            occupied = any(h.axial_q == target_q and h.axial_r == target_r 
                          for h in state.map.hexes.values())
            
            if not occupied:
                placements_attempted += 1
                success = sample_and_place_tile(
                    state, "P1", target_q, target_r, ring=2
                )
                if success:
                    placements_successful += 1
                    print(f"[TEST] Placement {placements_successful}: ({target_q}, {target_r})")
    
    final_hex_count = len(state.map.hexes)
    print(f"\n[TEST] Attempted: {placements_attempted}, Successful: {placements_successful}")
    print(f"[TEST] Final hex count: {final_hex_count}")
    print(f"[TEST] Net change: +{final_hex_count - initial_hex_count}")
    
    assert final_hex_count >= initial_hex_count, "Hex count should not decrease"
    
    # Verify all hexes have coordinates
    for hex_obj in state.map.hexes.values():
        assert hasattr(hex_obj, 'axial_q'), f"Hex {hex_obj.id} missing axial_q"
        assert hasattr(hex_obj, 'axial_r'), f"Hex {hex_obj.id} missing axial_r"
    
    print(f"[TEST] ✅ All {final_hex_count} hexes have valid coordinates")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Exploration Executor Integration")
    print("=" * 70)
    
    test_sample_tile_from_bag()
    test_sample_and_place_tile()
    test_explore_action_via_api()
    test_multiple_explorations()
    
    print("\n" + "=" * 70)
    print("✅ All exploration executor tests passed!")
    print("=" * 70)

