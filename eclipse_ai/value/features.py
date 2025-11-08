from __future__ import annotations

from statistics import mean
from typing import Any, Dict


def extract_features(state: Any, context: Any | None = None) -> Dict[str, float]:
    """
    Extract comprehensive normalized heuristic features from a game state.
    
    Features are organized into categories:
    - VP & Scoring: Current VP, reputation, discoveries
    - Economy: Resources, income, upkeep efficiency  
    - Military: Fleet strength, ship quality, tech level
    - Territory: Hex control, planet coverage, connectivity
    - Strategic: Tech diversity, action efficiency, positioning
    - Threats: Enemy pressure, danger zones, vulnerability
    
    Args:
        state: GameState object with players, map, and game configuration
        context: Optional context with opponent models and threat assessments
        
    Returns:
        Dictionary of feature_name -> normalized_value pairs
    """
    feats: Dict[str, float] = {}
    
    # Get active player for focused evaluation
    active_player_id = getattr(state, "active_player", None) or getattr(state, "active_player_id", "you")
    players = getattr(state, "players", {})
    player = players.get(active_player_id) if players else None
    
    if player is None:
        # Return minimal features if no player state
        return _minimal_features(state, context)
    
    # ===== VP & Scoring Features =====
    feats.update(_extract_vp_features(state, player))
    
    # ===== Economy Features =====
    feats.update(_extract_economy_features(state, player))
    
    # ===== Military Features =====
    feats.update(_extract_military_features(state, player))
    
    # ===== Territory Features =====
    feats.update(_extract_territory_features(state, player, active_player_id))
    
    # ===== Strategic Position Features =====
    feats.update(_extract_strategic_features(state, player))
    
    # ===== Threat & Opposition Features =====
    feats.update(_extract_threat_features(state, player, active_player_id, context))
    
    return feats


def _minimal_features(state: Any, context: Any | None) -> Dict[str, float]:
    """Return minimal feature set when player state unavailable."""
    return {
        "vp_now": float(getattr(state, "vp", 0.0)),
        "round_index": float(getattr(state, "round_index", 1)),
    }


def _extract_vp_features(state: Any, player: Any) -> Dict[str, float]:
    """Extract VP and scoring-related features."""
    feats = {}
    
    # Direct VP (if tracked)
    feats["vp_now"] = float(getattr(state, "vp", 0.0) or getattr(player, "vp", 0.0))
    
    # Reputation tiles (key VP source)
    reputation = getattr(player, "reputation", [])
    if reputation:
        feats["reputation_tiles"] = float(len(reputation))
        feats["reputation_value"] = float(sum(reputation))
    else:
        feats["reputation_tiles"] = 0.0
        feats["reputation_value"] = 0.0
    
    # Discovery tiles
    feats["discoveries"] = float(getattr(player, "discoveries_kept", 0))
    
    # Monoliths (3 VP each typically)
    feats["monoliths"] = float(getattr(player, "monolith_count", 0))
    
    # Ambassadors (can convert to VP)
    feats["ambassadors"] = float(getattr(player, "ambassadors", 0) or len(getattr(player, "ambassadors", {})))
    
    return feats


def _extract_economy_features(state: Any, player: Any) -> Dict[str, float]:
    """Extract economic health features."""
    feats = {}
    
    # Current resources
    resources = getattr(player, "resources", None)
    if resources:
        feats["money"] = float(getattr(resources, "money", 0))
        feats["science"] = float(getattr(resources, "science", 0))
        feats["materials"] = float(getattr(resources, "materials", 0))
        feats["total_resources"] = feats["money"] + feats["science"] + feats["materials"]
    else:
        feats["money"] = feats["science"] = feats["materials"] = feats["total_resources"] = 0.0
    
    # Income per turn
    income = getattr(player, "income", None)
    if income:
        feats["money_income"] = float(getattr(income, "money", 0))
        feats["science_income"] = float(getattr(income, "science", 0))
        feats["materials_income"] = float(getattr(income, "materials", 0))
        feats["total_income"] = feats["money_income"] + feats["science_income"] + feats["materials_income"]
    else:
        feats["money_income"] = feats["science_income"] = feats["materials_income"] = feats["total_income"] = 0.0
    
    # Economy object (if available)
    economy = getattr(player, "economy", None)
    if economy:
        feats["orange_bank"] = float(getattr(economy, "orange_bank", 0))
        feats["orange_income"] = float(getattr(economy, "orange_income", 0))
        feats["orange_upkeep"] = float(getattr(economy, "orange_upkeep_fixed", 0))
        feats["action_slots_filled"] = float(getattr(economy, "action_slots_filled", 0))
        
        # Economic efficiency: net income after upkeep
        net_income = feats["orange_income"] - feats["orange_upkeep"]
        feats["orange_net_income"] = float(net_income)
        feats["orange_efficiency"] = float(net_income / max(1, feats["orange_income"])) if feats["orange_income"] > 0 else 0.0
        
        # Action capacity
        max_actions = getattr(economy, "max_additional_actions", lambda: 0)()
        feats["action_capacity"] = float(max_actions)
    else:
        feats["orange_bank"] = feats["orange_income"] = feats["orange_upkeep"] = 0.0
        feats["action_slots_filled"] = feats["orange_net_income"] = feats["orange_efficiency"] = 0.0
        feats["action_capacity"] = 0.0
    
    # Influence discs (upkeep cost indicator)
    feats["influence_discs"] = float(getattr(player, "influence_discs", 0))
    feats["spare_discs"] = max(0.0, 13.0 - feats["influence_discs"] - feats["action_slots_filled"])
    
    return feats


def _extract_military_features(state: Any, player: Any) -> Dict[str, float]:
    """Extract military strength and capability features."""
    feats = {}
    
    # Ship designs quality
    ship_designs = getattr(player, "ship_designs", {})
    
    total_firepower = 0.0
    total_defense = 0.0
    total_mobility = 0.0
    ship_classes = ["interceptor", "cruiser", "dreadnought", "starbase"]
    
    for ship_class in ship_classes:
        design = ship_designs.get(ship_class)
        if design:
            cannons = float(getattr(design, "cannons", 0))
            missiles = float(getattr(design, "missiles", 0))
            computer = float(getattr(design, "computer", 0))
            shield = float(getattr(design, "shield", 0))
            hull = float(getattr(design, "hull", 1))
            initiative = float(getattr(design, "initiative", 0))
            drives = float(getattr(design, "drives", 0) or getattr(design, "drive", 0))
            
            # Store per-class stats
            feats[f"{ship_class}_firepower"] = cannons + 0.8 * missiles
            feats[f"{ship_class}_defense"] = hull + 0.5 * shield + 0.3 * computer
            feats[f"{ship_class}_mobility"] = drives
            feats[f"{ship_class}_initiative"] = initiative
            
            total_firepower += feats[f"{ship_class}_firepower"]
            total_defense += feats[f"{ship_class}_defense"]
            total_mobility += feats[f"{ship_class}_mobility"]
        else:
            feats[f"{ship_class}_firepower"] = 0.0
            feats[f"{ship_class}_defense"] = 0.0
            feats[f"{ship_class}_mobility"] = 0.0
            feats[f"{ship_class}_initiative"] = 0.0
    
    feats["total_firepower_designs"] = total_firepower
    feats["total_defense_designs"] = total_defense
    feats["avg_mobility"] = total_mobility / 4.0
    
    # Fleet composition (actual ships on board)
    fleet_counts = {"interceptor": 0, "cruiser": 0, "dreadnought": 0, "starbase": 0}
    map_state = getattr(state, "map", None)
    if map_state:
        hexes = getattr(map_state, "hexes", {})
        player_id = getattr(player, "player_id", "you")
        for hex_obj in hexes.values():
            pieces = getattr(hex_obj, "pieces", {}).get(player_id)
            if pieces:
                ships = getattr(pieces, "ships", {})
                for ship_class, count in ships.items():
                    if ship_class in fleet_counts:
                        fleet_counts[ship_class] += int(count)
                starbase = getattr(pieces, "starbase", 0)
                fleet_counts["starbase"] += int(starbase)
    
    feats["fleet_interceptors"] = float(fleet_counts["interceptor"])
    feats["fleet_cruisers"] = float(fleet_counts["cruiser"])
    feats["fleet_dreadnoughts"] = float(fleet_counts["dreadnought"])
    feats["fleet_starbases"] = float(fleet_counts["starbase"])
    feats["total_fleet_size"] = sum(float(c) for c in fleet_counts.values())
    
    # Fleet power (composition × quality)
    fleet_power = 0.0
    for ship_class, count in fleet_counts.items():
        if count > 0:
            firepower = feats.get(f"{ship_class}_firepower", 0.0)
            defense = feats.get(f"{ship_class}_defense", 1.0)
            fleet_power += count * (firepower + 0.5 * defense)
    feats["fleet_power"] = fleet_power
    
    return feats


def _extract_territory_features(state: Any, player: Any, player_id: str) -> Dict[str, float]:
    """Extract territorial control features."""
    feats = {}
    
    map_state = getattr(state, "map", None)
    if not map_state:
        return {
            "controlled_hexes": 0.0,
            "colonized_planets": 0.0,
            "planet_diversity": 0.0,
        }
    
    hexes = getattr(map_state, "hexes", {})
    controlled_hexes = 0
    colonized_planets = {"orange": 0, "pink": 0, "brown": 0, "wild": 0}
    total_planets = 0
    has_influence_disc = 0
    
    for hex_obj in hexes.values():
        pieces = getattr(hex_obj, "pieces", {}).get(player_id)
        if pieces:
            # Control indicated by discs or ships
            discs = int(getattr(pieces, "discs", 0))
            ships = getattr(pieces, "ships", {})
            starbase = int(getattr(pieces, "starbase", 0))
            
            if discs > 0 or starbase > 0 or sum(ships.values()) > 0:
                controlled_hexes += 1
            
            if discs > 0:
                has_influence_disc += 1
        
        # Count colonized planets
        planets = getattr(hex_obj, "planets", [])
        for planet in planets:
            if getattr(planet, "colonized_by", None) == player_id:
                planet_type = getattr(planet, "type", "").lower()
                if "orange" in planet_type or "money" in planet_type:
                    colonized_planets["orange"] += 1
                elif "pink" in planet_type or "science" in planet_type:
                    colonized_planets["pink"] += 1
                elif "brown" in planet_type or "material" in planet_type:
                    colonized_planets["brown"] += 1
                elif "wild" in planet_type:
                    colonized_planets["wild"] += 1
                total_planets += 1
    
    feats["controlled_hexes"] = float(controlled_hexes)
    feats["influence_hexes"] = float(has_influence_disc)
    feats["colonized_planets"] = float(total_planets)
    feats["orange_planets"] = float(colonized_planets["orange"])
    feats["pink_planets"] = float(colonized_planets["pink"])
    feats["brown_planets"] = float(colonized_planets["brown"])
    feats["wild_planets"] = float(colonized_planets["wild"])
    
    # Planet diversity (balanced economy is valuable)
    planet_counts = [colonized_planets["orange"], colonized_planets["pink"], colonized_planets["brown"]]
    feats["planet_diversity"] = float(min(planet_counts)) if total_planets > 0 else 0.0
    
    # Connectivity (from state if available)
    connectivity = getattr(state, "connectivity_metrics", {}).get(player_id, {})
    feats["reachable_hexes"] = float(connectivity.get("count", 0))
    
    return feats


def _extract_strategic_features(state: Any, player: Any) -> Dict[str, float]:
    """Extract strategic position features."""
    feats = {}
    
    # Technology advancement
    owned_tech_ids = getattr(player, "owned_tech_ids", set())
    feats["tech_count"] = float(len(owned_tech_ids))
    
    # Tech diversity across categories
    tech_by_category = getattr(player, "tech_count_by_category", {})
    feats["military_tech"] = float(tech_by_category.get("military", 0))
    feats["grid_tech"] = float(tech_by_category.get("grid", 0))
    feats["nano_tech"] = float(tech_by_category.get("nano", 0))
    
    # Wormhole generator is strategically important
    feats["has_wormhole_generator"] = 1.0 if getattr(player, "has_wormhole_generator", False) else 0.0
    
    # Action flexibility
    feats["has_passed"] = 1.0 if getattr(player, "passed", False) else 0.0
    feats["is_collapsed"] = 1.0 if getattr(player, "collapsed", False) else 0.0
    
    # Round progression
    round_index = getattr(state, "round_index", 1) or getattr(state, "round", 1)
    feats["round_index"] = float(round_index)
    feats["early_game"] = 1.0 if round_index <= 2 else 0.0
    feats["mid_game"] = 1.0 if 3 <= round_index <= 6 else 0.0
    feats["late_game"] = 1.0 if round_index >= 7 else 0.0
    
    return feats


def _extract_threat_features(state: Any, player: Any, player_id: str, context: Any | None) -> Dict[str, float]:
    """Extract threat assessment and enemy-related features."""
    feats = {}
    
    # Opponent modeling from context
    if context is not None:
        threat_map = getattr(context, "threat_map", None)
        if threat_map is not None:
            danger_values = []
            for sector_danger in getattr(threat_map, "danger", {}).values():
                danger_values.extend(float(v) for v in sector_danger.values())
            danger_max = max(getattr(threat_map, "danger_by_opponent", {}).values(), default=0.0)
            feats["danger_max"] = float(danger_max)
            feats["danger_mean"] = float(mean(danger_values)) if danger_values else 0.0
        else:
            feats["danger_max"] = 0.0
            feats["danger_mean"] = 0.0

        opponent_models = getattr(context, "opponent_models", {}) or {}
        if opponent_models:
            agg_aggression = max(
                (getattr(model, "metrics", None) and getattr(model.metrics, "aggression", 0.0) or 0.0 
                 for model in opponent_models.values()),
                default=0.0,
            )
            agg_tech = max(
                (getattr(model, "metrics", None) and getattr(model.metrics, "tech_pace", 0.0) or 0.0
                 for model in opponent_models.values()),
                default=0.0,
            )
        else:
            agg_aggression = 0.0
            agg_tech = 0.0
        feats["opp_aggression_max"] = float(agg_aggression)
        feats["opp_tech_max"] = float(agg_tech)
    else:
        feats["danger_max"] = 0.0
        feats["danger_mean"] = 0.0
        feats["opp_aggression_max"] = 0.0
        feats["opp_tech_max"] = 0.0
    
    # Direct enemy presence analysis
    map_state = getattr(state, "map", None)
    if map_state:
        hexes = getattr(map_state, "hexes", {})
        enemy_ships_total = 0
        contested_hexes = 0
        
        for hex_obj in hexes.values():
            pieces_dict = getattr(hex_obj, "pieces", {})
            player_ships = 0
            enemy_ships = 0
            
            player_pieces = pieces_dict.get(player_id)
            if player_pieces:
                player_ships = sum(getattr(player_pieces, "ships", {}).values())
                player_ships += int(getattr(player_pieces, "starbase", 0))
            
            for pid, pieces in pieces_dict.items():
                if pid != player_id:
                    enemy_ships += sum(getattr(pieces, "ships", {}).values())
                    enemy_ships += int(getattr(pieces, "starbase", 0))
            
            if player_ships > 0 and enemy_ships > 0:
                contested_hexes += 1
            
            enemy_ships_total += enemy_ships
        
        feats["enemy_ships_total"] = float(enemy_ships_total)
        feats["contested_hexes"] = float(contested_hexes)
        
        # Threat level indicator
        player_fleet_size = feats.get("total_fleet_size", 1.0)
        feats["threat_ratio"] = float(enemy_ships_total / max(1.0, player_fleet_size))
    else:
        feats["enemy_ships_total"] = 0.0
        feats["contested_hexes"] = 0.0
        feats["threat_ratio"] = 0.0
    
    return feats
