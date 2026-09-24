"""HH520 Stable V3.5 Phase 1 selective decision filter.

Phase 1 keeps the V3.4 H/D/A probability model unchanged and upgrades only:
- FT calibration thresholds (55/60/65)
- low-probability abstention
- existing reliability/missing-data gates

Draw research is NOT promoted in this phase.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .market_failure_detector import market_failure_detector

VERSION = "HH520 Decision Filter V3.5 Phase 1"

_TIER_ORDER = {"CONFIRM": 0, "BALANCED": 1, "TAIL_ALERT": 2, "PASS": 3}


def _worse(a, b):
    return a if _TIER_ORDER.get(a, 3) >= _TIER_ORDER.get(b, 3) else b


def _ft_grade(primary, pmax):
    if primary not in {"home", "away"}:
        return "DRAW_LEGACY"
    if pmax is None:
        return "BALANCED"
    pmax = float(pmax)
    if pmax >= 0.65:
        return "HIGH"
    if pmax >= 0.60:
        return "STRONG"
    if pmax >= 0.55:
        return "STANDARD"
    return "BALANCED"


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

    probs = probability.get("probabilities") or {}
    ordered_pairs = sorted(probs.items(), key=lambda kv: float(kv[1]), reverse=True) if probs else []
    ordered = [k for k, _ in ordered_pairs]
    margin = (float(ordered_pairs[0][1]) - float(ordered_pairs[1][1])) if len(ordered_pairs) > 1 else None
    primary = probability.get("direction")
    pmax = probability.get("pmax")
    ft_grade = _ft_grade(primary, pmax)
    ft_direction_authorized = primary == "draw" or ft_grade in {"STANDARD", "STRONG", "HIGH"}

    # Historical FT calibration: a side below 55% is not a formal single-direction pick.
    if not hard_invalid and primary in {"home", "away"} and ft_grade == "BALANCED":
        decision = _worse(decision, "BALANCED")
        reasons.append("ft_pmax<55%_no_forced_single_direction")

    # Retain V3.4.1 separation gate.
    if not hard_invalid and margin is not None:
        if margin < 0.04:
            decision = _worse(decision, "TAIL_ALERT")
            reasons.append("probability_margin<4%")
        elif margin < 0.08:
            decision = _worse(decision, "BALANCED")
            reasons.append("probability_margin<8%")

    warnings = set(quality.get("warnings", []))
    modules_missing = "team_modules_missing_or_zero" in warnings
    possession_missing = "possession_missing" in warnings

    if not hard_invalid and modules_missing and possession_missing:
        decision = _worse(decision, "PASS")
        reasons.append("critical_structural_data_missing")
    elif not hard_invalid and (modules_missing or possession_missing):
        decision = _worse(decision, "BALANCED")
        reasons.append("structural_data_incomplete")

    if hard_invalid:
        reasons = ["data_quality_or_probability_invalid"] + quality.get("errors", [])

    return {
        "version": VERSION,
        "decision": decision,
        "allow_prediction": not hard_invalid,
        "strong_recommendation": decision == "CONFIRM" and ft_grade in {"STRONG", "HIGH"},
        "decision_score": pmax,
        "probability_margin": margin,
        "hard_pass": hard_invalid,
        "state": decision,
        "base_state": failure.get("tier", decision),
        "primary_direction": primary,
        "alternate_direction": ordered[1] if len(ordered) > 1 else None,
        "ft_grade": ft_grade,
        "ft_direction_authorized": ft_direction_authorized,
        "ft_thresholds": {"standard": 0.55, "strong": 0.60, "high": 0.65},
        "tail_alert": decision in {"TAIL_ALERT", "PASS"},
        "draw_candidate": primary == "draw",
        "draw_rule_promoted": False,
        "risk": decision,
        "risk_score": failure.get("risk_score"),
        "risk_reasons": failure.get("signals", []),
        "risk_is_advisory": True,
        "failure_detector": failure,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "source": "HH520_10027s_ONLY",
        "selection_rule": "V35_PHASE1_FT_CALIBRATION_PLUS_MFD",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
        "value_layer_used_for_confirmation": False,
    }
