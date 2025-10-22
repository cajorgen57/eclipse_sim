from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional


_DEFAULT_CUMULATIVE_COST: List[int] = [0, 1, 2, 3, 4, 5, 7, 9, 12, 16, 21, 27]


@dataclass(slots=True)
class Economy:
    """Lightweight snapshot of a player's orange economy state."""

    orange_bank: int = 0
    orange_income: int = 0
    orange_upkeep_fixed: int = 0
    action_slots_filled: int = 0
    action_track_cum_cost: List[int] = field(
        default_factory=lambda: list(_DEFAULT_CUMULATIVE_COST)
    )

    def _cum_cost(self, slots: int) -> int:
        if not self.action_track_cum_cost:
            return 0
        if slots <= 0:
            return 0
        if slots < len(self.action_track_cum_cost):
            return self.action_track_cum_cost[slots]
        # Clamp to last known value; callers should ensure the table is long enough.
        return self.action_track_cum_cost[-1]

    def max_additional_actions(self) -> int:
        """Maximum number of additional action slots affordable this round."""

        base_cum = self._cum_cost(self.action_slots_filled)
        budget = self.orange_bank + self.orange_income - self.orange_upkeep_fixed
        remaining = budget - base_cum
        if remaining < 0:
            return 0
        hi = max(0, len(self.action_track_cum_cost) - 1 - self.action_slots_filled)
        lo = 0
        while lo < hi:
            mid = (lo + hi + 1) // 2
            need = self._cum_cost(self.action_slots_filled + mid) - base_cum
            if need <= remaining:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def prefix_affordable(self, added_actions: int) -> bool:
        """Return ``True`` if the next ``added_actions`` slots remain affordable."""

        if added_actions <= 0:
            return True
        base_cum = self._cum_cost(self.action_slots_filled)
        budget = self.orange_bank + self.orange_income - self.orange_upkeep_fixed
        remaining = budget - base_cum
        if remaining < 0:
            return False
        need = self._cum_cost(self.action_slots_filled + added_actions) - base_cum
        return need <= remaining

    def refresh(
        self,
        *,
        bank: Optional[int] = None,
        income: Optional[int] = None,
        upkeep_fixed: Optional[int] = None,
        action_slots_filled: Optional[int] = None,
    ) -> None:
        if bank is not None:
            self.orange_bank = int(bank)
        if income is not None:
            self.orange_income = int(income)
        if upkeep_fixed is not None:
            self.orange_upkeep_fixed = max(0, int(upkeep_fixed))
        if action_slots_filled is not None:
            self.action_slots_filled = max(0, int(action_slots_filled))


def count_action_discs(player: Any) -> int:
    """Return the number of discs occupying the player's action board."""

    board = getattr(player, "action_spaces", {}) or {}
    total = 0
    if isinstance(board, Mapping):
        iterator: Iterable[Any] = board.values()
    else:
        iterator = []
    for slots in iterator:
        if isinstance(slots, Iterable) and not isinstance(slots, (str, bytes)):
            try:
                total += sum(1 for _ in slots)
            except TypeError:
                # Fallback: treat as sized container
                try:
                    total += len(slots)  # type: ignore[arg-type]
                except Exception:
                    continue
        else:
            try:
                total += len(slots)  # type: ignore[arg-type]
            except Exception:
                continue
    return total


def count_influence_discs(state: Any, player_id: str) -> int:
    """Count discs the player has committed on the map (influence upkeep)."""

    map_state = getattr(state, "map", None)
    if map_state is None:
        return 0
    hexes: Mapping[Any, Any] = getattr(map_state, "hexes", {}) or {}
    total = 0
    for hex_obj in hexes.values():
        pieces = getattr(hex_obj, "pieces", None)
        entry = None
        if isinstance(pieces, Mapping):
            entry = pieces.get(player_id)
        elif pieces is not None:
            entry = getattr(pieces, player_id, None)
        if entry is None:
            continue
        discs = getattr(entry, "discs", 0)
        try:
            total += int(discs or 0)
        except Exception:
            continue
    return total
