"""Identity matching acceptance tests for Dongqiudi candidate integration."""
from datetime import datetime, timezone, timedelta
from integration.dongqiudi_fixture_matcher import match_fixture

BASE = {"league": "英超", "kickoff": "2026-10-11T15:00:00+08:00",
        "home": "利物浦", "away": "曼城"}
ALIASES = {"Liverpool": "利物浦", "Manchester City": "曼城"}
LEAGUES = {"Premier League": "英超"}

def test_alias_and_timezone():
    other = {"league": "Premier League", "kickoff": "2026-10-11T07:00:00Z",
             "home": "Liverpool", "away": "Manchester City"}
    status, match = match_fixture(BASE, [other], LEAGUES, ALIASES)
    assert status == "MATCHED" and match is other

def test_no_cross_match_same_time_league():
    other = {"league": "Premier League", "kickoff": BASE["kickoff"],
             "home": "Liverpool", "away": "Arsenal"}
    assert match_fixture(BASE, [other], LEAGUES, ALIASES)[0] == "NO_FIXTURE_MATCH"

def test_ambiguous_duplicate():
    other = {"league": "Premier League", "kickoff": BASE["kickoff"],
             "home": "Liverpool", "away": "Manchester City"}
    assert match_fixture(BASE, [other, dict(other)], LEAGUES, ALIASES)[0] == "AMBIGUOUS_MATCH"

def test_swapped_teams_rejected():
    other = {"league": "英超", "kickoff": BASE["kickoff"],
             "home": "曼城", "away": "利物浦"}
    assert match_fixture(BASE, [other], LEAGUES, ALIASES)[0] == "NO_FIXTURE_MATCH"

def test_outside_time_window():
    other = {"league": "英超", "kickoff": "2026-10-11T07:20:00Z",
             "home": "利物浦", "away": "曼城"}
    assert match_fixture(BASE, [other], LEAGUES, ALIASES)[0] == "NO_FIXTURE_MATCH"
