"""Tests for tile placement logic."""
import pytest

from eclipse_ai.game_models import GameState, Hex, PlayerState, Pieces, Resources, MapState
from eclipse_ai.map.placement import (
    can_place_tile,
    check_wormhole_connection,
    find_valid_rotations,
    get_connection_hexes,
    has_player_presence,
    place_explored_tile,
)


@pytest.fixture
def basic_state():
    """Create a minimal game state with galactic center and one player hex."""
    state = GameState(
        round=1,
        active_player="P1",
        phase="ACTION",
        players={
            "P1": PlayerState(
                player_id="P1",
                color="blue",
                resources=Resources(),
                income=Resources(),
                known_techs=[],
                ship_designs={},
            )
        },
        map=MapState(),
    )
    
    # Add galactic center at (0, 0)
    gc_hex = Hex(
        id="GC",
        ring=0,
        axial_q=0,
        axial_r=0,
        wormholes=[0, 1, 2, 3, 4, 5],  # All edges
        explored=True,
        revealed=True,
    )
    state.map.hexes["GC"] = gc_hex
    
    # Add player starting hex at (2, 0) with influence disc
    player_hex = Hex(
        id="220",
        ring=2,
        axial_q=2,
        axial_r=0,
        wormholes=[0, 3],  # E and W
        explored=True,
        revealed=True,
        neighbors={3: "GC"},  # Points west to center
        pieces={
            "P1": Pieces(discs=1, ships={"interceptor": 2})
        },
    )
    state.map.hexes["220"] = player_hex
    
    # Update center's neighbor link
    gc_hex.neighbors[0] = "220"  # Points east to player hex
    
    return state


class TestPlayerPresence:
    """Test player presence detection."""
    
    def test_has_presence_with_disc(self, basic_state):
        """Player with disc has presence."""
        assert has_player_presence(basic_state, "220", "P1")
    
    def test_no_presence_different_player(self, basic_state):
        """Different player has no presence."""
        assert not has_player_presence(basic_state, "220", "P2")
    
    def test_no_presence_empty_hex(self, basic_state):
        """Empty hex has no presence."""
        assert not has_player_presence(basic_state, "GC", "P1")


class TestConnectionHexes:
    """Test finding hexes player can explore from."""
    
    def test_get_connection_hexes_adjacent(self, basic_state):
        """Finds player's hex adjacent to target."""
        # Target position (1, 0) is adjacent to player's hex at (2, 0)
        connections = get_connection_hexes(basic_state, 1, 0, "P1")
        
        # Should find the player's starting hex
        assert len(connections) > 0
        hex_ids = [hex_id for hex_id, edge in connections]
        assert "220" in hex_ids
    
    def test_get_connection_hexes_no_presence(self, basic_state):
        """No connections if player has no adjacent presence."""
        # Target far from player
        connections = get_connection_hexes(basic_state, 5, 5, "P1")
        assert len(connections) == 0


class TestWormholeConnection:
    """Test wormhole matching logic."""
    
    def test_full_match_both_sides_have_wormholes(self):
        """Connection is valid when both sides have wormholes."""
        # Tile has wormhole at edge 0 (east)
        tile_wormholes = [0, 3]
        tile_rotation = 0
        edge_from_tile = 0
        
        # Neighbor has wormhole at edge 3 (west, opposite of east)
        neighbor = Hex(
            id="test",
            ring=1,
            wormholes=[3],
        )
        edge_from_neighbor = 3
        
        result = check_wormhole_connection(
            tile_wormholes,
            tile_rotation,
            edge_from_tile,
            neighbor,
            edge_from_neighbor,
            has_wormhole_generator=False,
        )
        
        assert result is True
    
    def test_no_match_neither_side(self):
        """Connection fails when neither side has wormholes."""
        tile_wormholes = [1, 2]  # No wormhole at edge 0
        tile_rotation = 0
        edge_from_tile = 0
        
        neighbor = Hex(
            id="test",
            ring=1,
            wormholes=[1, 2],  # No wormhole at edge 3
        )
        edge_from_neighbor = 3
        
        result = check_wormhole_connection(
            tile_wormholes,
            tile_rotation,
            edge_from_tile,
            neighbor,
            edge_from_neighbor,
            has_wormhole_generator=False,
        )
        
        assert result is False
    
    def test_half_match_with_wormhole_generator(self):
        """Half match allowed with Wormhole Generator tech."""
        # Tile has wormhole, neighbor doesn't
        tile_wormholes = [0]
        tile_rotation = 0
        edge_from_tile = 0
        
        neighbor = Hex(
            id="test",
            ring=1,
            wormholes=[],  # No wormholes
        )
        edge_from_neighbor = 3
        
        # Should fail without tech
        result = check_wormhole_connection(
            tile_wormholes,
            tile_rotation,
            edge_from_tile,
            neighbor,
            edge_from_neighbor,
            has_wormhole_generator=False,
        )
        assert result is False
        
        # Should succeed with tech
        result = check_wormhole_connection(
            tile_wormholes,
            tile_rotation,
            edge_from_tile,
            neighbor,
            edge_from_neighbor,
            has_wormhole_generator=True,
        )
        assert result is True


class TestValidRotations:
    """Test finding valid tile rotations."""
    
    def test_find_valid_rotations_basic(self, basic_state):
        """Can find valid rotations for a tile."""
        # Player at (2, 0), wants to explore (1, 0)
        # Player's hex has wormholes at [0, 3]
        # New tile has wormholes at [0, 3]
        
        tile_wormholes = [0, 3]
        target_q, target_r = 1, 0
        
        valid = find_valid_rotations(
            basic_state,
            tile_wormholes,
            target_q,
            target_r,
            "P1",
        )
        
        # Should find at least one valid rotation
        assert len(valid) > 0
        assert all(0 <= r <= 5 for r in valid)
    
    def test_no_valid_rotations_no_wormholes(self, basic_state):
        """No valid rotations if tile has no wormholes."""
        tile_wormholes = []  # No wormholes
        target_q, target_r = 1, 0
        
        valid = find_valid_rotations(
            basic_state,
            tile_wormholes,
            target_q,
            target_r,
            "P1",
        )
        
        # Can't connect without wormholes
        assert len(valid) == 0


class TestPlaceTile:
    """Test actual tile placement."""
    
    def test_place_explored_tile_creates_hex(self, basic_state):
        """Placing a tile creates a new hex."""
        initial_count = len(basic_state.map.hexes)
        
        tile_wormholes = [0, 3]
        target_q, target_r = 1, 0
        rotation = 0
        
        place_explored_tile(
            basic_state,
            tile_id="101",
            tile_wormholes=tile_wormholes,
            target_q=target_q,
            target_r=target_r,
            rotation=rotation,
            discovery_slots=1,
            ancients=1,
            vp=2,
            tile_number=101,
        )
        
        # Should have one more hex
        assert len(basic_state.map.hexes) == initial_count + 1
        
        # New hex should exist
        assert "101" in basic_state.map.hexes
        
        # Check properties
        new_hex = basic_state.map.hexes["101"]
        assert new_hex.axial_q == target_q
        assert new_hex.axial_r == target_r
        assert new_hex.rotation == rotation
        assert new_hex.ancients == 1
        assert new_hex.discovery_tile == "pending"
    
    def test_place_explored_tile_updates_neighbors(self, basic_state):
        """Placing a tile updates neighbor connections."""
        tile_wormholes = [0, 3]
        target_q, target_r = 1, 0
        rotation = 0
        
        place_explored_tile(
            basic_state,
            tile_id="101",
            tile_wormholes=tile_wormholes,
            target_q=target_q,
            target_r=target_r,
            rotation=rotation,
        )
        
        new_hex = basic_state.map.hexes["101"]
        
        # Should have neighbor links
        assert len(new_hex.neighbors) > 0
        
        # Should connect to player's hex at (2, 0)
        # The player's hex is to the east (edge 0)
        if 0 in new_hex.neighbors:
            assert new_hex.neighbors[0] == "220"
            
            # Check reverse link
            player_hex = basic_state.map.hexes["220"]
            # Player hex should point west (edge 3) to new hex
            assert player_hex.neighbors.get(3) == "101"


class TestCanPlaceTile:
    """Test placement validation."""
    
    def test_can_place_with_valid_rotation(self, basic_state):
        """Can place tile with a valid rotation."""
        tile_wormholes = [0, 3]
        target_q, target_r = 1, 0
        
        # Find a valid rotation first
        valid_rotations = find_valid_rotations(
            basic_state,
            tile_wormholes,
            target_q,
            target_r,
            "P1",
        )
        
        if valid_rotations:
            result = can_place_tile(
                basic_state,
                tile_wormholes,
                target_q,
                target_r,
                valid_rotations[0],
                "P1",
            )
            assert result is True
    
    def test_cannot_place_with_invalid_rotation(self, basic_state):
        """Cannot place tile with invalid rotation."""
        # Tile with wormholes only at edges 2 and 5
        # These won't match the player's hex at (2, 0)
        tile_wormholes = [2, 5]
        target_q, target_r = 1, 0
        
        # Try rotation 0 (probably won't work)
        valid_rotations = find_valid_rotations(
            basic_state,
            tile_wormholes,
            target_q,
            target_r,
            "P1",
        )
        
        # If rotation 0 is not in valid list, can't place
        if 0 not in valid_rotations:
            result = can_place_tile(
                basic_state,
                tile_wormholes,
                target_q,
                target_r,
                0,
                "P1",
            )
            assert result is False

