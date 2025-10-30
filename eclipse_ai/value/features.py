from typing import Dict, Any


def extract_features(state: Any, context: Dict[str, Any] | None = None) -> Dict[str, float]:
    """Derive normalized heuristic features from a game state."""
    feats = {
        "vp_now": float(getattr(state, "vp", 0.0)) if hasattr(state, "vp") else 0.0,
        "spare_discs": float(getattr(state, "spare_discs", 0.0)) if hasattr(state, "spare_discs") else 0.0,
    }
    return feats
