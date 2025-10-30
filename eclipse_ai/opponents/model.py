from __future__ import annotations

from typing import Any, Dict

from .infer import infer_style
from .observe import OppHistory, make_snapshot
from .stats import compute_metrics
from .threat import build_threat_map
from .types import OpponentMetrics, OpponentModel, ThreatMap


def analyze_state(
    state: Any, my_id: int | None = None, round_idx: int | None = None
) -> tuple[dict[int, OpponentModel], ThreatMap | None]:
    rd = round_idx if isinstance(round_idx, int) else getattr(state, "round_index", 0)
    snap_now = make_snapshot(state, rd)
    hist = OppHistory(K=2)
    hist.record(make_snapshot(state, max(0, rd - 1)))
    hist.record(snap_now)

    metrics = compute_metrics(hist)
    models: Dict[int, OpponentModel] = {}
    for pid, metric in metrics.items():
        style, conf, tags = infer_style(metric)
        models[pid] = OpponentModel(
            player_id=pid,
            style=style,
            confidence=conf,
            metrics=metric,
            tags=tags,
            notes=(),
        )

    board = getattr(state, "board", None) or getattr(state, "map", None)
    if board is None:
        return models, None
    if my_id is None:
        my_id = getattr(state, "active_player_id", 0)
    metrics_by_player: Dict[int, OpponentMetrics] = {pid: model.metrics for pid, model in models.items()}
    threat_map = build_threat_map(board, my_id, metrics_by_player)
    return models, threat_map

