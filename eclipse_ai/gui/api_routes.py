"""API routes for Eclipse AI GUI."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

# Import Eclipse AI modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eclipse_ai import recommend
from eclipse_ai.state_assembler import from_dict, apply_overrides
from eclipse_ai.game_models import GameState
from eclipse_ai.overlay import plan_overlays

router = APIRouter()

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Request/Response models
class PredictRequest(BaseModel):
    state: Dict[str, Any]
    config: Dict[str, Any] = {}

class SaveStateRequest(BaseModel):
    state: Dict[str, Any]
    filename: str

# ============================================================================
# Fixtures Management
# ============================================================================

@router.get("/fixtures")
async def list_fixtures() -> List[Dict[str, Any]]:
    """List all available test fixtures."""
    fixtures = []
    
    # Scan project root for common fixture files
    for json_file in PROJECT_ROOT.glob("*round*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            # Check if it looks like a game state (has players and/or map)
            if "players" in data or "map" in data or "state" in data:
                fixtures.append({
                    "name": json_file.stem,
                    "path": str(json_file.relative_to(PROJECT_ROOT)),
                    "round": data.get("round", data.get("state", {}).get("round")),
                    "active_player": data.get("active_player", data.get("state", {}).get("active_player")),
                    "source": "root"
                })
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
            pass
    
    # Scan tests/ directory
    tests_dir = PROJECT_ROOT / "tests"
    if tests_dir.exists():
        for json_file in tests_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                if "players" in data or "map" in data:
                    fixtures.append({
                        "name": json_file.stem,
                        "path": str(json_file.relative_to(PROJECT_ROOT)),
                        "round": data.get("round"),
                        "active_player": data.get("active_player"),
                        "source": "tests"
                    })
            except Exception:
                pass
    
    # Scan eclipse_ai/eclipse_test/cases/
    test_cases_dir = PROJECT_ROOT / "eclipse_ai" / "eclipse_test" / "cases"
    if test_cases_dir.exists():
        for subdir in test_cases_dir.iterdir():
            if subdir.is_dir():
                for json_file in subdir.glob("*.json"):
                    if ".annotations." not in json_file.name and ".tech." not in json_file.name:
                        try:
                            with open(json_file) as f:
                                data = json.load(f)
                            if "players" in data or "map" in data:
                                fixtures.append({
                                    "name": f"{subdir.name}/{json_file.stem}",
                                    "path": str(json_file.relative_to(PROJECT_ROOT)),
                                    "round": data.get("round"),
                                    "active_player": data.get("active_player"),
                                    "source": "test_cases"
                                })
                        except Exception:
                            pass
    
    return fixtures

@router.get("/fixtures/{fixture_name:path}")
async def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load a specific fixture by name."""
    fixtures = await list_fixtures()
    
    # Find matching fixture
    fixture = next((f for f in fixtures if f["name"] == fixture_name), None)
    if not fixture:
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_name}' not found")
    
    # Load the JSON
    fixture_path = PROJECT_ROOT / fixture["path"]
    try:
        with open(fixture_path) as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load fixture: {str(e)}")

# ============================================================================
# State Management
# ============================================================================

@router.post("/state/save")
async def save_state(request: SaveStateRequest):
    """Save the current state to a JSON file."""
    output_dir = PROJECT_ROOT / "eclipse_ai" / "gui" / "saved_states"
    output_dir.mkdir(exist_ok=True)
    
    # Sanitize filename
    filename = request.filename.replace("..", "").replace("/", "_")
    if not filename.endswith(".json"):
        filename += ".json"
    
    output_path = output_dir / filename
    
    try:
        with open(output_path, "w") as f:
            json.dump(request.state, f, indent=2)
        return {
            "success": True,
            "path": str(output_path.relative_to(PROJECT_ROOT)),
            "message": f"State saved to {filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save state: {str(e)}")

# ============================================================================
# Prediction
# ============================================================================

@router.post("/predict")
async def predict(request: PredictRequest) -> Dict[str, Any]:
    """Run the planner with provided state and configuration."""
    try:
        # Parse state
        state = from_dict(request.state)
        
        # Extract configuration
        config = request.config or {}
        planner_config = config.get("planner", {})
        
        # Build manual_inputs for recommend()
        manual_inputs = {
            "_planner": {
                "simulations": planner_config.get("simulations", 600),
                "depth": planner_config.get("depth", 3),
                "pw_alpha": planner_config.get("pw_alpha", 0.65),
                "pw_c": planner_config.get("pw_c", 1.8),
                "prior_scale": planner_config.get("prior_scale", 0.6),
                "seed": planner_config.get("seed", 0),
            }
        }
        
        # Add profile if specified
        if "profile" in config:
            manual_inputs["_profile"] = config["profile"]
        
        # Add any state overrides
        if "overrides" in config:
            state = apply_overrides(state, config["overrides"])
        
        # Run recommendation
        result = recommend(
            None,  # No board image
            None,  # No tech image
            prior_state=state,
            manual_inputs=manual_inputs,
            top_k=config.get("top_k", 5),
            planner=config.get("planner_type", "pw_mcts"),
        )
        
        # Add overlays to each plan
        for i, plan in enumerate(result.get("plans", []), 1):
            try:
                overlays = plan_overlays(plan, plan_index=i)
                plan["overlays"] = overlays
            except Exception:
                plan["overlays"] = []
        
        # Extract features if verbose mode
        if config.get("verbose", False):
            try:
                from eclipse_ai.value import features
                extracted_features = features.extract_features(state)
                result["features"] = extracted_features
            except Exception as e:
                result["features"] = {"error": str(e)}
        
        return result
        
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )

# ============================================================================
# Game Generation
# ============================================================================

class NewGameRequest(BaseModel):
    num_players: int = 4
    species_by_player: Optional[Dict[str, str]] = None
    seed: Optional[int] = None
    ancient_homeworlds: bool = False
    starting_round: int = 1

@router.post("/generate")
async def generate_game(request: NewGameRequest) -> Dict[str, Any]:
    """Generate a new random game state with proper setup."""
    try:
        from eclipse_ai.game_setup import new_game
        from dataclasses import asdict
        
        print(f"[API] Generating game with {request.num_players} players, ancient_homeworlds={request.ancient_homeworlds}, starting_round={request.starting_round}")
        
        # Generate new game state
        state = new_game(
            num_players=request.num_players,
            species_by_player=request.species_by_player,
            seed=request.seed,
            ancient_homeworlds=request.ancient_homeworlds,
            starting_round=request.starting_round
        )
        
        print(f"[API] Game generated: {len(state.players)} players, {len(state.map.hexes)} hexes")
        print(f"[API] Hex IDs: {list(state.map.hexes.keys())}")
        
        # Convert to dict for JSON response
        state_dict = asdict(state)
        
        print(f"[API] After asdict: {len(state_dict.get('map', {}).get('hexes', {}))} hexes in dict")
        print(f"[API] Dict hex IDs: {list(state_dict.get('map', {}).get('hexes', {}).keys())}")
        
        return state_dict
        
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )

# ============================================================================
# Reference Data
# ============================================================================

@router.get("/profiles")
async def list_profiles() -> List[str]:
    """List available strategy profiles."""
    try:
        from eclipse_ai.value.profiles import load_profiles
        profiles_data = load_profiles()
        return list(profiles_data.keys()) if profiles_data else []
    except Exception:
        # Fallback to known profiles
        return [
            "balanced",
            "aggressive",
            "economic",
            "tech_rush",
            "defensive",
            "expansion",
            "late_game",
            "turtle"
        ]

@router.get("/species")
async def list_species() -> List[Dict[str, Any]]:
    """List available species."""
    try:
        from eclipse_ai.species_data import all_species
        species_dict = all_species()
        result = []
        for species_id, config in species_dict.items():
            result.append({
                "id": species_id,
                "name": config.name,
                "expansion": config.get("expansion", "base")
            })
        return result
    except Exception:
        pass
    
    # Fallback to known species
    return [
        {"id": "terrans", "name": "Terrans", "expansion": "base"},
        {"id": "orion", "name": "Orion Hegemony", "expansion": "base"},
        {"id": "mechanema", "name": "Mechanema", "expansion": "base"},
        {"id": "planta", "name": "Planta", "expansion": "base"},
        {"id": "hydran", "name": "Hydrans", "expansion": "base"},
        {"id": "eridani", "name": "Eridani Empire", "expansion": "base"},
        {"id": "magellan", "name": "Magellan", "expansion": "rota"},
        {"id": "rho_indi", "name": "Rho Indi Syndicate", "expansion": "rota"},
    ]

@router.get("/techs")
async def list_techs() -> List[Dict[str, Any]]:
    """List available technologies."""
    try:
        tech_file = PROJECT_ROOT / "eclipse_ai" / "data" / "tech.json"
        if tech_file.exists():
            with open(tech_file) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return [{"name": k, **v} for k, v in data.items()]
            return data
    except Exception:
        pass
    
    # Fallback to common techs
    return [
        {"name": "Plasma Cannon", "category": "Military"},
        {"name": "Fusion Drive", "category": "Propulsion"},
        {"name": "Positron Computer", "category": "Computer"},
        {"name": "Gauss Shield", "category": "Defense"},
        {"name": "Advanced Mining", "category": "Economic"},
    ]

