from __future__ import annotations

from eclipse_ai import state_assembler
from eclipse_ai.game_models import GameState, MapState, TechDisplay, Hex, Planet, Pieces


def _make_prior(round_num: int = 1) -> GameState:
    return GameState(round=round_num, players={}, map=MapState(), tech_display=TechDisplay())


def test_populate_explore_bags_turn_one_full() -> None:
    catalog = state_assembler._TILE_CATALOG
    assert catalog.total_by_ring, "tile catalog failed to load"

    map_state = MapState(
        hexes={
            "Terran": Hex(
                id="Terran",
                ring=1,
                planets=[Planet("yellow", "P1")],
                pieces={"P1": Pieces(ships={}, starbase=0, discs=1, cubes={})},
            ),
            "Hydran": Hex(
                id="Hydran",
                ring=1,
                planets=[Planet("blue", "P2")],
                pieces={"P2": Pieces(ships={}, starbase=0, discs=1, cubes={})},
            ),
        }
    )

    gs = state_assembler.assemble_state(map_state, TechDisplay(), prior_state=_make_prior(1))

    for ring, total in catalog.total_by_ring.items():
        bag = gs.bags.get(f"R{ring}", {})
        assert bag.get("unknown", 0) == total


def test_populate_explore_bags_round_five_empty() -> None:
    catalog = state_assembler._TILE_CATALOG
    assert catalog.total_by_ring, "tile catalog failed to load"

    map_state = MapState(hexes={})
    gs = state_assembler.assemble_state(map_state, TechDisplay(), prior_state=_make_prior(5))

    for ring in catalog.total_by_ring:
        bag = gs.bags.get(f"R{ring}", {})
        assert sum(bag.values()) == 0
