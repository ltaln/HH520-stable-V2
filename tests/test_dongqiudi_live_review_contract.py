from pathlib import Path

from collector import dongqiudi_runtime
from collector.dongqiudi_source import parse_analysis_markdown
from engine.full_data_layer import data_mode


INSTRUCTIONS = Path("integration/CHATGPT_INSTRUCTIONS.md").read_text(encoding="utf-8")


def test_dongqiudi_is_formal_collector_not_post_ready_review():
    assert "Dongqiudi is part of the **formal collection/enrichment chain**" in INSTRUCTIONS
    assert "10027S base -> Dongqiudi per-fixture enrichment" in INSTRUCTIONS
    assert "Do not run a second post-READY web-review workflow" in INSTRUCTIONS


def test_dongqiudi_result_stability_can_complete_full_data_profile():
    match = {
        "goal_timing": {
            "available": True,
            "home": {
                "first_half_gf_signal": 0.45, "first_half_ga_signal": 0.40,
                "profile_stats": {"shots": 12.0, "shots_on_target": 5.0},
            },
            "away": {
                "first_half_gf_signal": 0.40, "first_half_ga_signal": 0.48,
                "profile_stats": {"shots": 10.0, "shots_on_target": 4.0},
            },
        },
        "dongqiudi_enrichment": {
            "available": True,
            "home": {"wins_rate": 0.5, "draws_rate": 0.3, "losses_rate": 0.2, "scored_per_match": 1.6, "conceded_per_match": 1.0},
            "away": {"wins_rate": 0.3, "draws_rate": 0.3, "losses_rate": 0.4, "scored_per_match": 1.2, "conceded_per_match": 1.3},
        },
    }
    result = data_mode(match)
    assert result["mode"] == "FULL_DATA"
    assert result["dongqiudi_available"] is True


def test_runtime_caches_formal_dongqiudi_result(tmp_path, monkeypatch):
    monkeypatch.setattr(dongqiudi_runtime.cache_manager, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        dongqiudi_runtime,
        "collect_match_analysis",
        lambda date, home, away, **kwargs: {
            "available": True,
            "home": {"wins_rate": 0.5, "draws_rate": 0.3, "losses_rate": 0.2},
            "away": {"wins_rate": 0.3, "draws_rate": 0.3, "losses_rate": 0.4},
        },
    )
    match = {
        "league": "TEST", "kickoff": "2026-10-15T20:00:00+08:00",
        "home_team": "主队", "away_team": "客队",
    }
    first = dongqiudi_runtime.collect_dongqiudi_for_match("2026-10-15", match)
    second = dongqiudi_runtime.collect_dongqiudi_for_match("2026-10-15", match)
    assert first["available"] is True and first["formal_enrichment"] is True
    assert second["cache_hit"] is True
    assert second["fixture_identity"]["league"] == "TEST"


def test_dongqiudi_analysis_parses_shots_and_six_bin_timing():
    markdown = """
主队
客队
射门 12 - 9
射正 5 - 3
控球率 55% - 45%
危险进攻 42 - 31
重大机会 4 - 2
6胜 2平 2负
近10场战绩
3胜 3平 4负
1.8球
场均进球
1.2球
1.0球
场均失球
1.4球
主队 进球 2 3 4 5 6 7
主队 失球 1 2 3 4 5 6
客队 进球 1 1 2 2 3 3
客队 失球 3 2 2 1 1 1
"""
    parsed = parse_analysis_markdown(markdown, "主队", "客队")
    assert parsed["home"]["shots"] == 12.0
    assert parsed["away"]["shots_on_target"] == 3.0
    assert parsed["home"]["shots_off_target"] == 7.0
    assert parsed["home"]["shot_on_target_rate"] == 5.0/12.0
    assert parsed["home"]["possession"] == 0.55
    assert parsed["away"]["dangerous_attacks"] == 31.0
    assert parsed["home"]["big_chances"] == 4.0
    assert parsed["home"]["goals_for_bins"] == [2.0,3.0,4.0,5.0,6.0,7.0]
    assert len(parsed["home"]["goals_for_share"]) == 6
    assert parsed["groups"]["SHOTS"] is True
    assert parsed["groups"]["GOAL_TIMING"] is True


def test_full_data_can_use_dongqiudi_timing_without_secondary_timing_source():
    match = {
        "goal_timing": {"available": False},
        "dongqiudi_enrichment": {
            "available": True,
            "home": {
                "shots": 12.0, "shots_on_target": 5.0,
                "wins_rate": 0.6, "draws_rate": 0.2, "losses_rate": 0.2,
                "scored_per_match": 1.8, "conceded_per_match": 1.0,
                "goals_for_share": [0.1,0.15,0.2,0.2,0.2,0.15],
                "goals_against_share": [0.1,0.15,0.15,0.2,0.2,0.2],
                "first_half_gf_signal": 0.45, "first_half_ga_signal": 0.40,
            },
            "away": {
                "shots": 9.0, "shots_on_target": 3.0,
                "wins_rate": 0.3, "draws_rate": 0.3, "losses_rate": 0.4,
                "scored_per_match": 1.2, "conceded_per_match": 1.4,
                "goals_for_share": [0.1,0.13,0.15,0.2,0.22,0.2],
                "goals_against_share": [0.2,0.15,0.15,0.15,0.15,0.2],
                "first_half_gf_signal": 0.38, "first_half_ga_signal": 0.50,
            },
        },
    }
    result = data_mode(match)
    assert result["mode"] == "FULL_DATA"
    assert result["timing_available"] is True


def test_full_data_rejects_partial_dongqiudi_core_fields():
    match = {
        "goal_timing": {"available": False},
        "dongqiudi_enrichment": {
            "available": True,
            "home": {
                "shots": 12.0,
                "wins_rate": 0.6, "draws_rate": 0.2, "losses_rate": 0.2,
                "scored_per_match": 1.8, "conceded_per_match": 1.0,
                "first_half_gf_signal": 0.45, "first_half_ga_signal": 0.40,
            },
            "away": {
                "shots": 9.0, "shots_on_target": 3.0,
                "wins_rate": 0.3, "draws_rate": 0.3, "losses_rate": 0.4,
                "scored_per_match": 1.2, "conceded_per_match": 1.4,
                "first_half_gf_signal": 0.38, "first_half_ga_signal": 0.50,
            },
        },
    }
    result = data_mode(match)
    assert result["mode"] == "10027_ONLY"
