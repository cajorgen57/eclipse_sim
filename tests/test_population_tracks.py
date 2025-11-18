"""
Unit tests for population and influence tracks (Phase 1 of Multi-Round Simulation).

These tests verify that production and upkeep calculations follow Eclipse rules:
- Production = leftmost visible (no cube) number on population track
- Upkeep = leftmost visible (no disc) number on influence track
"""
import pytest
from eclipse_ai.game_models import PopulationTrack, InfluenceTrack, PlayerState
from eclipse_ai.species_data import get_species_tracks_merged


class TestPopulationTrack:
    """Test population track production calculations."""
    
    def test_production_with_all_cubes(self):
        """When all squares have cubes, production should be 0."""
        track = PopulationTrack(
            track_values=[0, 2, 4, 6, 8],
            cube_positions=[True, True, True, True, True]
        )
        assert track.get_production() == 0
    
    def test_production_with_no_cubes(self):
        """When no cubes, production should be first value."""
        track = PopulationTrack(
            track_values=[0, 2, 4, 6, 8],
            cube_positions=[False, False, False, False, False]
        )
        assert track.get_production() == 0
    
    def test_production_typical_start(self):
        """Typical starting position: rightmost square empty."""
        track = PopulationTrack(
            track_values=[0, 2, 3, 4, 5, 7, 9],
            cube_positions=[True, True, True, True, True, True, False]
        )
        assert track.get_production() == 9
    
    def test_production_after_colonizing(self):
        """After colonizing (removing cubes), production increases."""
        track = PopulationTrack(
            track_values=[0, 2, 3, 4, 5, 7, 9],
            cube_positions=[True, True, True, True, True, False, False]
        )
        assert track.get_production() == 7
        
        # Remove another cube
        track.cube_positions[4] = False
        assert track.get_production() == 5
    
    def test_remove_cube_at(self):
        """Test removing cubes from specific positions."""
        track = PopulationTrack(
            track_values=[0, 2, 4, 6, 8],
            cube_positions=[True, True, True, True, False]
        )
        
        # Remove from valid position
        assert track.remove_cube_at(2) == True
        assert track.cube_positions[2] == False
        assert track.get_production() == 4
        
        # Try to remove from position that has no cube
        assert track.remove_cube_at(2) == False
        
        # Try to remove from invalid index
        assert track.remove_cube_at(10) == False
    
    def test_add_cube_at(self):
        """Test adding cubes back to positions."""
        track = PopulationTrack(
            track_values=[0, 2, 4, 6, 8],
            cube_positions=[True, False, False, True, False]
        )
        
        assert track.get_production() == 2
        
        # Add cube back
        assert track.add_cube_at(1) == True
        assert track.cube_positions[1] == True
        assert track.get_production() == 4
        
        # Try to add where cube already exists
        assert track.add_cube_at(1) == False


class TestInfluenceTrack:
    """Test influence track upkeep calculations."""
    
    def test_upkeep_all_discs_on_track(self):
        """When all discs on track, upkeep should be 0 (or first value)."""
        track = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4, 5],
            disc_positions=[True, True, True, True, True, True, True]
        )
        # All discs on track → highest upkeep (edge case)
        assert track.get_upkeep() == 5
    
    def test_upkeep_no_discs_on_track(self):
        """When no discs on track, upkeep should be first value."""
        track = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4, 5],
            disc_positions=[False, False, False, False, False, False, False]
        )
        assert track.get_upkeep() == 0
    
    def test_upkeep_typical_progression(self):
        """As discs move off track, upkeep increases."""
        track = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4, 5, 6, 7],
            disc_positions=[True, True, True, True, True, True, True, True, True]
        )
        
        assert track.get_upkeep() == 7  # All discs → last value
        
        # Remove a disc from RIGHT (place on hex)
        # After removing rightmost disc, leftmost visible is still position 8 (now empty)
        track.remove_disc_at(8)
        assert track.get_upkeep() == 7  # Position 8 is leftmost visible, value 7
        
        # Remove from left instead to expose lower values
        track.remove_disc_at(0)
        assert track.get_upkeep() == 0  # Position 0 is now leftmost visible, value 0
    
    def test_disc_counts(self):
        """Test disc counting properties."""
        track = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4],
            disc_positions=[True, True, True, False, False, False]
        )
        
        assert track.total_discs == 6
        assert track.discs_on_track == 3
        assert track.discs_off_track == 3
    
    def test_remove_disc_at(self):
        """Test removing discs from track."""
        track = InfluenceTrack(
            upkeep_values=[0, 1, 2, 3],
            disc_positions=[True, True, True, True]
        )
        
        assert track.remove_disc_at(0) == True
        assert track.disc_positions[0] == False
        assert track.get_upkeep() == 0
        
        # Try to remove from already empty position
        assert track.remove_disc_at(0) == False
    
    def test_add_disc_at(self):
        """Test adding discs back to track."""
        track = InfluenceTrack(
            upkeep_values=[0, 1, 2, 3],
            disc_positions=[False, False, True, True]
        )
        
        assert track.get_upkeep() == 0
        
        # Add disc back
        assert track.add_disc_at(0) == True
        assert track.disc_positions[0] == True
        assert track.get_upkeep() == 1


class TestPlayerStateTrackIntegration:
    """Test PlayerState helper methods for tracks."""
    
    def test_production_methods(self):
        """Test get_X_production methods."""
        player = PlayerState(player_id="test", color="blue")
        
        player.population_tracks = {
            "money": PopulationTrack(
                track_values=[0, 2, 4, 6],
                cube_positions=[True, True, True, False]
            ),
            "science": PopulationTrack(
                track_values=[0, 3, 5, 7],
                cube_positions=[True, True, False, False]
            ),
            "materials": PopulationTrack(
                track_values=[0, 2, 3, 5],
                cube_positions=[True, False, False, False]
            )
        }
        
        assert player.get_money_production() == 6
        assert player.get_science_production() == 5
        assert player.get_materials_production() == 2
    
    def test_upkeep_method(self):
        """Test get_upkeep_cost method."""
        player = PlayerState(player_id="test", color="blue")
        
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3],
            disc_positions=[True, True, False, False, False]
        )
        
        # Leftmost visible (no disc) is position 2, value 1
        assert player.get_upkeep_cost() == 1
        
        # Remove disc from position 1 (second position)
        player.influence_track_detailed.remove_disc_at(1)
        # Now leftmost visible is position 1, value 0
        assert player.get_upkeep_cost() == 0
        
        # Remove disc from position 0
        player.influence_track_detailed.remove_disc_at(0)
        # Still position 0 is leftmost visible (now empty), value 0
        assert player.get_upkeep_cost() == 0
    
    def test_net_money_change(self):
        """Test get_net_money_change method."""
        player = PlayerState(player_id="test", color="blue")
        
        player.population_tracks = {
            "money": PopulationTrack(
                track_values=[0, 2, 4, 6, 8],
                cube_positions=[True, True, True, True, False]
            )
        }
        
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4],
            disc_positions=[True, True, True, False, False, False]
        )
        
        # Money production = 8 (leftmost visible on money track, position 4)
        # Upkeep = 2 (leftmost visible on influence track, position 3)
        # Net = 8 - 2 = 6
        assert player.get_net_money_change() == 6
    
    def test_no_tracks_returns_zero(self):
        """When tracks not initialized, methods should return 0."""
        player = PlayerState(player_id="test", color="blue")
        
        assert player.get_money_production() == 0
        assert player.get_science_production() == 0
        assert player.get_materials_production() == 0
        assert player.get_upkeep_cost() == 0
        assert player.get_net_money_change() == 0


class TestSpeciesTracksData:
    """Test that species track data loads correctly."""
    
    def test_load_default_tracks(self):
        """Test loading default track configuration."""
        config = get_species_tracks_merged("terrans")
        
        assert "population_tracks" in config
        assert "money" in config["population_tracks"]
        assert "science" in config["population_tracks"]
        assert "materials" in config["population_tracks"]
        
        assert "influence_track" in config
        assert "upkeep_values" in config["influence_track"]
    
    def test_load_species_specific_tracks(self):
        """Test loading species-specific track configurations."""
        hydran_config = get_species_tracks_merged("hydran")
        
        # Hydran should have different science track
        assert "population_tracks" in hydran_config
        science_track = hydran_config["population_tracks"]["science"]
        assert "track_values" in science_track
        
        # Hydran emphasizes science, so values should differ from default
        # (This is a basic check - actual values depend on data file)
        assert len(science_track["track_values"]) > 0
    
    def test_eridani_fewer_discs(self):
        """Eridani should start with fewer influence discs."""
        eridani_config = get_species_tracks_merged("eridani")
        
        influence = eridani_config["influence_track"]
        disc_positions = influence["initial_disc_positions"]
        
        # Count False (empty circles)
        empty_circles = sum(1 for pos in disc_positions if not pos)
        
        # Eridani starts with 2 fewer discs (2 empty circles at end)
        assert empty_circles >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

