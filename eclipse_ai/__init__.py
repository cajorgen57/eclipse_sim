"""Eclipse AI: parse board images, build state, search actions, and recommend plays."""

__version__ = "0.1.0"

from .game_models import (
    ActionType,
    Resources,
    ShipDesign,
    Pieces,
    Planet,
    Hex,
    TechDisplay,
    PlayerState,
    MapState,
    GameState,
    Action,
    Score,
    Disc,
    ColonyShips,
)
from .main import recommend
from .search_policy import MCTSPlanner, Plan, PlanStep
from .overlay import plan_overlays
from .uncertainty import BeliefState, DiscreteHMM, TileParticleFilter, TileParticle

__all__ = [
    "recommend",
    "ActionType",
    "Resources",
    "ShipDesign",
    "Pieces",
    "Planet",
    "Hex",
    "TechDisplay",
    "PlayerState",
    "MapState",
    "GameState",
    "Action",
    "Score",
    "Disc",
    "ColonyShips",
    "MCTSPlanner",
    "Plan",
    "PlanStep",
    "plan_overlays",
    "BeliefState",
    "DiscreteHMM",
    "TileParticleFilter",
    "TileParticle",
    "__version__",
]
