from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_v35_phase2_active_prompt_and_config_are_aligned():
    prompt = (ROOT / "prompts" / "HH520_Stable_V3_5_Phase2_Prediction_Prompt.md").read_text(encoding="utf-8")
    config = yaml.safe_load((ROOT / "config" / "stable.yaml").read_text(encoding="utf-8"))
    assert "HH520 Stable V3.5 Phase 2" in prompt
    assert "EXPLANATION_ONLY" in prompt
    assert config["project"]["version"] == "3.5-p2"
    assert config["prediction"]["gpt_role"] == "EXPLANATION_ONLY"
    assert config["prediction"]["page_probability_for_state"] is False
    assert config["prediction"]["automatic_market_override"] is False


def test_v351_integration_contract_exposes_locked_predictions():
    spec = json.loads((ROOT / "integration" / "chatgpt-action.openapi.json").read_text(encoding="utf-8"))
    assert spec["info"]["version"] == "3.5.1"
    schema = spec["paths"]["/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "predictions" in schema["properties"]
    assert "output_contract" in schema["properties"]
    assert "display_rows" in schema["properties"]
    instructions = (ROOT / "integration" / "CHATGPT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "顶层 predictions" in instructions
    assert "EXPLANATION_ONLY" in instructions


def test_v34_output_contract_is_six_columns():
    from formatter.output_formatter import OUTPUT_COLUMNS, build_output_contract, build_display_row

    assert OUTPUT_COLUMNS == [
        "球队对阵",
        "胜平负场景",
        "市场概率",
        "比分×2及概率",
        "半全场×2及概率",
        "总进球及概率",
    ]
    sample = {
        "home_team": "韩国亚",
        "away_team": "沙特亚",
        "direction": "主胜",
        "alternate_direction": "平",
        "state": "BALANCED",
        "market_probability": 0.42,
        "score1": "1:0",
        "score2": "1:1",
        "score1_probability": 0.12,
        "score2_probability": 0.11,
        "htft1": "平/主",
        "htft2": "平/平",
        "htft1_probability": 0.20,
        "htft2_probability": 0.18,
        "total_goals": "2球",
        "total_goals_probability": 0.26,
    }
    row = build_display_row(sample)
    assert list(row.keys()) == OUTPUT_COLUMNS
    assert "均衡" in row["胜平负场景"]
    assert row["市场概率"] == "42.0%"
    assert "12.0%" in row["比分×2及概率"]
    assert "20.0%" in row["半全场×2及概率"]
    assert "26.0%" in row["总进球及概率"]

    contract = build_output_contract([sample])
    assert contract["strict"] is True
    assert contract["required_columns"] == OUTPUT_COLUMNS
    assert "置信等级" not in contract["required_columns"]
    assert "置信度" not in contract["required_columns"]
    assert "最终筛选" not in contract["required_columns"]


def test_openapi_object_schemas_are_explicit_for_gpt_editor():
    spec = json.loads((ROOT / "integration" / "chatgpt-action.openapi.json").read_text(encoding="utf-8"))
    assert isinstance(spec.get("components", {}).get("schemas"), dict)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert isinstance(node.get("properties"), dict)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)


def test_prediction_action_schema_uses_raw_json_and_cache_busting():
    spec = json.loads((ROOT / "integration" / "chatgpt-action.openapi.json").read_text(encoding="utf-8"))
    get_op = spec["paths"]["/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json"]["get"]
    params = {(p["in"], p["name"]) for p in get_op["parameters"]}
    assert ("header", "Accept") in params
    assert ("path", "request_id") in params
    assert ("query", "ref") in params
    assert ("query", "poll_timestamp") in params
    accept = next(p for p in get_op["parameters"] if p["name"] == "Accept")
    assert accept["schema"]["default"] == "application/vnd.github.raw+json"
    post_op = spec["paths"]["/repos/ltaln/HH520-stable-V2/actions/workflows/hh520-predict.yml/dispatches"]["post"]
    assert "200" in post_op["responses"]
    assert "204" in post_op["responses"]
