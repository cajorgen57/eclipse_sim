"""Game setup helpers for applying species configuration to players."""
from __future__ import annotations

from typing import Mapping, Iterable, Optional, Dict, Any

from .game_models import GameState, PlayerState, Pieces
from .species_data import SpeciesConfig, get_species
from .state_assembler import _initialise_player_state


def apply_species_setup(state: GameState, species_by_player: Mapping[str, str]) -> None:
    """Apply species configuration data to the given players in ``state``.

    The helper normalises player technology lists, applies starting discs and
    resources, and installs species-specific override flags so downstream rules
    modules can reason about faction abilities.
    """
    if not state or not species_by_player:
        return
    for player_id, species_id in species_by_player.items():
        player = state.players.get(player_id) if state.players else None
        if not player:
            continue
        config = get_species(species_id)
        _apply_species_to_player(state, player, config)


def _apply_species_to_player(state: GameState, player: PlayerState, config: SpeciesConfig) -> None:
    raw = dict(config.raw)
    player.species_id = config.species_id

    _apply_starting_resources(player, raw.get("starting_resources", {}))
    _apply_starting_discs(player, raw.get("starting_discs_delta"))
    _apply_starting_techs(state, player, raw.get("starting_techs", []), raw.get("rare_techs_starting", []))
    _apply_starting_ships(state, player, raw.get("starting_ships", {}))
    _apply_starting_structures(state, player, raw.get("starting_structures", {}))

    player.action_overrides = dict(raw.get("action_overrides", {}))
    player.build_overrides = dict(raw.get("build_overrides", {}))
    player.explore_overrides = dict(raw.get("explore_overrides", {}))
    player.move_overrides = dict(raw.get("move_overrides", {}))
    player.cannot_build = set(raw.get("cannot_build", []))
    player.vp_bonuses = dict(raw.get("vp_bonuses", {}))

    special_rules = dict(raw.get("special_rules", {}))
    player.species_flags = special_rules
    _apply_special_resources(player, special_rules)

    _initialise_player_state(player, state.tech_definitions)


def _apply_starting_resources(player: PlayerState, resources: Dict[str, Any]) -> None:
    if not resources:
        return
    for key in ("money", "science", "materials"):
        value = resources.get(key)
        if value is None:
            continue
        setattr(player.resources, key, int(value))


def _apply_starting_discs(player: PlayerState, delta: Optional[Any]) -> None:
    if delta is None:
        return
    try:
        player.influence_discs = int(player.influence_discs or 0) + int(delta)
    except (TypeError, ValueError):
        pass


def _apply_starting_techs(state: GameState, player: PlayerState, techs: Iterable[str], rare_techs: Iterable[str]) -> None:
    current = set(player.known_techs or [])
    for tech in techs:
        if tech and tech not in current:
            player.known_techs.append(tech)
            current.add(tech)
    for rare in rare_techs:
        if rare and rare not in current:
            player.known_techs.append(rare)
            current.add(rare)
        _remove_tech_from_supply(state, rare)


def _apply_starting_ships(state: GameState, player: PlayerState, layout: Dict[str, Dict[str, Any]]) -> None:
    if not layout:
        return
    home = _find_home_hex(state, player.player_id)
    if home is None:
        return
    pieces = home.pieces.setdefault(player.player_id, Pieces())
    ships = layout.get("home", {})
    for ship_class, count in ships.items():
        if count is None:
            continue
        if ship_class == "starbase":
            pieces.starbase = max(int(pieces.starbase or 0), int(count))
        else:
            pieces.ships[ship_class] = max(int(pieces.ships.get(ship_class, 0)), int(count))


def _apply_starting_structures(state: GameState, player: PlayerState, layout: Dict[str, Dict[str, Any]]) -> None:
    if not layout:
        return
    home = _find_home_hex(state, player.player_id)
    if home is None:
        return
    structures = layout.get("home", {})
    for struct, count in structures.items():
        if count is None:
            continue
        value = int(count)
        if struct == "orbital":
            home.orbital = bool(value)
        elif struct == "monolith":
            home.monolith = bool(value)
        elif struct == "deathmoon":
            pieces = home.pieces.setdefault(player.player_id, Pieces())
            pieces.starbase = max(int(pieces.starbase or 0), value)


def _apply_special_resources(player: PlayerState, special_rules: Dict[str, Any]) -> None:
    if not special_rules:
        return
    mutagen_income = special_rules.get("mutagen_production_per_round")
    if mutagen_income:
        player.special_resources.setdefault("mutagen", 0)
        player.special_resources["mutagen_income"] = int(mutagen_income)
        player.special_resources.setdefault("mutagen_trade_rate", 3)
    if special_rules.get("single_resource_transmatter"):
        player.special_resources.setdefault("transmatter_single_resource", True)


def _remove_tech_from_supply(state: GameState, tech_name: str) -> None:
    if not tech_name:
        return
    if state.market and tech_name in state.market:
        state.market.remove(tech_name)
    if state.tech_display and tech_name in state.tech_display.available:
        state.tech_display.available.remove(tech_name)
    for bag in (state.tech_bags or {}).values():
        while tech_name in bag:
            bag.remove(tech_name)


def _find_home_hex(state: GameState, player_id: str):
    if not state.map or not state.map.hexes:
        return None
    best = None
    for hx in state.map.hexes.values():
        pieces = hx.pieces.get(player_id) if hx.pieces else None
        if not pieces:
            continue
        if best is None or hx.ring < best.ring:
            best = hx
    return best
