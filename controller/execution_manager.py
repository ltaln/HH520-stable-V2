from collector.service import collect_date
from prediction import build_predictions
from prediction.builder import build_model_input
from formatter.output_formatter import build_output_contract
from pathlib import Path
import yaml

PROMPT_FILE = "HH520_Stable_V3_3_Prediction_Prompt.md"


def execute_prediction(date: str, use_gpt: bool = False):
    data = collect_date(date)
    data["predictions"] = build_predictions(data["matches"], use_gpt=use_gpt)
    data["output_contract"] = build_output_contract(data["predictions"])
    data["display_rows"] = data["output_contract"]["display_rows"]
    if not use_gpt:
        root = Path(__file__).resolve().parents[1]
        data["gpt_handoff"] = {
            "role": "EXPLANATION_ONLY",
            "stable_version": "HH520 Stable V3.3",
            "prompt": (root / "prompts" / PROMPT_FILE).read_text(encoding="utf-8"),
            "config": yaml.safe_load((root / "config/stable.yaml").read_text(encoding="utf-8")),
            "matches": build_model_input(data["matches"]),
            "locked_predictions": data["predictions"],
            "output_contract": data["output_contract"],
            "goal_timing_summary": data.get("goal_timing_summary"),
        }
    return data
