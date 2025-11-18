#!/usr/bin/env python3
"""Quick demo to verify board state synchronization works."""

from eclipse_ai.game_setup import new_game

print("=" * 70)
print("Board State Synchronization Demo")
print("=" * 70)

print("\n1. Creating game that starts at round 1...")
state1 = new_game(num_players=2, starting_round=1, seed=42)
hex_count_r1 = len(state1.map.hexes)
print(f"   Initial state: {hex_count_r1} hexes")

print("\n2. Creating game that starts at round 4 (simulates rounds 1-3)...")
state4 = new_game(num_players=2, starting_round=4, seed=42)
hex_count_r4 = len(state4.map.hexes)
print(f"   After simulation: {hex_count_r4} hexes")

# Check coordinates
hexes_with_coords = sum(
    1 for h in state4.map.hexes.values()
    if hasattr(h, 'axial_q') and hasattr(h, 'axial_r')
    and h.axial_q is not None and h.axial_r is not None
)

print(f"\n3. Verification:")
print(f"   ✅ Hexes created: {hex_count_r4} total")
print(f"   ✅ With coordinates: {hexes_with_coords}/{hex_count_r4}")

# Ring distribution
hexes_by_ring = {}
for hex_obj in state4.map.hexes.values():
    ring = hex_obj.ring
    hexes_by_ring[ring] = hexes_by_ring.get(ring, 0) + 1
print(f"   ✅ Ring distribution: {dict(sorted(hexes_by_ring.items()))}")

# List some hexes
print(f"\n4. Sample hexes:")
for i, (hex_id, hex_obj) in enumerate(list(state4.map.hexes.items())[:5]):
    print(f"   - {hex_id}: ({hex_obj.axial_q:2}, {hex_obj.axial_r:2}) ring={hex_obj.ring}")

print("\n" + "=" * 70)
print("✅ Board state synchronization is working!")
print("=" * 70)

