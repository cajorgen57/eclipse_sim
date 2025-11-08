"""Utilities for loading serialized `GameState` fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union, Any

from ..game_models import GameState


PathLike = Union[str, Path]


def load_state(path: PathLike) -> GameState:
    """Load a :class:`GameState` from a JSON file.

    Relative paths are resolved from the current working directory, matching
    pytest's default behavior for fixtures. The JSON payload should follow the
    structure produced by :meth:`GameState.to_json`.
    """

    candidate = Path(path)
    if not candidate.exists():
        raise FileNotFoundError(f"State fixture not found: {path}")
    with candidate.open("r", encoding="utf-8") as handle:
        payload: Any = json.load(handle)
    return GameState.from_dict(payload)


__all__ = ["load_state"]
