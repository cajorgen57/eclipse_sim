from eclipse_ai.data.exploration_tiles import (
    load_exploration_tiles,
    tile_counts_by_ring,
    tile_numbers_by_ring,
    tiles_by_ring,
)


def test_loads_known_tile() -> None:
    tiles = load_exploration_tiles()
    assert "105" in tiles
    tile = tiles["105"]
    assert tile.ring == 1
    assert tile.discovery_tile is True
    assert tile.resources["science"] == 1
    assert tile.advanced_resources["money"] == 0


def test_counts_align_with_numbers() -> None:
    counts = tile_counts_by_ring()
    numbers = tile_numbers_by_ring()
    assert counts
    for ring, ids in numbers.items():
        assert counts[ring] == len(ids)
        assert all(rec.tile_number in ids for rec in tiles_by_ring(ring))
