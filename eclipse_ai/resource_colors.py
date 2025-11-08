"""Canonical resource color handling and normalization utilities."""

from __future__ import annotations

from typing import Dict, Mapping, Any


# Canonical display order for resource-linked colors.
RESOURCE_COLOR_ORDER: tuple[str, ...] = ("orange", "pink", "brown")


_RESOURCE_ALIASES: Dict[str, str] = {
    # Money
    "orange": "orange",
    "money": "orange",
    "credit": "orange",
    "yellow": "orange",
    "y": "orange",
    # Science
    "pink": "pink",
    "science": "pink",
    "research": "pink",
    "blue": "pink",
    "b": "pink",
    # Materials
    "brown": "brown",
    "materials": "brown",
    "material": "brown",
    "m": "brown",
    "r": "brown",
    # Backwards compatibility for legacy material cube key.
    "p": "brown",
}


def normalize_resource_color(value: str) -> str:
    """Map ``value`` to the canonical resource color if known."""

    if not isinstance(value, str):  # tolerate non-strings from loose JSON
        return value
    return _RESOURCE_ALIASES.get(value.lower(), value.lower())


def canonical_resource_counts(
    source: Mapping[str, Any] | None = None,
    *,
    include_zero: bool = True,
) -> Dict[str, int]:
    """Return a dict keyed by canonical colors aggregated from ``source``.

    Unrecognized keys are ignored. When ``include_zero`` is ``False``, zero-value
    entries are stripped to keep payloads succinct.
    """

    counts: Dict[str, int] = {color: 0 for color in RESOURCE_COLOR_ORDER}
    if source:
        for raw_key, raw_value in source.items():
            color = normalize_resource_color(raw_key)
            if color in counts:
                try:
                    counts[color] += int(raw_value)
                except Exception:
                    continue
    if include_zero:
        return counts
    return {color: value for color, value in counts.items() if value}

