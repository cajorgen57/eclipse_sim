"""
Unit tests for upkeep and production engine (Phase 2 of Multi-Round Simulation).

Tests verify that upkeep mechanics follow Eclipse rules:
- Production calculated from tracks
- Upkeep paid from money
- Resources can be traded 3:1 to money
- Discs can be removed to reduce upkeep
- Players collapse if they can't pay
"""
import pytest
from eclipse_ai.game_models import (
    GameState, PlayerState, MapState, Hex, Pieces, Resources,
    PopulationTrack, InfluenceTrack
)
from eclipse_ai.upkeep import (
    calculate_production,
    calculate_upkeep_cost,
    can_afford_upkeep,
    trade_resources_to_money,
    remove_influence_discs_for_upkeep,
    apply_upkeep,
    apply_upkeep_all_players,
)


def create_test_player(
    player_id: str = "test",
    money: int = 10,
    science: int = 10,
    materials: int = 10,
    money_prod: int = 5,
    upkeep: int = 2,
) -> PlayerState:
    """Helper to create a test player with tracks."""
    player = PlayerState(player_id=player_id, color="blue")
    player.resources = Resources(money=money, science=science, materials=materials)
    
    # Setup population tracks
    player.population_tracks = {
        "money": PopulationTrack(
            track_values=[0, 2, 4, 6, 8, 10, 12],
            cube_positions=[True] * 6 + [False]  # Last one empty → prod = 12
        ),
        "science": PopulationTrack(
            track_values=[0, 2, 4, 6, 8, 10, 12],
            cube_positions=[True] * 6 + [False]
        ),
        "materials": PopulationTrack(
            track_values=[0, 2, 4, 6, 8, 10, 12],
            cube_positions=[True] * 6 + [False]
        ),
    }
    
    # Adjust to get desired production by manipulating cube positions
    # (This is a simplification for testing)
    
    # Setup influence track
    player.influence_track_detailed = InfluenceTrack(
        upkeep_values=[0, 0, 1, 2, 3, 4, 5, 6],
        disc_positions=[True] * 8  # All discs on track → low upkeep
    )
    
    return player


class TestCalculateProduction:
    """Test production calculation."""
    
    def test_calculate_production_basic(self):
        """Test basic production calculation."""
        player = create_test_player()
        
        production = calculate_production(player)
        
        assert "money" in production
        assert "science" in production
        assert "materials" in production
        assert all(p >= 0 for p in production.values())
    
    def test_production_with_different_tracks(self):
        """Test production with asymmetric tracks."""
        player = PlayerState(player_id="test", color="blue")
        
        player.population_tracks = {
            "money": PopulationTrack(
                track_values=[0, 2, 4, 6, 8],
                cube_positions=[True, True, True, False, False]
            ),
            "science": PopulationTrack(
                track_values=[0, 3, 5, 7, 9],
                cube_positions=[True, True, False, False, False]
            ),
            "materials": PopulationTrack(
                track_values=[0, 2, 3, 5, 7],
                cube_positions=[True, False, False, False, False]
            ),
        }
        
        production = calculate_production(player)
        
        assert production["money"] == 6
        assert production["science"] == 5
        assert production["materials"] == 2


class TestCalculateUpkeep:
    """Test upkeep cost calculation."""
    
    def test_calculate_upkeep_basic(self):
        """Test basic upkeep calculation."""
        player = create_test_player()
        
        upkeep = calculate_upkeep_cost(player)
        
        assert upkeep >= 0
    
    def test_upkeep_with_discs_removed(self):
        """Test upkeep increases as discs are removed."""
        player = PlayerState(player_id="test", color="blue")
        
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4, 5],
            disc_positions=[True, True, True, True, True, True, True]
        )
        
        assert calculate_upkeep_cost(player) == 5  # All discs → highest
        
        # Remove discs from left to expose lower costs
        player.influence_track_detailed.remove_disc_at(0)
        assert calculate_upkeep_cost(player) == 0  # Leftmost empty = pos 0
        
        # Removing another disc still leaves leftmost at pos 0
        player.influence_track_detailed.remove_disc_at(1)
        assert calculate_upkeep_cost(player) == 0  # Still leftmost empty = pos 0
        
        # But if we start with discs only on right...
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 0, 1, 2, 3, 4, 5],
            disc_positions=[False, False, True, True, True, True, True]
        )
        assert calculate_upkeep_cost(player) == 0  # Leftmost empty = pos 0
        
        # Remove disc at pos 2 doesn't change leftmost empty
        player.influence_track_detailed.remove_disc_at(2)
        assert calculate_upkeep_cost(player) == 0  # Still pos 0


class TestCanAffordUpkeep:
    """Test bankruptcy detection."""
    
    def test_can_afford_with_plenty_money(self):
        """Player with enough money can afford upkeep."""
        player = create_test_player(money=20)
        production = {"money": 5, "science": 5, "materials": 5}
        upkeep = 3
        
        assert can_afford_upkeep(player, production, upkeep) == True
    
    def test_cannot_afford_with_low_money(self):
        """Player with insufficient money cannot afford upkeep."""
        player = create_test_player(money=2)
        production = {"money": 1, "science": 5, "materials": 5}
        upkeep = 5  # Net: 2 + 1 - 5 = -2
        
        assert can_afford_upkeep(player, production, upkeep) == False
    
    def test_exactly_zero_is_affordable(self):
        """Player ending at exactly 0 money can afford."""
        player = create_test_player(money=4)
        production = {"money": 2, "science": 0, "materials": 0}
        upkeep = 6  # Net: 4 + 2 - 6 = 0
        
        assert can_afford_upkeep(player, production, upkeep) == True


class TestTradeResources:
    """Test resource trading for bankruptcy."""
    
    def test_trade_science_to_money(self):
        """Test trading science at 3:1 ratio."""
        player = create_test_player(money=5, science=9, materials=0)
        
        money_gained = trade_resources_to_money(player, 2)
        
        assert money_gained == 2
        assert player.resources.science == 3  # 9 - 6 = 3
        assert player.resources.money == 7   # 5 + 2 = 7
    
    def test_trade_materials_to_money(self):
        """Test trading materials at 3:1 ratio."""
        player = create_test_player(money=5, science=0, materials=12)
        
        money_gained = trade_resources_to_money(player, 3)
        
        assert money_gained == 3
        assert player.resources.materials == 3  # 12 - 9 = 3
        assert player.resources.money == 8  # 5 + 3 = 8
    
    def test_trade_both_resources(self):
        """Test trading both science and materials."""
        player = create_test_player(money=0, science=6, materials=6)
        
        money_gained = trade_resources_to_money(player, 4)
        
        assert money_gained == 4
        assert player.resources.science == 0   # All science traded first
        assert player.resources.materials == 0  # Then 6 materials traded
        assert player.resources.money == 4
    
    def test_trade_insufficient_resources(self):
        """Test trading when not enough resources available."""
        player = create_test_player(money=0, science=4, materials=2)
        
        # Can only trade science once (need 3), can't trade materials (need 3)
        money_gained = trade_resources_to_money(player, 5)
        
        assert money_gained == 1  # Only got 1 money from science
        assert player.resources.science == 1  # 4 - 3 = 1
        assert player.resources.materials == 2  # Unchanged (insufficient)


class TestRemoveInfluenceDiscs:
    """Test disc removal for bankruptcy."""
    
    def test_remove_disc_reduces_upkeep(self):
        """Removing disc from hex reduces upkeep."""
        state = GameState(
            round=1,
            active_player="test",
            players={},
            map=MapState(),
        )
        
        player = create_test_player()
        player.discs_on_hexes = ["220", "221"]
        player.cubes_on_hexes = {
            "220": {"money": 1, "science": 1},
            "221": {"materials": 1},
        }
        
        # Setup hexes in map
        state.map.hexes["220"] = Hex(
            id="220",
            ring=2,
            wormholes=[0, 3],
            planets=[],
            pieces={player.player_id: Pieces(ships={}, discs=1, cubes={})},
        )
        state.map.hexes["221"] = Hex(
            id="221",
            ring=2,
            wormholes=[1, 4],
            planets=[],
            pieces={player.player_id: Pieces(ships={}, discs=1, cubes={})},
        )
        
        discs_removed, money_saved = remove_influence_discs_for_upkeep(
            state, player, money_needed=10
        )
        
        assert discs_removed >= 1
        assert len(player.discs_on_hexes) < 2


class TestApplyUpkeep:
    """Test full upkeep application."""
    
    def test_apply_upkeep_normal(self):
        """Test normal upkeep (can afford)."""
        state = GameState(
            round=1,
            active_player="test",
            players={},
            map=MapState(),
        )
        
        player = create_test_player(money=10, science=5, materials=5)
        state.players["test"] = player
        
        result = apply_upkeep(state, "test")
        
        assert result["collapsed"] == False
        assert result["traded_resources"] == False
        assert result["discs_removed"] == 0
        assert player.resources.money >= 0
        assert player.resources.science > 5  # Production added
        assert player.resources.materials > 5
    
    def test_apply_upkeep_with_trading(self):
        """Test upkeep with resource trading."""
        state = GameState(
            round=1,
            active_player="test",
            players={},
            map=MapState(),
        )
        
        player = create_test_player(money=1, science=9, materials=0)
        # Set production low and upkeep high
        player.population_tracks["money"] = PopulationTrack(
            track_values=[0, 1, 2],
            cube_positions=[True, True, False]  # Prod = 2
        )
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 5, 10],
            disc_positions=[True, False, False]  # Upkeep = 5
        )
        
        state.players["test"] = player
        
        # Money: 1 + 2 - 5 = -2, needs trading
        result = apply_upkeep(state, "test")
        
        assert result["traded_resources"] == True or result["discs_removed"] > 0
        assert player.resources.money >= 0
    
    def test_apply_upkeep_collapse(self):
        """Test player collapse when can't pay."""
        state = GameState(
            round=1,
            active_player="test",
            players={},
            map=MapState(),
        )
        
        player = create_test_player(money=0, science=0, materials=0)
        player.discs_on_hexes = []  # No discs to remove
        
        # Set high upkeep
        player.population_tracks["money"] = PopulationTrack(
            track_values=[0, 1],
            cube_positions=[True, False]  # Prod = 1
        )
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=[0, 10],
            disc_positions=[True, False]  # Upkeep = 10
        )
        
        state.players["test"] = player
        
        # Money: 0 + 1 - 10 = -9, no resources to trade, no discs to remove
        result = apply_upkeep(state, "test")
        
        assert result["collapsed"] == True
        assert player.collapsed == True


class TestApplyUpkeepAllPlayers:
    """Test upkeep for multiple players."""
    
    def test_all_players(self):
        """Test applying upkeep to all players."""
        state = GameState(
            round=1,
            active_player="P1",
            players={},
            map=MapState(),
        )
        
        # Add three players
        for i in range(1, 4):
            player_id = f"P{i}"
            player = create_test_player(player_id=player_id, money=10 + i)
            state.players[player_id] = player
        
        results = apply_upkeep_all_players(state)
        
        assert len(results) == 3
        assert all(player_id in results for player_id in ["P1", "P2", "P3"])
        
        # All players should still be alive
        for player in state.players.values():
            assert not player.collapsed
            assert player.resources.money >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

