import json
from unittest.mock import Mock
import pytest
import requests
from prediction import build_predictions, gpt
from collector import cache_manager

def match():
    return {"match_id":"1","home_team":"甲","away_team":"乙",
            "market":{"home_odds":1.5,"draw_odds":4,"away_odds":6},
            "team_dna":{"attack":{"home":10,"away":8},"defense":{"home":1.2,"away":1.6}},
            "value":{"ev":100,"kelly":0.02}, "page_prediction":{}}

def row():
    return {"match_id":"1","score1":"2:0","score2":"2:1","htft1":"主/主","htft2":"平/主",
            "total_goals":"2—3球","direction":"主胜","confidence":50,"status":"GPT",
            "reason":"依据已采集进攻防守结构；统计口径未验证"}

@pytest.fixture
def api(monkeypatch,tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY","test")
    monkeypatch.setenv("OPENAI_MODEL","test-model")
    monkeypatch.setattr(cache_manager,"CACHE_DIR",tmp_path)
    response = Mock(status_code=200)
    response.json.return_value = {"status":"completed","output":[{"type":"message","content":[
        {"type":"output_text","text":json.dumps({"predictions":[row()]})}]}]}
    post=Mock(return_value=response)
    monkeypatch.setattr(gpt.requests,"post",post)
    return post

def set_output(api,value):
    api.return_value.json.return_value["output"][0]["content"][0]["text"]=json.dumps({"predictions":[value]})

def test_complete_inference_without_page_answers_and_cache(api):
    source=match()
    source["raw_markdown"]="SECRET_RAW"
    first=build_predictions([source],use_gpt=True)
    assert first==build_predictions([source],use_gpt=True)
    assert first[0]["status"]=="GPT"
    assert first[0]["score1"]=="2:0"
    assert first[0]["htft2"]=="平/主"
    assert api.call_count==1
    body=api.call_args.kwargs["json"]
    payload=json.loads(body["input"])
    assert "SECRET_RAW" not in body["input"]
    assert "result" not in payload["matches"][0]
    assert payload["matches"][0]["team_dna"]["attack"]["home"]==10
    assert payload["matches"][0]["analysis"]["value"]["used_for_direction"] is False
    assert payload["config"]["project"]["version"]=="2.1"
    assert body["store"] is False

@pytest.mark.parametrize("changes",[
    {"direction":"客胜"},{"score1":"0:2"},{"htft1":"主/客"},
    {"score2":"2:0"},{"htft2":"主/主"},{"total_goals":"未知"},
    {"status":"PASS"},{"total_goals":"7—9球"},
    {"score1":"1:0","score2":"2:0","htft1":"客/主","total_goals":"1—2球"},
])
def test_invalid_or_conflicting_final_predictions_pass(api,changes):
    value=row(); value.update(changes); set_output(api,value)
    result=build_predictions([match()],use_gpt=True)[0]
    assert result["status"]=="PASS"
    assert result["score1"]=="未提供"

def test_no_arbitrary_sixty_percent_cap(api):
    source=match()
    source["market"]={"home_odds":1.05,"draw_odds":20,"away_odds":30}
    value=row(); value["confidence"]=85; set_output(api,value)
    assert build_predictions([source],use_gpt=True)[0]["confidence"]==85

def test_timeout_does_not_retry(api):
    api.side_effect=requests.Timeout("failed")
    for _ in range(2):
        with pytest.raises(RuntimeError): build_predictions([match()],use_gpt=True)
    assert api.call_count==1

def test_refusal_does_not_cache_success(api):
    api.return_value.json.return_value={"status":"completed","output":[]}
    with pytest.raises(RuntimeError): build_predictions([match()],use_gpt=True)
    assert not list(cache_manager.CACHE_DIR.glob("gpt_*.json"))

def test_settled_and_invalid_probability_do_not_call_api(api):
    settled=dict(match(),result="1:0 / 2:1")
    invalid=dict(match(),market={})
    result=build_predictions([settled,invalid],use_gpt=True)
    assert [x["status"] for x in result]==["SKIP","PASS"]
    api.assert_not_called()
