from collector import dongqiudi_technical as tech


def _overview(shots_a, shots_b, sot_a, sot_b, possession_a, possession_b, danger_a, danger_b, big_a, big_b, events):
    return {
        "statistics": {
            "list": [
                {"type": "射门", "team_A": {"value": shots_a}, "team_B": {"value": shots_b}},
                {"type": "射正", "team_A": {"value": sot_a}, "team_B": {"value": sot_b}},
                {"type": "射偏", "team_A": {"value": shots_a-sot_a}, "team_B": {"value": shots_b-sot_b}},
                {"type": "控球率", "team_A": {"value": possession_a}, "team_B": {"value": possession_b}},
                {"type": "危险进攻", "team_A": {"value": danger_a}, "team_B": {"value": danger_b}},
                {"type": "绝佳机会", "team_A": {"value": big_a}, "team_B": {"value": big_b}},
                {"type": "预期进球(xG)", "team_A": {"value": 1.7}, "team_B": {"value": 1.1}},
            ]
        },
        "events": events,
    }


def test_schedule_api_fallback_builds_complete_prematch_history(monkeypatch):
    target_id = "54493236"
    lineup = {
        "persons": {
            "team_A": {"team_id": 50001762, "team_name": "比利亚雷亚尔"},
            "team_B": {"team_id": 50001764, "team_name": "皇家贝蒂斯"},
        },
        "recent_match_persons": None,
    }
    schedules = {
        "50001762": [
            {"match_id": "54493221", "status": "Played", "start_play": "2026-09-05 19:00:00",
             "team_A_id": "50001762", "team_B_id": "1", "team_A_name": "比利亚雷亚尔", "team_B_name": "对手1"},
            {"match_id": "54577265", "status": "Played", "start_play": "2026-09-08 19:00:00",
             "team_A_id": "2", "team_B_id": "50001762", "team_A_name": "对手2", "team_B_name": "比利亚雷亚尔"},
            {"match_id": target_id, "status": "Played", "start_play": "2026-09-14 19:00:00",
             "team_A_id": "50001762", "team_B_id": "50001764", "team_A_name": "比利亚雷亚尔", "team_B_name": "皇家贝蒂斯"},
        ],
        "50001764": [
            {"match_id": "7001", "status": "Played", "start_play": "2026-09-03 18:00:00",
             "team_A_id": "50001764", "team_B_id": "3", "team_A_name": "皇家贝蒂斯", "team_B_name": "对手3"},
            {"match_id": "7002", "status": "Played", "start_play": "2026-09-09 18:00:00",
             "team_A_id": "4", "team_B_id": "50001764", "team_A_name": "对手4", "team_B_name": "皇家贝蒂斯"},
            {"match_id": target_id, "status": "Played", "start_play": "2026-09-14 19:00:00",
             "team_A_id": "50001762", "team_B_id": "50001764", "team_A_name": "比利亚雷亚尔", "team_B_name": "皇家贝蒂斯"},
        ],
    }

    event_home = {
        "20": {"minute": "20", "teamAEvents": [{"code": "G"}], "teamBEvents": []},
        "70": {"minute": "70", "teamAEvents": [], "teamBEvents": [{"code": "G"}]},
    }
    event_away = {
        "10": {"minute": "10", "teamAEvents": [{"code": "G"}], "teamBEvents": []},
        "80": {"minute": "80", "teamAEvents": [], "teamBEvents": [{"code": "G"}]},
    }
    overviews = {
        "54493221": _overview(14, 8, 6, 3, 58, 42, 55, 30, 4, 1, event_home),
        "54577265": _overview(18, 13, 6, 6, 52, 48, 67, 25, 6, 2, event_away),
        "7001": _overview(11, 7, 5, 2, 60, 40, 44, 23, 3, 1, event_home),
        "7002": _overview(16, 10, 7, 4, 49, 51, 38, 41, 5, 2, event_away),
    }

    monkeypatch.setattr(tech, "_lineup", lambda match_id: lineup)
    monkeypatch.setattr(tech, "_schedule_rows", lambda team_id, target_dt=None: schedules[str(team_id)])
    monkeypatch.setattr(tech, "_overview", lambda match_id: overviews[str(match_id)])

    result = tech.collect_prematch_technical_history(
        target_id, "比利亚雷亚尔", "皇家贝蒂斯", "2026-09-14T19:00:00+00:00"
    )

    assert result["home"]["sample_count"] == 2
    assert result["away"]["sample_count"] == 2
    assert target_id not in [x["match_id"] for x in result["home"]["observations"]]
    assert result["home"]["metrics"]["shots"] == 13.5
    assert result["home"]["metrics"]["shots_on_target"] == 6.0
    assert result["home"]["metrics"]["shots_off_target"] == 7.5
    assert result["home"]["metrics"]["possession"] == 0.53
    assert result["home"]["metrics"]["dangerous_attacks"] == 40.0
    assert result["home"]["metrics"]["big_chances"] == 3.0
    assert len(result["home"]["metrics"]["goals_for_share"]) == 6
    assert len(result["away"]["metrics"]["goals_against_share"]) == 6


def test_goal_bins_counts_penalty_and_own_goal_correctly():
    overview = {
        "events": {
            "12": {"minute": "12", "teamAEvents": [{"code": "PG"}], "teamBEvents": []},
            "50": {"minute": "50", "teamAEvents": [{"code": "OG"}], "teamBEvents": []},
        }
    }
    bins = tech._goal_bins(overview)
    assert bins["team_A"][0] == 1.0
    assert bins["team_B"][3] == 1.0
