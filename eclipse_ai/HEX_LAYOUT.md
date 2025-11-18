# Eclipse Hex Layout System

## Overview

Eclipse uses a hexagonal grid system with a specific numbering scheme for hex tiles. This document defines the canonical mapping between Eclipse hex IDs and their positions in axial coordinates.

**Implementation Status:** ✅ **IMPLEMENTED** - The coordinate system, tile placement, and exploration logic are now fully integrated into the codebase.

## Hex Coordinate System

### Coordinate System: Pointy-Top

This codebase uses **pointy-top** hex coordinates, where hexagons have vertices pointing up/down and flat sides on the left/right. This matches Eclipse's board layout where starting sectors are positioned at vertex angles (30°, 90°, 150°, etc.) from the galactic center.

### Axial Coordinates (q, r)

Eclipse hexes are positioned using axial coordinates where:
- **q** = horizontal axis (East-West)
- **r** = diagonal axis
- **Galactic Center** is at (0, 0)

The third coordinate **s** can be derived as: s = -q - r (ensures q + r + s = 0)

### Ring System

Hexes are organized in rings around the Galactic Center:
- **Ring 0**: Galactic Center (GC)
- **Ring 1**: Inner ring (8 hexes, IDs 101-108)
- **Ring 2**: Middle ring (11 base hexes 201-211, plus species starting sectors 224-239)
- **Ring 3**: Outer ring (18 hexes, IDs 301-324)

## Canonical Hex Positions

### Galactic Center (Ring 0)
- **GC** / **center**: (0, 0)

### Ring 1 - Inner Ring (8 hexes)
Hex IDs 101-108, clockwise from top-right:
- **101**: (1, -1)
- **102**: (1, 0)
- **103**: (0, 1)
- **104**: (-1, 1)
- **105**: (-1, 0)
- **106**: (-1, -1)
- **107**: (0, -1)
- **108**: (1, -1) - Alternative position for 8-hex ring

### Ring 2 - Middle Ring (11 base + species sectors)

#### Base Middle Ring (201-214)
Two hexes from center, clockwise pattern:
- **201**: (2, -2)
- **202**: (2, -1)
- **203**: (2, 0)
- **204**: (2, 1)
- **205**: (1, 2)
- **206**: (0, 2)
- **207**: (-1, 2)
- **208**: (-2, 2)
- **209**: (-2, 1)
- **210**: (-2, 0)
- **211**: (-2, -1)
- **212**: (-2, -2)
- **213**: (-1, -2)
- **214**: (0, -2)

#### Species Starting Sectors (Ring 2)
These are the species-specific starting sectors from species.json:
- **224**: (2, -1) - Eridani Empire
- **226**: (0, 2) - Hydran Progress
- **227**: (-1, 2) - Mechanema
- **228**: (-2, 1) - Planta
- **229**: (-2, 0) - Descendants of Draco
- **230**: (-2, -1) - Orion Hegemony
- **234**: (2, 0) - Magellan
- **239**: (1, 2) - The Exiles

### Ring 3 - Outer Ring (18+ hexes)
Full outer ring hexes, IDs 301-324:
- **301**: (3, -3)
- **302**: (3, -2)
- **303**: (3, -1)
- **304**: (3, 0)
- **305**: (3, 1)
- **306**: (2, 2)
- **307**: (1, 3)
- **308**: (0, 3)
- **309**: (-1, 3)
- **310**: (-2, 3)
- **311**: (-3, 3)
- **312**: (-3, 2)
- **313**: (-3, 1)
- **314**: (-3, 0)
- **315**: (-3, -1)
- **316**: (-3, -2)
- **317**: (-2, -3)
- **318**: (-1, -3)
- **319**: (0, -3)
- **320**: (1, -3)
- **321**: (2, -3)
- **322**: (2, -2)
- **323**: (2, 3)
- **324**: (3, 2)

## Tile Resources

Based on `eclipse_tiles.csv`, starting sector tiles contain specific planet resources:

### Example Tiles (from CSV data)
- **Tile 101**: 1 Materials, 1 Science, 1 Money, 1 Advanced Materials (ring 1)
- **Tile 201**: 1 Science, 1 Money (ring 2)
- **Tile 224** (Eridani): Resources based on exploration tile assignment
- **Tile 301**: 2 Materials, 1 Science, 1 Money, 1 Advanced Materials (ring 3)

## Setup Rules

### Starting Sector Placement
According to SETUP_GUIDE.md:
- Starting sectors are placed at **six middle-ring entry points**
- Each sector is **two hexes from the Galactic Center** (Ring 2)
- Default positions: 201, 202, 203, 204, 205, 206
- Species-specific positions override defaults (e.g., Eridani uses 224)

### Player Setup
Each player's starting sector contains:
1. **Ships**: 1-2 interceptors or 1 cruiser (species-dependent)
2. **Colonies**: 1-3 population cubes on planets (species-dependent)
3. **Influence**: 1 influence disc

## Wormhole Connections

Wormholes connect adjacent hexes. In axial coordinates, hex (q, r) has up to 6 neighbors (pointy-top orientation):
- **(q+1, r)**: East (edge 0)
- **(q+1, r-1)**: Northeast (edge 1)
- **(q, r-1)**: Northwest (edge 2)
- **(q-1, r)**: West (edge 3)
- **(q-1, r+1)**: Southwest (edge 4)
- **(q, r+1)**: Southeast (edge 5)

### Edge Numbering

Wormholes are represented as edge indices **0-5** (clockwise from East):

```
        2 (NW)     1 (NE)
           \       /
            \     /
      3 (W)  \   /  0 (E)
              \ /
              HEX
              / \
      4 (SW) /   \ 5 (SE)
            /     \
```

### Rotation and Placement

When a tile is placed:
1. The tile has **base wormholes** defined in its tile definition (e.g., `[0, 3]` for wormholes at East and West)
2. The tile is **rotated** (0-5 steps clockwise) to align with existing hexes
3. The **effective wormholes** after rotation are stored in the placed `Hex`

Example:
- Base wormholes: `[0, 3]` (East and West)
- Rotation: `1` (rotate 1 step clockwise)
- Effective wormholes: `[1, 4]` (Northeast and Southwest)

### Connectivity Rules (from Eclipse rules)

A tile can only be placed if:
1. At least one wormhole edge connects to a wormhole on an adjacent hex where the player has a disc or ship
2. **Full match** (both sides have wormholes) is required by default
3. **Half match** (only one side has wormhole) is allowed if player has **Wormhole Generator** technology

Implementation: See `eclipse_ai/map/placement.py` for tile placement validation.

## Implementation Notes

### Frontend (board-renderer.js)
- `getEclipseHexCoords()`: Returns canonical mapping
- `parseHexId(hexId)`: Converts hex ID to (q, r) coordinates
- `hexToPixel(q, r)`: Converts (q, r) to screen coordinates

### Backend Implementation

#### Coordinate System (`eclipse_ai/map/coordinates.py`)
- `hex_id_to_axial(hex_id)`: Convert Eclipse hex ID to (q, r) coordinates
- `axial_to_hex_id(q, r)`: Reverse lookup from coordinates to hex ID
- `ring_radius(q, r)`: Calculate ring distance from center
- `axial_neighbors(q, r)`: Get all 6 neighboring coordinates
- `effective_wormholes(base_wormholes, rotation)`: Calculate wormholes after rotation
- `rotate_to_face_direction(wormholes, edge)`: Find rotation to orient tile

#### Tile Placement (`eclipse_ai/map/placement.py`)
- `find_valid_rotations(state, tile, target_q, target_r, player)`: Find all legal rotations
- `can_place_tile(...)`: Check if specific rotation is valid
- `place_explored_tile(...)`: Actually place tile on map with neighbors

#### Game Setup (`eclipse_ai/game_setup.py`)
- `_setup_galactic_center()`: Places center at (0, 0) with discovery tile
- `_create_starting_sector()`: Places player's starting hex at ring 2 position
- Uses `get_starting_spot_coordinates()` for the six canonical starting positions
- Automatically orients starting sectors to face galactic center

#### Data Files
- `eclipse_ai/data/hex_tiles.json`: Complete tile definitions with wormholes, VP, discovery, ancients
- `eclipse_ai/data/hex_tile_loader.py`: Loads tile data into `HexTile` objects
- `eclipse_tiles.csv`: Original exploration tile data (being enhanced)

#### Validation (`eclipse_ai/map/validation.py`)
- `validate_board_geometry()`: Check coordinates form valid rings
- `validate_wormhole_connections()`: Verify neighbor links and wormholes
- `validate_tile_placement()`: Check rotations and tile properties
- `validate_starting_sectors()`: Ensure proper starting setup

## References

- Eclipse tiles data: `eclipse_tiles.csv`
- Species configuration: `eclipse_ai/data/species.json`
- Setup guide: `SETUP_GUIDE.md`
- Board renderer: `eclipse_ai/gui/static/js/board-renderer.js`
- Game setup: `eclipse_ai/game_setup.py`

## Visual Reference

```
        Ring 3 (Outer)
           Ring 2 (Middle)  
              Ring 1 (Inner)
                  GC (Center)

Hex numbering is clockwise from top positions in each ring.
Starting sectors (224-239) are positioned "two hexes from center" in Ring 2.
```

## Validation

To validate hex layout:
```python
from eclipse_ai.game_setup import _validate_hex_layout

# After creating game state
_validate_hex_layout(state)
```

This will warn about any hex IDs that don't match the canonical Eclipse hex system.

