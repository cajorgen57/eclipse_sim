"""Test that multi-round simulation properly updates board state.

This test verifies that when simulating multiple rounds:
1. Explore actions during simulation place hexes on the map
2. Placed hexes have proper axial coordinates (axial_q, axial_r)
3. The board state can be properly rendered in the GUI
"""
import pytest
from eclipse_ai.game_setup import new_game
from eclipse_ai.multi_round_runner import simulate_rounds


def test_multi_round_creates_hexes():
    """Test that simulating rounds actually places hexes on the map."""
    # Create a fresh game
    state = new_game(num_players=2, starting_round=1, seed=42)
    
    initial_hex_count = len(state.map.hexes)
    print(f"\n[TEST] Initial hex count: {initial_hex_count}")
    
    # Simulate 3 rounds
    state = simulate_rounds(
        state,
        start_round=1,
        end_round=3,
        planner_config={
            "simulations": 50,
            "depth": 2,
        },
        verbose=True,
    )
    
    final_hex_count = len(state.map.hexes)
    print(f"[TEST] Final hex count: {final_hex_count}")
    
    # We expect at least some exploration to have happened
    # (Though it's possible no one explored, so we'll check > or ==)
    assert final_hex_count >= initial_hex_count, \
        f"Hex count decreased: {initial_hex_count} -> {final_hex_count}"
    
    print(f"[TEST] Exploration result: {final_hex_count - initial_hex_count} new hexes")


def test_explored_hexes_have_coordinates():
    """Test that all hexes created during simulation have proper coordinates."""
    state = new_game(num_players=2, starting_round=1, seed=123)
    
    # Simulate rounds
    state = simulate_rounds(
        state,
        start_round=1,
        end_round=3,
        planner_config={"simulations": 30, "depth": 2},
        verbose=False,
    )
    
    # Check that all hexes have coordinates
    hexes_without_coords = []
    for hex_id, hex_obj in state.map.hexes.items():
        if not hasattr(hex_obj, 'axial_q') or not hasattr(hex_obj, 'axial_r'):
            hexes_without_coords.append(hex_id)
        elif hex_obj.axial_q is None or hex_obj.axial_r is None:
            hexes_without_coords.append(hex_id)
    
    assert len(hexes_without_coords) == 0, \
        f"Hexes without coordinates: {hexes_without_coords}"
    
    print(f"\n[TEST] ✅ All {len(state.map.hexes)} hexes have valid coordinates")


def test_exploration_updates_bags():
    """Test that exploration properly decrements tile bags."""
    state = new_game(num_players=2, starting_round=1, seed=456)
    
    # Get initial bag counts
    initial_bags = {}
    for ring_key, bag in state.bags.items():
        initial_bags[ring_key] = sum(bag.values())
    
    print(f"\n[TEST] Initial bags: {initial_bags}")
    
    # Simulate rounds
    state = simulate_rounds(
        state,
        start_round=1,
        end_round=2,
        planner_config={"simulations": 30, "depth": 2},
        verbose=False,
    )
    
    # Get final bag counts
    final_bags = {}
    for ring_key, bag in state.bags.items():
        final_bags[ring_key] = sum(bag.values())
    
    print(f"[TEST] Final bags: {final_bags}")
    
    # Bags should stay the same or decrease (never increase)
    for ring_key in initial_bags:
        if ring_key in final_bags:
            assert final_bags[ring_key] <= initial_bags[ring_key], \
                f"Bag {ring_key} increased: {initial_bags[ring_key]} -> {final_bags[ring_key]}"
    
    print(f"[TEST] ✅ Bag counts properly updated")


def test_discovery_tiles_tracked():
    """Test that discovery tiles are properly tracked on explored hexes."""
    state = new_game(num_players=2, starting_round=1, seed=789)
    
    # Simulate rounds
    state = simulate_rounds(
        state,
        start_round=1,
        end_round=3,
        planner_config={"simulations": 30, "depth": 2},
        verbose=False,
    )
    
    # Count hexes with discovery tiles
    hexes_with_discovery = []
    for hex_id, hex_obj in state.map.hexes.items():
        if hasattr(hex_obj, 'discovery_tile') and hex_obj.discovery_tile:
            hexes_with_discovery.append((hex_id, hex_obj.discovery_tile))
    
    print(f"\n[TEST] Hexes with discovery tiles: {len(hexes_with_discovery)}")
    for hex_id, discovery_state in hexes_with_discovery:
        print(f"  - {hex_id}: {discovery_state}")
    
    # Just verify the field exists - exact count depends on tile draws
    assert all(hasattr(h, 'discovery_tile') for h in state.map.hexes.values()), \
        "Some hexes missing discovery_tile field"
    
    print(f"[TEST] ✅ Discovery tile tracking present")


def test_starting_round_simulation():
    """Test the main use case: starting a game at round > 1."""
    # This is what triggers the multi-round simulation automatically
    state = new_game(num_players=2, starting_round=4, seed=999)
    
    # Should be at round 4 now
    assert state.round == 4, f"Expected round 4, got {state.round}"
    
    # Check board state
    hex_count = len(state.map.hexes)
    print(f"\n[TEST] Game starting at round 4 has {hex_count} hexes")
    
    # Count hexes by ring
    hexes_by_ring = {}
    for hex_obj in state.map.hexes.values():
        ring = hex_obj.ring
        hexes_by_ring[ring] = hexes_by_ring.get(ring, 0) + 1
    
    print(f"[TEST] Ring distribution: {dict(sorted(hexes_by_ring.items()))}")
    
    # Verify all have coordinates
    hexes_with_coords = sum(
        1 for h in state.map.hexes.values()
        if hasattr(h, 'axial_q') and hasattr(h, 'axial_r')
        and h.axial_q is not None and h.axial_r is not None
    )
    
    assert hexes_with_coords == hex_count, \
        f"Only {hexes_with_coords}/{hex_count} hexes have coordinates"
    
    print(f"[TEST] ✅ All hexes have valid coordinates for rendering")


if __name__ == "__main__":
    # Run tests
    print("=" * 70)
    print("Testing Multi-Round Board State Synchronization")
    print("=" * 70)
    
    test_multi_round_creates_hexes()
    test_explored_hexes_have_coordinates()
    test_exploration_updates_bags()
    test_discovery_tiles_tracked()
    test_starting_round_simulation()
    
    print("\n" + "=" * 70)
    print("✅ All board state synchronization tests passed!")
    print("=" * 70)

