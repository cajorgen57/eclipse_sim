"""Axial coordinate system for Eclipse hex map.

This module implements the flat-topped hexagonal grid coordinate system
as specified in the Eclipse board setup rules.

Coordinate System:
    - Axial coordinates (q, r) where q is horizontal (E-W) and r is diagonal (NE-SW)
    - Galactic Center at (0, 0)
    - Ring radius = max(|q|, |r|, |-(q+r)|)

Edge Numbering (clockwise from East):
    0 = East     : (+1,  0)
    1 = Northeast: ( 0, +1)
    2 = Northwest: (-1, +1)
    3 = West     : (-1,  0)
    4 = Southwest: ( 0, -1)
    5 = Southeast: (+1, -1)
"""
from __future__ import annotations

from typing import Dict, List, Tuple, Optional

# Direction vectors for pointy-top hex grid (clockwise from East)
# These produce face-center angles at 0°, 60°, 120°, 180°, 240°, 300° with pointy-top rendering
AXIAL_DIRECTIONS: List[Tuple[int, int]] = [
    (+1,  0),  # 0: East (0°)
    (+1, -1),  # 1: Northeast (60°) 
    ( 0, -1),  # 2: Northwest (120°)
    (-1,  0),  # 3: West (180°)
    (-1, +1),  # 4: Southwest (240°)
    ( 0, +1),  # 5: Southeast (300°)
]


def axial_add(coord: Tuple[int, int], direction: int) -> Tuple[int, int]:
    """Add a direction vector to axial coordinates.
    
    Args:
        coord: (q, r) axial coordinates
        direction: Edge index 0-5
    
    Returns:
        New (q, r) coordinates
    """
    q, r = coord
    dq, dr = AXIAL_DIRECTIONS[direction % 6]
    return (q + dq, r + dr)


def axial_neighbors(q: int, r: int) -> Dict[int, Tuple[int, int]]:
    """Return all 6 neighbors of a hex as a dict of edge -> (q, r).
    
    Args:
        q: Axial q coordinate
        r: Axial r coordinate
    
    Returns:
        Dict mapping edge index (0-5) to neighbor coordinates
    """
    neighbors = {}
    for edge in range(6):
        neighbors[edge] = axial_add((q, r), edge)
    return neighbors


def ring_radius(q: int, r: int) -> int:
    """Calculate the ring distance from the galactic center.
    
    Ring 0 = Galactic Center
    Ring 1 = Inner (8 hexes around center)
    Ring 2 = Middle (including starting sectors)
    Ring 3+ = Outer
    
    Args:
        q: Axial q coordinate
        r: Axial r coordinate
    
    Returns:
        Ring number (distance from center)
    """
    s = -(q + r)
    return max(abs(q), abs(r), abs(s))


def axial_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Calculate the distance between two hexes in axial coordinates.
    
    Uses the axial coordinate distance formula:
    distance = max(|q1-q2|, |r1-r2|, |-(q1-q2)-(r1-r2)|)
    
    Args:
        q1, r1: First hex coordinates
        q2, r2: Second hex coordinates
    
    Returns:
        Number of hexes between the two positions
    """
    dq = q1 - q2
    dr = r1 - r2
    ds = -(dq + dr)
    return max(abs(dq), abs(dr), abs(ds))


def sector_for_ring(ring: int) -> str:
    """Map ring number to sector stack identifier.
    
    Args:
        ring: Ring radius (1, 2, or 3+)
    
    Returns:
        Sector identifier: "I", "II", or "III"
    """
    if ring == 1:
        return "I"
    elif ring == 2:
        return "II"
    else:
        return "III"


def opposite_edge(edge: int) -> int:
    """Return the opposite edge index.
    
    Edge 0 (East) is opposite to edge 3 (West), etc.
    
    Args:
        edge: Edge index 0-5
    
    Returns:
        Opposite edge index
    """
    return (edge + 3) % 6


def rotate_edge(edge: int, rotation: int) -> int:
    """Rotate an edge index clockwise.
    
    Args:
        edge: Original edge index 0-5
        rotation: Rotation steps (0-5)
    
    Returns:
        Rotated edge index
    """
    return (edge + rotation) % 6


def rotate_wormhole_array(wormholes: List[int], rotation: int) -> List[int]:
    """Apply rotation to a wormhole edge array.
    
    The wormhole array represents which edges have wormholes in the tile's
    base orientation. When placed with rotation R, the wormhole at base
    edge E appears at world edge (E + R) % 6.
    
    Args:
        wormholes: List of edge indices (0-5) that have wormholes
        rotation: Clockwise rotation steps (0-5)
    
    Returns:
        List of rotated edge indices
    """
    if not wormholes or rotation == 0:
        return list(wormholes)
    return [rotate_edge(e, rotation) for e in wormholes]


def effective_wormholes(base_wormholes: List[int], rotation: int) -> List[int]:
    """Calculate effective wormhole positions after rotation.
    
    Args:
        base_wormholes: Base wormhole edges from tile definition
        rotation: Applied rotation (0-5)
    
    Returns:
        Sorted list of effective edge indices with wormholes
    """
    return sorted(rotate_wormhole_array(base_wormholes, rotation))


# Canonical hex ID to axial coordinate mapping (from HEX_LAYOUT.md)
CANONICAL_HEX_POSITIONS: Dict[str, Tuple[int, int]] = {
    # Ring 0: Galactic Center
    "GC": (0, 0),
    "center": (0, 0),
    "001": (0, 0),
    
    # Ring 1: Inner (8 hexes) - clockwise from top-right (matches HEX_LAYOUT.md)
    "101": (1, -1),
    "102": (1, 0),
    "103": (0, 1),
    "104": (-1, 1),
    "105": (-1, 0),
    "106": (-1, -1),
    "107": (0, -1),
    "108": (1, -1),  # Alternative inner position
    
    # Ring 2: Middle base tiles (201-214) - matches HEX_LAYOUT.md
    "201": (2, -2),
    "202": (2, -1),
    "203": (2, 0),
    "204": (2, 1),
    "205": (1, 2),
    "206": (0, 2),
    "207": (-1, 2),
    "208": (-2, 2),
    "209": (-2, 1),
    "210": (-2, 0),
    "211": (-2, -1),
    "212": (-2, -2),
    "213": (-1, -2),
    "214": (0, -2),
    
    # Ring 2: Species starting sectors (220-239)
    # Six canonical starting positions evenly distributed at ring 2:
    # East (2,0), NE (0,2), NW (-2,2), West (-2,0), SW (0,-2), SE (2,-2)
    "220": (2, 0),    # Generic start - East
    "221": (0, 2),    # Generic start - NE
    "222": (-2, 2),   # Eridani Empire - NW (species.json says 222 is Eridani)
    "223": (-2, 0),   # Generic start - West
    "224": (0, -2),   # Hydran Progress - SW
    "225": (2, -2),   # Generic start - SE
    "226": (0, 2),    # Planta - NE
    "227": (-2, 2),   # Generic start - NW
    "228": (-2, 0),   # Descendants of Draco - West
    "229": (0, -2),   # Generic start - SW
    "230": (2, -2),   # Mechanema - SE
    "231": (2, 0),    # Generic start - East
    "232": (0, 2),    # Orion Hegemony - NE
    "234": (2, 0),    # Magellan - East
    "236": (0, 2),    # Generic start - NE
    "237": (-2, 2),   # Rho Indi - NW
    "238": (-2, 0),   # Enlightened - West
    "239": (0, -2),   # The Exiles - SW
    
    # Ring 3: Outer (301-324) - matches HEX_LAYOUT.md
    "301": (3, -3),
    "302": (3, -2),
    "303": (3, -1),
    "304": (3, 0),
    "305": (3, 1),
    "306": (2, 2),
    "307": (1, 3),
    "308": (0, 3),
    "309": (-1, 3),
    "310": (-2, 3),
    "311": (-3, 3),
    "312": (-3, 2),
    "313": (-3, 1),
    "314": (-3, 0),
    "315": (-3, -1),
    "316": (-3, -2),
    "317": (-2, -3),
    "318": (-1, -3),
    "319": (0, -3),
    "320": (1, -3),
    "321": (2, -3),
    "322": (2, -2),
    "323": (2, 3),
    "324": (3, 2),
}


def hex_id_to_axial(hex_id: str) -> Tuple[int, int]:
    """Convert Eclipse hex ID to axial coordinates.
    
    Uses canonical mapping from HEX_LAYOUT.md. For unmapped IDs,
    attempts to infer from the ID pattern.
    
    Args:
        hex_id: Eclipse hex identifier (e.g., "101", "GC", "301")
    
    Returns:
        (q, r) axial coordinates
    
    Raises:
        ValueError: If hex_id cannot be mapped
    """
    # Try canonical lookup first
    if hex_id in CANONICAL_HEX_POSITIONS:
        return CANONICAL_HEX_POSITIONS[hex_id]
    
    # Try to infer from ID pattern (e.g., "1xx" -> ring 1)
    if len(hex_id) == 3 and hex_id.isdigit():
        ring = int(hex_id[0])
        # This is a fallback - actual placement should use canonical positions
        # For now, place in a default position for the ring
        if ring == 1:
            return (1, 0)
        elif ring == 2:
            return (2, 0)
        elif ring == 3:
            return (3, 0)
    
    raise ValueError(f"Unknown hex ID: {hex_id}")


def axial_to_hex_id(q: int, r: int) -> Optional[str]:
    """Reverse lookup: find hex ID for given axial coordinates.
    
    Args:
        q: Axial q coordinate
        r: Axial r coordinate
    
    Returns:
        Hex ID string, or None if no canonical hex exists at these coords
    """
    for hex_id, coords in CANONICAL_HEX_POSITIONS.items():
        if coords == (q, r):
            return hex_id
    return None


def get_starting_spot_coordinates() -> List[Tuple[int, int]]:
    """Return the six canonical starting sector positions.
    
    Starting sectors are placed at ring 2, at the cardinal and intercardinal
    directions from the galactic center.
    
    Returns:
        List of 6 (q, r) coordinate tuples for starting positions
    """
    return [
        (2, 0),    # ENE (30°)
        (0, 2),    # NNW (90°)
        (-2, 2),   # WNW (150°)
        (-2, 0),   # WSW (-150°)
        (0, -2),   # SSE (-90°)
        (2, -2),   # ESE (-30°)
    ]


def direction_between_coords(from_q: int, from_r: int, to_q: int, to_r: int) -> Optional[int]:
    """Find the edge direction from one hex to an adjacent hex.
    
    Args:
        from_q, from_r: Source hex coordinates
        to_q, to_r: Target hex coordinates
    
    Returns:
        Edge index (0-5) if hexes are adjacent, None otherwise
    """
    delta_q = to_q - from_q
    delta_r = to_r - from_r
    
    for edge, (dq, dr) in enumerate(AXIAL_DIRECTIONS):
        if (delta_q, delta_r) == (dq, dr):
            return edge
    
    return None


def rotate_to_face_direction(tile_wormholes: List[int], target_edge: int) -> int:
    """Find rotation to place a wormhole at target edge.
    
    Picks the first wormhole in the tile and rotates it to face the target edge.
    
    Args:
        tile_wormholes: List of edges with wormholes in base orientation
        target_edge: Desired edge (0-5) to face
    
    Returns:
        Rotation value (0-5) that places a wormhole at target_edge
    """
    if not tile_wormholes:
        return 0
    
    # Use the first wormhole
    base_edge = tile_wormholes[0]
    
    # Calculate rotation needed: target - base
    rotation = (target_edge - base_edge) % 6
    return rotation


__all__ = [
    "AXIAL_DIRECTIONS",
    "axial_add",
    "axial_neighbors",
    "axial_to_hex_id",
    "direction_between_coords",
    "effective_wormholes",
    "get_starting_spot_coordinates",
    "hex_id_to_axial",
    "opposite_edge",
    "ring_radius",
    "rotate_edge",
    "rotate_to_face_direction",
    "rotate_wormhole_array",
    "sector_for_ring",
]

