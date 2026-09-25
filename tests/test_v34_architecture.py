from engine.probability_layer import probability_layer
from engine.market_failure_detector import market_failure_detector
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer
from engine.decision_filter import decision_filter
from engine.value_layer import value_layer


def match():
    return {
        "match_id":"1","home_team":"A","away_team":"B","league":"L",
        "market":{"home_odds":1.60,"draw_odds":3.80,"away_odds":4.50},
        "possession":{"home":56,"away":48},
        "research_factors":{
            "home_attack":10,"away_attack":8,
            "home_defense":1.5,"away_defense":1.0,
            "home_h2h":8,"away_h2h":5,
            "home_form":1.0,"away_form":0.8,
        },
        "page_probability":{"home":0.20,"draw":0.20,"away":0.60},
    }


def test_draw_anchor_and_side_share_sum_to_one():
    p=probability_layer(match())
    assert p["valid"] is True
    assert abs(sum(p["probabilities"].values())-1)<1e-9
    assert p["page_probability_used_for_direction"] is False
    assert 0 < p["draw_anchor"] < 1
    assert 0 < p["home_share"] < 1


def test_failure_detector_does_not_override_probability():
    m=match(); p=probability_layer(m)
    f=market_failure_detector(m,p)
    assert f["probability_overridden"] is False
    assert f["tier"] in {"CONFIRM","BALANCED","TAIL_ALERT","PASS"}


def test_htft_and_score_are_independent_in_phase2():
    m=match()
    m["goal_timing"]={"available":True,"source_domain":"test","timing_mode":"six_bin",
        "home":{"first_half_gf_signal":0.40,"first_half_ga_signal":0.42},
        "away":{"first_half_gf_signal":0.46,"first_half_ga_signal":0.44}}
    p=probability_layer(m); v=value_layer(m,p); d=decision_filter(m,p,v)
    h=htft_layer(p,m,d)
    s=score_layer(m,p,h)
    assert h["model"]=="INDEPENDENT_POISSON_SPLIT_HTFT_V3_EXISTING_DATA"
    assert h["timing_used"] is False
    assert h["ft_core_unchanged"] is True
    assert s["model"]=="HDA_POISSON_V1"
    assert s["feature_snapshot"]["ft_direction_lock"] is False


def test_value_does_not_drive_direction():
    m=match(); p=probability_layer(m); v=value_layer(m,p); d=decision_filter(m,p,v)
    assert d["value_layer_used_for_direction"] is False
    assert d["selection_rule"]=="V351_FT_CALIBRATION_PLUS_FORMAL_DRAW_LOGISTIC_PLUS_MFD"
