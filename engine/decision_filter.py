"""HH520 Stable V3.5 Phase 2 selective decision filter.

Phase 2 keeps the V3.4 H/D/A probability core unchanged, retains the validated
55/60/65 side calibration, and adds a formal draw resolver ONLY inside the
low-confidence side zone. The draw resolver never overrides an authorized
>=55% home/away direction.

Draw resolver was selected on May-Aug historical data and stress-tested on
Sep 1-20. It is deliberately treated as a BALANCED draw decision, not a
CONFIRM tier.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .market_failure_detector import market_failure_detector

VERSION = "HH520 Decision Filter V3.5 Phase 2"

_TIER_ORDER = {"CONFIRM": 0, "BALANCED": 1, "TAIL_ALERT": 2, "PASS": 3}

DRAW_RULE = {
    "pd_min": 0.29,
    "side_gap_max": 0.20,
    "draw_top_gap_max": 0.16,
    "pmax_max": 0.45,
    "home_share_dev_max": 0.16,
}


def _worse(a, b):
    return a if _TIER_ORDER.get(a, 3) >= _TIER_ORDER.get(b, 3) else b


def _ft_grade(primary, pmax):
    if primary not in {"home", "away"}:
        return "DRAW"
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


def _draw_resolver(probability):
    probs = probability.get("probabilities") or {}
    if len(probs) != 3:
        return False, {}
    ph, pd, pa = (float(probs.get(k, 0.0)) for k in ("home", "draw", "away"))
    pmax = max(ph, pd, pa)
    home_share = probability.get("home_share")
    if home_share is None:
        return False, {}
    metrics = {
        "pd": pd,
        "side_gap": abs(ph - pa),
        "draw_top_gap": max(ph, pa) - pd,
        "pmax": pmax,
        "home_share_dev": abs(float(home_share) - 0.5),
    }
    passed = (
        pd >= DRAW_RULE["pd_min"]
        and metrics["side_gap"] <= DRAW_RULE["side_gap_max"]
        and metrics["draw_top_gap"] <= DRAW_RULE["draw_top_gap_max"]
        and pmax <= DRAW_RULE["pmax_max"]
        and metrics["home_share_dev"] <= DRAW_RULE["home_share_dev_max"]
    )
    return passed, metrics


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

    # Formal draw resolution is allowed only where the old Phase 1 output would
    # have been BALANCED/no-forced-side. It cannot overturn an authorized side.
    draw_rule_passed, draw_metrics = _draw_resolver(probability)
    draw_rule_promoted = (
        not hard_invalid
        and primary in {"home", "away"}
        and ft_grade == "BALANCED"
        and draw_rule_passed
    )
    resolved_direction = "draw" if draw_rule_promoted else primary
    ft_direction_authorized = (
        resolved_direction == "draw"
        or ft_grade in {"STANDARD", "STRONG", "HIGH"}
    )

    if draw_rule_promoted:
        decision = _worse(decision, "BALANCED")
        reasons.append("formal_draw_resolver_triggered")
    elif not hard_invalid and primary in {"home", "away"} and ft_grade == "BALANCED":
        decision = _worse(decision, "BALANCED")
        reasons.append("ft_pmax<55%_no_forced_single_direction")

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

    strong_recommendation = (
        decision == "CONFIRM"
        and resolved_direction in {"home", "away"}
        and ft_grade in {"STRONG", "HIGH"}
    )

    return {
        "version": VERSION,
        "decision": decision,
        "allow_prediction": not hard_invalid,
        "strong_recommendation": strong_recommendation,
        "decision_score": probs.get(resolved_direction) if resolved_direction else pmax,
        "probability_margin": margin,
        "hard_pass": hard_invalid,
        "state": decision,
        "base_state": failure.get("tier", decision),
        "primary_direction": primary,
        "resolved_direction": resolved_direction,
        "alternate_direction": ordered[1] if len(ordered) > 1 else None,
        "ft_grade": "DRAW_STANDARD" if draw_rule_promoted else ft_grade,
        "ft_direction_authorized": ft_direction_authorized,
        "ft_thresholds": {"standard": 0.55, "strong": 0.60, "high": 0.65},
        "tail_alert": decision in {"TAIL_ALERT", "PASS"},
        "draw_candidate": resolved_direction == "draw",
        "draw_rule_promoted": draw_rule_promoted,
        "draw_rule": DRAW_RULE,
        "draw_rule_metrics": draw_metrics,
        "draw_rule_scope": "BALANCED_SIDE_ZONE_ONLY",
        "draw_rule_never_overrides_authorized_side": True,
        "risk": decision,
        "risk_score": failure.get("risk_score"),
        "risk_reasons": failure.get("signals", []),
        "risk_is_advisory": True,
        "failure_detector": failure,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "source": "HH520_10027s_ONLY",
        "selection_rule": "V35_PHASE2_FT_CALIBRATION_PLUS_FORMAL_DRAW_RESOLVER_PLUS_MFD",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
        "value_layer_used_for_confirmation": False,
    }
