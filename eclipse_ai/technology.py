from __future__ import annotations

import json
import csv
from collections import Counter, defaultdict
from pathlib import Path
from random import Random
from typing import Dict, List, Optional, Set, Tuple

from .game_models import GameState, PlayerState, Tech
from .research import discounted_cost as _expansion_discounted_cost, can_afford


class ResearchError(RuntimeError):
    """Raised when a research action is illegal."""


_TECH_DATA_CACHE: Optional[Dict[str, Tech]] = None
_TECH_TILE_POOL_CACHE: Optional[Dict[str, List[str]]] = None


MARKET_SIZES_BY_PLAYER_COUNT = {
    2: 4,
    3: 5,
    4: 6,
    5: 7,
    6: 8,
    7: 9,
    8: 10,
    9: 11
}


def _tech_data_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "tech.json"


def _tech_tile_pool_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "tech.json"


def load_tech_definitions() -> Dict[str, Tech]:
    """Load the canonical tech definitions from disk (cached)."""

    global _TECH_DATA_CACHE
    if _TECH_DATA_CACHE is not None:
        return _TECH_DATA_CACHE

    path = _tech_data_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - configuration error
        raise ResearchError(f"technology data file missing: {path}") from exc

    entries = raw.get("techs", raw) if isinstance(raw, dict) else raw

    catalog: Dict[str, Tech] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category", "grid")).lower()
        base_cost = int(entry.get("base_cost", entry.get("min_cost", 4)))
        cost_range = entry.get("cost_range") or [base_cost, entry.get("max_cost", base_cost)]
        if isinstance(cost_range, list) and len(cost_range) == 2:
            cost_tuple = (int(cost_range[0]), int(cost_range[1]))
        else:
            cost_tuple = (base_cost, base_cost)

        parts = entry.get("grants_parts", entry.get("unlocks_parts", [])) or []
        structs = entry.get("grants_structures", entry.get("unlocks_structures", [])) or []

        tech = Tech(
            id=entry["id"],
            name=entry.get("name", entry["id"]),
            category=category,
            base_cost=base_cost,
            is_rare=bool(entry.get("is_rare", False)),
            cost_range=cost_tuple,
            grants_parts=list(parts),
            grants_structures=list(structs),
            immediate_effect=entry.get("immediate_effect"),
        )
        catalog[tech.id] = tech
        catalog.setdefault(tech.name, tech)

    _TECH_DATA_CACHE = catalog
    return catalog


def load_tech_tile_pool() -> Dict[str, List[str]]:
    """Return the randomized tile pool entries grouped by tier.

    The pool is expanded according to the "frequency" column so each entry
    represents a single physical tile. Callers receive a defensive copy so the
    caller may shuffle or consume the lists without mutating the cached
    template.
    """

    global _TECH_TILE_POOL_CACHE
    if _TECH_TILE_POOL_CACHE is not None:
        return {tier: list(tiles) for tier, tiles in _TECH_TILE_POOL_CACHE.items()}

    path = _tech_tile_pool_path()
    pool: Dict[str, List[str]] = defaultdict(list)
    
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - configuration error
        raise ResearchError(f"technology market data file missing: {path}") from exc
    
    # Handle both {"techs": [...]} and [...] formats
    techs = data.get("techs", data) if isinstance(data, dict) else data
    
    for tech_entry in techs:
        if not isinstance(tech_entry, dict):
            continue
        
        tech_id = tech_entry.get("id", "").strip()
        if not tech_id:
            continue
        
        # Skip rare techs - they're handled separately
        if tech_entry.get("is_rare", False):
            continue
        
        # Assign tier based on cost_range if not specified
        cost_range = tech_entry.get("cost_range", [4, 4])
        if isinstance(cost_range, list) and len(cost_range) == 2:
            max_cost = cost_range[1]
        else:
            max_cost = tech_entry.get("base_cost", 4)
        
        # Determine tier: low cost = I, medium = II, high = III
        if max_cost <= 3:
            tier = "I"
        elif max_cost <= 8:
            tier = "II"
        else:
            tier = "III"
        
        # Default frequency: 2 tiles per tech (standard Eclipse setup)
        frequency = tech_entry.get("frequency", 2)
        try:
            repeats = max(0, int(frequency))
        except (TypeError, ValueError):
            repeats = 2
        
        pool[tier].extend([tech_id] * repeats)

    _TECH_TILE_POOL_CACHE = {tier: list(tiles) for tier, tiles in pool.items()}
    return {tier: list(tiles) for tier, tiles in _TECH_TILE_POOL_CACHE.items()}


def build_starting_tech_market(
    tech_count: int,
    owned_tech_names: Set[str],
    rng: Optional[Random] = None,
) -> Tuple[List[str], Dict[str, List[str]], Dict[str, int]]:
    """Generate the initial technology market and leftover bags.

    Args:
        tech_count: Number of tiles that should be face up in the market.
        owned_tech_names: Case-insensitive set of technology names already owned
            at setup; these tiles are removed from the supply entirely.
        rng: Optional random number generator; defaults to ``random.Random`` if
            omitted to keep caller control over determinism.

    Returns:
        Tuple of ``(market_ids, tech_bags, tier_counts)`` where ``market_ids``
        is the ordered list of technology ids for the face-up market,
        ``tech_bags`` contains the remaining face-down tiles keyed by tier, and
        ``tier_counts`` records how many tiles of each tier were drawn into the
        market.
    """

    generator = rng or Random()
    definitions = load_tech_definitions()
    owned_lower = {name.lower() for name in owned_tech_names}
    pool = load_tech_tile_pool()

    market: List[str] = []
    tier_counts: Counter[str] = Counter()
    tiles_by_tier: Dict[str, List[str]] = {}

    for tier in ("I", "II", "III"):
        tiles = list(pool.get(tier, []))
        if tiles:
            generator.shuffle(tiles)
        tiles_by_tier[tier] = tiles

    while len(market) < tech_count:
        total_tiles = sum(len(v) for v in tiles_by_tier.values())
        if total_tiles <= 0:
            break
        pick = generator.randrange(total_tiles)
        chosen_tier: Optional[str] = None
        tile_id: Optional[str] = None
        for tier in ("I", "II", "III"):
            tier_tiles = tiles_by_tier.get(tier, [])
            if pick < len(tier_tiles):
                chosen_tier = tier
                tile_id = tier_tiles.pop(pick)
                break
            pick -= len(tier_tiles)
        if tile_id is None or chosen_tier is None:
            break
        tech = definitions.get(tile_id) or definitions.get(tile_id.lower())
        if tech is None or tech.is_rare:
            continue
        if tech.name.lower() in owned_lower:
            continue
        market.append(tile_id)
        tier_counts[chosen_tier] += 1

    bags: Dict[str, List[str]] = {tier: list(tiles) for tier, tiles in tiles_by_tier.items()}

    rare_tiles = pool.get("Rare", [])
    rare_tiles = list(rare_tiles)
    if rare_tiles:
        generator.shuffle(rare_tiles)
    bags["Rare"] = rare_tiles

    normalized_counts = {tier: tier_counts.get(tier, 0) for tier in ("I", "II", "III")}
    return market, bags, normalized_counts


def discounted_cost(player: PlayerState, tech: Tech, band_cost: Optional[int] = None) -> int:
    """Return the Science cost after applying category discounts."""

    return _expansion_discounted_cost(player, tech, band_cost)


def _assert_phase_is_action(state: GameState) -> None:
    if state.phase.lower() != "action":
        raise ResearchError("cannot research during Reaction")


def _assert_disc_available(player: PlayerState) -> None:
    if player.influence_discs <= 0:
        raise ResearchError("no influence discs available for Research")


def _market_size_for_players(state: GameState) -> int:
    count = max(2, len(state.players) or 2)
    return MARKET_SIZES_BY_PLAYER_COUNT.get(count, 8)


def _market_without_duplicates(state: GameState, taken_rare_ids: Set[str]) -> List[str]:
    """Return the market list filtered for duplicates and illegal rares."""

    seen: Set[str] = set()
    filtered: List[str] = []
    for tech_id in state.market:
        if tech_id in seen:
            continue
        tech = state.tech_definitions.get(tech_id)
        if tech is None:
            continue
        if tech.is_rare and tech_id in taken_rare_ids:
            continue
        seen.add(tech_id)
        filtered.append(tech_id)
    return filtered


def cleanup_refresh_market(state: GameState) -> None:
    """Refill the face-up market from the draw bags during Cleanup."""

    if not state.tech_definitions:
        state.tech_definitions = load_tech_definitions()

    taken_rares: Set[str] = set()
    for player in state.players.values():
        for tech_id in player.owned_tech_ids:
            tech = state.tech_definitions.get(tech_id)
            if tech and tech.is_rare:
                taken_rares.add(tech_id)

    state.market = _market_without_duplicates(state, taken_rares)
    target = _market_size_for_players(state)
    if len(state.market) >= target:
        state.market = state.market[:target]
        return

    # Draw from bags in key order (tiers typically I < II < III).
    for bag_name in sorted(state.tech_bags.keys()):
        bag = state.tech_bags[bag_name]
        draw_index = 0
        while draw_index < len(bag) and len(state.market) < target:
            tech_id = bag[draw_index]
            tech = state.tech_definitions.get(tech_id)
            draw_index += 1
            if tech is None:
                continue
            if tech.is_rare and tech_id in taken_rares:
                continue
            if tech_id in state.market:
                continue
            state.market.append(tech_id)

        # Remove the tiles that were effectively drawn.
        if draw_index > 0:
            del bag[:draw_index]
        if len(state.market) >= target:
            break


def can_research(state: GameState, player: PlayerState, tech_id: str) -> bool:
    try:
        validate_research(state, player, tech_id)
        return True
    except ResearchError:
        return False


def validate_research(state: GameState, player: PlayerState, tech_id: str) -> None:
    """Raise ResearchError if the research action is illegal."""

    if not state.tech_definitions:
        state.tech_definitions = load_tech_definitions()

    _assert_phase_is_action(state)
    _assert_disc_available(player)

    if tech_id not in state.market:
        raise ResearchError("tech not available in market")

    tech = state.tech_definitions.get(tech_id)
    if tech is None:
        raise ResearchError("unknown technology id")

    if tech.is_rare and tech_id in player.owned_tech_ids:
        raise ResearchError("Rare tech already taken")

    if tech_id in player.owned_tech_ids:
        raise ResearchError("technology already owned")

    if tech.is_rare:
        for other in state.players.values():
            if other is player:
                continue
            if tech_id in other.owned_tech_ids:
                raise ResearchError("Rare tech already taken")

    cost = discounted_cost(player, tech)
    if not can_afford(player, tech):
        raise ResearchError("insufficient Science after discount")


def _apply_immediate_effect(state: GameState, player: PlayerState, tech: Tech) -> None:
    effect = tech.immediate_effect or {}
    if not isinstance(effect, dict):
        return

    if effect.get("science"):
        delta = int(effect["science"])
        player.science += delta
        player.resources.science = max(0, player.science)
    if effect.get("money"):
        delta = int(effect["money"])
        player.resources.money += delta
    if effect.get("materials"):
        delta = int(effect["materials"])
        player.resources.materials += delta


def _recompute_category_cache(player: PlayerState, definitions: Dict[str, Tech]) -> None:
    counts: Dict[str, int] = {}
    for tech_id in player.owned_tech_ids:
        tech = definitions.get(tech_id)
        if tech is None:
            continue
        counts[tech.category] = counts.get(tech.category, 0) + 1
    player.tech_count_by_category = counts


def _unlock_from_tech(player: PlayerState, tech: Tech) -> None:
    if tech.grants_parts:
        player.unlocked_parts.update(tech.grants_parts)
    if tech.grants_structures:
        player.unlocked_structures.update(tech.grants_structures)


def do_research(state: GameState, player: PlayerState, tech_id: str) -> None:
    """Execute the research action for the player."""

    validate_research(state, player, tech_id)
    tech = state.tech_definitions[tech_id]
    cost = discounted_cost(player, tech)

    player.influence_discs -= 1
    player.science -= cost
    player.resources.science = max(0, player.science)

    state.market = [tid for tid in state.market if tid != tech_id]
    player.owned_tech_ids.add(tech_id)
    if tech.name not in player.known_techs:
        player.known_techs.append(tech.name)
    _unlock_from_tech(player, tech)
    _recompute_category_cache(player, state.tech_definitions)
    _apply_immediate_effect(state, player, tech)


def ensure_structure_allowed(player: PlayerState, structure: str) -> None:
    if structure not in player.unlocked_structures:
        raise ResearchError("required technology not owned")


def ensure_part_allowed(player: PlayerState, part: str) -> None:
    if part not in player.unlocked_parts:
        raise ResearchError("required technology not owned")
