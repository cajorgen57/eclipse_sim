"""Game setup functions for creating proper turn 1 board states."""
from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List, Optional, Mapping

from .game_models import (
    GameState,
    PlayerState,
    MapState,
    Hex,
    Planet,
    Pieces,
    Resources,
    ShipDesign,
    TechDisplay,
    Disc,
    ColonyShips,
)
from .species_data import get_species, SpeciesConfig
from .state_assembler import _initialise_player_state, _refresh_player_economies
from .technology import _tech_tile_pool_path, load_tech_definitions, build_starting_tech_market
try:
    from .data.exploration_tiles import tile_counts_by_ring
except ImportError:
    # Fallback if exploration_tiles module not available
    def tile_counts_by_ring():
        return {1: 6, 2: 11, 3: 18}
from .resource_colors import RESOURCE_COLOR_ORDER


# Setup constants from SETUP_GUIDE.md
OUTER_SECTORS_BY_PLAYERS = {
    2: 5,
    3: 10,
    4: 14,
    5: 16,
    6: 18,
    7: 20,
    8: 22,
    9: 24

}

TECH_TILES_BY_PLAYERS = {
    2: 12,
    3: 14,
    4: 16,
    5: 18,
    6: 20,
    7: 22,
    8: 24,
    9: 26
}

# Starting sector hex IDs (middle ring, two hexes from center)
STARTING_SECTOR_IDS = list(range(220, 240))

# Valid Eclipse hex IDs based on official tile set
VALID_HEX_IDS = set(['GC', 'center'])
# Inner ring: 101-110 (homeworld and inner exploration tiles)
VALID_HEX_IDS.update([f'1{i:02d}' for i in range(1, 11)])
# Middle ring: 201-214 plus species starting sectors (220-239)
VALID_HEX_IDS.update([f'2{i:02d}' for i in range(1, 15)])
VALID_HEX_IDS.update([f'2{i:02d}' for i in range(20, 40)])  # Species sectors: 220-239
# Outer ring: 301-324
VALID_HEX_IDS.update([f'3{i:02d}' for i in range(1, 25)])


def new_game(
    num_players: int = 4,
    species_by_player: Optional[Mapping[str, str]] = None,
    seed: Optional[int] = None,
    ancient_homeworlds: bool = False,
    starting_round: int = 1,
) -> GameState:
    """
    Create a properly initialized turn 1 game state following Eclipse setup rules.
    
    This function sets up a complete game state ready for turn 1, including:
    - Galactic Center hex
    - Player homeworld hexes in inner ring (1xx)
    - Player starting sectors in middle ring (2xx) with proper hex placement
    - Player resources, techs, and ships from species.json
    - Proper exploration bags by ring (scaled to player count)
    - Tech display with appropriate tile counts
    - Ship designs initialized with default/base stats
    
    Args:
        num_players: Number of players (2-6)
        species_by_player: Optional mapping of player_id -> species_id. 
                          If None, all players use Terrans.
                          If partial, missing players default to Terrans.
                          Valid species IDs: terrans, orion, eridani, hydran, mechanema, etc.
                          See eclipse_ai/data/species.json for full list.
        seed: Random seed for setup randomization (currently unused, reserved for future use)
    
    Returns:
        GameState with proper board setup, players, exploration bags, and tech display.
        Ready for turn 1 action phase.
    
    Example:
        # All Terrans (default)
        state = new_game(num_players=4)
        
        # Mixed species
        state = new_game(
            num_players=4,
            species_by_player={
                "P1": "terrans",
                "P2": "orion",
                "P3": "eridani",
                "P4": "hydran"
            }
        )
        
        # Use in tests
        from eclipse_ai.game_setup import new_game
        from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner
        
        state = new_game(num_players=2, species_by_player={"you": "orion"})
        planner = PW_MCTSPlanner()
        plans = planner.plan(state)
    """
    if num_players < 2 or num_players > 9:
        raise ValueError(f"num_players must be 2-9, got {num_players}")
    
    # Generate player IDs if not provided
    if species_by_player is None:
        species_by_player = {}
    
    player_ids = list(species_by_player.keys())
    while len(player_ids) < num_players:
        player_ids.append(f"P{len(player_ids) + 1}")
    
    # Ensure all players have a species (default to Terrans)
    species_map: Dict[str, str] = {}
    for pid in player_ids:
        species_map[pid] = species_by_player.get(pid, "terrans")
    
    rng = random.Random(seed)

    # Create base state
    state = GameState(
        round=starting_round,
        active_player=player_ids[0],
        phase="ACTION",
        players={},
        map=MapState(),
        tech_display=TechDisplay(),
        bags={},
        exploration_tile_bags={},
        tech_definitions=load_tech_definitions(),
        turn_order=player_ids,
        turn_index=0,
    )
    
    # Setup board: Galactic Center
    _setup_galactic_center(state)
    
    # Setup players with proper starting sectors
    _setup_players(state, player_ids, species_map)
    print(f"[DEBUG] Created {len(state.players)} players: {list(state.players.keys())}")
    print(f"[DEBUG] Created {len(state.map.hexes)} hexes: {list(state.map.hexes.keys())}")
    
    # Setup ancient homeworlds if enabled
    if ancient_homeworlds:
        _setup_ancient_homeworlds(state, num_players)
        print(f"[DEBUG] After ancient homeworlds: {len(state.map.hexes)} hexes")
    
    # Setup exploration bags
    _setup_exploration_bags(state, num_players, rng)

    # Setup tech display
    _setup_tech_display(state, num_players, rng) # where is this defined? should not return none, shoukd return tech values right?
    
    # Initialize player states (techs, ship designs, etc.)
    for player in state.players.values():
        _initialise_player_state(player, state.tech_definitions)
    
    # Refresh economies
    _refresh_player_economies(state)
    
    # Set starting player
    state.starting_player = player_ids[0]
    state.active_player = player_ids[0]
    
    # Validate hex layout
    _validate_hex_layout(state)
    
    # If starting beyond round 1, simulate previous rounds
    if starting_round > 1:
        from .multi_round_runner import simulate_rounds
        print(f"[SETUP] Simulating rounds 1-{starting_round - 1} for game starting at round {starting_round}")
        
        try:
            state = simulate_rounds(
                state,
                start_round=1,
                end_round=starting_round - 1,
                planner_config={
                    "simulations": 50,  # Faster simulation for setup
                    "depth": 2,
                },
                verbose=True,
            )
            
            print(f"[SETUP] Multi-round simulation complete - Game ready for round {starting_round}")
            
        except Exception as e:
            print(f"[SETUP] Warning: Multi-round simulation encountered error: {e}")
            print(f"[SETUP] Continuing with round 1 state")
            # Reset to round 1 if simulation failed
            state.round = 1
    
    return state


def _setup_galactic_center(state: GameState) -> None:
    """Place the Galactic Center hex with GCDS tile at (0, 0)."""
    gc_hex = Hex(
        id="GC",
        ring=0,
        axial_q=0,
        axial_r=0,
        wormholes=[0, 1, 2, 3, 4, 5],  # Center connects in all directions
        has_gcds=True,
        explored=True,
        revealed=True,
        tile_number=1,  # Center is always last in combat order (special case)
        discovery_tile="pending",  # Center always has a discovery tile
    )
    state.map.hexes["GC"] = gc_hex


def _setup_players(
    state: GameState,
    player_ids: List[str],
    species_map: Dict[str, str],
) -> None:
    """Set up players with proper starting sectors, resources, ships, and colonies."""
    from .map.coordinates import get_starting_spot_coordinates, hex_id_to_axial
    
    # Get the six canonical starting positions (ring 2, two hexes from center)
    starting_spots = get_starting_spot_coordinates()
    print(f"[DEBUG] Setting up {len(player_ids)} players at positions: {starting_spots[:len(player_ids)]}")
    
    # Track used starting sector IDs to ensure uniqueness
    used_sector_ids = set()
    # Track how many times each species has been used (for selecting variant sectors)
    species_counts = {}
    
    for idx, player_id in enumerate(player_ids):
        species_id = species_map[player_id]
        species_config = get_species(species_id)
        print(f"[DEBUG] Setting up player {idx}: {player_id} ({species_id})")
        
        # Create player with base state
        player = PlayerState(
            player_id=player_id,
            color=_get_player_color(idx),
            resources=Resources(0, 0, 0),
            income=Resources(0, 0, 0),
            known_techs=[],
            ship_designs={},
        )
        
        # Apply species starting configuration
        _apply_species_to_player(state, player, species_config)
        
        # Get axial coordinates for this player's starting position
        if idx < len(starting_spots):
            axial_q, axial_r = starting_spots[idx]
        else:
            # Fallback if more than 6 players (use remaining spots)
            axial_q, axial_r = starting_spots[idx % len(starting_spots)]
        
        # Determine starting sector ID
        # Track how many times this species has been used
        if species_id not in species_counts:
            species_counts[species_id] = 0
        
        species_instance = species_counts[species_id]
        species_counts[species_id] += 1
        
        # Get species-specific starting sector
        species_base_sector = str(species_config.raw.get("starting_sector", ""))
        
        # Generate sector ID based on species rules:
        # - Alien species: use their specific sector (222, 224, 226, 228, 230, 232)
        # - Terrans: use odd numbers (220, 221, 223, 225, 227, 229, 231)
        if species_id == "terrans":
            # Terran sectors: 220 (base), 221, 223, 225, 227, 229, 231
            # Pattern: 220 + [0, 1, 3, 5, 7, 9, 11]
            terran_offsets = [0, 1, 3, 5, 7, 9, 11]
            offset = terran_offsets[species_instance] if species_instance < len(terran_offsets) else (species_instance * 2 - 1)
            starting_sector_id = f"{220 + offset}"
        elif species_base_sector and species_base_sector.isdigit():
            # Other species: use their specific sector number
            # Multiple players of same alien species is rare, but handle it with offset if needed
            base_num = int(species_base_sector)
            if species_instance == 0:
                starting_sector_id = species_base_sector
            else:
                # If multiple of same alien species, add even offset to avoid conflicts
                starting_sector_id = f"{base_num + (species_instance * 2)}"
            
            # Ensure uniqueness
            if starting_sector_id in used_sector_ids:
                # Fallback to next available sector
                fallback_num = 220
                while f"{fallback_num}" in used_sector_ids:
                    fallback_num += 1
                starting_sector_id = f"{fallback_num}"
        else:
            # Fallback to position-based (220 + index)
            starting_sector_id = f"{220 + idx}"
        
        used_sector_ids.add(starting_sector_id)
        
        starting_hex = _create_starting_sector(
            state, player, species_config, starting_sector_id, axial_q, axial_r
        )
        print(f"[DEBUG] Created hex {starting_sector_id} at ({axial_q}, {axial_r}) for player {player_id}")
        
        # Remove influence disc from track for starting hex colonization
        # In Eclipse, each colonized hex requires one influence disc
        if hasattr(player, 'influence_track_detailed') and player.influence_track_detailed:
            track = player.influence_track_detailed
            # Remove disc from leftmost position (first disc gets placed on starting hex)
            for i in range(len(track.disc_positions)):
                if track.disc_positions[i]:
                    track.remove_disc_at(i)
                    print(f"[DEBUG] Removed influence disc from track for {player_id}'s starting hex (now {track.discs_on_track} on track)")
                    break
        
        # Note: Inner ring hexes (101-108) are NOT starting positions
        # They are explored sector tiles to be drawn during the game
        
        state.players[player_id] = player


def _initialize_player_tracks(player: PlayerState, species_id: str) -> None:
    """
    Initialize population and influence tracks for a player based on species.
    
    Tracks are used to calculate production and upkeep during the Upkeep Phase.
    Production = leftmost visible (no cube) number on population track.
    Upkeep = leftmost visible (no disc) number on influence track.
    
    Reference: Eclipse Rulebook - Upkeep Phase
    """
    from .species_data import get_species_tracks_merged
    from .game_models import PopulationTrack, InfluenceTrack
    
    # Load track configuration for this species
    tracks_config = get_species_tracks_merged(species_id)
    
    # Initialize population tracks (money, science, materials)
    player.population_tracks = {}
    pop_tracks_config = tracks_config.get("population_tracks", {})
    
    for resource_type in ["money", "science", "materials"]:
        if resource_type in pop_tracks_config:
            track_config = pop_tracks_config[resource_type]
            player.population_tracks[resource_type] = PopulationTrack(
                track_values=list(track_config.get("track_values", [])),
                cube_positions=list(track_config.get("initial_cube_positions", []))
            )
    
    # Initialize influence track
    influence_config = tracks_config.get("influence_track", {})
    if influence_config:
        player.influence_track_detailed = InfluenceTrack(
            upkeep_values=list(influence_config.get("upkeep_values", [])),
            disc_positions=list(influence_config.get("initial_disc_positions", []))
        )
    
    # Initialize tracking lists
    player.discs_on_hexes = []
    player.discs_on_actions = {}
    player.cubes_on_hexes = {}


def _apply_species_to_player(
    state: GameState,
    player: PlayerState,
    species_config: SpeciesConfig,
) -> None:
    """Apply species configuration to a player."""
    raw = species_config.raw
    
    # Set species ID
    player.species_id = species_config.species_id
    
    # Initialize population and influence tracks
    _initialize_player_tracks(player, species_config.species_id)
    
    # Starting resources
    starting_resources = raw.get("starting_resources", {})
    player.resources.money = int(starting_resources.get("money", 0))
    player.resources.science = int(starting_resources.get("science", 0))
    player.resources.materials = int(starting_resources.get("materials", 0))
    
    # Starting techs
    starting_techs = raw.get("starting_techs", [])
    player.known_techs = list(starting_techs)
    
    # Colony ships
    # Default: 3 colony ships (1 of each color), but some species differ:
    # - Planta: 4 colony ships
    # - Enlightened: 2 colony ships
    colony_ships_count = int(raw.get("colony_ships", 3))
    player.colony_ships = ColonyShips()
    player.colony_ships.face_up = {
        "orange": 1,
        "pink": 1,
        "brown": 1,
        "wild": 0,
    }
    # Adjust if species has different colony ship count
    
    # Species-specific overrides
    player.action_overrides = dict(raw.get("action_overrides", {}))
    player.build_overrides = dict(raw.get("build_overrides", {}))
    player.move_overrides = dict(raw.get("move_overrides", {}))
    player.explore_overrides = dict(raw.get("explore_overrides", {}))
    player.cannot_build = set(raw.get("cannot_build", []))
    player.vp_bonuses = dict(raw.get("vp_bonuses", {}))
    player.species_flags = dict(raw.get("special_rules", {}))


def _create_homeworld_hex(
    state: GameState,
    player: PlayerState,
    species_config: SpeciesConfig,
    hex_id: str,
) -> Hex:
    """Create a homeworld hex in the inner ring for a player."""
    # Homeworld is typically just a placeholder hex with the player's starting colonies
    # For simplicity, we'll create a minimal hex - actual homeworld setup may vary
    hex_obj = Hex(
        id=hex_id,
        ring=1,  # Inner ring
        wormholes=[0, 1, 2, 3, 4, 5],  # Homeworld connects to all directions
        planets=[],  # Homeworld planets are typically on starting sector
        pieces={},
        explored=True,
        revealed=True,
    )
    state.map.hexes[hex_id] = hex_obj
    return hex_obj


def _create_starting_sector(
    state: GameState,
    player: PlayerState,
    species_config: SpeciesConfig,
    hex_id: str,
    axial_q: int,
    axial_r: int,
) -> Hex:
    """Create a starting sector hex for a player."""
    raw = species_config.raw
    
    # Create planets based on starting colonies
    planets = []
    starting_colonies = raw.get("starting_colonies", {}).get("home", {})
    for resource_type, count in starting_colonies.items():
        if count and count > 0:
            # Map resource types to planet types
            planet_type = _resource_to_planet_type(resource_type)
            for _ in range(int(count)):
                planets.append(Planet(type=planet_type, colonized_by=player.player_id))
    
    # Default: if no colonies specified, create standard 3 planets (Terran setup)
    if not planets:
        planets = [
            Planet(type="orange", colonized_by=player.player_id),
            Planet(type="pink", colonized_by=player.player_id),
            Planet(type="brown", colonized_by=player.player_id),
        ]
    
    # Create pieces for this player
    pieces = Pieces()
    
    # Starting ships
    # Species-specific starting ships:
    # - Terrans: 2 interceptors (default)
    # - Eridani: 1 interceptor, 1 cruiser
    # - Hydran: 2 interceptors
    # - Mechanema: 1 cruiser (not interceptor)
    # - Orion: 1 cruiser (not interceptor)
    # - Rho Indi: 2 interceptors
    starting_ships = raw.get("starting_ships", {}).get("home", {})
    if starting_ships:
        pieces.ships = {k: int(v) for k, v in starting_ships.items() if v and int(v) > 0}
    else:
        # Default Terran: 2 interceptors
        pieces.ships = {"interceptor": 2}
    
    # Starting influence disc
    pieces.discs = 1
    
    # Starting population cubes (colonies)
    starting_colonies = raw.get("starting_colonies", {}).get("home", {})
    for resource_type, count in starting_colonies.items():
        if count and count > 0:
            planet_color = _resource_to_planet_type(resource_type)
            pieces.cubes[planet_color] = pieces.cubes.get(planet_color, 0) + int(count)
    
    # Default: if no colonies specified, add standard cubes (Terran setup)
    if not pieces.cubes:
        pieces.cubes = {"orange": 1, "pink": 1, "brown": 1}
    
    # Starting structures (e.g., Exiles start with Orbital)
    starting_structures = raw.get("starting_structures", {}).get("home", {})
    if starting_structures:
        # Note: Structures are typically tracked separately, but we can note them here
        # Exiles start with 1 Orbital in their starting sector
        if starting_structures.get("orbital", 0) > 0:
            # Orbital is a structure, not a piece, but we note it for completeness
            pass  # Structures are typically handled separately in the game state
    
    # Create hex with axial coordinates
    from .map.coordinates import (
        axial_neighbors,
        direction_between_coords,
        ring_radius,
        rotate_to_face_direction,
    )
    
    # Calculate ring from coordinates
    hex_ring = ring_radius(axial_q, axial_r)
    
    # Determine wormholes and rotation to face center
    # Starting sectors typically have wormholes on 2-3 edges
    # For determinism, we orient one wormhole to face the galactic center
    base_wormholes = [0, 3]  # Default: opposite edges (E and W)
    
    # Find direction from this hex to center (0, 0)
    direction_to_center = direction_between_coords(axial_q, axial_r, 0, 0)
    rotation = 0
    if direction_to_center is not None:
        rotation = rotate_to_face_direction(base_wormholes, direction_to_center)
    
    # Apply rotation to get effective wormholes
    from .map.coordinates import effective_wormholes
    rotated_wormholes = effective_wormholes(base_wormholes, rotation)
    
    # Build neighbor links
    neighbors_dict = {}
    all_neighbors = axial_neighbors(axial_q, axial_r)
    for edge, (neighbor_q, neighbor_r) in all_neighbors.items():
        # Check if neighbor exists
        for existing_hex_id, existing_hex in state.map.hexes.items():
            if (
                hasattr(existing_hex, 'axial_q') and
                hasattr(existing_hex, 'axial_r') and
                existing_hex.axial_q == neighbor_q and
                existing_hex.axial_r == neighbor_r
            ):
                neighbors_dict[edge] = existing_hex_id
                # Update neighbor's link back to this hex
                from .map.coordinates import opposite_edge
                existing_hex.neighbors[opposite_edge(edge)] = hex_id
                break
    
    hex_obj = Hex(
        id=hex_id,
        ring=hex_ring,
        axial_q=axial_q,
        axial_r=axial_r,
        rotation=rotation,
        wormholes=rotated_wormholes,
        neighbors=neighbors_dict,
        planets=planets,
        pieces={player.player_id: pieces},
        explored=True,
        revealed=True,
        tile_number=int(hex_id) if hex_id.isdigit() else 200,  # Combat ordering
    )
    
    state.map.hexes[hex_id] = hex_obj
    
    # Update player colonies
    player.colonies[hex_id] = dict(pieces.cubes)
    
    # Initialize default ship designs if not already set
    # These are the base designs before any tech modifications
    # Tech grants will be applied by _initialise_player_state
    if not player.ship_designs:
        player.ship_designs = {
            "interceptor": ShipDesign(
                initiative=2,
                hull=1,
                cannons=1,
                drives=1,
            ),
            "cruiser": ShipDesign(
                computer=1,
                initiative=3,
                hull=2,
                cannons=1,
                drives=1,
            ),
            "dreadnought": ShipDesign(
                computer=1,
                shield=1,
                initiative=2,
                hull=3,
                cannons=2,
                drives=1,
            ),
            "starbase": ShipDesign(
                initiative=4,
                hull=2,
                cannons=2,
            ),
        }
    
    return hex_obj


def _get_starting_sector_wormholes(player_index: int) -> List[int]:
    """
    Get wormhole connections for starting sectors.
    
    Starting sectors are placed two hexes from center in middle ring.
    They connect to inner ring and can connect to outer ring.
    """
    # Standard starting sector has connections to adjacent positions
    # This is a simplified model - actual connections depend on precise placement
    # For now, return a reasonable default pattern
    base_connections = [0, 3]  # Opposite edges
    # Adjust based on position around the board
    offset = player_index % 6
    return [(c + offset) % 6 for c in base_connections]


def _resource_to_planet_type(resource: str) -> str:
    """Map resource type to planet color."""
    resource_lower = resource.lower()
    if resource_lower in ("money", "orange"):
        return "orange"
    elif resource_lower in ("science", "pink"):
        return "pink"
    elif resource_lower in ("materials", "brown"):
        return "brown"
    else:
        return "wild"


def _setup_ancient_homeworlds(state: GameState, num_players: int) -> None:
    """Create ancient homeworlds at unused starting spots.
    
    Ancient homeworlds are placed at the remaining starting positions
    (there are 6 total starting spots, so if 4 players, 2 ancient homeworlds).
    They contain ancient ships and some planets but no player pieces.
    """
    from .map.coordinates import (
        get_starting_spot_coordinates,
        axial_neighbors,
        direction_between_coords,
        ring_radius,
        rotate_to_face_direction,
        effective_wormholes,
        opposite_edge,
    )
    
    starting_spots = get_starting_spot_coordinates()
    
    # Create ancient homeworlds at unused spots
    for idx in range(num_players, len(starting_spots)):
        axial_q, axial_r = starting_spots[idx]
        hex_id = f"{240 + idx}"  # Use 240+ IDs for ancient homeworlds
        
        # Create planets (fewer than player homeworlds)
        planets = [
            Planet(type="orange"),
            Planet(type="brown"),
        ]
        
        # Calculate ring and wormholes
        hex_ring = ring_radius(axial_q, axial_r)
        base_wormholes = [0, 3]  # Opposite edges
        
        # Orient toward center
        direction_to_center = direction_between_coords(axial_q, axial_r, 0, 0)
        rotation = 0
        if direction_to_center is not None:
            rotation = rotate_to_face_direction(base_wormholes, direction_to_center)
        
        rotated_wormholes = effective_wormholes(base_wormholes, rotation)
        
        # Build neighbor links
        neighbors_dict = {}
        all_neighbors = axial_neighbors(axial_q, axial_r)
        for edge, (neighbor_q, neighbor_r) in all_neighbors.items():
            for existing_hex_id, existing_hex in state.map.hexes.items():
                if (
                    hasattr(existing_hex, 'axial_q') and
                    hasattr(existing_hex, 'axial_r') and
                    existing_hex.axial_q == neighbor_q and
                    existing_hex.axial_r == neighbor_r
                ):
                    neighbors_dict[edge] = existing_hex_id
                    existing_hex.neighbors[opposite_edge(edge)] = hex_id
                    break
        
        # Create ancient homeworld hex
        ancient_hex = Hex(
            id=hex_id,
            ring=hex_ring,
            axial_q=axial_q,
            axial_r=axial_r,
            rotation=rotation,
            wormholes=rotated_wormholes,
            neighbors=neighbors_dict,
            planets=planets,
            pieces={},  # No player pieces
            ancients=4,  # 4 ancient ships
            explored=True,
            revealed=True,
            tile_number=int(hex_id) if hex_id.isdigit() else 240,
        )
        
        state.map.hexes[hex_id] = ancient_hex


def _get_player_color(index: int) -> str:
    """Get a color for a player by index."""
    colors = ["orange", "blue", "teal", "green", "yellow", "purple"]
    return colors[index % len(colors)]


def _setup_exploration_bags(state: GameState, num_players: int, rng: random.Random) -> None:
    """Set up exploration bags with proper tile counts by ring."""
    tile_counts = tile_counts_by_ring()
    outer_limit = OUTER_SECTORS_BY_PLAYERS.get(num_players, 18)
    
    # Count already explored hexes by ring
    # Skip ring 0 (Galactic Center) as it's not part of exploration tiles
    explored_by_ring: Dict[int, int] = {}
    for hex_obj in state.map.hexes.values():
        ring = int(getattr(hex_obj, "ring", 1))
        if ring == 0:  # Skip Galactic Center
            continue
        if hex_obj.explored or hex_obj.revealed:
            explored_by_ring[ring] = explored_by_ring.get(ring, 0) + 1
    
    # Inner ring (I): Full set minus explored tiles
    inner_total = tile_counts.get(1, 11)
    inner_explored = explored_by_ring.get(1, 0)
    inner_remaining = max(0, inner_total - inner_explored)
    state.bags["R1"] = {"unknown": inner_remaining} if inner_remaining > 0 else {}
    
    # Middle ring (II): Full set minus explored tiles
    middle_total = tile_counts.get(2, 17)
    middle_explored = explored_by_ring.get(2, 0)
    middle_remaining = max(0, middle_total - middle_explored)
    state.bags["R2"] = {"unknown": middle_remaining} if middle_remaining > 0 else {}
    
    # Outer ring (III): Limited by player count (not yet explored)
    outer_total = tile_counts.get(3, 34)
    outer_limit_for_stack = min(outer_total, outer_limit)
    outer_explored = explored_by_ring.get(3, 0)
    outer_remaining = max(0, outer_limit_for_stack - outer_explored)
    outer_selection: List[str] = []
    if outer_remaining > 0:
        sector_three_tiles = _load_sector_tiles(3)
        draw_count = min(outer_remaining, len(sector_three_tiles))
        if draw_count:
            outer_selection = rng.sample(sector_three_tiles, draw_count)
    state.exploration_tile_bags["R3"] = list(outer_selection)
    state.bags["R3"] = {"unknown": outer_remaining} if outer_remaining > 0 else {}


def _setup_tech_display(state: GameState, num_players: int, rng: random.Random) -> None:
    """Set up tech display with proper tile counts."""
    tech_count = TECH_TILES_BY_PLAYERS.get(num_players, 16)

    owned_tech_names = {tech for player in state.players.values() for tech in (player.known_techs or [])}
    market_ids, tech_bags, tier_counts = build_starting_tech_market(tech_count, owned_tech_names, rng)

    state.tech_bags = tech_bags
    state.market = list(market_ids)

    # Map market ids to display names using loaded definitions
    definitions = state.tech_definitions or load_tech_definitions()
    available_names: List[str] = []
    for tech_id in market_ids:
        tech = definitions.get(tech_id)
        if tech is None:
            continue
        available_names.append(tech.name)
    state.tech_display.available = available_names

    # Ensure all tiers present even if zero draws occurred
    normalized_counts = {"I": 0, "II": 0, "III": 0}
    normalized_counts.update(tier_counts)
    state.tech_display.tier_counts = normalized_counts


_SECTOR_TILE_CACHE: Dict[int, List[str]] = {}


def _load_sector_tiles(sector: int) -> List[str]:
    """Load tile numbers for a given sector from the master CSV file."""

    if sector in _SECTOR_TILE_CACHE:
        return list(_SECTOR_TILE_CACHE[sector])

    tiles: List[str] = []
    csv_path = Path(__file__).resolve().parents[1] / "eclipse_tiles.csv"
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                try:
                    row_sector = int((row.get("Sector") or "").strip())
                except ValueError:
                    continue
                if row_sector != sector:
                    continue
                tile_number = row.get("TileNumber") or row.get("Tile") or row.get("id")
                if tile_number is None:
                    continue
                tile_str = str(tile_number).strip()
                if tile_str:
                    tiles.append(tile_str)
    except FileNotFoundError as exc:  # pragma: no cover - configuration error
        raise RuntimeError(f"Missing exploration tile data file at {csv_path}") from exc

    _SECTOR_TILE_CACHE[sector] = list(tiles)
    return list(tiles)


def _validate_hex_layout(state: GameState) -> None:
    """Validate that all hex IDs in the game state are valid Eclipse hex IDs."""
    invalid_hexes = []
    for hex_id in state.map.hexes.keys():
        if hex_id not in VALID_HEX_IDS:
            invalid_hexes.append(hex_id)
    
    if invalid_hexes:
        print(f"Warning: Invalid hex IDs found in game state: {invalid_hexes}")
        print(f"Valid hex IDs are: {sorted(VALID_HEX_IDS)}")


__all__ = ["new_game", "OUTER_SECTORS_BY_PLAYERS", "TECH_TILES_BY_PLAYERS", "_validate_hex_layout"]
