"""Utilities for loading faction/species configuration data."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class SpeciesConfig:
    """Immutable wrapper around a species configuration block."""

    species_id: str
    raw: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @property
    def name(self) -> str:
        return self.raw.get("name", self.species_id)

    @property
    def expansion(self) -> str:
        return self.raw.get("expansion", "base")

    @property
    def trade_rate(self) -> Any:
        return self.raw.get("trade_rate")


class SpeciesRegistry:
    """Singleton-style registry that loads JSON data on demand."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(os.path.dirname(__file__), "data", "species.json")
        self._data: Dict[str, SpeciesConfig] = {}
        self._meta: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self._meta = payload.get("_meta", {})
        species_entries = {k: v for k, v in payload.items() if not k.startswith("_")}
        for species_id, block in species_entries.items():
            self._data[species_id] = SpeciesConfig(species_id=species_id, raw=block)
        self._loaded = True

    @property
    def meta(self) -> Dict[str, Any]:
        self.load()
        return self._meta

    def get(self, species_id: str) -> SpeciesConfig:
        self.load()
        try:
            return self._data[species_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._data))
            raise KeyError(f"Unknown species '{species_id}'. Available: {available}") from exc

    def all_species(self) -> Dict[str, SpeciesConfig]:
        self.load()
        return dict(self._data)


_registry: Optional[SpeciesRegistry] = None


def get_registry(path: Optional[str] = None) -> SpeciesRegistry:
    global _registry
    if _registry is None or path is not None:
        _registry = SpeciesRegistry(path=path)
    return _registry


def get_species(species_id: str) -> SpeciesConfig:
    return get_registry().get(species_id)


def all_species() -> Dict[str, SpeciesConfig]:
    return get_registry().all_species()
