from __future__ import annotations
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json

def _build_dataclass(cls, data: Dict[str, Any]):
    """Recursively coerce nested dicts/lists into a dataclass instance."""
    if not is_dataclass(cls):
        return data
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue  # keep default
        v = data[f.name]
        ft = f.type
        origin = get_origin(ft)

        if is_dataclass(ft) and isinstance(v, dict):
            kwargs[f.name] = _build_dataclass(ft, v)
        elif origin is list and isinstance(v, list):
            (inner,) = get_args(ft) or (Any,)
            if inner and is_dataclass(inner):
                kwargs[f.name] = [_build_dataclass(inner, x) if isinstance(x, dict) else x for x in v]
            else:
                kwargs[f.name] = v
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
    drive: int = 0

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
    planets: List[Planet] = field(default_factory=list)
    pieces: Dict[str, Pieces] = field(default_factory=dict)  # player_id -> Pieces
    ancients: int = 0
    monolith: bool = False
    anomaly: bool = False

@dataclass
class TechDisplay:
    available: List[str] = field(default_factory=list)
    tier_counts: Dict[str, int] = field(default_factory=lambda: {"I":0,"II":0,"III":0})

@dataclass
class PlayerState:
    player_id: str
    color: str
    known_techs: List[str] = field(default_factory=list)
    resources: Resources = field(default_factory=Resources)
    ship_designs: Dict[str, ShipDesign] = field(default_factory=dict)  # interceptor, cruiser, dreadnought, starbase
    reputation: List[int] = field(default_factory=list)
    diplomacy: Dict[str, str] = field(default_factory=dict)

@dataclass
class MapState:
    hexes: Dict[str, Hex] = field(default_factory=dict)

@dataclass
class GameState:
    round: int = 1
    active_player: str = "you"
    players: Dict[str, PlayerState] = field(default_factory=dict)
    map: MapState = field(default_factory=MapState)
    tech_display: TechDisplay = field(default_factory=TechDisplay)
    bags: Dict[str, Dict[str, int]] = field(default_factory=dict)  # bag per ring: tile_type -> count

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

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
