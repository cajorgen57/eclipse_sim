"""Tile sampling for exploration during multi-round simulation.

This module provides utilities to sample exploration tiles from bags
and integrate with the existing placement system.
"""
from __future__ import annotations

import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_models import GameState
    from .map.decks import HexTile


def sample_tile_from_bag(state: GameState, ring: int) -> Optional[HexTile]:
    """Sample a tile from the exploration bag for the given ring.
    
    This function:
    1. Checks if tiles are available in the bag for this ring
    2. Loads tile definitions for the appropriate stack
    3. Randomly selects a tile from available tiles
    4. Decrements the bag count
    
    Args:
        state: Game state containing tile bags
        ring: Ring number (1=inner, 2=middle, 3=outer)
    
    Returns:
        HexTile object if available, None if bag is empty
        
    Reference: Eclipse Rulebook - Exploration Phase
    """
    from .data.hex_tile_loader import load_hex_tiles
    
    # Check bag availability
    bag_key = f"R{ring}"
    if bag_key not in state.bags:
        return None
    
    tile_counts = state.bags[bag_key]
    total_tiles = sum(tile_counts.values())
    
    if total_tiles <= 0:
        return None
    
    # Load all tile definitions
    all_tiles = load_hex_tiles()
    
    # Filter tiles for this ring
    ring_tiles = [tile for tile in all_tiles.values() if tile.ring == ring]
    
    if not ring_tiles:
        return None
    
    # Check if we have specific tile tracking or just "unknown" count
    if "unknown" in tile_counts and tile_counts["unknown"] > 0:
        # Generic tracking - sample randomly from all ring tiles
        # Filter out starting sectors for ring 2
        if ring == 2:
            # Starting sectors are typically 220-239
            ring_tiles = [t for t in ring_tiles if not (t.id.isdigit() and 220 <= int(t.id) <= 239)]
        
        # Sample randomly
        tile = random.choice(ring_tiles)
        
        # Decrement bag
        tile_counts["unknown"] -= 1
        if tile_counts["unknown"] <= 0:
            del tile_counts["unknown"]
        
        return tile
    else:
        # Specific tile tracking - sample from available tiles
        available_tiles = []
        for tile_id, count in tile_counts.items():
            if count > 0 and tile_id in all_tiles:
                available_tiles.append(all_tiles[tile_id])
        
        if not available_tiles:
            return None
        
        # Sample randomly
        tile = random.choice(available_tiles)
        
        # Decrement bag
        tile_counts[tile.id] -= 1
        if tile_counts[tile.id] <= 0:
            del tile_counts[tile.id]
        
        return tile


def sample_and_place_tile(
    state: GameState,
    player_id: str,
    target_q: int,
    target_r: int,
    ring: int,
) -> bool:
    """Sample a tile and place it on the map.
    
    This is the main entry point for exploration during simulation.
    It combines tile sampling with the existing placement logic.
    
    Args:
        state: Game state to modify
        player_id: Player performing exploration
        target_q: Target Q coordinate
        target_r: Target R coordinate
        ring: Ring number for tile selection
    
    Returns:
        True if tile was successfully placed, False otherwise
        
    Reference: Eclipse Rulebook - Exploration Phase
    """
    from .map.placement import place_explored_tile, find_valid_rotations
    
    # Sample tile from bag
    tile = sample_tile_from_bag(state, ring)
    if tile is None:
        return False
    
    # Find valid rotations for placement
    valid_rotations = find_valid_rotations(
        state,
        list(tile.wormholes),
        target_q,
        target_r,
        player_id,
    )
    
    if not valid_rotations:
        # Can't place tile - would need to put it back in bag
        # For simulation purposes, we'll just skip it
        return False
    
    # Use first valid rotation
    rotation = valid_rotations[0]
    
    # Generate unique tile ID for this placement
    # Use format: {ring}{sequence} e.g., "201", "202", "301"
    existing_count = len([h for h in state.map.hexes.values() if h.ring == ring])
    tile_id = f"{ring}{existing_count + 1:02d}"
    
    # Place tile using existing placement function
    place_explored_tile(
        state,
        tile_id=tile_id,
        tile_wormholes=list(tile.wormholes),
        target_q=target_q,
        target_r=target_r,
        rotation=rotation,
        discovery_slots=tile.discovery_slots,
        ancients=tile.ancients,
        vp=tile.vp,
        tile_number=tile.tile_number,
    )
    
    return True


__all__ = [
    "sample_tile_from_bag",
    "sample_and_place_tile",
]

