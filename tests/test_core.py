from collector.url_builder import build_10023s_url
from controller.command_router import parse_command
from engine.market_baseline import dejuice_1x2

def test_url_builder():
    u = build_10023s_url("2026-09-18")
    assert "riqi=2026-09-18" in u
    assert "threshold=1" in u
    assert "bankroll=5000" in u

def test_command():
    x = parse_command("预测 2026-09-18 全部比赛")
    assert x["date"] == "2026-09-18"

def test_dejuice():
    p = dejuice_1x2(2.0, 3.5, 4.0)
    assert abs(p["home"] + p["draw"] + p["away"] - 1.0) < 1e-9
