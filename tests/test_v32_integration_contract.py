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
