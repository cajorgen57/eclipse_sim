from eclipse_ai.config import _deep_merge, env_overrides

def test_deep_merge_simple():
    a = {"planner": {"sims": 100, "depth": 1}, "value": {"alpha": 0.1}}
    b = {"planner": {"depth": 3}, "value": {"beta": 0.2}}
    c = _deep_merge(a, b)
    assert c["planner"]["sims"] == 100 and c["planner"]["depth"] == 3
    assert c["value"]["alpha"] == 0.1 and c["value"]["beta"] == 0.2

def test_env_overrides_parsing(monkeypatch):
    monkeypatch.setenv("ECLIPSE_AI__PLANNER__SIMS", "512")
    monkeypatch.setenv("ECLIPSE_AI__PLANNER__USE_PW", "true")
    d = env_overrides()
    assert d["planner"]["sims"] == 512
    assert d["planner"]["use_pw"] is True

