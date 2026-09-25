from copy import deepcopy

from collector.goal_timing_service import _needs_timing, _team
from engine.htft_layer import htft_layer
from engine.probability_layer import probability_layer
from engine.score_layer import score_layer
from engine.state_engine import build_state
from engine.consistency_layer import consistency_layer


def sample_match():
    return {
        "match_id":"9","home_team":"A","away_team":"B","league":"联赛",
        "market":{"home_odds":2.35,"draw_odds":3.10,"away_odds":2.85},
        "page_probability":{"home":0.36,"draw":0.33,"away":0.31},
        "possession":{"home":52,"away":48},
        "research_factors":{
            "home_attack":9,"away_attack":8,"home_defense":1.3,"away_defense":1.4,
            "home_h2h":6,"away_h2h":5,"home_form":1.0,"away_form":0.9,"structure":"均衡",
        },
    }


def test_goal_timing_utility_still_normalizes_for_research_compatibility():
    row=_team({"goals_for":[2,1,1,3,2,1],"goals_against":[1,1,2,2,1,1],"scope":"last20"})
    assert row is not None
    assert abs(sum(row["goals_for_share"])-1.0)<1e-9


def test_goal_timing_collector_legacy_budget_function_remains_callable(monkeypatch):
    monkeypatch.setenv("HH520_GOAL_TIMING_ONLY_UNCERTAIN","1")
    uncertain=sample_match()
    assert _needs_timing(uncertain) is True
    strong=deepcopy(uncertain)
    strong["market"]={"home_odds":1.20,"draw_odds":7.0,"away_odds":14.0}
    strong["page_probability"]={"home":0.80,"draw":0.12,"away":0.08}
    strong["research_factors"].update({"structure":"强优","risk":"低","pattern":"🔶风控赔率"})
    assert _needs_timing(strong) is False


def test_v351_htft_uses_frozen_existing_data_split_without_changing_ft_core():
    m=sample_match()
    m["goal_timing"]={"available":True,"source_domain":"soccerstats.com","timing_mode":"six_bin",
        "home":{"first_half_gf_signal":0.45,"first_half_ga_signal":0.35},
        "away":{"first_half_gf_signal":0.38,"first_half_ga_signal":0.48}}
    p=probability_layer(m); before=dict(p["probabilities"]); h=htft_layer(p,m)
    assert h["valid"] is True
    assert h["timing_used"] is False
    assert h["ft_core_unchanged"] is True
    assert p["probabilities"]==before


def test_consistency_selects_two_independent_htft_candidates_with_timing():
    m=sample_match()
    m["goal_timing"]={"available":True,"source_domain":"test","timing_mode":"six_bin",
        "home":{"first_half_gf_signal":0.40,"first_half_ga_signal":0.42},
        "away":{"first_half_gf_signal":0.46,"first_half_ga_signal":0.44}}
    p=probability_layer(m); state=build_state(m,p)
    ht=htft_layer(p,m); score=score_layer(m,p,ht)
    c=consistency_layer(p,state,ht,score)
    assert c["valid"] is True
    assert len(c["htft_top"])==2
    assert len(c["score_top"])==2
    assert c["probability_conservation"]["wdl_anchor_unchanged"] is True


def test_independent_score_exposes_tail_diagnostics():
    m=sample_match(); p=probability_layer(m); s=score_layer(m,p)
    assert s["model"]=="HDA_POISSON_V1"
    assert s["high_variance_challenger_promoted"] is False
    assert 0<=s["high_score_mass"]<=1
    assert len(s["all_scores"])>=len(s["top_scores"])
