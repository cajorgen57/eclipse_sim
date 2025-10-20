from __future__ import annotations
from typing import List, Dict, Any, Optional, Union

# Public API

def plan_overlays(plan: Any, plan_index: int = 1) -> List[Dict[str, Any]]:
    """Return vector overlays for a single plan. Supports dataclass or dict plans."""
    steps = _get_steps(plan)
    overlays: List[Dict[str, Any]] = []
    for i, step in enumerate(steps, start=1):
        aname = _action_name(step)
        payload = _payload(step)
        ev = _ev(step)
        risk = _risk(step)
        color = _risk_color(risk)
        if aname == "Move":
            frm = payload.get("from")
            to = payload.get("to") or frm
            ships = payload.get("ships", {})
            width = 1 + min(4, int(sum(ships.values()) // 2))
            overlays.append({
                "type": "arrow",
                "from": frm,
                "to": to,
                "style": {"color": color, "width": width},
                "meta": {"plan": plan_index, "step": i, "ev": ev, "risk": risk, "ships": ships},
            })
            overlays.append(_label_overlay(text=_fmt_ev(ev, risk), anchor_hex=to, plan_index=plan_index, step=i, color=color))
        elif aname == "Explore":
            ring = payload.get("ring")
            where = payload.get("direction", f"ring {ring}")
            overlays.append({
                "type": "circle",
                "hex": where,
                "style": {"color": color, "dash": True},
                "meta": {"plan": plan_index, "step": i, "ev": ev, "risk": risk, "ring": ring},
            })
            # parse exploration notes if present
            notes = _detail(step, "explore_notes")
            label = f"Explore R{ring}  " + _fmt_ev(ev, risk)
            if notes:
                tops = _top_picks_from_notes(notes)
                if tops:
                    label += f"  Top:{tops}"
            overlays.append(_label_overlay(text=label, anchor_hex=where, plan_index=plan_index, step=i, color=color))
        elif aname == "Build":
            hex_id = payload.get("hex")
            ships = payload.get("ships", {})
            starbase = payload.get("starbase", 0)
            icon = "build"
            overlays.append({
                "type": "icon",
                "hex": hex_id,
                "icon": icon,
                "style": {"color": color},
                "meta": {"plan": plan_index, "step": i, "ev": ev, "risk": risk, "ships": ships, "starbase": starbase},
            })
            desc = ", ".join(f"{k[:3]}×{v}" for k,v in ships.items()) if ships else ("starbase×1" if starbase else "build")
            overlays.append(_label_overlay(text=f"Build {desc}  " + _fmt_ev(ev, risk), anchor_hex=hex_id, plan_index=plan_index, step=i, color=color))
        elif aname == "Research":
            tech = payload.get("tech", "tech")
            overlays.append(_label_overlay(text=f"Research {tech}  " + _fmt_ev(ev, risk), anchor_hex=None, plan_index=plan_index, step=i, color=color))
        elif aname == "Influence":
            hex_id = payload.get("hex")
            overlays.append({
                "type": "icon",
                "hex": hex_id,
                "icon": "influence",
                "style": {"color": color},
                "meta": {"plan": plan_index, "step": i, "ev": ev, "risk": risk},
            })
            overlays.append(_label_overlay(text="Influence  " + _fmt_ev(ev, risk), anchor_hex=hex_id, plan_index=plan_index, step=i, color=color))
        elif aname == "Upgrade":
            overlays.append(_label_overlay(text="Upgrade  " + _fmt_ev(ev, risk), anchor_hex=None, plan_index=plan_index, step=i, color=color))
        elif aname == "Diplomacy":
            ally = payload.get("with", "?")
            overlays.append(_label_overlay(text=f"Diplomacy with {ally}  " + _fmt_ev(ev, risk), anchor_hex=None, plan_index=plan_index, step=i, color=color))
        elif aname == "Pass":
            overlays.append(_label_overlay(text="Pass", anchor_hex=None, plan_index=plan_index, step=i, color=color))
        else:
            overlays.append(_label_overlay(text=f"{aname}  " + _fmt_ev(ev, risk), anchor_hex=None, plan_index=plan_index, step=i, color=color))
    return overlays

# Helpers

def _get_steps(plan: Any):
    # plan may be dataclass with .steps or a dict with "steps"
    if hasattr(plan, "steps"):
        return list(plan.steps)
    if isinstance(plan, dict):
        return list(plan.get("steps", []))
    return []

def _action_name(step: Any) -> str:
    # step may be dataclass with .action.type.value or dict with "action"
    try:
        return step.action.type.value  # type: ignore[attr-defined]
    except Exception:
        a = getattr(step, "action", None)
        if a and hasattr(a, "type"):
            return str(a.type)
        if isinstance(step, dict):
            return str(step.get("action", "Unknown"))
        return "Unknown"

def _payload(step: Any) -> Dict[str, Any]:
    try:
        return dict(step.action.payload)  # type: ignore[attr-defined]
    except Exception:
        if isinstance(step, dict):
            return dict(step.get("payload", {}))
        return {}

def _ev(step: Any) -> float:
    try:
        return float(step.score.expected_vp)  # type: ignore[attr-defined]
    except Exception:
        if isinstance(step, dict):
            return float(step.get("score", 0.0))
        return 0.0

def _risk(step: Any) -> float:
    # risk might be stored on score or in details; fall back
    try:
        return float(step.score.risk)  # type: ignore[attr-defined]
    except Exception:
        # try to find numeric 'risk' in step
        if isinstance(step, dict):
            d = step.get("details", {})
            if isinstance(d, dict) and "risk" in d:
                try:
                    return float(d["risk"])
                except Exception:
                    pass
        return 0.35

def _detail(step: Any, key: str) -> Optional[str]:
    try:
        return step.score.details.get(key)  # type: ignore[attr-defined]
    except Exception:
        if isinstance(step, dict):
            d = step.get("details", {})
            if isinstance(d, dict):
                return d.get(key)
        return None

def _risk_color(risk: float) -> str:
    if risk <= 0.15: return "green"
    if risk <= 0.35: return "yellow"
    if risk <= 0.60: return "orange"
    return "red"

def _fmt_ev(ev: float, risk: float) -> str:
    return f"ΔVP {ev:+.2f} | risk {risk:.2f}"

def _label_overlay(text: str, anchor_hex: Optional[str], plan_index: int, step: int, color: str) -> Dict[str, Any]:
    return {
        "type": "label",
        "text": text,
        "anchor": {"type": "hex", "id": anchor_hex} if anchor_hex else {"type": "screen", "pos": "auto"},
        "style": {"color": color},
        "meta": {"plan": plan_index, "step": step},
    }

def _top_picks_from_notes(notes_json: str) -> str:
    try:
        import json
        data = json.loads(notes_json)
        top = data.get("top_picks", [])
        names = [str(t.get("category","")) for t in top[:2] if t]
        return "/".join(names)
    except Exception:
        return ""
