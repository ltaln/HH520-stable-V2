from research.result_joiner import join_results


def test_join_uses_date_and_match_id_not_match_id_alone():
    prematch = [
        {"date":"2026-08-01","match_id":"1","home_team":"A"},
        {"date":"2026-08-02","match_id":"1","home_team":"C"},
    ]
    labels = [
        {"date":"2026-08-01","match_id":"1","actual_score":"2-0","actual_outcome":"HOME","actual_total_goals":2},
        {"date":"2026-08-02","match_id":"1","actual_score":"0-1","actual_outcome":"AWAY","actual_total_goals":1},
    ]
    joined = join_results(prematch, labels)
    assert joined[0]["result_label"]["actual_outcome"] == "HOME"
    assert joined[1]["result_label"]["actual_outcome"] == "AWAY"
    assert joined[0]["result_label"]["actual_score"] == "2-0"
    assert joined[1]["result_label"]["actual_score"] == "0-1"
