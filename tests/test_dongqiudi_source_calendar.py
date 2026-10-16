from collector.dongqiudi_source import _fixture_date_variants, _candidate_queries

def test_after_midnight_fixture_accepts_next_calendar_day():
    assert _fixture_date_variants("2026-10-16","03:00") == ["2026-10-16","2026-10-17"]

def test_evening_fixture_does_not_expand_calendar_day():
    assert _fixture_date_variants("2026-10-16","17:00") == ["2026-10-16"]

def test_candidate_queries_include_next_day_for_overnight():
    queries=_candidate_queries("2026-10-16","拉科","莱万特","03:00")
    assert any("2026-10-17" in q for q in queries)

def test_candidate_queries_do_not_expand_normal_kickoff():
    queries=_candidate_queries("2026-10-16","悉尼FC","西悉尼","17:00")
    assert not any("2026-10-17" in q for q in queries)
