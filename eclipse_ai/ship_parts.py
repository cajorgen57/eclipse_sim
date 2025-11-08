"""Canonical definitions for ship parts and blueprint metadata.

This module centralises the per-part data so that both the rules engine and
tests share a single source of truth. Only a subset of the Eclipse catalog is
encoded; it is sufficient for legality checks and can be extended as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ShipPart:
    """Static data describing a ship part tile."""

    name: str
    category: str  # computer, shield, cannon, missile, drive, energy, hull
    weapon_type: Optional[str] = None  # ion, plasma, gauss, antimatter
    weapon_strength: int = 0
    missiles: int = 0
    computer: int = 0
    shield: int = 0
    hull: int = 0
    initiative: int = 0
    movement: int = 0
    energy_consumption: int = 0
    energy_production: int = 0
    requires_tech: Optional[str] = None
    slots: int = 1


# Primary ship parts referenced by the tests and legality checks. Values are
# derived from Eclipse 2E, with initiative bonuses simplified for drives.
SHIP_PARTS: Dict[str, ShipPart] = {
    "Ion Cannon": ShipPart(
        name="Ion Cannon",
        category="cannon",
        weapon_type="ion",
        weapon_strength=1,
    ),
    "Plasma Cannon": ShipPart(
        name="Plasma Cannon",
        category="cannon",
        weapon_type="plasma",
        weapon_strength=2,
        energy_consumption=2,
        requires_tech="Plasma Cannon",
    ),
    "Electron Computer": ShipPart(
        name="Electron Computer",
        category="computer",
        computer=1,
        energy_consumption=1,
    ),
    "Positron Computer": ShipPart(
        name="Positron Computer",
        category="computer",
        computer=2,
        energy_consumption=2,
        requires_tech="Positron Computer",
    ),
    "Gauss Shield": ShipPart(
        name="Gauss Shield",
        category="shield",
        shield=2,
        energy_consumption=1,
        requires_tech="Gauss Shield",
    ),
    "Hull": ShipPart(
        name="Hull",
        category="hull",
        hull=1,
    ),
    "Improved Hull": ShipPart(
        name="Improved Hull",
        category="hull",
        hull=2,
        requires_tech="Improved Hull",
    ),
    "Nuclear Drive": ShipPart(
        name="Nuclear Drive",
        category="drive",
        movement=1,
        initiative=1,
        energy_consumption=1,
    ),
    "Fusion Drive": ShipPart(
        name="Fusion Drive",
        category="drive",
        movement=2,
        initiative=2,
        energy_consumption=2,
        requires_tech="Fusion Drive",
    ),
    "Antimatter Drive": ShipPart(
        name="Antimatter Drive",
        category="drive",
        movement=3,
        initiative=3,
        energy_consumption=3,
        requires_tech="Antimatter Drive",
    ),
    "Nuclear Source": ShipPart(
        name="Nuclear Source",
        category="energy",
        energy_production=3,
    ),
    "Fusion Source": ShipPart(
        name="Fusion Source",
        category="energy",
        energy_production=6,
        requires_tech="Fusion Source",
    ),
    "Plasma Missile": ShipPart(
        name="Plasma Missile",
        category="missile",
        missiles=2,
        initiative=2,
        energy_consumption=1,
        requires_tech="Plasma Missile",
    ),
}


# Blueprint slot limits by ship class (Eclipse 2E reference board).
SHIP_BLUEPRINT_SLOTS: Dict[str, int] = {
    "interceptor": 6,
    "cruiser": 8,
    "dreadnought": 10,
    "starbase": 6,
}


MOBILE_SHIPS = {"interceptor", "cruiser", "dreadnought"}

