"""Eclipse AI: parse board images, build state, search actions, and recommend plays."""

from importlib import import_module
from typing import Any

__version__ = "0.1.0"
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
    "Economy",
    "MCTSPlanner",
    "Plan",
    "PlanStep",
    "plan_overlays",
    "BeliefState",
    "DiscreteHMM",
    "TileParticleFilter",
    "TileParticle",
    "SpeciesConfig",
    "get_species",
    "all_species",
    "get_registry",
    "__version__",
]

_EXPORTS = {
    "ActionType": ("game_models", "ActionType"),
    "Resources": ("game_models", "Resources"),
    "ShipDesign": ("game_models", "ShipDesign"),
    "Pieces": ("game_models", "Pieces"),
    "Planet": ("game_models", "Planet"),
    "Hex": ("game_models", "Hex"),
    "TechDisplay": ("game_models", "TechDisplay"),
    "PlayerState": ("game_models", "PlayerState"),
    "MapState": ("game_models", "MapState"),
    "GameState": ("game_models", "GameState"),
    "Action": ("game_models", "Action"),
    "Score": ("game_models", "Score"),
    "Disc": ("game_models", "Disc"),
    "ColonyShips": ("game_models", "ColonyShips"),
    "Economy": ("models.economy", "Economy"),
    "recommend": ("main", "recommend"),
    "MCTSPlanner": ("search_policy", "MCTSPlanner"),
    "Plan": ("search_policy", "Plan"),
    "PlanStep": ("search_policy", "PlanStep"),
    "plan_overlays": ("overlay", "plan_overlays"),
    "BeliefState": ("uncertainty", "BeliefState"),
    "DiscreteHMM": ("uncertainty", "DiscreteHMM"),
    "TileParticleFilter": ("uncertainty", "TileParticleFilter"),
    "TileParticle": ("uncertainty", "TileParticle"),
    "SpeciesConfig": ("species_data", "SpeciesConfig"),
    "get_species": ("species_data", "get_species"),
    "all_species": ("species_data", "all_species"),
    "get_registry": ("species_data", "get_registry"),
}


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        module = import_module(f".{module_name}", __name__)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(__all__)))
