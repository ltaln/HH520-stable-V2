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


def test_page_probability_cannot_override_market_direction():
    match = {
        "market": {"home_odds": 1.50, "draw_odds": 4.0, "away_odds": 7.0},
        "page_probability": {"home": 0.05, "draw": 0.05, "away": 0.90},
    }
    p = probability_layer(match)
    assert p["direction"] == "home"
    assert p["page_probability_used_for_direction"] is False


def test_v32_allows_only_s_threshold_candidate():
    strong = {
        "match_id": "1", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 1.20, "draw_odds": 6.0, "away_odds": 13.0},
        "research_factors": {"risk": "高"},
    }
    p = probability_layer(strong)
    v = value_layer(strong, p)
    q = data_quality_gate(strong, p)
    c = classify_match(strong, p)
    r = assess_risk(strong, p, v, q, c)
    d = decision_filter(strong, p, v, q, c, r)
    assert d["version"] == "HH520 Decision Filter V3.2"
    assert d["decision"] == "BET_CANDIDATE"
    assert d["risk_is_advisory"] is True


def test_v32_passes_normal_market_even_with_valid_prediction():
    match = {
        "match_id": "2", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 2.4, "draw_odds": 3.1, "away_odds": 2.8},
    }
    p = probability_layer(match)
    v = value_layer(match, p)
    d = decision_filter(match, p, v)
    assert p["valid"] is True
    assert d["decision"] == "PASS"
    assert confidence_from_probability(p, d) > 0


def test_risk_engine_v31_version_and_balanced_penalty():
    from engine.risk_engine import assess_risk_v3, assess_risk_v31
    match = {
        "match_id": "3", "home_team": "A", "away_team": "B", "league": "联赛",
        "market": {"home_odds": 2.4, "draw_odds": 3.1, "away_odds": 2.8},
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


def test_risk_engine_v32_is_research_candidate_only():
    from engine.risk_engine import assess_risk_v32
    match = {
        "match_id":"4","home_team":"A","away_team":"B","league":"联赛",
        "market":{"home_odds":1.6,"draw_odds":3.8,"away_odds":5.5},
        "research_factors":{"risk":"高","pattern":"极端"},
    }
    p=probability_layer(match); v=value_layer(match,p); q=data_quality_gate(match,p); c=classify_match(match,p)
    prod=assess_risk(match,p,v,q,c)
    cand=assess_risk_v32(match,p,v,q,c)
    assert prod["version"]=="HH520 Risk Engine V3.0"
    assert cand["version"]=="HH520 Risk Engine V3.2 Candidate"
