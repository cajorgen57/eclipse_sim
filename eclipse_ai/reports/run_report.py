from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple
from datetime import datetime
import json

def _sanitize_payload(payload: Dict[str, Any], max_len: int = 200) -> Dict[str, Any]:
    # Drop raw/large fields and repr nested unknowns
    out: Dict[str, Any] = {}
    for k, v in payload.items():
        if str(k).startswith("__"):  # drop __raw__ etc
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            rv = repr(v)
            out[k] = rv if len(rv) <= max_len else rv[:max_len] + "…"
    return out

@dataclass
class ActionDiag:
    type: str
    prior: float
    visits: int
    mean_value: float
    payload: Dict[str, Any]

@dataclass
class OpponentDiag:
    player_id: int
    style: str
    confidence: float
    metrics: Dict[str, float]
    tags: Tuple[str, ...] = ()

@dataclass
class ThreatDiag:
    top_opponents: List[Tuple[int, float]]
    border_sectors: int
    max_danger: float
    mean_danger: float

@dataclass
class RunReport:
    timestamp: str
    planner: str
    params: Dict[str, Any]
    seed: int
    determinization: int
    sims: int
    depth: int
    top_actions: List[ActionDiag]
    opponent_summary: List[OpponentDiag]
    threat_summary: ThreatDiag | None
    features_snapshot: Dict[str, float] | None

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2, sort_keys=False)

    def to_markdown(self) -> str:
        lines = []
        lines.append(f"# Eclipse AI Run Report ({self.planner})")
        lines.append(f"- **Timestamp:** {self.timestamp}")
        lines.append(f"- **Seed:** {self.seed}  |  **Sims:** {self.sims}  |  **Depth:** {self.depth}  |  **Determinization:** {self.determinization}")
        lines.append("\n## Top Actions")
        for i, a in enumerate(self.top_actions, 1):
            lines.append(f"{i}. `{a.type}`  | prior={a.prior:.3f}  | visits={a.visits}  | value={a.mean_value:.3f}")
            lines.append(f"    - payload: `{_sanitize_payload(a.payload)}`")
        if self.opponent_summary:
            lines.append("\n## Opponents")
            for od in self.opponent_summary:
                lines.append(f"- P{od.player_id}: **{od.style}** (conf {od.confidence:.2f}) tags={list(od.tags)}")
        if self.threat_summary:
            ts = self.threat_summary
            lines.append("\n## Threat Summary")
            lines.append(f"- border sectors: {ts.border_sectors} | max danger: {ts.max_danger:.2f} | mean danger: {ts.mean_danger:.2f}")
            if ts.top_opponents:
                top = ", ".join([f"P{pid}:{d:.2f}" for pid, d in ts.top_opponents])
                lines.append(f"- top opponents by danger: {top}")
        if self.features_snapshot:
            lines.append("\n## Feature Snapshot")
            for k, v in sorted(self.features_snapshot.items()):
                lines.append(f"- {k}: {v:.3f}")
        return "\n".join(lines)

def build_run_report(
    planner_name: str,
    params: Dict[str, Any],
    seed: int,
    determinization: int,
    sims: int,
    depth: int,
    child_stats: List[Dict[str, Any]],
    opponent_models: Dict[int, Any] | None,
    threat_map: Any | None,
    features_snapshot: Dict[str, float] | None
) -> RunReport:
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    top_actions: List[ActionDiag] = []
    for ch in child_stats:
        top_actions.append(ActionDiag(
            type=str(ch.get("type","?")),
            prior=float(ch.get("prior", 0.0)),
            visits=int(ch.get("visits", 0)),
            mean_value=float(ch.get("mean_value", 0.0)),
            payload=_sanitize_payload(ch.get("payload", {}))
        ))

    opp_summary: List[OpponentDiag] = []
    if opponent_models:
        for pid, model in opponent_models.items():
            style = getattr(model, "style", None)
            conf = getattr(model, "confidence", 0.0)
            metrics = getattr(model, "metrics", None)
            tags = getattr(model, "tags", ())
            opp_summary.append(OpponentDiag(
                player_id=pid,
                style=str(style.name if hasattr(style, "name") else style),
                confidence=float(conf),
                metrics={k: float(getattr(metrics, k)) for k in vars(metrics)} if metrics else {},
                tags=tuple(tags)
            ))

    tdiag: ThreatDiag | None = None
    if threat_map:
        dbo = getattr(threat_map, "danger_by_opponent", {}) or {}
        top_opps = sorted(dbo.items(), key=lambda kv: kv[1], reverse=True)[:3]
        # flatten all border danger values
        all_d = []
        danger = getattr(threat_map, "danger", {}) or {}
        for sid, m in danger.items():
            all_d.extend(float(x) for x in m.values())
        border_count = len(danger)
        max_d = max(all_d) if all_d else 0.0
        mean_d = sum(all_d)/len(all_d) if all_d else 0.0
        tdiag = ThreatDiag(top_opponents=top_opps, border_sectors=border_count, max_danger=max_d, mean_danger=mean_d)

    return RunReport(
        timestamp=timestamp,
        planner=planner_name,
        params=dict(params),
        seed=int(seed),
        determinization=int(determinization),
        sims=int(sims),
        depth=int(depth),
        top_actions=top_actions,
        opponent_summary=opp_summary,
        threat_summary=tdiag,
        features_snapshot=features_snapshot or {}
    )

__all__ = ["RunReport", "build_run_report"]
