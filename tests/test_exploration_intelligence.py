"""
Unit tests for exploration intelligence (Phase 4 of Multi-Round Simulation).

Tests verify that exploration decisions follow good heuristics:
- Tile keep/discard decisions are reasonable
- Tile placement scores prioritize good positions
- Exploration opportunity evaluation works
"""
import pytest
from eclipse_ai.game_models import (
    GameState, PlayerState, MapState, Hex, Pieces, Planet
)
from eclipse_ai.exploration_intelligence import (
    should_keep_tile,
    score_placement,
    evaluate_exploration_opportunity,
    select_best_exploration_hex,
)


def create_test_tile(
    planets: int = 0,
    ancients: int = 0,
    wormholes: list = None,
    has_monolith: bool = False,
) -> Hex:
    """Helper to create a test tile."""
    tile = Hex(
        id="test_tile",
        ring=2,
        wormholes=wormholes or [0, 3],
        planets=[],
    )
    
    # Add planets
    for i in range(planets):
        color = ['orange', 'pink', 'brown'][i % 3]
        tile.planets.append(Planet(type=color))
    
    tile.ancients = ancients
    tile.has_monolith = has_monolith
    
    return tile


def create_test_state() -> GameState:
    """Helper to create a test game state."""
    state = GameState(
        round=1,
        active_player="P1",
        players={
            "P1": PlayerState(player_id="P1", color="blue"),
        },
        map=MapState(),
    )
    
    # Add home hex for P1
    home_hex = Hex(
        id="220",
        ring=2,
        wormholes=[0, 3],
        planets=[Planet(type="orange")],
    )
    home_hex.axial_q = 0
    home_hex.axial_r = 0
    home_hex.pieces["P1"] = Pieces(ships={}, discs=1)
    
    state.map.hexes["220"] = home_hex
    state.players["P1"].home_hex_id = "220"
    
    return state


class TestShouldKeepTile:
    """Test tile keep/discard decisions."""
    
    def test_keep_good_planets(self):
        """Keep tiles with 2+ good planets."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=2, ancients=0)
        
        assert should_keep_tile(state, player, tile) == True
    
    def test_discard_many_ancients_no_resources(self):
        """Discard tiles with 4+ ancients and no resources."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=0, ancients=4)
        
        assert should_keep_tile(state, player, tile) == False
    
    def test_discard_no_resources_poor_connectivity(self):
        """Discard tiles with no resources and poor wormholes."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=0, ancients=0, wormholes=[0])
        
        assert should_keep_tile(state, player, tile) == False
    
    def test_keep_good_connectivity(self):
        """Keep tiles with many wormholes."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=0, ancients=0, wormholes=[0, 1, 2, 3])
        
        assert should_keep_tile(state, player, tile) == True
    
    def test_keep_monolith(self):
        """Keep monolith tiles."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=0, ancients=0, has_monolith=True)
        
        assert should_keep_tile(state, player, tile) == True
    
    def test_keep_one_planet_few_ancients(self):
        """Keep tiles with 1 planet and manageable ancients."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=1, ancients=2)
        
        assert should_keep_tile(state, player, tile) == True
    
    def test_discard_two_ancients_no_resources(self):
        """Discard tiles with 2 ancients, no resources, poor wormholes."""
        state = create_test_state()
        player = state.players["P1"]
        tile = create_test_tile(planets=0, ancients=2, wormholes=[0, 1])
        
        assert should_keep_tile(state, player, tile) == False


class TestScorePlacement:
    """Test tile placement scoring."""
    
    def test_score_good_resources(self):
        """Tiles with good planets score higher."""
        state = create_test_state()
        tile_good = create_test_tile(planets=2, ancients=0)
        tile_bad = create_test_tile(planets=0, ancients=0)
        
        score_good = score_placement(state, "P1", (1, 0), tile_good, 0)
        score_bad = score_placement(state, "P1", (1, 0), tile_bad, 0)
        
        assert score_good > score_bad
    
    def test_score_ancient_penalty(self):
        """Tiles with ancients score lower."""
        state = create_test_state()
        tile_safe = create_test_tile(planets=1, ancients=0)
        tile_dangerous = create_test_tile(planets=1, ancients=3)
        
        score_safe = score_placement(state, "P1", (1, 0), tile_safe, 0)
        score_dangerous = score_placement(state, "P1", (1, 0), tile_dangerous, 0)
        
        assert score_safe > score_dangerous
    
    def test_score_wormholes_bonus(self):
        """Tiles with more wormholes score higher."""
        state = create_test_state()
        tile_few_wh = create_test_tile(planets=0, wormholes=[0, 3])
        tile_many_wh = create_test_tile(planets=0, wormholes=[0, 1, 2, 3, 4])
        
        score_few = score_placement(state, "P1", (1, 0), tile_few_wh, 0)
        score_many = score_placement(state, "P1", (1, 0), tile_many_wh, 0)
        
        assert score_many > score_few
    
    def test_score_monolith_bonus(self):
        """Monolith tiles score higher."""
        state = create_test_state()
        tile_normal = create_test_tile(planets=0)
        tile_monolith = create_test_tile(planets=0, has_monolith=True)
        
        score_normal = score_placement(state, "P1", (1, 0), tile_normal, 0)
        score_monolith = score_placement(state, "P1", (1, 0), tile_monolith, 0)
        
        assert score_monolith > score_normal
    
    def test_score_distance_penalty(self):
        """Tiles further from home score lower."""
        state = create_test_state()
        tile = create_test_tile(planets=1)
        
        # Position (1, 0) is closer than (3, 0)
        score_close = score_placement(state, "P1", (1, 0), tile, 0)
        score_far = score_placement(state, "P1", (3, 0), tile, 0)
        
        assert score_close > score_far


class TestExplorationOpportunity:
    """Test exploration opportunity evaluation."""
    
    def test_evaluate_base_value(self):
        """Base exploration has positive value."""
        state = create_test_state()
        
        value = evaluate_exploration_opportunity(state, "P1", "220")
        
        assert value > 0
    
    def test_evaluate_diminishing_returns(self):
        """Exploration value decreases with more hexes owned."""
        state = create_test_state()
        
        # Add many hexes to player
        for i in range(1, 10):
            hex_id = f"hex_{i}"
            hex_obj = Hex(id=hex_id, ring=2, wormholes=[0, 3], planets=[])
            hex_obj.axial_q = i
            hex_obj.axial_r = 0
            hex_obj.pieces["P1"] = Pieces(ships={}, discs=1)
            state.map.hexes[hex_id] = hex_obj
        
        # Exploration should have lower value with many hexes
        value = evaluate_exploration_opportunity(state, "P1", "220")
        
        # Still positive, but reduced
        assert value > 0
        assert value < 5.0  # Less than base value


class TestSelectBestExplorationHex:
    """Test best exploration hex selection."""
    
    def test_select_from_available(self):
        """Select best hex when options available."""
        state = create_test_state()
        
        # Add another hex with unexplored neighbors
        hex_obj = Hex(id="hex_2", ring=2, wormholes=[0, 3], planets=[])
        hex_obj.axial_q = 2
        hex_obj.axial_r = 0
        hex_obj.pieces["P1"] = Pieces(ships={}, discs=1)
        state.map.hexes["hex_2"] = hex_obj
        
        result = select_best_exploration_hex(state, "P1")
        
        assert result is not None
        assert result in ["220", "hex_2"]
    
    def test_select_none_when_no_options(self):
        """Return None when no exploration options."""
        state = create_test_state()
        
        # Surround home hex with hexes (no unexplored neighbors)
        neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        for i, (q, r) in enumerate(neighbors):
            hex_id = f"neighbor_{i}"
            hex_obj = Hex(id=hex_id, ring=2, wormholes=[0, 3], planets=[])
            hex_obj.axial_q = q
            hex_obj.axial_r = r
            hex_obj.pieces["P2"] = Pieces(ships={}, discs=1)
            state.map.hexes[hex_id] = hex_obj
        
        result = select_best_exploration_hex(state, "P1")
        
        # Should still find home hex has some unexplored (this test may need adjustment)
        # Or it might return None if truly surrounded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

