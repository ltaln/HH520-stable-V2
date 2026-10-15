from pathlib import Path

from collector import dongqiudi_runtime
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
                "profile_stats": {"shots": 12.0},
            },
            "away": {
                "first_half_gf_signal": 0.40, "first_half_ga_signal": 0.48,
                "profile_stats": {"shots_on_target": 4.0},
            },
        },
        "dongqiudi_enrichment": {
            "available": True,
            "home": {"wins_rate": 0.5, "draws_rate": 0.3, "losses_rate": 0.2},
            "away": {"wins_rate": 0.3, "draws_rate": 0.3, "losses_rate": 0.4},
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
        lambda date, home, away: {
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
