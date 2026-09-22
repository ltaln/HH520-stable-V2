from prediction import build_predictions
from prediction.builder import build_model_input

def fixture_match():
    return {
        "match_id":"1",
        "home_team":"甲",
        "away_team":"乙",
        "league":"联赛",
        "market":{"home_odds":1.5,"draw_odds":4,"away_odds":6},
        "team_dna":{"attack":{"home":10,"away":8},"defense":{"home":1.2,"away":1.6}},
        "possession":{"home":56,"away":44},
        "research_factors":{
            "home_attack":10,"away_attack":8,
            "home_defense":1.2,"away_defense":1.6,
            "home_h2h":7,"away_h2h":5,
            "home_form":1.2,"away_form":0.9,
        },
    }

def test_without_gpt_returns_deterministic_prediction():
    match = fixture_match()
    match["page_prediction"] = {"scores":"1-0、2-0"}
    result = build_predictions([match])[0]
    assert result["status"] == "PREDICTED"
    assert result["score1"] != "未提供"
    assert result["score2"] != "未提供"
    assert result["htft1"] != "未提供"
    assert result["total_goals"] != "未提供"
    assert result["stable_version"] == "HH520 Stable V3.2"

def test_finished_match_is_skipped():
    match = fixture_match()
    match["result"] = "2:1"
    assert build_predictions([match])[0]["status"] == "SKIP"
    assert build_model_input([match]) == []

def test_model_input_contains_locked_prediction():
    payload = build_model_input([fixture_match()])
    assert len(payload) == 1
    assert payload[0]["gpt_role"] == "EXPLANATION_ONLY"
    assert payload[0]["locked_prediction"]["score1"]
    assert set(payload[0]["analysis"]) == {
        "probability","research_confidence","decision","confidence","htft","score"
    }

def test_missing_probabilities_pass():
    match = fixture_match()
    match["market"] = {}
    assert build_predictions([match])[0]["status"] == "PASS"
