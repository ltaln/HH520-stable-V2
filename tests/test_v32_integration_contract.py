from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_v32_active_prompt_and_config_are_aligned():
    prompt = (ROOT / "prompts" / "HH520_Stable_V3_2_Prediction_Prompt.md").read_text(encoding="utf-8")
    config = yaml.safe_load((ROOT / "config" / "stable.yaml").read_text(encoding="utf-8"))
    assert "HH520 Stable V3.2" in prompt
    assert "EXPLANATION_ONLY" in prompt
    assert config["project"]["version"] == "3.2"
    assert config["prediction"]["gpt_role"] == "EXPLANATION_ONLY"
    assert config["prediction"]["confidence_s_threshold"] == 0.73


def test_v32_integration_contract_exposes_locked_predictions():
    spec = json.loads((ROOT / "integration" / "chatgpt-action.openapi.json").read_text(encoding="utf-8"))
    assert spec["info"]["version"] == "3.2"
    schema = spec["paths"]["/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "predictions" in schema["properties"]
    instructions = (ROOT / "integration" / "CHATGPT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "顶层 predictions" in instructions
    assert "EXPLANATION_ONLY" in instructions


def test_legacy_v2_prompt_is_not_active():
    assert not (ROOT / "prompts" / "HH520_Stable_V2_Prediction_Prompt.md").exists()
    execution = (ROOT / "controller" / "execution_manager.py").read_text(encoding="utf-8")
    gpt = (ROOT / "prediction" / "gpt.py").read_text(encoding="utf-8")
    assert "HH520_Stable_V2_Prediction_Prompt.md" not in execution
    assert "HH520_Stable_V2_Prediction_Prompt.md" not in gpt


def test_v32_output_contract_forbids_legacy_five_column_table():
    from formatter.output_formatter import OUTPUT_COLUMNS, build_output_contract, build_display_row

    assert OUTPUT_COLUMNS == [
        "球队对阵",
        "胜平负",
        "市场概率",
        "置信等级",
        "比分×2",
        "半全场×2",
        "总进球",
        "置信度",
        "最终筛选",
    ]

    sample = {
        "home_team": "韩国亚",
        "away_team": "沙特亚",
        "direction": "主胜",
        "market_probability": 0.70,
        "confidence_tier": "NORMAL",
        "score1": "2:0",
        "score2": "2:1",
        "htft1": "主/主",
        "htft2": "平/主",
        "total_goals": "3球",
        "confidence": 70,
        "stable_v32_decision": "PASS",
    }
    row = build_display_row(sample)
    assert list(row.keys()) == OUTPUT_COLUMNS
    assert row["胜平负"] == "主胜"
    assert row["市场概率"] == "70.0%"
    assert row["置信等级"] == "NORMAL"
    assert row["最终筛选"] == "PASS"

    contract = build_output_contract([sample])
    assert contract["strict"] is True
    assert contract["required_columns"] == OUTPUT_COLUMNS
    assert contract["display_rows"][0] == row

    instructions = (ROOT / "integration" / "CHATGPT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "禁止退回旧版 5 列简表" in instructions
    assert "球队对阵 | 胜平负 | 市场概率 | 置信等级 | 比分×2 | 半全场×2 | 总进球 | 置信度 | 最终筛选" in instructions

    spec = json.loads((ROOT / "integration" / "chatgpt-action.openapi.json").read_text(encoding="utf-8"))
    schema = spec["paths"]["/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "output_contract" in schema["properties"]
    assert "display_rows" in schema["properties"]


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
