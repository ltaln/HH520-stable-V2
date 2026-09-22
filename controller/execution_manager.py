from collector.service import collect_date
from prediction import build_predictions
from prediction.builder import build_model_input
from pathlib import Path
import yaml

PROMPT_FILE = "HH520_Stable_V3_2_Prediction_Prompt.md"


def execute_prediction(date: str, use_gpt: bool = False):
    data = collect_date(date)
    data["predictions"] = build_predictions(data["matches"], use_gpt=use_gpt)
    if not use_gpt:
        root = Path(__file__).resolve().parents[1]
        data["gpt_handoff"] = {
            "role": "EXPLANATION_ONLY",
            "stable_version": "HH520 Stable V3.2",
            "prompt": (root / "prompts" / PROMPT_FILE).read_text(encoding="utf-8"),
            "config": yaml.safe_load((root / "config/stable.yaml").read_text(encoding="utf-8")),
            "matches": build_model_input(data["matches"]),
            "locked_predictions": data["predictions"],
        }
    return data
