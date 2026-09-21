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


def test_decision_filter_v2_allows_strong_10027_candidate():
    match = {
        "market": {"home_odds": 1.4, "draw_odds": 4.5, "away_odds": 7.0},
        "page_probability": {"home": 0.70, "draw": 0.18, "away": 0.12},
        "research_factors": {"structure": "强优", "risk": "低"},
    }
    probability = probability_layer(match)
    decision = decision_filter(match, probability, {})
    assert decision["version"] == "HH520 Decision Filter V2.0"
    assert decision["decision"] == "BET_CANDIDATE"
    assert decision["allow_prediction"] is True
    assert decision["source"] == "HH520_10027s"


def test_decision_filter_v2_hard_passes_low_concentration():
    match = {
        "market": {"home_odds": 2.4, "draw_odds": 3.1, "away_odds": 2.8},
        "page_probability": {"home": 0.39, "draw": 0.33, "away": 0.28},
        "research_factors": {"risk": "中高"},
    }
    probability = probability_layer(match)
    decision = decision_filter(match, probability, {})
    assert decision["decision"] == "PASS"
    assert decision["hard_pass"] is True
    assert decision["allow_prediction"] is False
