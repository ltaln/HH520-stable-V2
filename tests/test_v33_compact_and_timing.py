import json

from collector.goal_timing_service import _team, _team_half_rates
from engine.htft_layer import htft_layer
from scripts.publish_action_result import _prediction_summary


def test_prediction_summary_is_compact_and_six_column_authoritative():
    contract = {
        "version": "HH520-OUTPUT-V3.3",
        "stable_version": "HH520 Stable V3.3",
        "strict": True,
        "required_columns": [
            "球队对阵", "胜平负场景", "市场概率",
            "比分×2及概率", "半全场×2及概率", "总进球及概率",
        ],
        "display_rows": [{"球队对阵": "A vs B"}],
        "render_rule": "six",
    }
    data = {
        "date": "2026-09-22",
        "captured_at": "now",
        "goal_timing_summary": {"enabled": True, "attempted": 1, "available": 1},
        "predictions": [{
            "match_id": "1", "home_team": "A", "away_team": "B",
            "direction": "主胜", "alternate_direction": "平", "state": "BALANCED",
            "market_probability": 0.42,
            "score1": "1:0", "score2": "1:1",
            "score1_probability": 0.1, "score2_probability": 0.09,
            "htft1": "主/主", "htft2": "平/平",
            "htft1_probability": 0.2, "htft2_probability": 0.18,
            "total_goals": "2球", "total_goals_probability": 0.25,
            "decision_filter": {"huge": "x" * 50000},
            "consistency": {"huge": "x" * 50000},
        }],
        "output_contract": contract,
        "display_rows": contract["display_rows"],
        "gpt_handoff": {"huge": "x" * 50000},
    }
    out = _prediction_summary(data, "hh520-test-1234")
    assert out["status"] == "READY"
    assert out["archive_path"] == "archive/hh520-test-1234.json"
    assert out["output_contract"]["required_columns"] == contract["required_columns"]
    assert "gpt_handoff" not in out
    assert "decision_filter" not in out["predictions"][0]
    assert "consistency" not in out["predictions"][0]
    assert len(json.dumps(out, ensure_ascii=False)) < 10000


def test_goal_timing_six_bin_and_half_rate_normalization():
    exact = _team({
        "goals_for": [2, 1, 1, 2, 2, 2],
        "goals_against": [1, 1, 2, 2, 2, 2],
        "scope": "season",
    })
    assert exact is not None
    assert abs(exact["first_half_gf_signal"] - 0.4) < 1e-9
    assert abs(exact["first_half_ga_signal"] - 0.4) < 1e-9

    fallback = _team_half_rates({
        "first_half_scoring_rate": 40,
        "first_half_conceding_rate": 35,
        "second_half_scoring_rate": 55,
        "second_half_conceding_rate": 45,
        "scope": "last10",
    })
    assert fallback is not None
    assert fallback["first_half_gf_signal"] == 0.4
    assert fallback["first_half_ga_signal"] == 0.35


def test_htft_accepts_half_aggregate_fallback_and_preserves_ft_anchor():
    probability = {
        "valid": True,
        "probabilities": {"home": 0.5, "draw": 0.3, "away": 0.2},
    }
    match = {
        "goal_timing": {
            "available": True,
            "timing_mode": "half_aggregate_fallback",
            "source_domain": "footystats.org",
            "home": {
                "first_half_gf_signal": 0.70,
                "first_half_ga_signal": 0.25,
            },
            "away": {
                "first_half_gf_signal": 0.35,
                "first_half_ga_signal": 0.60,
            },
        }
    }
    out = htft_layer(probability, match)
    assert out["valid"] is True
    assert out["timing_used"] is True
    assert out["timing_mode"] == "half_aggregate_fallback"
    assert out["ft_marginal_preserved"] is True
    home_ft = sum(x["probability"] for x in out["distribution"] if x["ft"] == "HOME")
    draw_ft = sum(x["probability"] for x in out["distribution"] if x["ft"] == "DRAW")
    away_ft = sum(x["probability"] for x in out["distribution"] if x["ft"] == "AWAY")
    assert abs(home_ft - 0.5) < 1e-9
    assert abs(draw_ft - 0.3) < 1e-9
    assert abs(away_ft - 0.2) < 1e-9
