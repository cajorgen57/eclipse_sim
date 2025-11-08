from types import SimpleNamespace

from eclipse_ai.opponents.threat import build_threat_map
from eclipse_ai.opponents.types import OpponentMetrics


class Sector(SimpleNamespace):
    pass


def mk_board() -> SimpleNamespace:
    a = Sector(id="A", owner=0)
    b = Sector(id="B", owner=1)
    a.neighbors = [b]
    b.neighbors = [a]
    return SimpleNamespace(sectors=[a, b])


def test_threat_adjacent_opponent() -> None:
    board = mk_board()
    metrics = {1: OpponentMetrics(aggression=0.8, fleet_power=0.7)}
    tmap = build_threat_map(board, my_id=0, metrics_by_player=metrics)
    assert "A" in tmap.danger
    assert tmap.danger["A"][1] > 0.5

