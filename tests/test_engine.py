import pytest
from engine.market_baseline import dejuice_1x2
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
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


def test_value_fields_do_not_change_direction_or_use_advice():
    match = {"market": {"home_odds": 2, "draw_odds": 3, "away_odds": 4}}
    first = probability_layer(match)["direction"]
    match["value"] = {"ev": -100, "kelly": 99, "signal": "away"}
    probability = probability_layer(match)
    value = value_layer(match, probability)
    assert probability["direction"] == first
    assert "page_signal" not in value
    assert value["forbidden_advice_fields_used"] is False


def test_v3_allows_strong_candidate():
    match = {
        "match_id": "1", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 1.4, "draw_odds": 4.5, "away_odds": 7.0},
        "page_probability": {"home": 0.70, "draw": 0.18, "away": 0.12},
        "research_factors": {"structure": "强优", "risk": "低"},
    }
    probability = probability_layer(match)
    value = value_layer(match, probability)
    quality = data_quality_gate(match, probability)
    classification = classify_match(match, probability)
    risk = assess_risk(match, probability, value, quality, classification)
    decision = decision_filter(match, probability, value, quality, classification, risk)
    assert decision["version"] == "HH520 Decision Filter V3.0"
    assert decision["decision"] == "BET_CANDIDATE"
    assert decision["forbidden_advice_fields_used"] is False


def test_v3_passes_balanced_low_concentration():
    match = {
        "match_id": "2", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 2.4, "draw_odds": 3.1, "away_odds": 2.8},
        "page_probability": {"home": 0.39, "draw": 0.33, "away": 0.28},
        "research_factors": {"risk": "中高"},
    }
    probability = probability_layer(match)
    value = value_layer(match, probability)
    decision = decision_filter(match, probability, value)
    assert decision["decision"] == "PASS"
    assert decision["allow_prediction"] is False

def test_risk_engine_v31_version_and_balanced_penalty():
    from engine.risk_engine import assess_risk_v3, assess_risk_v31
    match = {
        "match_id": "3", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 2.4, "draw_odds": 3.1, "away_odds": 2.8},
        "page_probability": {"home": 0.39, "draw": 0.33, "away": 0.28},
        "research_factors": {"risk": "低"},
    }
    p = probability_layer(match)
    v = value_layer(match, p)
    q = data_quality_gate(match, p)
    c = classify_match(match, p)
    old = assess_risk_v3(match, p, v, q, c)
    new = assess_risk_v31(match, p, v, q, c)
    prod = assess_risk(match, p, v, q, c)
    assert new["version"] == "HH520 Risk Engine V3.1"
    assert prod["version"] == "HH520 Risk Engine V3.0"
    assert new["score"] >= old["score"]
