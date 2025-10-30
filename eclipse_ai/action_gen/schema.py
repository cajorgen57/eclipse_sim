from dataclasses import dataclass
from typing import Any, Mapping, Tuple, Literal

ActionType = Literal["EXPLORE","INFLUENCE","RESEARCH","UPGRADE","BUILD","MOVE_FIGHT","DIPLOMACY","PASS","LEGACY"]

@dataclass(frozen=True)
class MacroAction:
    type: ActionType
    payload: Mapping[str, Any]
    prior: float = 0.0

    def stable_key(self) -> Tuple:
        # exclude transient/private fields (e.g., __raw__)
        def norm(v):
            if isinstance(v, dict):
                return tuple(sorted((k, norm(x)) for k,x in v.items() if not str(k).startswith("_")))
            if isinstance(v, (list, tuple)):
                return tuple(norm(x) for x in v)
            return v
        return (self.type, norm(dict(self.payload)))
