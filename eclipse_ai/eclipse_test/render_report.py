"""Generate a simple SVG summary for a saved test run."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


DEFAULT_JSON_PATH = Path(__file__).resolve().parents[2] / "tests" / "test_run.json"
DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[2] / "tests" / "test_report.svg"


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


def _format_payload(payload) -> str:
    if payload is None or payload == {}:
        return "—"
    if isinstance(payload, (str, int, float)):
        return str(payload)
    return json.dumps(payload, ensure_ascii=False)


def _plan_body_lines(plan: dict) -> tuple[str, list[str]]:
    title = plan.get("label") or plan.get("action") or "Plan"
    score = _fmt_number(plan.get("score"))
    risk = _fmt_number(plan.get("risk"), percent=True)
    header = f"Score: {score}    Risk: {risk}"

    lines: list[str] = [header, ""]
    steps: Iterable[dict] = plan.get("steps", [])
    if not steps:
        lines.append("No detailed steps provided.")
        return title, lines

    for idx, step in enumerate(steps, start=1):
        action = step.get("action", "?")
        payload = _format_payload(step.get("payload"))
        stats_parts = []
        if step.get("ev") is not None:
            stats_parts.append(f"EV {_fmt_number(step['ev'])}")
        if step.get("risk") is not None:
            stats_parts.append(f"Risk {_fmt_number(step['risk'], percent=True)}")
        stats = f" ({', '.join(stats_parts)})" if stats_parts else ""
        raw_line = f"{idx}. {action}: {payload}{stats}"
        wrapped = textwrap.wrap(raw_line, width=80) or [raw_line]
        lines.extend(wrapped)
    return title, lines


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
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="Path to a JSON file saved by run_test (default: tests/test_run.json).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Destination path for the rendered SVG report (default: tests/test_report.svg).",
    )
    parser.add_argument("--title", help="Optional custom title for the report header.")
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    render_report(data, args.output, title=args.title)


if __name__ == "__main__":
    main()
