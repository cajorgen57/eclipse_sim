"""Validation functions for Eclipse board geometry and tile placement.

Ensures that game state follows canonical Eclipse rules for hex positioning,
wormhole connectivity, and tile placement.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..game_models import GameState

from .coordinates import (
    axial_neighbors,
    hex_id_to_axial,
    opposite_edge,
    ring_radius,
)


def validate_board_geometry(state: GameState) -> List[str]:
    """Validate that all hex coordinates form valid Eclipse rings.
    
    Checks:
    - Galactic Center at (0, 0)
    - Ring distances match hex IDs
    - No duplicate coordinates
    
    Args:
        state: Game state to validate
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    # Track coordinate uniqueness
    seen_coords = set()
    
    for hex_id, hex_obj in state.map.hexes.items():
        # Check if hex has axial coordinates
        if not hasattr(hex_obj, 'axial_q') or not hasattr(hex_obj, 'axial_r'):
            errors.append(f"Hex {hex_id} missing axial coordinates")
            continue
        
        q = hex_obj.axial_q
        r = hex_obj.axial_r
        
        # Check for duplicate coordinates
        if (q, r) in seen_coords:
            errors.append(f"Duplicate coordinates ({q}, {r}) for hex {hex_id}")
        seen_coords.add((q, r))
        
        # Validate galactic center
        if hex_id in ("GC", "center", "001"):
            if (q, r) != (0, 0):
                errors.append(f"Galactic Center {hex_id} should be at (0, 0), found at ({q}, {r})")
        
        # Validate ring matches coordinates
        calculated_ring = ring_radius(q, r)
        if hasattr(hex_obj, 'ring') and hex_obj.ring != calculated_ring:
            errors.append(
                f"Hex {hex_id} ring mismatch: stored={hex_obj.ring}, "
                f"calculated={calculated_ring} from coords ({q}, {r})"
            )
    
    return errors


def validate_wormhole_connections(state: GameState) -> List[str]:
    """Validate that neighbor links have proper wormhole connectivity.
    
    Checks:
    - Bidirectional neighbor links
    - Wormhole presence on connected edges
    
    Args:
        state: Game state to validate
    
    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []
    
    for hex_id, hex_obj in state.map.hexes.items():
        if not hasattr(hex_obj, 'neighbors'):
            continue
        
        for edge, neighbor_id in hex_obj.neighbors.items():
            if neighbor_id is None:
                continue
            
            neighbor_hex = state.map.hexes.get(neighbor_id)
            if neighbor_hex is None:
                warnings.append(f"Hex {hex_id} references non-existent neighbor {neighbor_id}")
                continue
            
            # Check bidirectional link
            opp_edge = opposite_edge(edge)
            if not hasattr(neighbor_hex, 'neighbors'):
                warnings.append(f"Neighbor {neighbor_id} has no neighbors dict")
                continue
            
            reverse_link = neighbor_hex.neighbors.get(opp_edge)
            if reverse_link != hex_id:
                warnings.append(
                    f"Broken bidirectional link: {hex_id} -> {neighbor_id} at edge {edge}, "
                    f"but {neighbor_id} edge {opp_edge} points to {reverse_link}"
                )
            
            # Check wormhole connectivity (informational only)
            hex_wormholes = getattr(hex_obj, 'wormholes', [])
            neighbor_wormholes = getattr(neighbor_hex, 'wormholes', [])
            
            hex_has_wormhole = edge in hex_wormholes
            neighbor_has_wormhole = opp_edge in neighbor_wormholes
            
            if not hex_has_wormhole and not neighbor_has_wormhole:
                warnings.append(
                    f"No wormholes between {hex_id} and {neighbor_id} "
                    f"(may require Wormhole Generator)"
                )
    
    return warnings


def validate_tile_placement(state: GameState) -> List[str]:
    """Validate tile-specific properties.
    
    Checks:
    - Rotation values are 0-5
    - Wormhole edges are 0-5
    - Tile numbers are reasonable
    
    Args:
        state: Game state to validate
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    for hex_id, hex_obj in state.map.hexes.items():
        # Check rotation
        if hasattr(hex_obj, 'rotation'):
            rotation = hex_obj.rotation
            if not (0 <= rotation <= 5):
                errors.append(f"Hex {hex_id} has invalid rotation {rotation} (must be 0-5)")
        
        # Check wormhole edges
        if hasattr(hex_obj, 'wormholes'):
            for edge in hex_obj.wormholes:
                if not isinstance(edge, int) or not (0 <= edge <= 5):
                    errors.append(f"Hex {hex_id} has invalid wormhole edge {edge}")
        
        # Check tile number
        if hasattr(hex_obj, 'tile_number'):
            tile_num = hex_obj.tile_number
            if tile_num < 0 or tile_num > 999:
                errors.append(f"Hex {hex_id} has unusual tile_number {tile_num}")
    
    return errors


def validate_starting_sectors(state: GameState) -> List[str]:
    """Validate that starting sectors are properly placed.
    
    Checks:
    - Starting sectors are at ring 2
    - Each player has a starting sector
    
    Args:
        state: Game state to validate
    
    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []
    
    starting_hexes = []
    for hex_id, hex_obj in state.map.hexes.items():
        # Starting sectors have IDs 220-239
        if hex_id.isdigit() and 220 <= int(hex_id) <= 239:
            starting_hexes.append((hex_id, hex_obj))
    
    for hex_id, hex_obj in starting_hexes:
        # Check ring
        if hasattr(hex_obj, 'axial_q') and hasattr(hex_obj, 'axial_r'):
            calculated_ring = ring_radius(hex_obj.axial_q, hex_obj.axial_r)
            if calculated_ring != 2:
                warnings.append(
                    f"Starting sector {hex_id} at ring {calculated_ring}, "
                    f"expected ring 2"
                )
    
    # Check player coverage
    for player_id, player in state.players.items():
        has_starting_hex = False
        for hex_id, hex_obj in state.map.hexes.items():
            pieces = hex_obj.pieces.get(player_id)
            if pieces and (pieces.discs > 0 or pieces.ships):
                has_starting_hex = True
                break
        
        if not has_starting_hex:
            warnings.append(f"Player {player_id} has no starting hex with pieces")
    
    return warnings


def validate_all(state: GameState) -> dict:
    """Run all validation checks on a game state.
    
    Args:
        state: Game state to validate
    
    Returns:
        Dictionary with validation results:
        {
            'geometry_errors': [...],
            'wormhole_warnings': [...],
            'placement_errors': [...],
            'starting_warnings': [...],
            'valid': bool
        }
    """
    geometry_errors = validate_board_geometry(state)
    wormhole_warnings = validate_wormhole_connections(state)
    placement_errors = validate_tile_placement(state)
    starting_warnings = validate_starting_sectors(state)
    
    all_errors = geometry_errors + placement_errors
    
    return {
        'geometry_errors': geometry_errors,
        'wormhole_warnings': wormhole_warnings,
        'placement_errors': placement_errors,
        'starting_warnings': starting_warnings,
        'valid': len(all_errors) == 0,
    }


__all__ = [
    "validate_all",
    "validate_board_geometry",
    "validate_starting_sectors",
    "validate_tile_placement",
    "validate_wormhole_connections",
]

