"""HH520 Stable V3.5.1 formal draw decision filter.

Phase 2 keeps the V3.4 H/D/A probability core unchanged, retains the validated
55/60/65 side calibration, and promotes a high-specificity draw resolver in the
low-confidence side zone. The draw resolver was selected only on May-Aug
development data with symmetric cross-fit validation, then stress-tested on
Sep 1-20. It never overrides an authorized >=55% home/away direction.
"""
import math

from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .market_failure_detector import market_failure_detector
from .score_layer import _fit_lambdas

VERSION = "HH520 Decision Filter V3.5.1 Draw Final"

_TIER_ORDER = {"CONFIRM": 0, "BALANCED": 1, "TAIL_ALERT": 2, "PASS": 3}

# Frozen high-specificity draw classifier selected by May-Aug cross-fit only.
# Sep 1-20 was held out for stress validation and was not used for selection.
DRAW_FEATURES = (
    "pd","side_gap","draw_top_gap","pmax","market_pd","home_share_dev",
    "lambda_total","lambda_gap","attack_gap","defense_gap","h2h_gap","form_gap",
    "possession_gap",
)
DRAW_MEAN = (
    0.24863391819116626,0.3008214796616723,0.2774598625440862,
    0.5261462362270642,0.24628963015356997,0.19548316647929714,
    2.5030973451327414,0.6687610619469035,3.7778761061946904,
    0.6472566371681415,5.474336283185841,0.5453716814159293,
    6.138743362831859,
)
DRAW_STD = (
    0.037173058858070186,0.18975251454989756,0.14514931876985446,
    0.11097824899495552,0.04711414303937914,0.11613248634382657,
    0.3148523453517267,0.4568914449474063,3.084538505183568,
    0.5756451521701617,4.665800612535865,0.4701367659171995,
    5.249709407513992,
)
DRAW_WEIGHTS = (
    -1.0954563656783047,
    0.36838412955099664,0.0865935677185142,-0.08491444459062916,
    0.04132106094108896,0.36838412955101246,0.1843527599708549,
    0.26593256512285707,-0.06877802027743841,0.07838883937096178,
    -0.05414301529034361,-0.009684011416704982,0.06295638996527687,
    -0.02550321545183099,
)
DRAW_THRESHOLD = 0.38
DRAW_PMAX_MIN = 0.39
DRAW_PMAX_LIMIT = 0.45


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


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gap(factors, name):
    home = _num(factors.get("home_" + name))
    away = _num(factors.get("away_" + name))
    return abs(home - away) if home is not None and away is not None else None


def _draw_features(match, probability):
    probs = probability.get("probabilities") or {}
    market = probability.get("market_probabilities") or {}
    if len(probs) != 3:
        return None
    ph, pd, pa = (float(probs.get(k, 0.0)) for k in ("home", "draw", "away"))
    home_share = probability.get("home_share")
    if home_share is None:
        return None

    fitted = _fit_lambdas(probs)
    if fitted is None:
        return None
    _, lambda_home, lambda_away = fitted

    factors = (match or {}).get("research_factors") or {}
    possession = (match or {}).get("possession") or {}
    hp, ap = _num(possession.get("home")), _num(possession.get("away"))
    values = {
        "pd": pd,
        "side_gap": abs(ph - pa),
        "draw_top_gap": max(ph, pa) - pd,
        "pmax": max(ph, pd, pa),
        "market_pd": float(market.get("draw", 0.0)),
        "home_share_dev": abs(float(home_share) - 0.5),
        "lambda_total": lambda_home + lambda_away,
        "lambda_gap": abs(lambda_home - lambda_away),
        "attack_gap": _gap(factors, "attack"),
        "defense_gap": _gap(factors, "defense"),
        "h2h_gap": _gap(factors, "h2h"),
        "form_gap": _gap(factors, "form"),
        "possession_gap": abs(hp - ap) if hp is not None and ap is not None else None,
    }
    return values


def _draw_resolver(match, probability):
    values = _draw_features(match, probability)
    if not values:
        return False, {"score": None}
    if values["pmax"] < DRAW_PMAX_MIN or values["pmax"] > DRAW_PMAX_LIMIT:
        return False, {"score": None, **values}
    missing = [name for name in DRAW_FEATURES if values.get(name) is None]
    if missing:
        return False, {"score": None, "missing_features": missing, **values}

    z = DRAW_WEIGHTS[0]
    for i, name in enumerate(DRAW_FEATURES):
        z += DRAW_WEIGHTS[i + 1] * ((values[name] - DRAW_MEAN[i]) / DRAW_STD[i])
    z = max(-30.0, min(30.0, z))
    score = 1.0 / (1.0 + math.exp(-z))
    return score >= DRAW_THRESHOLD, {"score": score, **values}


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

    draw_rule_passed, draw_metrics = _draw_resolver(match, probability)
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
        reasons.append("formal_draw_logistic_resolver_triggered")
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
        reasons.append("optional_structural_data_missing_advisory")
    elif not hard_invalid and (modules_missing or possession_missing):
        reasons.append("optional_structural_data_incomplete_advisory")

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
        "draw_rule_type": "CROSS_FIT_LOGISTIC_V1",
        "draw_rule_threshold": DRAW_THRESHOLD,
        "draw_rule_pmax_min": DRAW_PMAX_MIN,
        "draw_rule_pmax_limit": DRAW_PMAX_LIMIT,
        "draw_rule_metrics": draw_metrics,
        "draw_rule_scope": "BALANCED_SIDE_ZONE_39_TO_45_ONLY",
        "draw_rule_never_overrides_authorized_side": True,
        "risk": decision,
        "risk_score": failure.get("risk_score"),
        "risk_reasons": failure.get("signals", []),
        "risk_is_advisory": True,
        "failure_detector": failure,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "source": "HH520_10027s_ONLY",
        "selection_rule": "V351_FT_CALIBRATION_PLUS_FORMAL_DRAW_LOGISTIC_PLUS_MFD",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
        "value_layer_used_for_confirmation": False,
    }
