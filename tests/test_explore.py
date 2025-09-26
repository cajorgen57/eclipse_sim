from __future__ import annotations

import random

import pytest

from eclipse_ai.explore import (
    ExploreState,
    PlayerExploreState,
    choose_explore_target,
    claim_discovery,
    draw_sector_tile,
    discard_sector_tile,
    place_tile,
)
from eclipse_ai.influence import (
    connection_allows_diplomacy,
    connection_allows_influence,
    place_influence_disc,
)
from eclipse_ai.map.decks import (
    DiscoveryDeck,
    DiscoveryTile,
    ExplorationDecks,
    HexTile,
    SectorDeck,
)
from eclipse_ai.map.hex import Hex, MapGraph


PLAYER_ID = "P1"


def _make_state(
    *,
    sector_tiles: list[HexTile] | None = None,
    discovery_tiles: list[DiscoveryTile] | None = None,
    home_wormholes: tuple[int, ...] = (0,),
    has_wormhole_generator: bool = False,
) -> ExploreState:
    map_state = MapGraph()
    home = Hex(id="Home", ring=1, wormholes=home_wormholes)
    home.owner = PLAYER_ID
    map_state.add_hex(home)
    map_state.register_exploration_target(origin="Home", edge=0, target="T1")
    sectors = {
        1: SectorDeck(ring=1, tiles=sector_tiles or [], rng=random.Random(0)),
    }
    discovery = DiscoveryDeck(tiles=discovery_tiles or [], rng=random.Random(0))
    decks = ExplorationDecks(sectors=sectors, discovery=discovery)
    players = {
        PLAYER_ID: PlayerExploreState(
            player_id=PLAYER_ID,
            has_wormhole_generator=has_wormhole_generator,
        )
    }
    return ExploreState(map=map_state, decks=decks, players=players, feature_flags={"warp_portals": True})


def test_explore_discard_ends_turn() -> None:
    tile = HexTile(id="New", ring=1, wormholes=(3,))
    state = _make_state(sector_tiles=[tile])
    choose_explore_target(state, PLAYER_ID, "T1")
    drawn = draw_sector_tile(state, PLAYER_ID, 1)
    discard_sector_tile(state, PLAYER_ID, drawn)
    assert state.players[PLAYER_ID].turn_ended is True


def test_place_requires_connection() -> None:
    tile = HexTile(id="New", ring=1, wormholes=(3,))
    state = _make_state(sector_tiles=[tile], home_wormholes=())
    choose_explore_target(state, PLAYER_ID, "T1")
    draw_sector_tile(state, PLAYER_ID, 1)
    with pytest.raises(ValueError):
        place_tile(state, PLAYER_ID, tile, orient=0)
    state.players[PLAYER_ID].has_wormhole_generator = True
    placed = place_tile(state, PLAYER_ID, tile, orient=0)
    assert placed.id == "T1"


def test_spawn_discovery_and_ancients() -> None:
    tile = HexTile(
        id="AncientDiscovery",
        ring=1,
        wormholes=(3,),
        symbols=("discovery", "ancient", "ancient"),
    )
    discovery_tile = DiscoveryTile(id="D1", effect="money", amount=5)
    state = _make_state(sector_tiles=[tile], discovery_tiles=[discovery_tile])
    choose_explore_target(state, PLAYER_ID, "T1")
    draw_sector_tile(state, PLAYER_ID, 1)
    placed = place_tile(state, PLAYER_ID, tile, orient=0)
    assert placed.discovery_tile == discovery_tile
    assert placed.ancients == 2


def test_control_requires_clearing_ancients_and_gcds() -> None:
    map_state = MapGraph()
    target = Hex(id="Target", ring=1, wormholes=())
    target.ancients = 1
    map_state.add_hex(target)
    decks = ExplorationDecks(
        sectors={1: SectorDeck(ring=1, tiles=[], rng=random.Random(0))},
        discovery=DiscoveryDeck(tiles=[], rng=random.Random(0)),
    )
    players = {PLAYER_ID: PlayerExploreState(player_id=PLAYER_ID)}
    state = ExploreState(map=map_state, decks=decks, players=players, feature_flags={})
    with pytest.raises(ValueError):
        place_influence_disc(state, PLAYER_ID, "Target")
    target.ancients = 0
    target.gcds = True
    with pytest.raises(ValueError):
        place_influence_disc(state, PLAYER_ID, "Target")
    target.gcds = False
    place_influence_disc(state, PLAYER_ID, "Target")
    assert map_state.hexes["Target"].owner == PLAYER_ID


def test_discovery_vp_or_benefit_choice() -> None:
    discovery_tile = DiscoveryTile(id="D-money", effect="money", amount=5)
    map_state = MapGraph()
    hex_obj = Hex(id="DiscoveryHex", ring=1, wormholes=())
    hex_obj.owner = PLAYER_ID
    hex_obj.discovery_tile = discovery_tile
    map_state.add_hex(hex_obj)
    decks = ExplorationDecks(
        sectors={1: SectorDeck(ring=1, tiles=[], rng=random.Random(0))},
        discovery=DiscoveryDeck(tiles=[], rng=random.Random(0)),
    )
    players = {PLAYER_ID: PlayerExploreState(player_id=PLAYER_ID)}
    state = ExploreState(map=map_state, decks=decks, players=players, feature_flags={})
    claim_discovery(state, PLAYER_ID, "DiscoveryHex", keep_vp=False)
    assert players[PLAYER_ID].resources.money == 5
    assert state.decks.discovery.discard_pile  # spent tile is discarded
    hex_obj.discovery_tile = DiscoveryTile(id="D-vp", effect="materials", amount=3)
    claim_discovery(state, PLAYER_ID, "DiscoveryHex", keep_vp=True)
    assert players[PLAYER_ID].discovery_vp == 2
    assert hex_obj.discovery_tile is None


def test_sector_stack_reshuffle_on_empty() -> None:
    tile = HexTile(id="Sector", ring=1, wormholes=(3,))
    state = _make_state(sector_tiles=[tile])
    choose_explore_target(state, PLAYER_ID, "T1")
    first = draw_sector_tile(state, PLAYER_ID, 1)
    discard_sector_tile(state, PLAYER_ID, first)
    state.players[PLAYER_ID].turn_ended = False
    choose_explore_target(state, PLAYER_ID, "T1")
    second = draw_sector_tile(state, PLAYER_ID, 1)
    assert second == first


def test_discovery_reshuffle() -> None:
    deck = DiscoveryDeck(tiles=[DiscoveryTile(id="D1", effect="science", amount=3)], rng=random.Random(0))
    first = deck.draw()
    deck.discard(first)
    second = deck.draw()
    assert second == first


def test_warp_portal_adjacency_for_influence_and_diplomacy() -> None:
    map_state = MapGraph()
    a = Hex(id="A", ring=1, wormholes=())
    b = Hex(id="B", ring=1, wormholes=())
    a.warp_portal = True
    b.warp_portal = True
    map_state.add_hex(a)
    map_state.add_hex(b)
    flags = {"warp_portals": True}
    assert connection_allows_influence(map_state, "A", "B", feature_flags=flags)
    assert connection_allows_diplomacy(map_state, "A", "B", feature_flags=flags)
    flags["warp_portals"] = False
    assert not connection_allows_influence(map_state, "A", "B", feature_flags=flags)
    assert not connection_allows_diplomacy(map_state, "A", "B", feature_flags=flags)


def test_diplomacy_requires_full_link_not_wg() -> None:
    map_state = MapGraph()
    a = Hex(id="A", ring=1, wormholes=(0,))
    b = Hex(id="B", ring=1, wormholes=())
    map_state.add_hex(a)
    map_state.add_hex(b)
    map_state.ensure_neighbor_link("A", 0, "B")
    flags = {"warp_portals": False}
    assert not connection_allows_influence(map_state, "A", "B", feature_flags=flags)
    assert connection_allows_influence(map_state, "A", "B", feature_flags=flags, player_has_wg=True)
    assert not connection_allows_diplomacy(map_state, "A", "B", feature_flags=flags)
