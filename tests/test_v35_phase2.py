from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.decision_filter import decision_filter
from engine.htft_layer import htft_layer
from prediction.builder import prepare_match


def _base_match():
    return {
        "match_id":"p2",
        "home_team":"A","away_team":"B","league":"TEST",
        "market":{"home_odds":2.25,"draw_odds":3.10,"away_odds":3.10},
        "possession":{"home":51,"away":49},
        "research_factors":{
            "home_attack":1.0,"away_attack":1.0,
            "home_defense":1.0,"away_defense":1.0,
            "home_h2h":1.0,"away_h2h":1.0,
            "home_form":1.0,"away_form":1.0,
        },
    }


def test_formal_draw_resolver_only_operates_in_balanced_side_zone():
    m=_base_match()
    p=probability_layer(m)
    v=value_layer(m,p)
    d=decision_filter(m,p,v)
    if d["draw_rule_promoted"]:
        assert d["resolved_direction"]=="draw"
        assert d["ft_grade"]=="DRAW_STANDARD"
        assert d["draw_rule_type"]=="CROSS_FIT_LOGISTIC_V1"
        assert d["draw_rule_metrics"]["score"] >= 0.38
        assert p["pmax"] <= 0.45
    else:
        assert d["resolved_direction"]==p["direction"]


def test_authorized_strong_side_cannot_be_overridden_by_draw_resolver():
    m=_base_match()
    m["market"]={"home_odds":1.45,"draw_odds":4.5,"away_odds":7.0}
    p=probability_layer(m); v=value_layer(m,p); d=decision_filter(m,p,v)
    assert d["resolved_direction"]=="home"
    assert d["draw_rule_promoted"] is False
    assert d["ft_direction_authorized"] is True


def test_htft_requires_no_new_goal_timing_collection():
    m=_base_match()
    p=probability_layer(m)
    h=htft_layer(p,m)
    assert h["valid"] is True
    assert h["status"]=="READY"
    assert h["timing_used"] is False
    assert h["new_timing_collection_required"] is False
    assert h["model"]=="INDEPENDENT_POISSON_SPLIT_HTFT_V3_EXISTING_DATA"
    assert h["home_half_share"]==0.36
    assert h["away_half_share"]==0.44
    assert len(h["top"])>=2


def test_htft_ignores_optional_goal_timing_payload():
    m=_base_match()
    m["goal_timing"]={
        "available":True,
        "home":{"first_half_gf_signal":0.9},
        "away":{"first_half_gf_signal":0.1},
    }
    p=probability_layer(m)
    h=htft_layer(p,m)
    assert h["valid"] is True
    assert h["timing_used"] is False
    assert h["home_half_share"]==0.36
    assert h["away_half_share"]==0.44


def test_builder_outputs_formal_htft_without_timing():
    row=prepare_match(_base_match())
    assert row["status"]=="PREDICTED"
    assert row["htft1"]!="未提供"
    assert row["htft2"]!="未提供"
    assert row["score1"]!="未提供"
    assert row["timing_used"] is False
    assert row["htft_model"]=="INDEPENDENT_POISSON_SPLIT_HTFT_V3_EXISTING_DATA"
