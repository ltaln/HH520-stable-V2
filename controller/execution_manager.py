from collector.service import collect_date
from prediction import build_predictions
from prediction.builder import build_model_input
from pathlib import Path
import yaml

def execute_prediction(date: str, use_gpt: bool = False):
    data = collect_date(date)
    data["predictions"] = build_predictions(data["matches"], use_gpt=use_gpt)
    if not use_gpt:
        root = Path(__file__).resolve().parents[1]
        data["gpt_handoff"] = {
            "prompt": (root / "prompts/HH520_Stable_V2_Prediction_Prompt.md").read_text(encoding="utf-8"),
            "config": yaml.safe_load((root / "config/stable.yaml").read_text(encoding="utf-8")),
            "matches": build_model_input(data["matches"]),
        }
    return data
