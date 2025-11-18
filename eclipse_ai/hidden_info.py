from copy import deepcopy
from typing import Any


def determinize(state: Any, rng=None) -> Any:
    """Return a deep copy of the state for deterministic planning."""
    # For now, return a safe deep copy; later, sample reputation/discovery draws and unrevealed tiles.
    return deepcopy(state)
