from __future__ import annotations

from typing import Any
import hashlib
import json


def hash_state(state: Any) -> int:
    """Compute a small hash for planner states."""

    try:
        if hasattr(state, "to_dict"):
            blob = state.to_dict()
        else:
            blob = {k: repr(v) for k, v in vars(state).items()}
    except Exception:
        blob = repr(state)
    s = json.dumps(blob, sort_keys=True, default=repr)
    return int(hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest(), 16)
