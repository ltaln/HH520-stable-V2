"""HH520 Stable V3.3 Decision/Insurance layer.

The filter no longer equates pmax with correctness. It consumes the State
Engine and preserves prediction output while distinguishing confirmed,
balanced, conflict and tail-alert scenarios.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .state_engine import build_state

VERSION = "HH520 Decision Filter V3.3"


def decision_filter(match: dict, probability: dict, value: dict,
                    quality: dict = None, classification: dict = None,
                    risk: dict = None, state: dict = None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    risk = risk or assess_risk(match, probability, value, quality, classification)
    state = state or build_state(match, probability)

    reasons = []
    hard_pass = False
    if not quality.get("valid"):
        hard_pass = True
        reasons.append("Data Quality Gate失败: " + ",".join(quality.get("errors", [])))
    if not probability.get("valid"):
        hard_pass = True
        reasons.append("无有效市场概率")

    if hard_pass:
        decision = "PASS"
    else:
        decision = state.get("state", "STANDARD")
        reasons.extend(state.get("confirmations", []))
        reasons.extend(state.get("conflicts", []))

    return {
        "version": VERSION,
        "decision": decision,
        "allow_prediction": not hard_pass,
        "decision_score": state.get("market_pmax"),
        "hard_pass": hard_pass,
        "state": state.get("state"),
        "base_state": state.get("base_state"),
        "primary_direction": state.get("primary_direction"),
        "alternate_direction": state.get("alternate_direction"),
        "tail_alert": bool(state.get("tail_alert")),
        "draw_candidate": bool(state.get("draw_candidate")),
        "risk": risk.get("level", "unknown"),
        "risk_score": risk.get("score"),
        "risk_reasons": risk.get("reasons", []),
        "risk_is_advisory": True,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "source": "HH520_10027s+PUBLIC_GOAL_TIMING_OPTIONAL",
        "selection_rule": "STATE_ENGINE_V3_3",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
        "value_layer_used_for_confirmation": bool(value.get("used_for_confirmation")),
    }
