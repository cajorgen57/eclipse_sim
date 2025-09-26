"""Shared lightweight dataclasses used across the rules engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ShipDesign:
    """A ship blueprint broken down by part category.

    The legacy aggregate fields (computer/shield/etc.) are retained for
    compatibility with existing evaluation and combat code. Validators are
    expected to keep them in sync with the underlying part dictionaries.
    """

    computer: int = 0
    shield: int = 0
    initiative: int = 0
    hull: int = 1
    cannons: int = 0
    missiles: int = 0
    drive: int = 0

    computer_parts: Dict[str, int] = field(default_factory=dict)
    shield_parts: Dict[str, int] = field(default_factory=dict)
    cannon_parts: Dict[str, int] = field(default_factory=dict)
    missile_parts: Dict[str, int] = field(default_factory=dict)
    drive_parts: Dict[str, int] = field(default_factory=dict)
    energy_sources: Dict[str, int] = field(default_factory=dict)
    hull_parts: Dict[str, int] = field(default_factory=dict)

    movement_value: int = 0
    energy_consumption: int = 0
    energy_production: int = 0

    def clone(self) -> "ShipDesign":
        """Deep-copy mutable dictionaries for safe manipulation."""

        return ShipDesign(
            computer=self.computer,
            shield=self.shield,
            initiative=self.initiative,
            hull=self.hull,
            cannons=self.cannons,
            missiles=self.missiles,
            drive=self.drive,
            computer_parts=dict(self.computer_parts),
            shield_parts=dict(self.shield_parts),
            cannon_parts=dict(self.cannon_parts),
            missile_parts=dict(self.missile_parts),
            drive_parts=dict(self.drive_parts),
            energy_sources=dict(self.energy_sources),
            hull_parts=dict(self.hull_parts),
            movement_value=self.movement_value,
            energy_consumption=self.energy_consumption,
            energy_production=self.energy_production,
        )

    # Convenience accessors for compatibility with legacy code that expects a
    # cannon breakdown by colour or missile count by type.
    def cannon_breakdown(self) -> Dict[str, int]:
        return dict(self.cannon_parts)

    def missile_breakdown(self) -> Dict[str, int]:
        return dict(self.missile_parts)

    def drive_count(self) -> int:
        return sum(self.drive_parts.values())

