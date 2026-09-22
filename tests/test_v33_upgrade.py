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


def test_v34_htft_ignores_external_timing_and_preserves_ft_marginal():
    m=sample_match()
    m["goal_timing"]={"available":True,"source_domain":"soccerstats.com",
        "home":{"first_half_gf_share":0.70,"first_half_ga_share":0.35},
        "away":{"first_half_gf_share":0.30,"first_half_ga_share":0.65}}
    p=probability_layer(m); h=htft_layer(p,m)
    assert h["timing_used"] is False
    by_ft={"HOME":0.0,"DRAW":0.0,"AWAY":0.0}
    for row in h["distribution"]: by_ft[row["ft"]]+=row["probability"]
    assert abs(by_ft["HOME"]-p["probabilities"]["home"])<1e-9
    assert abs(by_ft["DRAW"]-p["probabilities"]["draw"])<1e-9
    assert abs(by_ft["AWAY"]-p["probabilities"]["away"])<1e-9


def test_consistency_selects_two_candidates_for_primary_ft():
    m=sample_match(); p=probability_layer(m); state=build_state(m,p)
    ht=htft_layer(p,m); score=score_layer(m,p,ht)
    c=consistency_layer(p,state,ht,score)
    assert c["valid"] is True
    assert len(c["htft_top"])==2
    assert len(c["score_top"])==2
    assert c["probability_conservation"]["wdl_anchor_unchanged"] is True


def test_score_template_exposes_tail_diagnostics():
    m=sample_match(); p=probability_layer(m); s=score_layer(m,p)
    assert s["model"]=="HTFT_SCORE_TEMPLATE_V1"
    assert s["high_variance_challenger_promoted"] is False
    assert 0<=s["high_score_mass"]<=1
    assert len(s["all_scores"])>=len(s["top_scores"])
