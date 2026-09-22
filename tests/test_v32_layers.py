from engine.probability_layer import probability_layer
from engine.research_confidence_layer import research_confidence_layer
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer


def sample_match(home_odds=1.20):
    return {
        "match_id":"9","home_team":"A","away_team":"B","league":"联赛",
        "market":{"home_odds":home_odds,"draw_odds":6.0,"away_odds":13.0},
        "possession":{"home":57,"away":43},
        "research_factors":{
            "home_attack":11,"away_attack":7,"home_defense":1.1,"away_defense":1.6,
            "home_h2h":8,"away_h2h":5,"home_form":1.3,"away_form":0.8,
        },
    }


def test_research_confidence_s_tier():
    p=probability_layer(sample_match())
    c=research_confidence_layer(p)
    assert c["tier"]=="S"
    assert c["pmax"]>=0.73
    assert c["direction_override"] is False


def test_htft_layer_produces_three_primary_ft_rows():
    p=probability_layer(sample_match())
    h=htft_layer(p,sample_match())
    assert h["valid"] is True
    assert len(h["top"])==3
    assert h["top"][0]["probability"]>=h["top"][1]["probability"]
    assert all(x["ft"]=="HOME" for x in h["top"])


def test_score_layer_uses_htft_templates():
    m=sample_match(); p=probability_layer(m)
    s=score_layer(m,p)
    assert s["valid"] is True
    assert s["model"]=="HTFT_SCORE_TEMPLATE_V1"
    assert len(s["top_scores"])>=2
    assert s["lambda_home"] is None and s["lambda_away"] is None
    assert s["total_goals_pick"].endswith("球")
