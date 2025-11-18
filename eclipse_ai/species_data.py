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


# ============================================================================
# Species Tracks Registry (Population and Influence tracks)
# ============================================================================

@dataclass(frozen=True)
class SpeciesTracksConfig:
    """Configuration for a species' population and influence tracks."""
    
    species_id: str
    raw: Dict[str, Any]
    
    def get_population_track_config(self, resource_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific population track (money/science/materials)."""
        pop_tracks = self.raw.get("population_tracks", {})
        return pop_tracks.get(resource_type)
    
    def get_influence_track_config(self) -> Optional[Dict[str, Any]]:
        """Get configuration for the influence track."""
        return self.raw.get("influence_track")


class SpeciesTracksRegistry:
    """Registry for species population and influence track configurations."""
    
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(os.path.dirname(__file__), "data", "species_tracks.json")
        self._data: Dict[str, SpeciesTracksConfig] = {}
        self._default: Optional[SpeciesTracksConfig] = None
        self._meta: Dict[str, Any] = {}
        self._loaded = False
    
    def load(self) -> None:
        if self._loaded:
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self._meta = payload.get("_meta", {})
        
        # Load default configuration
        if "default" in payload:
            self._default = SpeciesTracksConfig(species_id="default", raw=payload["default"])
        
        # Load species-specific configurations
        species_entries = {k: v for k, v in payload.items() if not k.startswith("_") and k != "default"}
        for species_id, block in species_entries.items():
            self._data[species_id] = SpeciesTracksConfig(species_id=species_id, raw=block)
        
        self._loaded = True
    
    def get(self, species_id: str) -> SpeciesTracksConfig:
        """Get track configuration for a species, falling back to default if not found."""
        self.load()
        
        if species_id in self._data:
            return self._data[species_id]
        
        # Return default if species not found
        if self._default:
            return self._default
        
        raise KeyError(f"No track configuration found for species '{species_id}' and no default available")
    
    def get_merged_config(self, species_id: str) -> Dict[str, Any]:
        """
        Get merged configuration for a species.
        Species-specific configs override defaults on a per-track basis.
        """
        self.load()
        
        # Start with default
        merged = {}
        if self._default:
            merged = json.loads(json.dumps(self._default.raw))  # Deep copy
        
        # Merge species-specific overrides
        if species_id in self._data:
            species_config = self._data[species_id].raw
            
            # Merge population tracks
            if "population_tracks" in species_config:
                if "population_tracks" not in merged:
                    merged["population_tracks"] = {}
                merged["population_tracks"].update(species_config["population_tracks"])
            
            # Merge influence track
            if "influence_track" in species_config:
                merged["influence_track"] = species_config["influence_track"]
        
        return merged


_tracks_registry: Optional[SpeciesTracksRegistry] = None


def get_tracks_registry(path: Optional[str] = None) -> SpeciesTracksRegistry:
    global _tracks_registry
    if _tracks_registry is None or path is not None:
        _tracks_registry = SpeciesTracksRegistry(path=path)
    return _tracks_registry


def get_species_tracks(species_id: str) -> SpeciesTracksConfig:
    """Get track configuration for a species."""
    return get_tracks_registry().get(species_id)


def get_species_tracks_merged(species_id: str) -> Dict[str, Any]:
    """Get merged track configuration (species-specific + defaults)."""
    return get_tracks_registry().get_merged_config(species_id)
