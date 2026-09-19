from research.evaluator import evaluate_records


def test_offline_baseline_metrics_and_coverage():
    result = evaluate_records([
        {"home_odds": 2, "draw_odds": 3, "away_odds": 4, "actual": "home",
         "probabilities": {"home": .5, "draw": .3, "away": .2}, "status": "LOCAL"},
        {"home_odds": 2, "draw_odds": 3, "away_odds": 4, "actual": "away",
         "probabilities": {"home": .5, "draw": .3, "away": .2}, "status": "PASS"},
        {"home_odds": 2, "draw_odds": 3, "away_odds": 4, "actual": "draw",
         "probabilities": {"home": 2, "draw": 0, "away": 0}, "status": "LOCAL"},
        {"home_odds": 0, "draw_odds": 3, "away_odds": 4, "actual": "away"},
        {"home_odds": 2, "draw_odds": 3, "away_odds": 4},
    ])
    assert result["baseline"]["count"] == 3
    assert result["coverage"] == 0.6
    assert result["pass_count"] == 1
    assert result["pass_rate"] == 1 / 3
    assert result["candidate"]["count"] == 1
    assert result["candidate_coverage"] == 1 / 3
    assert result["invalid_candidate_count"] == 1
    assert result["invalid_or_unlabelled_count"] == 2
    assert set(("accuracy", "log_loss", "brier")) <= set(result["baseline"])
