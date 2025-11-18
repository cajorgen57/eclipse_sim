"""Structured access to Eclipse exploration hex data."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ExplorationTileRecord:
    """Metadata describing a single exploration hex tile."""

    tile_number: str
    ring: int
    ancient_resistance: int = 0
    resources: Dict[str, int] = field(default_factory=dict)
    advanced_resources: Dict[str, int] = field(default_factory=dict)
    discovery_tile: bool = False
    victory_points: int = 0
    has_black_hole: bool = False
    has_wormhole: bool = False
    has_anomalies: bool = False
    has_supernova: bool = False
    has_nebula: bool = False
    ancient_hive: int = 0
    has_pulsar: bool = False


def _csv_path(csv_override: Optional[str] = None) -> str:
    base_path = os.path.join(os.path.dirname(__file__), "..", "..", "eclipse_tiles.csv")
    return os.path.abspath(csv_override or base_path)


def _to_int(value: Optional[str]) -> int:
    if value is None:
        return 0
    value = value.strip()
    if not value:
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def _to_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    value = value.strip().lower()
    return value in {"1", "true", "yes"}


@lru_cache()
def load_exploration_tiles(csv_override: Optional[str] = None) -> Dict[str, ExplorationTileRecord]:
    """Parse the exploration CSV into structured records keyed by tile id."""

    path = _csv_path(csv_override)
    if not os.path.exists(path):
        return {}

    records: Dict[str, ExplorationTileRecord] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            tile_id = (row.get("TileNumber") or "").strip()
            ring = _to_int(row.get("Sector"))
            if not tile_id or ring <= 0:
                continue

            record = ExplorationTileRecord(
                tile_number=tile_id,
                ring=ring,
                ancient_resistance=_to_int(row.get("AncientResistance")),
                resources={
                    "money": _to_int(row.get("Money")),
                    "science": _to_int(row.get("Science")),
                    "materials": _to_int(row.get("Materials")),
                    "white": _to_int(row.get("White")),
                },
                advanced_resources={
                    "money": _to_int(row.get("AdvMoney")),
                    "science": _to_int(row.get("AdvScience")),
                    "materials": _to_int(row.get("AdvMaterials")),
                    "white": _to_int(row.get("AdvWhite")),
                },
                discovery_tile=_to_bool(row.get("DiscoveryTile")),
                victory_points=_to_int(row.get("VictoryPoints")),
                has_black_hole=_to_bool(row.get("BlackHole")),
                has_wormhole=_to_bool(row.get("Wormhole")),
                has_anomalies=_to_bool(row.get("Anomalies")),
                has_supernova=_to_bool(row.get("Supernova")),
                has_nebula=_to_bool(row.get("Nebula")),
                ancient_hive=_to_int(row.get("AncientHive")),
                has_pulsar=_to_bool(row.get("Pulsar")),
            )
            records[record.tile_number] = record
    return records


@lru_cache()
def tile_numbers_by_ring() -> Dict[int, List[str]]:
    """Return tile ids grouped by sector ring."""

    grouped: Dict[int, List[str]] = {}
    for record in load_exploration_tiles().values():
        grouped.setdefault(record.ring, []).append(record.tile_number)
    for entries in grouped.values():
        entries.sort()
    return grouped


@lru_cache()
def tiles_by_ring(ring: int) -> List[ExplorationTileRecord]:
    """Return a list of tile records for the specified ring."""

    tiles = [rec for rec in load_exploration_tiles().values() if rec.ring == ring]
    tiles.sort(key=lambda rec: rec.tile_number)
    return tiles


@lru_cache()
def tile_counts_by_ring() -> Dict[int, int]:
    """Summarise how many tiles exist in each exploration ring."""

    return {ring: len(ids) for ring, ids in tile_numbers_by_ring().items()}


def iter_tiles() -> Iterable[ExplorationTileRecord]:
    """Iterate over all known exploration tiles."""

    return load_exploration_tiles().values()


__all__ = [
    "ExplorationTileRecord",
    "iter_tiles",
    "load_exploration_tiles",
    "tile_counts_by_ring",
    "tile_numbers_by_ring",
    "tiles_by_ring",
]
