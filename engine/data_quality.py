"""Hard data-quality gate for Stable V3 prediction input."""
import math


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def data_quality_gate(match: dict, probability: dict) -> dict:
    errors = []
    warnings = []

    for key in ("match_id", "home_team", "away_team", "league"):
        if not str(match.get(key, "")).strip():
            errors.append(f"missing:{key}")

    market = match.get("market") or {}
    odds = {}
    for key in ("home_odds", "draw_odds", "away_odds"):
        number = _finite_number(market.get(key))
        if number is None or number <= 1.0:
            errors.append(f"invalid_market:{key}")
        else:
            odds[key] = number

    if not probability.get("valid"):
        errors.append("invalid_probability")

    probs = probability.get("probabilities") or {}
    if probs:
        total = sum(probs.values())
        if abs(total - 1.0) > 0.001:
            errors.append("probability_not_normalized")
        if max(probs.values()) > 0.90:
            warnings.append("extreme_probability")

    if match.get("home_team") and match.get("away_team") and match.get("home_team") == match.get("away_team"):
        errors.append("same_team")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "market": odds,
    }
