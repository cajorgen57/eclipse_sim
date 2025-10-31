from eclipse_ai.reports.run_report import _sanitize_payload

def test_sanitize_drops_raw_and_truncates():
    p = {"__raw__": object(), "name":"X", "blob":"Y"*500}
    s = _sanitize_payload(p)
    assert "__raw__" not in s and len(s["blob"]) < 250
