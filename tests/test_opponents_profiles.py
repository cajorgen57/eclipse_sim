from eclipse_ai.opponents.infer import OpponentStyle, infer_style
from eclipse_ai.opponents.types import OpponentMetrics


def test_infer_style_rusher_vs_techer() -> None:
    m_r = OpponentMetrics(aggression=0.9, build_intensity=0.8, mobility=0.7)
    style_r, conf_r, tags_r = infer_style(m_r)
    assert style_r == OpponentStyle.RUSHER
    assert conf_r >= 0.5
    assert "aggressive" in tags_r

    m_t = OpponentMetrics(tech_pace=0.85, upgrade_intensity=0.7, aggression=0.2)
    style_t, conf_t, tags_t = infer_style(m_t)
    assert style_t == OpponentStyle.TECHER
    assert conf_t >= 0.5
    assert "techer" in tags_t

