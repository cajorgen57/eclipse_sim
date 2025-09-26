from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .game_models import GameState, PlayerState, Tech


class ResearchError(RuntimeError):
    """Raised when a research action is illegal."""


_TECH_DATA_CACHE: Optional[Dict[str, Tech]] = None


MARKET_SIZES_BY_PLAYER_COUNT = {
    2: 4,
    3: 5,
    4: 6,
    5: 7,
    6: 8,
}


def _tech_data_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "tech.json"


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

    catalog: Dict[str, Tech] = {}
    for entry in raw:
        tech = Tech(
            id=entry["id"],
            name=entry.get("name", entry["id"]),
            category=entry.get("category", "grid"),
            base_cost=int(entry.get("base_cost", 4)),
            is_rare=bool(entry.get("is_rare", False)),
            grants_parts=list(entry.get("grants_parts", [])),
            grants_structures=list(entry.get("grants_structures", [])),
            immediate_effect=entry.get("immediate_effect"),
        )
        catalog[tech.id] = tech

    _TECH_DATA_CACHE = catalog
    return catalog


def discounted_cost(player: PlayerState, tech: Tech) -> int:
    """Return the Science cost after applying category discounts."""

    discounts = player.tech_count_by_category.get(tech.category, 0)
    return max(1, tech.base_cost - discounts)


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
    if player.science < cost:
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
