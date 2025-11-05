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
from .technology import load_tech_definitions, build_starting_tech_market
try:
    from .data.exploration_tiles import tile_counts_by_ring
except ImportError:
    # Fallback if exploration_tiles module not available
    def tile_counts_by_ring():
        return {1: 11, 2: 17, 3: 34}
from .resource_colors import RESOURCE_COLOR_ORDER


# Setup constants from SETUP_GUIDE.md
OUTER_SECTORS_BY_PLAYERS = {
    2: 5,
    3: 10,
    4: 14,
    5: 16,
    6: 18,
}

TECH_TILES_BY_PLAYERS = {
    2: 12,
    3: 14,
    4: 16,
    5: 18,
    6: 20,
}

# Starting sector hex IDs (middle ring, two hexes from center)
# These are the 6 entry points in the middle ring
STARTING_SECTOR_IDS = ["201", "202", "203", "204", "205", "206"]


def new_game(
    num_players: int = 4,
    species_by_player: Optional[Mapping[str, str]] = None,
    seed: Optional[int] = None,
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
    if num_players < 2 or num_players > 6:
        raise ValueError(f"num_players must be 2-6, got {num_players}")
    
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
        round=1,
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
    
    # Setup exploration bags
    _setup_exploration_bags(state, num_players, rng)

    # Setup tech display
    _setup_tech_display(state, num_players, rng)
    
    # Initialize player states (techs, ship designs, etc.)
    for player in state.players.values():
        _initialise_player_state(player, state.tech_definitions)
    
    # Refresh economies
    _refresh_player_economies(state)
    
    # Set starting player
    state.starting_player = player_ids[0]
    state.active_player = player_ids[0]
    
    return state


def _setup_galactic_center(state: GameState) -> None:
    """Place the Galactic Center hex with GCDS tile."""
    # Galactic Center is typically hex 0 or "GC" or similar
    # For now, we'll use a placeholder - actual implementation may vary
    gc_hex = Hex(
        id="GC",
        ring=0,
        wormholes=[],
        has_gcds=True,
        explored=True,
        revealed=True,
    )
    state.map.hexes["GC"] = gc_hex


def _setup_players(
    state: GameState,
    player_ids: List[str],
    species_map: Dict[str, str],
) -> None:
    """Set up players with proper starting sectors, resources, ships, and colonies."""
    # Get tile counts for exploration bag calculation
    tile_counts = tile_counts_by_ring()
    
    for idx, player_id in enumerate(player_ids):
        species_id = species_map[player_id]
        species_config = get_species(species_id)
        
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
        
        # Create homeworld hex in inner ring (1xx)
        homeworld_id = f"1{str(idx + 1).zfill(2)}"
        _create_homeworld_hex(state, player, species_config, homeworld_id)
        
        # Create starting sector hex
        # Use species starting_sector from species.json
        # Species-specific starting sectors:
        # Base game: Eridani 222, Hydran 224, Planta 226, Draco 228, Mechanema 230, Orion 232
        # RotA: Magellan 233/235/237, Exiles 234, Rho Indi 236, Enlightened 238
        # SotR: Octantis/Pyxis/Shapers 241-244
        species_sector = str(species_config.raw.get("starting_sector", ""))
        if species_sector and species_sector.isdigit():
            starting_sector_id = species_sector
        else:
            # Fallback to default positions if species doesn't specify
            starting_sector_id = STARTING_SECTOR_IDS[idx % len(STARTING_SECTOR_IDS)]
        
        starting_hex = _create_starting_sector(
            state, player, species_config, starting_sector_id
        )
        
        state.players[player_id] = player


def _apply_species_to_player(
    state: GameState,
    player: PlayerState,
    species_config: SpeciesConfig,
) -> None:
    """Apply species configuration to a player."""
    raw = species_config.raw
    
    # Set species ID
    player.species_id = species_config.species_id
    
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
    
    # Influence discs: start with all on track (default setup)
    # The SETUP_GUIDE says "Place 1 disc on each circle of the Influence track"
    # We'll initialize with a reasonable default (typically 9-10 discs)
    player.influence_discs = 9  # Default starting count
    discs_delta = raw.get("starting_discs_delta", 0)
    if discs_delta:
        player.influence_discs = max(0, player.influence_discs + int(discs_delta))
    
    # Create influence discs on track
    for i in range(player.influence_discs):
        player.influence_track.append(Disc(id=f"{player.player_id}-disc-{i+1}"))


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
    
    # Create hex
    # Determine ring from hex ID: 1xx = ring 1, 2xx = ring 2, 3xx = ring 3
    # Starting sectors vary: Base game species use 2xx (ring 2), some RotA/SotR use 2xx or 3xx
    hex_ring = int(hex_id[0]) if hex_id and hex_id[0].isdigit() else 2
    
    hex_obj = Hex(
        id=hex_id,
        ring=hex_ring,
        wormholes=_get_starting_sector_wormholes(len(state.players)),
        planets=planets,
        pieces={player.player_id: pieces},
        explored=True,
        revealed=True,
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
                drive=1,  # Legacy compatibility
            ),
            "cruiser": ShipDesign(
                computer=1,
                initiative=3,
                hull=2,
                cannons=1,
                drives=1,
                drive=1,
            ),
            "dreadnought": ShipDesign(
                computer=1,
                shield=1,
                initiative=2,
                hull=3,
                cannons=2,
                drives=1,
                drive=1,
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


__all__ = ["new_game", "OUTER_SECTORS_BY_PLAYERS", "TECH_TILES_BY_PLAYERS"]
