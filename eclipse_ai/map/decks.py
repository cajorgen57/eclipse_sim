from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass
class HexTile:
    """Prototype for an unexplored hex tile."""

    id: str
    ring: int
    wormholes: Sequence[int]
    symbols: Sequence[str] = field(default_factory=tuple)
    warp_portal: bool = False
    gcds: bool = False


@dataclass
class DiscoveryTile:
    """Representation of a discovery tile."""

    id: str
    effect: str
    amount: int = 0

    def apply(self, player: "PlayerProtocol") -> None:
        """Execute the immediate effect of the tile on ``player``."""

        if self.effect == "money":
            player.resources.money += self.amount
        elif self.effect == "science":
            player.resources.science += self.amount
        elif self.effect == "materials":
            player.resources.materials += self.amount
        elif self.effect == "ancient_tech":
            player.ancient_tech += 1
        elif self.effect == "ancient_cruiser":
            player.ancient_cruisers += 1
        elif self.effect == "ancient_part":
            player.ancient_parts += 1
        else:
            raise ValueError(f"Unknown discovery effect: {self.effect}")


class PlayerProtocol:
    resources: "ResourcePool"
    ancient_tech: int
    ancient_cruisers: int
    ancient_parts: int


@dataclass
class ResourcePool:
    money: int = 0
    science: int = 0
    materials: int = 0


@dataclass
class _DeckBase:
    draw_pile: List
    discard_pile: List = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def draw(self):
        if not self.draw_pile:
            self._reshuffle_from_discards()
        if not self.draw_pile:
            raise RuntimeError("Deck is empty and no discards are available")
        return self.draw_pile.pop()

    def discard(self, item) -> None:
        self.discard_pile.append(item)

    def _reshuffle_from_discards(self) -> None:
        if not self.discard_pile:
            return
        self.draw_pile = list(self.discard_pile)
        self.discard_pile.clear()
        self.rng.shuffle(self.draw_pile)


@dataclass
class SectorDeck(_DeckBase):
    """Sector stack for a given ring."""

    ring: int = 1

    def __init__(self, *, ring: int, tiles: Optional[Sequence[HexTile]] = None, rng: Optional[random.Random] = None):
        tiles = list(tiles or [])
        rng = rng or random.Random()
        super().__init__(draw_pile=list(tiles), discard_pile=[], rng=rng)
        self.ring = ring


@dataclass
class DiscoveryDeck(_DeckBase):
    """Stack for discovery tiles."""

    def __init__(self, *, tiles: Optional[Sequence[DiscoveryTile]] = None, rng: Optional[random.Random] = None):
        tiles = list(tiles or [])
        rng = rng or random.Random()
        super().__init__(draw_pile=list(tiles), discard_pile=[], rng=rng)


@dataclass
class ExplorationDecks:
    sectors: Dict[int, SectorDeck]
    discovery: DiscoveryDeck

    def get_sector(self, ring: int) -> SectorDeck:
        try:
            return self.sectors[ring]
        except KeyError as exc:
            raise KeyError(f"No sector deck for ring {ring}") from exc
