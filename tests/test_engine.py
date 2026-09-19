import pytest
from engine.market_baseline import dejuice_1x2
from engine.probability_layer import probability_layer
from engine.decision_filter import decision_filter
from analysis.confidence import confidence_from_probability


def test_invalid_odds_rejected():
    with pytest.raises(ValueError):
        dejuice_1x2(0, 3, 4)


def test_missing_probability_is_pass():
    probability = probability_layer({})
    decision = decision_filter({}, probability, {})
    assert probability["direction"] is None
    assert decision["allow_prediction"] is False
    assert confidence_from_probability(probability, decision) == 0


def test_value_fields_do_not_change_direction():
    match = {"market": {"home_odds": 2, "draw_odds": 3, "away_odds": 4}}
    first = probability_layer(match)["direction"]
    match["value"] = {"ev": -100, "kelly": 99, "signal": "away"}
    assert probability_layer(match)["direction"] == first
