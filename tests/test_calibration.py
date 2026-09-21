from research.calibration import calibrate
from research.calibration.report import render_calibration_report


def _joined(mid, probs, score, market=None, league="联赛"):
    h, a = map(int, score.split("-"))
    actual = "HOME" if h > a else "AWAY" if h < a else "DRAW"
    return {
        "date": "2026-09-01",
        "match_id": str(mid),
        "home_team": "A",
        "away_team": "B",
        "league": league,
        "market": market or {"home_odds": 1.6, "draw_odds": 3.8, "away_odds": 5.5},
        "research_prediction": {
            "page_probability": probs,
            "page_prediction": {"scores": "1-0 2-0", "htft": "平/主"},
        },
        "label_status": "MATCHED",
        "result_label": {"actual_outcome": actual, "actual_score": score},
        "research_factors": {"risk": "低"},
        "value": {"ev": 0.1, "kelly": 2},
    }


def test_calibration_is_read_only_and_has_all_five_areas():
    rows = [_joined(i, {"home": .70, "draw": .18, "away": .12}, "2-0") for i in range(1, 26)]
    result = calibrate(rows, {"summary": {}, "rows": []})
    assert result["stable_access"] == "READ_ONLY"
    assert result["guardrails"]["automatic_stable_write"] is False
    assert result["guardrails"]["forbidden_inputs"] == ["建议下注", "是否下注"]
    assert result["risk_score"]["threshold_scan"]
    assert result["probability_margin"]["threshold_scan"]
    assert result["value_edge"]["threshold_scan"]
    assert "strong_favorite" in result["match_type"]
    assert "output_error" in result


def test_calibration_report_marks_candidates_only():
    rows = [_joined(i, {"home": .70, "draw": .18, "away": .12}, "2-0") for i in range(1, 26)]
    result = calibrate(rows, {"summary": {}, "rows": []})
    text = render_calibration_report(result, "2026-08-01", "2026-09-20")
    assert "CANDIDATE_ONLY" in text
    assert "自动修改Stable：禁止" in text
