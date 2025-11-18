"""Loader for hex tile definitions from hex_tiles.json."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, List, Optional

from ..map.decks import HexTile


def _json_path() -> str:
    """Get path to hex_tiles.json."""
    base_path = os.path.join(os.path.dirname(__file__), "hex_tiles.json")
    return os.path.abspath(base_path)


@lru_cache()
def load_hex_tiles() -> Dict[str, HexTile]:
    """Load hex tile definitions from JSON.
    
    Returns:
        Dictionary mapping tile ID to HexTile objects
    """
    path = _json_path()
    if not os.path.exists(path):
        return {}
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tiles = {}
    for tile_id, tile_data in data.get('tiles', {}).items():
        tile = HexTile(
            id=tile_data.get('id', tile_id),
            ring=tile_data.get('ring', 1),
            wormholes=tuple(tile_data.get('wormholes', [])),
            symbols=tuple(tile_data.get('symbols', [])),
            warp_portal=tile_data.get('warp_portal', False),
            gcds=tile_data.get('gcds', False),
            vp=tile_data.get('vp', 0),
            discovery_slots=tile_data.get('discoverySlots', 0),
            ancients=tile_data.get('ancients', 0),
            artifacts=tile_data.get('artifacts', 0),
            tile_number=tile_data.get('number', 0),
            pop=tile_data.get('pop', {}),
        )
        tiles[tile_id] = tile
    
    return tiles


@lru_cache()
def load_tiles_by_stack() -> Dict[str, List[HexTile]]:
    """Load tiles grouped by stack (I, II, III, START).
    
    Returns:
        Dictionary mapping stack name to list of tiles
    """
    all_tiles = load_hex_tiles()
    
    stacks = {
        "I": [],
        "II": [],
        "III": [],
        "START": [],
        "CENTER": [],
    }
    
    for tile in all_tiles.values():
        stack = getattr(tile, 'stack', None)
        if stack and stack in stacks:
            stacks[stack].append(tile)
        else:
            # Infer from ring
            if tile.ring == 0:
                stacks["CENTER"].append(tile)
            elif tile.ring == 1:
                stacks["I"].append(tile)
            elif tile.ring == 2:
                # Check if it's a starting sector (220-239)
                if tile.id.isdigit() and 220 <= int(tile.id) <= 239:
                    stacks["START"].append(tile)
                else:
                    stacks["II"].append(tile)
            elif tile.ring >= 3:
                stacks["III"].append(tile)
    
    return stacks


def get_tile(tile_id: str) -> Optional[HexTile]:
    """Get a specific tile by ID.
    
    Args:
        tile_id: Tile identifier
    
    Returns:
        HexTile object or None if not found
    """
    tiles = load_hex_tiles()
    return tiles.get(tile_id)


__all__ = [
    "get_tile",
    "load_hex_tiles",
    "load_tiles_by_stack",
]

