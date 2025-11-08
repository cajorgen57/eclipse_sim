"""Generate a simple SVG summary for a saved test run."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Sequence
from xml.sax.saxutils import escape

from ..rules_engine import BUILD_COST


SVG_WIDTH = 900
HEADER_Y = 40
LEFT_MARGIN = 30
RIGHT_MARGIN = 30
CARD_PADDING = 16
CARD_SPACING = 20
TITLE_FONT_SIZE = 18
BODY_FONT_SIZE = 14
TITLE_LINE_HEIGHT = 24
LINE_HEIGHT = 20


def _risk_color(risk: float | None) -> str:
    if risk is None:
        return "#f5f5f5"
    if risk < 0.2:
        return "#d0f0c0"
    if risk < 0.4:
        return "#fff4b3"
    if risk < 0.6:
        return "#ffdab9"
    return "#ffc0cb"


def _fmt_number(value, percent: bool = False) -> str:
    if value is None:
        return "N/A"
    if percent:
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"
def _plan_body_lines(plan: dict) -> tuple[str, list[str]]:
    title = plan.get("label") or plan.get("action") or "Plan"
    score = _fmt_number(plan.get("score"))
    steps: Sequence[Dict[str, Any]] = plan.get("steps", [])
    probabilistic = any(_is_probabilistic_step(step) for step in steps)
    risk_value = plan.get("risk") if probabilistic else None
    risk = _fmt_number(risk_value, percent=True) if probabilistic else "N/A"
    header = f"Score: {score}    Risk: {risk}"

    lines: list[str] = [header, ""]
    if not steps:
        lines.append("No detailed steps provided.")
        return title, lines

    for idx, step in enumerate(steps, start=1):
        for raw_line in _render_step_lines(step, idx):
            lines.extend(_wrap_preserving_indent(raw_line))
    return title, lines


def _render_step_lines(step: Dict[str, Any], index: int) -> List[str]:
    action = step.get("action", "?")
    payload = step.get("payload") or {}
    details = step.get("details") or {}
    expected_vp = step.get("score")
    action_key = str(action).lower()

    summary = _summarize_step_header(index, action_key, payload)
    lines = [summary]

    cost_line = _describe_cost(action_key, payload)
    if cost_line:
        lines.append("   " + cost_line)

    benefit_line = _describe_benefit(action_key, expected_vp, details)
    if benefit_line:
        lines.append("   " + benefit_line)

    for reason in _describe_reason(action_key, payload, details):
        lines.append("   " + reason)

    if _is_probabilistic_step(step) and isinstance(step.get("risk"), (int, float)):
        lines.append(f"   Risk: {step['risk'] * 100:.1f}% outcome variance")

    return lines


def _wrap_preserving_indent(line: str) -> List[str]:
    indent = len(line) - len(line.lstrip(" "))
    text = line.strip()
    width = max(20, 80 - indent)
    wrapped = textwrap.wrap(text, width=width) or [text]
    prefix = " " * indent
    return [prefix + part for part in wrapped]


def _summarize_step_header(index: int, action_key: str, payload: Dict[str, Any]) -> str:
    if action_key == "build":
        location = payload.get("hex") or payload.get("at")
        targets = _summarize_build_targets(payload)
        loc_text = f" at {location}" if location else ""
        return f"{index}. Build{loc_text} — {targets}"
    if action_key == "move":
        src = payload.get("from") or payload.get("source")
        dst = payload.get("to") or payload.get("target")
        ships = _summarize_ships(payload.get("ships"))
        path = f"{src} → {dst}" if src or dst else "fleet reposition"
        ship_text = f" with {ships}" if ships else ""
        return f"{index}. Move {path}{ship_text}"
    if action_key == "explore":
        origin = payload.get("from") or payload.get("source")
        target = payload.get("pos") or payload.get("hex") or payload.get("position")
        draws = payload.get("draws") or payload.get("draw")
        draw_text = f" ({draws} draw{'s' if draws and draws != 1 else ''})" if draws else ""
        if origin and target:
            return f"{index}. Explore from {origin} toward {target}{draw_text}"
        if target:
            return f"{index}. Explore new hex {target}{draw_text}"
        return f"{index}. Explore{draw_text}"
    if action_key == "research":
        tech = payload.get("tech") or payload.get("technology")
        return f"{index}. Research {tech or 'technology'}"
    if action_key == "upgrade":
        return f"{index}. Upgrade ship designs"
    if action_key == "influence":
        target = payload.get("hex") or payload.get("target")
        return f"{index}. Influence {target or 'territory'}"
    if action_key == "diplomacy":
        ally = payload.get("with") or payload.get("ally")
        return f"{index}. Diplomacy with {ally or 'opponent'}"
    if action_key == "pass":
        return f"{index}. Pass"
    return f"{index}. {action_key.capitalize()}"


def _describe_cost(action_key: str, payload: Dict[str, Any]) -> str:
    if action_key == "build":
        total = _estimate_build_cost(payload)
        if total is not None:
            return f"Resource cost: Materials {total}"
    if action_key == "research":
        if isinstance(payload.get("approx_cost"), (int, float)):
            return f"Resource cost: Science ≈ {int(payload['approx_cost'])}"
    cost_payload = payload.get("cost") or payload.get("costs")
    if isinstance(cost_payload, dict) and cost_payload:
        formatted = ", ".join(f"{k} {v}" for k, v in cost_payload.items())
        return f"Resource cost: {formatted}"
    return "Resource cost: None noted"


def _describe_benefit(action_key: str, expected_vp: Any, details: Dict[str, Any]) -> str | None:
    if not isinstance(expected_vp, (int, float)):
        return None
    text = f"Potential gain: ΔVP {expected_vp:+.2f}"
    if action_key == "move" and isinstance(details, dict):
        if "post_control_ev" in details:
            text += f" (territory {details['post_control_ev']:+.2f})"
    return text


def _describe_reason(action_key: str, payload: Dict[str, Any], details: Dict[str, Any]) -> List[str]:
    details = details if isinstance(details, dict) else {}
    if action_key == "explore":
        summary = _summarize_explore_notes(details.get("explore_notes"))
        if summary:
            return [f"Likely gains: {summary}"]
        return ["Exploration value modeled from tile bag distribution."]
    if action_key == "move":
        if "combat_win_prob" in details:
            win = float(details.get("combat_win_prob", 0.0)) * 100.0
            atk = details.get("expected_losses_attacker")
            dfn = details.get("expected_losses_defender")
            parts = [f"Combat advantage: {win:.1f}% win chance"]
            if isinstance(atk, (int, float)) and isinstance(dfn, (int, float)):
                parts.append(
                    f"Expected losses – attacker {atk:.1f}, defender {dfn:.1f}"
                )
            return parts
        if details.get("positional"):
            terr = details.get("territory_ev")
            if isinstance(terr, (int, float)):
                return [f"Positional play securing territory value {terr:+.2f} VP."]
            return ["Positional move to improve board presence."]
        return ["Fleet reposition without immediate combat."]
    if action_key == "build":
        contested = details.get("contested")
        ships = details.get("ships")
        extras: List[str] = []
        if isinstance(ships, dict) and ships:
            extras.append(f"New assets improve fleet mix: {_summarize_ships(ships)}")
        if contested:
            extras.append("Reinforces a contested hex against enemy presence.")
        if not extras:
            extras.append("Build action to expand military capacity.")
        return extras
    if action_key == "research":
        tech = payload.get("tech") or payload.get("technology")
        pressure = details.get("pressure")
        if isinstance(pressure, (int, float)):
            return [f"Tech pressure score {pressure:.2f} guides priority for {tech}."]
        return [f"Researching {tech} to improve capabilities."]
    if action_key == "upgrade":
        delta = details.get("delta_power")
        if isinstance(delta, (int, float)):
            return [f"Design changes raise fleet power by {delta:.2f}."]
        return ["Ship upgrades bolster future combats."]
    if action_key == "influence":
        income = details.get("income_delta")
        if isinstance(income, dict) and income:
            formatted = ", ".join(f"{k} {v:+d}" for k, v in income.items() if isinstance(v, int))
            pv = details.get("pv")
            if isinstance(pv, (int, float)):
                return [f"Income shift ({formatted}) with PV factor {pv:.2f}."]
            return [f"Income shift ({formatted})."]
        return ["Influence realignment for better economy."]
    if action_key == "diplomacy":
        ally = payload.get("with") or payload.get("ally")
        ships = details.get("ally_ships")
        if isinstance(ships, (int, float)) and ally:
            return [f"Alliance with {ally} covering {int(ships)} ships on the board."]
        if ally:
            return [f"Pursuing diplomatic pact with {ally}."]
        return ["Diplomatic action to secure support."]
    return []


def _summarize_build_targets(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    ships = payload.get("ships")
    if isinstance(ships, dict) and ships:
        parts.append(_summarize_ships(ships))
    for key in ("starbase", "orbital", "monolith"):
        if int(payload.get(key, 0)) > 0:
            parts.append(f"{int(payload[key])} {key}")
    structures = payload.get("structures")
    if isinstance(structures, dict) and structures:
        parts.append(_summarize_ships(structures))
    return ", ".join(parts) if parts else "expand forces"


def _summarize_ships(ships: Dict[str, Any] | None) -> str:
    if not isinstance(ships, dict) or not ships:
        return ""
    parts: List[str] = []
    for cls, count in ships.items():
        try:
            n = int(count)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        name = str(cls)
        parts.append(f"{n} {name}")
    return ", ".join(parts)


def _estimate_build_cost(payload: Dict[str, Any]) -> int | None:
    total = 0
    counted = False
    ships = payload.get("ships")
    if isinstance(ships, dict):
        for cls, count in ships.items():
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            key = str(cls).lower()
            if key in BUILD_COST and n > 0:
                total += BUILD_COST[key] * n
                counted = True
    structures = payload.get("structures")
    if isinstance(structures, dict):
        for struct, count in structures.items():
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            key = str(struct).lower()
            if key in BUILD_COST and n > 0:
                total += BUILD_COST[key] * n
                counted = True
    for key in ("starbase", "orbital", "monolith"):
        try:
            n = int(payload.get(key, 0))
        except (TypeError, ValueError):
            continue
        if key in BUILD_COST and n > 0:
            total += BUILD_COST[key] * n
            counted = True
    return total if counted else None


def _summarize_explore_notes(notes: Any) -> str | None:
    if not isinstance(notes, str):
        return None
    try:
        info = json.loads(notes)
    except (ValueError, TypeError):
        return None
    top = info.get("top_picks") or []
    if not top:
        return None
    pieces: List[str] = []
    for entry in top[:3]:
        cat = entry.get("category")
        rate = entry.get("pick_rate")
        avg = entry.get("avg_score")
        if cat is None or rate is None or avg is None:
            continue
        pieces.append(f"{cat} ({float(rate)*100:.0f}% @ {float(avg):+.2f} VP)")
    return "; ".join(pieces) if pieces else None


def _is_probabilistic_step(step: Dict[str, Any]) -> bool:
    action = str(step.get("action", "")).lower()
    if action == "explore":
        return True
    if action == "move":
        details = step.get("details")
        if isinstance(details, dict) and ("combat_win_prob" in details):
            return True
    return False


def render_report(data: dict, output_path: Path, *, title: str | None = None) -> None:
    plans = data.get("plans", [])
    if not plans:
        raise ValueError("No plans were found in the provided test output.")

    cards = []
    for plan in plans:
        plan_title, body_lines = _plan_body_lines(plan)
        color = _risk_color(plan.get("risk"))
        line_count = len(body_lines)
        card_height = CARD_PADDING * 2 + TITLE_LINE_HEIGHT + line_count * LINE_HEIGHT
        cards.append((plan_title, body_lines, color, card_height))

    total_height = HEADER_Y + 30  # space for header text
    for _, _, _, card_height in cards:
        total_height += card_height + CARD_SPACING

    total_height += CARD_SPACING

    round_no = data.get("round")
    active_player = data.get("active_player")
    composed_title = title or "Eclipse AI Test Run"
    meta_parts = []
    if round_no is not None:
        meta_parts.append(f"Round {round_no}")
    if active_player is not None:
        meta_parts.append(f"Active: {active_player}")
    if meta_parts:
        composed_title += " — " + " • ".join(meta_parts)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{total_height}" viewBox="0 0 {SVG_WIDTH} {total_height}">',
        '<style>'
        'text { font-family: "DejaVu Sans", "Helvetica", "Arial", sans-serif; fill: #1a1a1a; }'
        '</style>',
        f'<text x="{LEFT_MARGIN}" y="{HEADER_Y}" font-size="24" font-weight="bold">{escape(composed_title)}</text>',
    ]

    y = HEADER_Y + 30
    card_width = SVG_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

    for plan_title, body_lines, color, card_height in cards:
        svg_parts.append(
            f'<rect x="{LEFT_MARGIN}" y="{y}" width="{card_width}" height="{card_height}" rx="16" ry="16" fill="{color}" stroke="#cccccc" stroke-width="1" />'
        )
        text_y = y + CARD_PADDING + TITLE_LINE_HEIGHT
        svg_parts.append(
            f'<text x="{LEFT_MARGIN + 14}" y="{text_y}" font-size="{TITLE_FONT_SIZE}" font-weight="bold">{escape(plan_title)}</text>'
        )
        body_y = text_y + BODY_FONT_SIZE
        for line in body_lines:
            svg_parts.append(
                f'<text x="{LEFT_MARGIN + 14}" y="{body_y}" font-size="{BODY_FONT_SIZE}">{escape(line)}</text>'
            )
            body_y += LINE_HEIGHT
        y += card_height + CARD_SPACING

    svg_parts.append("</svg>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg_parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Path to a JSON file saved by run_test.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests") / "test_report.svg",
        help="Destination path for the rendered SVG report.",
    )
    parser.add_argument("--title", help="Optional custom title for the report header.")
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    render_report(data, args.output, title=args.title)


if __name__ == "__main__":
    main()
