"""Special research rules for expansion factions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .game_models import GameState, PlayerState, Action, ActionType, Tech


def discounted_cost(player: PlayerState, tech: Tech, band_cost: Optional[int] = None) -> int:
    """Compute a player's discounted price for a technology."""

    base = band_cost if band_cost is not None else tech.base_cost
    if tech.is_rare:
        min_cost = tech.cost_range[0] if getattr(tech, "cost_range", None) else tech.base_cost
        return max(min_cost, base)

    discount = player.tech_count_by_category.get(tech.category, 0)
    return max(1, base - discount)


def can_afford(player: PlayerState, tech: Tech, band_cost: Optional[int] = None) -> bool:
    """Return True if the player has enough Science to purchase the tech."""

    return player.science >= discounted_cost(player, tech, band_cost)

_EVOLUTION_TILE_DEFAULT_COST = 4


def enumerate_research_actions(state: GameState, player: PlayerState) -> List[Action]:
    """Return additional Research actions unlocked by species abilities."""
    if not player:
        return []

    actions: List[Action] = []
    if _evolution_enabled(player):
        cost = int(player.species_flags.get("evolution_tile_cost", _EVOLUTION_TILE_DEFAULT_COST))
        pool = ensure_evolution_pool(player)
        if pool.get("size", 0) > 0 and player.resources.science >= cost:
            actions.append(
                Action(
                    ActionType.RESEARCH,
                    {
                        "evolution_tile": 1,
                        "approx_cost": cost,
                        "notes": "Draw an Evolution tile",
                    },
                )
            )

    actions.extend(_mutagen_trade_actions(player))
    return actions


def ensure_evolution_pool(player: PlayerState) -> Dict[str, Any]:
    """Initialise the player's Evolution pool data structure if required."""
    pool = player.species_pools.setdefault("evolution", {})
    size = int(player.species_flags.get("evolution_pool_size", 0) or 0)
    if pool.get("size") != size:
        pool["size"] = size
    tiles = pool.get("tiles")
    if tiles is None or len(tiles) < size:
        pool["tiles"] = list((tiles or []))
        while len(pool["tiles"]) < size:
            pool["tiles"].append(None)
    return pool


def produce_mutagen(player: PlayerState) -> int:
    """Apply passive Mutagen production for Octantis factions."""
    income = int(player.special_resources.get("mutagen_income", 0)) if player.special_resources else 0
    if income <= 0:
        return 0
    current = player.special_resources.get("mutagen", 0)
    player.special_resources["mutagen"] = int(current) + income
    return income


def _mutagen_trade_actions(player: PlayerState) -> List[Action]:
    rate = int(player.special_resources.get("mutagen_trade_rate", 0)) if player.special_resources else 0
    if rate <= 0:
        return []
    actions: List[Action] = []
    for resource in ("money", "science", "materials"):
        amount = getattr(player.resources, resource, 0)
        if amount >= rate:
            actions.append(
                Action(
                    ActionType.RESEARCH,
                    {
                        "mutagen_trade": {
                            "resource": resource,
                            "spend": rate,
                            "gain_mutagen": 1,
                        },
                        "notes": "Convert resources to Mutagen",
                    },
                )
            )
    return actions


def _evolution_enabled(player: PlayerState) -> bool:
    try:
        return bool(player.species_flags.get("evolution_enabled"))
    except AttributeError:
        return False
