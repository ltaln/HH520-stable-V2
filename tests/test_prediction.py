from prediction import build_predictions
from prediction.builder import build_model_input

def fixture_match():
    return {"match_id":"1", "home_team":"甲", "away_team":"乙",
            "market":{"home_odds":1.5,"draw_odds":4,"away_odds":6},
            "team_dna":{"attack":{"home":10,"away":8},"defense":{"home":1.2,"away":1.6}}}

def test_without_gpt_waits_instead_of_copying_page():
    match = fixture_match()
    match["page_prediction"] = {"scores":"1-0、2-0"}
    result = build_predictions([match])[0]
    assert result["status"] == "READY_FOR_GPT"
    assert result["score1"] == "未提供"

def test_finished_match_is_skipped():
    match = fixture_match()
    match["result"] = "2:1"
    assert build_predictions([match])[0]["status"] == "SKIP"
    assert build_model_input([match]) == []

def test_missing_page_picks_does_not_block_inference():
    payload = build_model_input([fixture_match()])
    assert len(payload) == 1
    assert payload[0]["team_dna"]["attack"]["home"] == 10
    assert set(payload[0]["analysis"]) == {"probability","value","decision","confidence"}

def test_missing_probabilities_pass():
    match = fixture_match()
    match["market"] = {}
    assert build_predictions([match])[0]["status"] == "PASS"
