import pytest
from engine.market_baseline import dejuice_1x2
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
from engine.decision_filter import decision_filter
from engine.market_failure_detector import market_failure_detector
from analysis.confidence import confidence_from_probability


def base_match():
    return {
        "match_id":"1","home_team":"A","away_team":"B","league":"联赛",
        "market":{"home_odds":1.45,"draw_odds":4.5,"away_odds":7.0},
        "page_probability":{"home":0.65,"draw":0.20,"away":0.15},
        "possession":{"home":58,"away":42},
        "research_factors":{
            "home_attack":10,"away_attack":7,
            "home_defense":1.0,"away_defense":1.6,
            "home_h2h":8,"away_h2h":4,
            "home_form":1.2,"away_form":0.8,"structure":"强优",
        },
    }


def test_invalid_odds_rejected():
    with pytest.raises(ValueError):
        dejuice_1x2(0,3,4)


def test_missing_probability_is_pass():
    probability=probability_layer({})
    decision=decision_filter({},probability,{})
    assert probability["direction"] is None
    assert decision["allow_prediction"] is False
    assert confidence_from_probability(probability,decision)==0


def test_page_probability_is_diagnostic_only():
    match=base_match()
    match["page_probability"]={"home":0.05,"draw":0.05,"away":0.90}
    p=probability_layer(match)
    v=value_layer(match,p)
    assert p["direction"]=="home"
    assert p["page_probability_used_for_direction"] is False
    assert p["page_probability_used_for_state"] is False
    assert v["used_for_confirmation"] is False
    assert v["independent_direction"]=="away"


def test_v35_phase2_decision_filter_uses_calibration_draw_and_failure_detector():
    match=base_match()
    p=probability_layer(match); v=value_layer(match,p)
    d=decision_filter(match,p,v)
    assert d["version"]=="HH520 Decision Filter V3.5 Phase 2"
    assert d["selection_rule"]=="V35_PHASE2_FT_CALIBRATION_PLUS_FORMAL_DRAW_LOGISTIC_PLUS_MFD"
    assert d["decision"] in {"CONFIRM","BALANCED","TAIL_ALERT","PASS"}
    assert d["allow_prediction"] is True


def test_failure_detector_never_overrides_probability():
    match=base_match(); p=probability_layer(match)
    f=market_failure_detector(match,p)
    assert f["probability_overridden"] is False
    assert f["favorite"] in {"home","away"}


def test_data_quality_missing_modules_does_not_hard_fail():
    match={"match_id":"2","home_team":"A","away_team":"B","league":"联赛",
           "market":{"home_odds":2.0,"draw_odds":3.0,"away_odds":4.0},
           "research_factors":{}}
    p=probability_layer(match); q=data_quality_gate(match,p)
    assert q["valid"] is True
    assert "team_modules_missing_or_zero" in q["warnings"]


def test_legacy_risk_engine_remains_advisory():
    match=base_match(); p=probability_layer(match); v=value_layer(match,p)
    q=data_quality_gate(match,p); c=classify_match(match,p)
    r=assess_risk(match,p,v,q,c); d=decision_filter(match,p,v,q,c,r)
    assert d["risk_is_advisory"] is True
    assert d["value_layer_used_for_direction"] is False
