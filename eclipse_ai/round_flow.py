from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, Union

from .game_models import (
    ActionType,
    Disc,
    GameState,
    Hex,
    MapState,
    Pieces,
    PlayerState,
)


ACTION_SPACE_KEYS: Tuple[str, ...] = (
    "explore",
    "influence",
    "research",
    "upgrade",
    "build",
    "move",
    "reaction",
)

REACTION_TYPES: Tuple[str, ...] = ("upgrade", "build", "move")


class PhaseError(RuntimeError):
    """Raised when a caller attempts to act outside of the current phase."""


class InfluenceError(RuntimeError):
    """Raised for invalid influence manipulations."""


# ---------------------------------------------------------------------------
# Round structure helpers
# ---------------------------------------------------------------------------

def begin_round(state: GameState) -> GameState:
    """Reset per-round flags and establish the active player."""

    _ensure_turn_order(state)
    state.phase = "ACTION"
    if state.pending_starting_player:
        state.starting_player = state.pending_starting_player
    state.pending_starting_player = None
    for player in state.players.values():
        player.passed = False
    if not state.turn_order:
        state.active_player = ""
        state.turn_index = 0
        return state
    start = state.starting_player or state.turn_order[0]
    if start not in state.turn_order:
        start = state.turn_order[0]
    state.turn_index = state.turn_order.index(start)
    state.active_player = state.turn_order[state.turn_index]
    return state


def take_action(
    state: GameState,
    player_id: str,
    action: Union[str, ActionType],
    payload: Optional[Dict[str, object]] = None,
) -> None:
    if state.phase != "ACTION":
        raise PhaseError("Actions can only be taken during the Action phase")
    player = _require_player_turn(state, player_id)
    if player.passed:
        raise PhaseError("Passed players may only perform reactions")
    disc = _pop_influence_disc(player)
    action_key = _normalise_action_key(action)
    if action_key not in ACTION_SPACE_KEYS[:-1]:  # exclude reaction slot
        raise ValueError(f"Unknown action space '{action}'")
    _ensure_action_board(player)[action_key].append(disc)
    payload = payload or {}
    if action_key == "influence":
        _apply_influence_payload(state, player, payload)
    _advance_turn(state)


def pass_action(state: GameState, player_id: str) -> None:
    if state.phase != "ACTION":
        raise PhaseError("Passing is only available during the Action phase")
    player = _require_player_turn(state, player_id)
    if not player.passed:
        player.passed = True
        if state.pending_starting_player is None:
            state.pending_starting_player = player_id
    _advance_turn(state)


def can_take_reaction(state: GameState, player_id: str) -> bool:
    if state.phase != "ACTION":
        return False
    player = state.players.get(player_id)
    return bool(player and player.passed and not player.collapsed)


def take_reaction(
    state: GameState,
    player_id: str,
    reaction_type: str,
    payload: Optional[Dict[str, object]] = None,
) -> None:
    if state.phase != "ACTION":
        raise PhaseError("Reactions may only be taken during the Action phase")
    player = _require_player_turn(state, player_id)
    if not player.passed:
        raise PhaseError("Only passed players may take reactions")
    reaction_key = reaction_type.lower()
    if reaction_key not in REACTION_TYPES:
        raise ValueError(
            "Reactions limited to Upgrade, Build, or Move"  # Nanorobots ignored
        )
    disc = _pop_influence_disc(player)
    _ensure_action_board(player)["reaction"].append(disc)
    payload = payload or {}
    if reaction_key == "build":
        _validate_single_build(payload)
    elif reaction_key == "move":
        _validate_single_move(payload)
    _advance_turn(state)


def end_action_phase_if_all_passed(state: GameState) -> bool:
    if state.phase != "ACTION":
        return False
    if not state.players:
        return False
    if all(p.passed or p.collapsed for p in state.players.values()):
        state.phase = "COMBAT"
        state.active_player = ""
        return True
    return False


# ---------------------------------------------------------------------------
# Upkeep and cleanup
# ---------------------------------------------------------------------------

def run_upkeep(state: GameState) -> None:
    if state.phase != "UPKEEP":
        raise PhaseError("Upkeep can only be resolved during the Upkeep phase")
    for player in state.players.values():
        if player.collapsed:
            continue
        income_money = int(getattr(player.income, "money", 0))
        money_available = int(getattr(player.resources, "money", 0)) + income_money
        cost = _influence_cost(state, player)
        while money_available < cost:
            if not _remove_disc_for_shortfall(state, player):
                player.collapsed = True
                money_available = 0
                break
            cost = _influence_cost(state, player)
        if player.collapsed:
            player.resources.money = 0
            player.resources.science += int(getattr(player.income, "science", 0))
            player.resources.materials += int(getattr(player.income, "materials", 0))
            continue
        player.resources.money = money_available - cost
        player.resources.science += int(getattr(player.income, "science", 0))
        player.resources.materials += int(getattr(player.income, "materials", 0))
    state.phase = "CLEANUP"


def run_cleanup(state: GameState) -> None:
    if state.phase != "CLEANUP":
        raise PhaseError("Cleanup may only be run during the Cleanup phase")
    for player in state.players.values():
        board = _ensure_action_board(player)
        for key in ACTION_SPACE_KEYS:
            while board[key]:
                player.influence_track.append(board[key].pop())
        for key in ACTION_SPACE_KEYS:
            board[key].clear()
        _flip_colony_ships_up(player)
        player.passed = False
    state.round += 1
    begin_round(state)


# ---------------------------------------------------------------------------
# Colony ships
# ---------------------------------------------------------------------------

def activate_colony_ship(
    state: GameState,
    player_id: str,
    color: str,
    count: int = 1,
    *,
    allow_upkeep: bool = False,
) -> None:
    if state.phase != "ACTION" and not (allow_upkeep and state.phase == "UPKEEP"):
        raise PhaseError("Colony ships may only be activated during your action")
    player = state.players[player_id]
    available = player.colony_ships.face_up.get(color, 0)
    if count < 0 or available < count:
        raise ValueError("Not enough colony ships available")
    player.colony_ships.face_up[color] = available - count
    player.colony_ships.face_down[color] = (
        player.colony_ships.face_down.get(color, 0) + count
    )


# ---------------------------------------------------------------------------
# Influence helpers
# ---------------------------------------------------------------------------

def _apply_influence_payload(
    state: GameState, player: PlayerState, payload: Dict[str, object]
) -> None:
    moves = payload.get("moves") if payload else None
    if moves is None:
        return
    if not isinstance(moves, Sequence):
        raise InfluenceError("Influence moves must be a sequence")
    if len(moves) > 2:
        raise InfluenceError("Influence allows at most two disc moves")
    has_generator = "Wormhole Generator" in (player.known_techs or [])
    for move in moves:
        if not isinstance(move, dict):
            raise InfluenceError("Influence moves must be dictionaries")
        src = move.get("from")
        dst = move.get("to")
        _resolve_influence_move(state, player, src, dst, has_generator)


def _resolve_influence_move(
    state: GameState,
    player: PlayerState,
    src: Optional[str],
    dst: Optional[str],
    has_generator: bool,
) -> None:
    src_key = _normalise_location(src)
    dst_key = _normalise_location(dst)
    if src_key == dst_key:
        raise InfluenceError("Influence move must change location")
    if dst_key == "track":
        disc = _remove_disc_from_hex(state, player, src_key, reason="influence")
        player.influence_track.append(disc)
        return
    if src_key == "track":
        disc = _pop_influence_disc(player)
        _place_disc_on_hex(state, player, dst_key, disc, has_generator)
        return
    disc = _remove_disc_from_hex(state, player, src_key, reason="influence")
    _place_disc_on_hex(state, player, dst_key, disc, has_generator)


def _place_disc_on_hex(
    state: GameState,
    player: PlayerState,
    hex_id: str,
    disc: Disc,
    has_generator: bool,
) -> None:
    hex_state = _require_hex(state.map, hex_id)
    _validate_influence_destination(state, player, hex_state, has_generator)
    pieces = hex_state.pieces.get(player.player_id)
    if pieces is None:
        pieces = hex_state.pieces[player.player_id] = Pieces(ships={}, starbase=0, discs=0, cubes={})
    if pieces.discs >= 1:
        raise InfluenceError("A hex may not hold more than one influence disc per player")
    pieces.discs += 1


def _remove_disc_from_hex(
    state: GameState,
    player: PlayerState,
    hex_id: str,
    *,
    reason: str,
) -> Disc:
    if reason == "influence":
        if state.phase != "ACTION":
            raise InfluenceError("Influence discs may be moved during the Action phase only")
    elif reason == "shortfall":
        if state.phase != "UPKEEP":
            raise InfluenceError("Upkeep disc removal only happens during Upkeep")
    else:
        raise InfluenceError("Unknown removal reason")
    hex_state = _require_hex(state.map, hex_id)
    pieces = hex_state.pieces.get(player.player_id)
    if not pieces or pieces.discs <= 0:
        raise InfluenceError("No influence disc to remove from hex")
    pieces.discs -= 1
    if pieces.cubes:
        for color, qty in list(pieces.cubes.items()):
            player.population[color] = player.population.get(color, 0) + qty
        pieces.cubes.clear()
    for planet in hex_state.planets:
        if planet.colonized_by == player.player_id:
            planet.colonized_by = None
    player.colonies.pop(hex_id, None)
    if pieces.discs == 0 and not pieces.ships and pieces.starbase == 0:
        hex_state.pieces.pop(player.player_id, None)
    return _new_disc(player)


def _validate_influence_destination(
    state: GameState,
    player: PlayerState,
    hex_state: Hex,
    has_generator: bool,
) -> None:
    if _has_influence(state, player.player_id, hex_state.id):
        return
    connected = False
    for neighbor_id in state.map.adjacency.get(hex_state.id, []):
        if _has_influence(state, player.player_id, neighbor_id):
            connected = True
            break
    if not connected and has_generator:
        for neighbor_id, targets in state.map.adjacency.items():
            if hex_state.id in targets and _has_influence(state, player.player_id, neighbor_id):
                connected = True
                break
    if not connected:
        raise InfluenceError("Destination hex is not connected by influence")


def _has_influence(state: GameState, player_id: str, hex_id: str) -> bool:
    pieces = state.map.hexes.get(hex_id, Hex(id=hex_id, ring=0)).pieces.get(player_id)
    return bool(pieces and pieces.discs > 0)


def _remove_disc_for_shortfall(state: GameState, player: PlayerState) -> bool:
    candidates: List[Tuple[int, str]] = []
    for hex_id, hx in state.map.hexes.items():
        pieces = hx.pieces.get(player.player_id)
        if pieces and pieces.discs > 0:
            candidates.append((hx.ring, hex_id))
    if not candidates:
        return False
    candidates.sort(reverse=True)
    _, hex_id = candidates[0]
    disc = _remove_disc_from_hex(state, player, hex_id, reason="shortfall")
    player.influence_track.append(disc)
    return True


def _influence_cost(state: GameState, player: PlayerState) -> int:
    cost = 0
    for hex_state in state.map.hexes.values():
        pieces = hex_state.pieces.get(player.player_id)
        if pieces:
            cost += int(pieces.discs)
    board = _ensure_action_board(player)
    for key in ACTION_SPACE_KEYS:
        cost += len(board[key])
    return cost


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ensure_turn_order(state: GameState) -> None:
    if not state.turn_order:
        state.turn_order = list(state.players.keys())
    state.turn_order = [pid for pid in state.turn_order if pid in state.players]
    for pid in state.players:
        if pid not in state.turn_order:
            state.turn_order.append(pid)


def _advance_turn(state: GameState) -> None:
    if not state.turn_order:
        state.active_player = ""
        return
    for _ in range(len(state.turn_order)):
        state.turn_index = (state.turn_index + 1) % len(state.turn_order)
        next_pid = state.turn_order[state.turn_index]
        player = state.players.get(next_pid)
        if player and not player.collapsed:
            state.active_player = next_pid
            return
    state.active_player = ""


def _ensure_action_board(player: PlayerState) -> Dict[str, List[Disc]]:
    board = player.action_spaces
    for key in ACTION_SPACE_KEYS:
        board.setdefault(key, [])
    return board


def _pop_influence_disc(player: PlayerState) -> Disc:
    if not player.influence_track:
        raise InfluenceError("No influence discs available on the track")
    return player.influence_track.pop()


def _new_disc(player: PlayerState, *, extra: bool = False) -> Disc:
    ident = f"{player.player_id}-disc-{len(player.influence_track) + 1}"
    return Disc(id=ident, extra=extra)


def _normalise_action_key(action: Union[str, ActionType]) -> str:
    if isinstance(action, ActionType):
        action = action.value
    return str(action).strip().lower()


def _normalise_location(loc: Optional[str]) -> str:
    if loc is None:
        return "track"
    loc = str(loc).strip()
    return "track" if loc.lower() == "track" else loc


def _require_player_turn(state: GameState, player_id: str) -> PlayerState:
    if state.active_player != player_id:
        raise PhaseError("It is not this player's turn")
    try:
        return state.players[player_id]
    except KeyError as exc:
        raise ValueError("Unknown player") from exc


def _require_hex(map_state: MapState, hex_id: str) -> Hex:
    try:
        return map_state.hexes[hex_id]
    except KeyError as exc:
        raise InfluenceError("Unknown hex") from exc


def _validate_single_build(payload: Dict[str, object]) -> None:
    ships = payload.get("ships") if payload else None
    if not isinstance(ships, dict) or not ships:
        raise ValueError("Reaction build must specify exactly one ship")
    total = sum(int(v) for v in ships.values())
    if total != 1:
        raise ValueError("Reactions build exactly one ship; Nanorobots ignored")


def _validate_single_move(payload: Dict[str, object]) -> None:
    ships = payload.get("ships") if payload else None
    if not isinstance(ships, dict) or not ships:
        raise ValueError("Reaction move must activate exactly one ship")
    total = sum(int(v) for v in ships.values())
    if total != 1:
        raise ValueError("Reaction move may activate only one ship")


def _remove_disc_from_hex_for_testing(
    state: GameState, player: PlayerState, hex_id: str
) -> Disc:
    """Testing hook to enforce removal restrictions."""

    return _remove_disc_from_hex(state, player, hex_id, reason="influence")


def _flip_colony_ships_up(player: PlayerState) -> None:
    for color, qty in list(player.colony_ships.face_down.items()):
        if not qty:
            continue
        player.colony_ships.face_up[color] = (
            player.colony_ships.face_up.get(color, 0) + qty
        )
        player.colony_ships.face_down[color] = 0

