"""No-network parser and safety tests."""
from datetime import datetime, timezone
import pytest
from integration.dongqiudi_collector import parse_page, validate_url, collect

URL = "https://m.dongqiudi.com/match/123"

def test_labeled_metrics_only():
    html = "<html><body>射门 12 - 8 射正 5 - 3 进球 2 - 1</body></html>"
    result = parse_page(html, url=URL)
    assert result["metrics"]["shots"] == {"home": 12.0, "away": 8.0}
    assert result["metrics"]["shots_on_target"]["away"] == 3.0
    assert result["complete"] is False
    assert "goal_timing" in result["missing_fields"]

def test_unstructured_content_does_not_invent_stats():
    result = parse_page("<html><body>球队战报和新闻</body></html>", url=URL)
    assert result["metrics"] == {}
    assert result["status"] == "NO_STRUCTURED_STATS"

def test_block_unsafe_urls():
    for url in ("http://m.dongqiudi.com/", "https://evil.com/",
                "https://m.dongqiudi.com.evil.com/"):
        with pytest.raises(ValueError):
            validate_url(url)

def test_post_kickoff_never_fetches():
    result = collect(URL, as_of="2020-01-01T00:00:00Z")
    assert result["status"] == "POST_KICKOFF_DATA"
