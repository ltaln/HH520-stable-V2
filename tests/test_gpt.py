import json
from unittest.mock import Mock
import pytest
import requests

from prediction import build_predictions, gpt
from prediction.builder import prepare_match
from collector import cache_manager


def match():
    return {
        "match_id":"1","home_team":"甲","away_team":"乙","league":"联赛",
        "market":{"home_odds":1.5,"draw_odds":4,"away_odds":6},
        "page_probability":{"home":0.62,"draw":0.23,"away":0.15},
        "possession":{"home":56,"away":44},
        "research_factors":{
            "home_attack":10,"away_attack":8,
            "home_defense":1.2,"away_defense":1.6,
            "home_h2h":7,"away_h2h":5,
            "home_form":1.2,"away_form":0.9,
            "structure":"强优",
        },
        "value":{"ev":100,"kelly":0.02},
        "page_prediction":{},
    }


def row(source=None):
    source = source or match()
    locked = prepare_match(source)
    return {
        "match_id": locked["match_id"],
        "score1": locked["score1"],
        "score2": locked["score2"],
        "htft1": locked["htft1"],
        "htft2": locked["htft2"],
        "total_goals": locked["total_goals"],
        "direction": locked["direction"],
        "alternate_direction": locked["alternate_direction"],
        "state": locked["state"],
        "status": "GPT",
        "reason": "仅解释冻结模型输出",
    }


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
    expected=prepare_match(source)
    set_output(api,row(source))
    first=build_predictions([source],use_gpt=True)
    assert first==build_predictions([source],use_gpt=True)
    assert first[0]["status"]=="PREDICTED_GPT_REVIEWED"
    assert first[0]["score1"]==expected["score1"]
    assert first[0]["htft2"]==expected["htft2"]
    assert api.call_count==1
    body=api.call_args.kwargs["json"]
    payload=json.loads(body["input"])
    assert "SECRET_RAW" not in body["input"]
    assert "result" not in payload["matches"][0]
    assert payload["matches"][0]["gpt_role"]=="EXPLANATION_ONLY"
    assert payload["config"]["project"]["version"]=="3.5-p1"
    assert body["store"] is False


@pytest.mark.parametrize("changes",[
    {"direction":"客胜"},{"score1":"0:2"},{"htft1":"主/客"},
    {"score2":"9:9"},{"htft2":"主/主"},{"total_goals":"未知"},
    {"alternate_direction":"客胜"},{"state":"TAIL_ALERT"},
])
def test_conflicting_gpt_changes_are_ignored(api,changes):
    source=match()
    expected=prepare_match(source)
    value=row(source); value.update(changes); set_output(api,value)
    result=build_predictions([source],use_gpt=True)[0]
    assert result["status"]=="PREDICTED_GPT_REVIEW_REJECTED"
    for key in ("direction","alternate_direction","state","score1","score2","htft1","htft2","total_goals"):
        assert result[key]==expected[key]
    assert result["gpt_rejected_changes"]


def test_gpt_pass_does_not_erase_model_prediction(api):
    source=match()
    expected=prepare_match(source)
    value=row(source); value["status"]="PASS"; set_output(api,value)
    result=build_predictions([source],use_gpt=True)[0]
    assert result["status"]=="PREDICTED_GPT_REVIEW_SKIPPED"
    assert result["score1"]==expected["score1"]
    assert result["direction"]==expected["direction"]


def test_timeout_does_not_retry(api):
    api.side_effect=requests.Timeout("failed")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            build_predictions([match()],use_gpt=True)
    assert api.call_count==1


def test_refusal_does_not_cache_success(api):
    api.return_value.json.return_value={"status":"completed","output":[]}
    with pytest.raises(RuntimeError):
        build_predictions([match()],use_gpt=True)
    assert not list(cache_manager.CACHE_DIR.glob("gpt_*.json"))


def test_settled_and_invalid_probability_do_not_call_api(api):
    settled=dict(match(),result="1:0 / 2:1")
    invalid=dict(match(),market={})
    result=build_predictions([settled,invalid],use_gpt=True)
    assert [x["status"] for x in result]==["SKIP","PASS"]
    api.assert_not_called()
