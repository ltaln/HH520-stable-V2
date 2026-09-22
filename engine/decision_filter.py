"""HH520 Stable V3.4 decision filter.

Probability predicts. Market Failure Detector grades reliability. Value remains
diagnostic and cannot change the selected direction.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .market_failure_detector import market_failure_detector

VERSION = "HH520 Decision Filter V3.4"


def decision_filter(match: dict, probability: dict, value: dict,
                    quality: dict = None, classification: dict = None,
                    risk: dict = None, state: dict = None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    risk = risk or assess_risk(match, probability, value, quality, classification)
    failure = market_failure_detector(match, probability)

    hard_invalid = not quality.get("valid") or not probability.get("valid")
    decision = "PASS" if hard_invalid else failure["tier"]
    reasons = list(failure.get("signals", []))
    if hard_invalid:
        reasons = ["data_quality_or_probability_invalid"] + quality.get("errors", [])

    probs = probability.get("probabilities") or {}
    ordered = sorted(probs, key=lambda k: float(probs[k]), reverse=True) if probs else []
    return {
        "version": VERSION,
        "decision": decision,
        "allow_prediction": not hard_invalid,
        "strong_recommendation": decision == "CONFIRM",
        "decision_score": probability.get("pmax"),
        "hard_pass": hard_invalid,
        "state": decision,
        "base_state": decision,
        "primary_direction": probability.get("direction"),
        "alternate_direction": ordered[1] if len(ordered) > 1 else None,
        "tail_alert": decision in {"TAIL_ALERT", "PASS"},
        "draw_candidate": probability.get("direction") == "draw",
        "risk": decision,
        "risk_score": failure.get("risk_score"),
        "risk_reasons": failure.get("signals", []),
        "risk_is_advisory": True,
        "failure_detector": failure,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "source": "HH520_10027s_ONLY",
        "selection_rule": "MARKET_FAILURE_DETECTOR_V1",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
        "value_layer_used_for_confirmation": False,
    }
