from __future__ import annotations
import sys
from dataclasses import dataclass, field, asdict, is_dataclass, fields
from typing import Dict, List, Optional, Tuple, Any, Set, Literal, get_args, get_origin, get_type_hints
from enum import Enum
import json
from .types import ShipDesign

def _build_dataclass(cls, data: Dict[str, Any]):
    """Recursively coerce nested dicts/lists into a dataclass instance."""
    if not is_dataclass(cls):
        return data
    type_hints = get_type_hints(cls, globalns=sys.modules[cls.__module__].__dict__)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue  # keep default
        v = data[f.name]
        ft = type_hints.get(f.name, f.type)
        origin = get_origin(ft)

        if v is None:
            # Treat nulls for dataclass/container fields as "use the default".
            # Many callers omit nested structures entirely and some serializers
            # explicitly emit `null`; in those cases we still want the default
            # dataclass/list/dict instance instead of propagating ``None`` and
            # breaking attribute access later on (e.g. PlayerState.resources
            # should remain a Resources dataclass). Only fall back to the
            # default when the target type is a dataclass or collection; simple
            # Optional scalars should still honour the explicit ``None``.
            union_args = get_args(ft) if origin is not None else ()
            if is_dataclass(ft) or origin in (list, dict) or any(
                is_dataclass(arg) for arg in union_args if arg is not type(None)
            ):
                continue

        if is_dataclass(ft) and isinstance(v, dict):
            kwargs[f.name] = _build_dataclass(ft, v)
        elif origin in (list, set, tuple) and isinstance(v, (list, set, tuple)):
            (inner,) = get_args(ft) or (Any,)
            if inner and is_dataclass(inner):
                items = [_build_dataclass(inner, x) if isinstance(x, dict) else x for x in v]
            else:
                items = list(v)
            if origin is set:
                kwargs[f.name] = set(items)
            elif origin is tuple:
                kwargs[f.name] = tuple(items)
            else:
                kwargs[f.name] = items
        elif origin is dict and isinstance(v, dict):
            kt, vt = get_args(ft) or (Any, Any)
            if vt and is_dataclass(vt):
                kwargs[f.name] = {k: _build_dataclass(vt, x) if isinstance(x, dict) else x for k, x in v.items()}
            else:
                kwargs[f.name] = v
        else:
            kwargs[f.name] = v
    return cls(**kwargs)

def _deep_override(obj: Any, updates: Any) -> Any:
    """Shallow replace for lists, recursive merge for dicts/dataclasses."""
    if updates is None:
        return obj
    if is_dataclass(obj):
        for k, v in updates.items():
            cur = getattr(obj, k, None)
            setattr(obj, k, _deep_override(cur, v))
        return obj
    if isinstance(obj, dict) and isinstance(updates, dict):
        for k, v in updates.items():
            obj[k] = _deep_override(obj.get(k), v)
        return obj
    # lists and scalars get replaced entirely
    return updates


class ActionType(str, Enum):
    EXPLORE = "Explore"
    MOVE = "Move"
    BUILD = "Build"
    UPGRADE = "Upgrade"
    INFLUENCE = "Influence"
    RESEARCH = "Research"
    DIPLOMACY = "Diplomacy"
    PASS = "Pass"
    REACTION = "Reaction"


@dataclass
class Disc:
    id: str
    extra: bool = False


def _default_population() -> Dict[str, int]:
    return {"yellow": 0, "blue": 0, "brown": 0}


def _default_action_spaces() -> Dict[str, List[Disc]]:
    return {
        "explore": [],
        "influence": [],
        "research": [],
        "upgrade": [],
        "build": [],
        "move": [],
        "reaction": [],
    }


@dataclass
class ColonyShips:
    face_up: Dict[str, int] = field(
        default_factory=lambda: {"yellow": 0, "blue": 0, "brown": 0, "wild": 0}
    )
    face_down: Dict[str, int] = field(
        default_factory=lambda: {"yellow": 0, "blue": 0, "brown": 0, "wild": 0}
    )

@dataclass
class Resources:
    money: int = 0
    science: int = 0
    materials: int = 0



@dataclass
class ShipDesign:
    computer: int = 0
    shield: int = 0
    initiative: int = 0
    hull: int = 1
    cannons: int = 0
    missiles: int = 0
    drive: int = 0  # legacy single-drive field kept for backward compatibility
    drives: int = 0
    has_jump_drive: bool = False
    interceptor_bays: int = 0
    def movement_value(self) -> int:
        """Return the total movement points provided by installed drives."""
        return max(0, int(self.drives if self.drives else self.drive))


@dataclass
class Pieces:
    ships: Dict[str, int] = field(default_factory=dict)  # class -> count
    starbase: int = 0
    discs: int = 0
    cubes: Dict[str, int] = field(default_factory=dict)  # y/b/p -> ints
    discovery: int = 0

@dataclass
class Planet:
    type: str  # "yellow" money, "blue" science, "brown" materials, "wild", etc.
    colonized_by: Optional[str] = None

@dataclass
class Hex:
    id: str
    ring: int
    wormholes: List[int] = field(default_factory=list)  # 0..5 edges present
    neighbors: Dict[int, str] = field(default_factory=dict)  # edge -> neighbor hex id
    planets: List[Planet] = field(default_factory=list)
    pieces: Dict[str, Pieces] = field(default_factory=dict)  # player_id -> Pieces
    ancients: int = 0
    monolith: bool = False
    orbital: bool = False
    anomaly: bool = False
    explored: bool = True
    has_warp_portal: bool = False
    has_gcds: bool = False

@dataclass
class TechDisplay:
    available: List[str] = field(default_factory=list)
    tier_counts: Dict[str, int] = field(default_factory=lambda: {"I":0,"II":0,"III":0})

Effect = Dict[str, Any]


@dataclass
class Tech:
    id: str
    name: str
    category: Literal["military", "grid", "nano", "quantum", "rare", "biotech", "economy"]
    base_cost: int
    is_rare: bool = False
    grants_parts: List[str] = field(default_factory=list)
    grants_structures: List[str] = field(default_factory=list)
    immediate_effect: Optional[Effect] = None


@dataclass
class PlayerState:
    player_id: str
    color: str
    resources: Resources = field(default_factory=Resources)
    income: Resources = field(default_factory=Resources)
    ship_designs: Dict[str, ShipDesign] = field(default_factory=dict)  # interceptor, cruiser, dreadnought, starbase
    reputation: List[int] = field(default_factory=list)
    diplomacy: Dict[str, str] = field(default_factory=dict)
    known_techs: List[str] = field(default_factory=list)
    owned_tech_ids: Set[str] = field(default_factory=set)
    tech_count_by_category: Dict[str, int] = field(default_factory=dict)
    science: int = 0
    influence_discs: int = 0
    unlocked_parts: Set[str] = field(default_factory=set)
    unlocked_structures: Set[str] = field(default_factory=set)
    available_components: Dict[str, int] = field(default_factory=dict)
    influence_track: List[Disc] = field(default_factory=list)
    action_spaces: Dict[str, List[Disc]] = field(default_factory=_default_action_spaces)
    colonies: Dict[str, Dict[str, int]] = field(default_factory=dict)
    population: Dict[str, int] = field(default_factory=_default_population)
    colony_ships: ColonyShips = field(default_factory=ColonyShips)
    passed: bool = False
    collapsed: bool = False
    has_wormhole_generator: bool = False


@dataclass
class MapState:
    hexes: Dict[str, Hex] = field(default_factory=dict)
    adjacency: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class GameState:
    round: int = 1
    active_player: str = "you"
    phase: str = "action"
    players: Dict[str, PlayerState] = field(default_factory=dict)
    map: MapState = field(default_factory=MapState)
    tech_display: TechDisplay = field(default_factory=TechDisplay)
    bags: Dict[str, Dict[str, int]] = field(default_factory=dict)  # bag per ring: tile_type -> count
    tech_bags: Dict[str, List[str]] = field(default_factory=dict)
    market: List[str] = field(default_factory=list)
    tech_definitions: Dict[str, Tech] = field(default_factory=dict)
    phase: str = "ACTION"
    starting_player: Optional[str] = None
    pending_starting_player: Optional[str] = None
    turn_order: List[str] = field(default_factory=list)
    turn_index: int = 0

    def to_json(self) -> str:
        def _normalize(value: Any) -> Any:
            if isinstance(value, set):
                return sorted(value)
            if isinstance(value, dict):
                return {k: _normalize(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_normalize(v) for v in value]
            return value

        return json.dumps(_normalize(asdict(self)), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        return _build_dataclass(cls, data)
    def apply_overrides(self, overrides: Dict[str, Any]) -> "GameState":
        _deep_override(self, overrides)
        return self


@dataclass
class Action:
    type: ActionType
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Score:
    expected_vp: float
    risk: float
    details: Dict[str, Any] = field(default_factory=dict)
