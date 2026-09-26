from collector.service import collect_date
from prediction import build_predictions
from prediction.builder import build_model_input
from collector.goal_timing_service import enrich_matches_with_goal_timing
from formatter.output_formatter import build_output_contract
from pathlib import Path
import yaml

PROMPT_FILE = "HH520_Stable_V3_5_Phase2_Prediction_Prompt.md"


def execute_prediction(date: str, use_gpt: bool = False):
    data = collect_date(date)
    timing_summary = enrich_matches_with_goal_timing(date, data["matches"])
    timing_summary["formal_chain"] = True
    timing_summary["role"] = "required_prediction_enrichment"
    data["goal_timing_summary"] = timing_summary
    data["predictions"] = build_predictions(data["matches"], use_gpt=use_gpt)
    data["output_contract"] = build_output_contract(data["predictions"])
    data["display_rows"] = data["output_contract"]["display_rows"]

    if not use_gpt:
        root = Path(__file__).resolve().parents[1]
        data["gpt_handoff"] = {
            "role": "EXPLANATION_ONLY",
            "stable_version": "HH520 Stable V3.5.1",
            "prompt_version": PROMPT_FILE,
            "prompt": (root / "prompts" / PROMPT_FILE).read_text(encoding="utf-8"),
            "config": yaml.safe_load((root / "config/stable.yaml").read_text(encoding="utf-8")),
            "matches": build_model_input(data["matches"]),
            "locked_predictions": data["predictions"],
            "output_contract": data["output_contract"],
        }
    return data
