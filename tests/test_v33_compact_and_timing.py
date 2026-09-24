import json

from collector.goal_timing_service import _team, _team_half_rates
from engine.htft_layer import htft_layer
from scripts.publish_action_result import _prediction_summary, _validate_prediction_contract
import pytest


@pytest.mark.parametrize("payload,reason", [
    ({"predictions": []}, "missing_predictions"),
    ({"predictions": [{}], "output_contract": {}}, "missing_locked_prediction_output"),
    ({"predictions": [{}], "output_contract": {"display_rows": [{}]}}, "missing_stable_version"),
])
def test_prediction_contract_rejects_incomplete_locked_output(payload, reason):
    with pytest.raises(ValueError, match=reason):
        _validate_prediction_contract(payload)


def test_prediction_contract_accepts_complete_locked_output():
    assert _validate_prediction_contract({
        "predictions": [{}],
        "output_contract": {"stable_version": "HH520 Stable V3.5.1", "display_rows": [{}]},
    }) is True


def test_prediction_summary_is_compact_and_six_column_authoritative():
    contract={
        "version":"HH520-OUTPUT-V3.5.1","stable_version":"HH520 Stable V3.5.1","strict":True,
        "required_columns":["球队对阵","胜平负场景","市场概率","比分×2及概率","半全场×2及概率","总进球及概率"],
        "display_rows":[{"球队对阵":"A vs B"}],"render_rule":"six",
    }
    data={"date":"2026-09-22","captured_at":"now",
          "predictions":[{"match_id":"1","home_team":"A","away_team":"B","direction":"主胜",
              "state":"CONFIRM","market_probability":0.42,"score1":"1:0","score2":"2:1",
              "score1_probability":0.1,"score2_probability":0.09,"htft1":"主/主","htft2":"平/主",
              "htft1_probability":0.2,"htft2_probability":0.18,"total_goals":"2球",
              "total_goals_probability":0.25,"decision_filter":{"huge":"x"*50000},"consistency":{"huge":"x"*50000}}],
          "output_contract":contract,"display_rows":contract["display_rows"],"gpt_handoff":{"huge":"x"*50000}}
    out=_prediction_summary(data,"hh520-test-1234")
    assert out["status"]=="READY"
    assert out["output_contract"]["required_columns"]==contract["required_columns"]
    assert "gpt_handoff" not in out
    assert "decision_filter" not in out["predictions"][0]
    assert len(json.dumps(out,ensure_ascii=False))<10000


def test_goal_timing_utils_remain_available_for_research():
    exact=_team({"goals_for":[2,1,1,2,2,2],"goals_against":[1,1,2,2,2,2],"scope":"season"})
    assert exact is not None
    fallback=_team_half_rates({"first_half_scoring_rate":40,"first_half_conceding_rate":35,
                               "second_half_scoring_rate":55,"second_half_conceding_rate":45,"scope":"last10"})
    assert fallback is not None


def test_v35_phase2_formal_htft_requires_and_uses_goal_timing():
    probability={"valid":True,"probabilities":{"home":0.5,"draw":0.3,"away":0.2},
                 "market_probabilities":{"home":0.5,"draw":0.3,"away":0.2},"home_share":0.714,"direction":"home"}
    match={"goal_timing":{"available":True,"timing_mode":"half_aggregate_fallback","source_domain":"footystats.org",
           "home":{"first_half_gf_signal":0.40,"first_half_ga_signal":0.35},
           "away":{"first_half_gf_signal":0.38,"first_half_ga_signal":0.42}}}
    out=htft_layer(probability,match)
    assert out["valid"] is True
    assert out["timing_used"] is True
    assert out["ft_core_unchanged"] is True
    assert out["model"]=="INDEPENDENT_POISSON_SPLIT_HTFT_V2_TIMING_REQUIRED"
