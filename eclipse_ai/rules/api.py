# eclipse_ai/rules/api.py
"""
Central rules API for eclipse_sim.

All callers (planner, CLI, agents, validators, tests) should use ONLY this module
to:
1. enumerate legal actions for a player
2. check if a specific action is legal
3. apply an action to produce a new state

This removes structural drift between:
- eclipse_ai/action_gen/legacy.py
- eclipse_ai/validators.py
- eclipse_ai/planners/mcts_pw.py
- eclipse_ai/rules_engine.py
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Iterable, Union

# Current source of truth for rules.
# We centralize access here first, then we can thin rules_engine later.
from eclipse_ai import rules_engine

def _norm_type(t):
    if isinstance(t, str):
        return t.upper()
    name = getattr(t, "name", None)
    if isinstance(name, str):
        return name.upper()
    value = getattr(t, "value", None)
    if isinstance(value, str):
        return value.upper()
    return str(t).split(".")[-1].upper()

ActionDict = Dict[str, Any]
State = Any
PlayerId = Union[str, int]


def _to_dict_action(a: Any) -> ActionDict:
    if isinstance(a, dict):
        d = dict(a)
        if "type" in d or "action" in d:
            at = d.get("type", d.get("action"))
            d["type"] = _norm_type(at)
            d.pop("action", None)
        if "payload" not in d:
            d["payload"] = {}
        return d

    to_dict = getattr(a, "to_dict", None)
    if callable(to_dict):
        d = to_dict()
        at = d.get("type", d.get("action"))
        d["type"] = _norm_type(at)
        d.pop("action", None)
        if "payload" not in d:
            d["payload"] = {}
        return d

    action_type = getattr(a, "action", getattr(a, "type", None))
    payload = getattr(a, "payload", None)
    return {
        "type": _norm_type(action_type),
        "payload": payload if payload is not None else {},
    }



def enumerate_actions(state: State, player_id: PlayerId) -> List[ActionDict]:
    """
    Return all legal actions for this player for the given state.
    This is the single source of truth for action generation.
    """
    raw_actions: Iterable[Any] = rules_engine.legal_actions(state, player_id)
    actions: List[ActionDict] = []
    for a in raw_actions:
        actions.append(_to_dict_action(a))
    return actions


def is_action_legal(state: State, player_id: PlayerId, action: ActionDict) -> bool:
    legal = enumerate_actions(state, player_id)
    legal_set = {(_norm_type(a.get("type")), tuple(sorted((a.get("payload") or {}).items()))) for a in legal}
    key = (_norm_type(action.get("type", action.get("action"))), tuple(sorted((action.get("payload") or {}).items())))
    return key in legal_set


def apply_action(state: State, player_id: PlayerId, action: ActionDict) -> State:
    """
    Pure state transition.

    Copies the state, then applies the given action.
    This MUST NOT mutate the input state.

    This function supports the common Eclipse action families:
    - PASS / NOOP
    - MOVE
    - EXPLORE
    - RESEARCH
    - BUILD
    - INFLUENCE
    - UPGRADE
    - DIPLOMACY / ALLIANCE

    If rules_engine already defines a more detailed transition, we delegate to it.
    Otherwise we do a deterministic transition here so planners can safely branch.
    """
    # If the repo already has a real transition, prefer that.
    re_apply = getattr(rules_engine, "apply_action", None)
    if callable(re_apply):
        # assume rules_engine.apply_action is also pure or we deep copy first
        new_state = deepcopy(state)
        return re_apply(new_state, player_id, action)

    # fallback: implement a generic transition here
    new_state = deepcopy(state)
    atype = action.get("type") or action.get("action")

    # normalize payload
    payload = action.get("payload", {})

    if atype is None:
        # unknown action type: do nothing, but return a copy
        return new_state

    # 1. PASS
    if atype in ("PASS", "END_TURN", "NOOP"):
        _advance_turn(new_state)
        return new_state

    # 2. MOVE
    if atype == "MOVE":
        _apply_move(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 3. EXPLORE
    if atype == "EXPLORE":
        _apply_explore(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 4. RESEARCH
    if atype == "RESEARCH":
        _apply_research(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 5. BUILD
    if atype == "BUILD":
        _apply_build(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 6. INFLUENCE
    if atype == "INFLUENCE":
        _apply_influence(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 7. UPGRADE
    if atype == "UPGRADE":
        _apply_upgrade(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # 8. DIPLOMACY / ALLIANCE
    if atype in ("DIPLOMACY", "ALLIANCE", "FORM_ALLIANCE"):
        _apply_diplomacy(new_state, player_id, payload)
        _advance_after_action(new_state)
        return new_state

    # default: do nothing but return copy
    return new_state


# ---------------------------------------------------------------------------
# internal helpers
# these are concrete, not placeholders. they expect your state to follow the
# structure you already use in rules_engine/state_assembler: i.e. a top-level
# object/dict that has players keyed by id and a board/hexes collection.
# if a field is missing, we fail silently but deterministically.
# ---------------------------------------------------------------------------

def _get_player(state: State, player_id: PlayerId) -> Dict[str, Any]:
    players = getattr(state, "players", None)
    if players is None and isinstance(state, dict):
        players = state.get("players", {})
    if players is None:
        return {}
    # players may be list or dict
    if isinstance(players, dict):
        return players.get(str(player_id)) or players.get(int(player_id), {})
    if isinstance(players, list):
        # assume index == player_id
        try:
            return players[int(player_id)]
        except Exception:
            return {}
    return {}


def _advance_turn(state: State) -> None:
    # try attribute style
    if hasattr(state, "turn"):
        current_turn = getattr(state, "turn", 0)
        state.turn = (current_turn or 0) + 1
        return
    # dict style
    if isinstance(state, dict):
        turn = state.get("turn", 0)
        state["turn"] = (turn or 0) + 1


def _advance_after_action(state: State) -> None:
    """
    Some Eclipse actions advance an action counter or consume orange.
    We try to decrement available actions here if present.
    """
    if hasattr(state, "actions_remaining"):
        rem = getattr(state, "actions_remaining", 0)
        if rem > 0:
            state.actions_remaining = rem - 1
        return

    if isinstance(state, dict):
        rem = state.get("actions_remaining")
        if isinstance(rem, int) and rem > 0:
            state["actions_remaining"] = rem - 1


def _apply_move(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "unit_id": "...",
      "from_hex": "0102",
      "to_hex": "0103"
    }
    We move the unit if we can find it. If not, we no-op.
    """
    unit_id = payload.get("unit_id")
    from_hex = payload.get("from_hex")
    to_hex = payload.get("to_hex")

    if not (unit_id and from_hex and to_hex):
        return

    board = getattr(state, "board", None)
    if board is None and isinstance(state, dict):
        board = state.get("board")
    if not board:
        return

    # board as dict of hex_id -> hex
    from_tile = board.get(from_hex)
    to_tile = board.get(to_hex)
    if not from_tile or not to_tile:
        return

    # units might be under "ships" or "pieces"
    moved = False
    for key in ("ships", "pieces", "units"):
        units = from_tile.get(key)
        if isinstance(units, list):
            for i, u in enumerate(units):
                uid = u.get("id") or u.get("unit_id")
                owner = u.get("owner") or u.get("player_id")
                if uid == unit_id and str(owner) == str(player_id):
                    # remove from old
                    unit_obj = units.pop(i)
                    # add to new
                    to_units = to_tile.setdefault(key, [])
                    to_units.append(unit_obj)
                    moved = True
                    break
        if moved:
            break


def _apply_explore(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Execute explore action by sampling and placing a tile.
    
    Supported payload formats:
    
    1. Coordinate-based (from action_gen/explore.py):
       {"target_q": int, "target_r": int, "ring": int}
    
    2. Generic (from rules_engine.py):
       {"ring": int, "draws": int, "direction": str}
    
    3. Legacy explicit hex:
       {"new_hex": {...}, "position": str}
    """
    from eclipse_ai.tile_sampler import sample_and_place_tile
    from eclipse_ai.map.coordinates import axial_neighbors
    
    # Handle coordinate-based explore (specific target)
    if "target_q" in payload and "target_r" in payload:
        target_q = payload["target_q"]
        target_r = payload["target_r"]
        ring = payload.get("ring", 2)
        
        sample_and_place_tile(state, player_id, target_q, target_r, ring)
        return
    
    # Handle generic explore (find a valid adjacent position)
    if "ring" in payload:
        ring = payload["ring"]
        
        # Find all hexes where player has presence
        player_hexes = []
        for hex_id, hex_obj in state.map.hexes.items():
            if not hasattr(hex_obj, 'pieces'):
                continue
            pieces = hex_obj.pieces.get(player_id)
            if pieces and (pieces.discs > 0 or pieces.ships):
                if hasattr(hex_obj, 'axial_q') and hasattr(hex_obj, 'axial_r'):
                    player_hexes.append((hex_obj.axial_q, hex_obj.axial_r))
        
        # Try to place adjacent to each player hex
        for q, r in player_hexes:
            neighbors = axial_neighbors(q, r)
            for edge, (neighbor_q, neighbor_r) in neighbors.items():
                # Check if position is already occupied
                occupied = False
                for hex_obj in state.map.hexes.values():
                    if (hasattr(hex_obj, 'axial_q') and hasattr(hex_obj, 'axial_r') and
                        hex_obj.axial_q == neighbor_q and hex_obj.axial_r == neighbor_r):
                        occupied = True
                        break
                
                if not occupied:
                    # Try to place here
                    if sample_and_place_tile(state, player_id, neighbor_q, neighbor_r, ring):
                        return  # Success - placed a hex
        
        # If we get here, couldn't place anywhere
        return
    
    # FALLBACK: Legacy explicit hex payloads
    board = getattr(state, "board", None)
    if board is None and isinstance(state, dict):
        board = state.get("board")
    if not board:
        return

    pos = payload.get("position")
    if not pos:
        return

    if "new_hex" in payload:
        board[pos] = payload["new_hex"]
    elif "tile_id" in payload:
        board[pos] = {
            "id": payload["tile_id"],
            "owner": None,
            "ships": [],
            "planets": [],
        }


def _apply_research(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "tech": "Plasma Cannon",
      "cost": 5
    }
    We add tech to player's researched list and deduct science if present.
    """
    tech_name = payload.get("tech")
    if not tech_name:
        return

    player = _get_player(state, player_id)
    if not player:
        return

    researched = player.setdefault("researched", [])
    if tech_name not in researched:
        researched.append(tech_name)

    cost = payload.get("cost")
    if cost is not None:
        science = player.get("science", 0)
        science = max(0, science - int(cost))
        player["science"] = science


def _apply_build(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "hex": "0102",
      "ship_type": "Interceptor"
    }
    We add the ship to the hex and reduce player's materials.
    """
    hex_id = payload.get("hex")
    ship_type = payload.get("ship_type")
    if not (hex_id and ship_type):
        return

    board = getattr(state, "board", None)
    if board is None and isinstance(state, dict):
        board = state.get("board")
    if not board:
        return

    tile = board.get(hex_id)
    if not tile:
        return

    ships = tile.setdefault("ships", [])
    ships.append(
        {
            "id": f"{player_id}_{ship_type}_{len(ships)}",
            "type": ship_type,
            "owner": str(player_id),
        }
    )

    player = _get_player(state, player_id)
    if player:
        mats = player.get("materials", 0)
        player["materials"] = max(0, mats - 1)


def _apply_influence(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "hex": "0102"
    }
    We set the owner of the hex.
    """
    hex_id = payload.get("hex")
    if not hex_id:
        return

    board = getattr(state, "board", None)
    if board is None and isinstance(state, dict):
        board = state.get("board")
    if not board:
        return

    tile = board.get(hex_id)
    if not tile:
        return

    tile["owner"] = str(player_id)


def _apply_upgrade(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "ship_type": "Interceptor",
      "part": "Plasma Cannon"
    }
    We add the part to player's upgrades.
    """
    ship_type = payload.get("ship_type")
    part = payload.get("part")
    if not (ship_type and part):
        return

    player = _get_player(state, player_id)
    if not player:
        return

    upgrades = player.setdefault("upgrades", {})
    ship_upgrades = upgrades.setdefault(ship_type, [])
    if part not in ship_upgrades:
        ship_upgrades.append(part)


def _apply_diplomacy(state: State, player_id: PlayerId, payload: Dict[str, Any]) -> None:
    """
    Expected payload:
    {
      "ally": "2"
    }
    We record alliance relationship.
    """
    ally = payload.get("ally")
    if not ally:
        return

    player = _get_player(state, player_id)
    if not player:
        return

    alliances = player.setdefault("alliances", [])
    if ally not in alliances:
        alliances.append(str(ally))