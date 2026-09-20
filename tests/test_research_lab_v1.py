import pytest
from research.lab import date_range, build_research_report
from research.sanitizer import sanitize_record

def test_sanitizer_removes_post_match_fields():
    clean, removed = sanitize_record({
        "home_team": "A", "away_team": "B", "result": "2:1",
        "final_score": "2:1", "market": {"home_odds": 2.0}
    })
    assert "result" not in clean
    assert "final_score" not in clean
    assert set(removed) == {"final_score", "result"}
    assert clean["home_team"] == "A"

def test_research_report_never_promotes_to_stable():
    records = [{"league": "L", "home_team": "A", "away_team": "B", "status": "READY_FOR_GPT"}]
    report = build_research_report(records, "2026-09-01", "2026-09-01")
    assert report["stable_access"] == "READ_ONLY"
    assert report["promotion_policy"] == "MANUAL_REVIEW_REQUIRED"
    assert report["league_dna"]["L"]["matches"] == 1

def test_date_range_limits_window():
    assert date_range("2026-09-01", "2026-09-02") == ["2026-09-01", "2026-09-02"]
    with pytest.raises(ValueError):
        date_range("2026-01-01", "2026-03-01")
