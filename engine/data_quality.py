"""Hard data-quality gate for HH520 Stable V3.4 production input."""
import math
from datetime import datetime, timezone


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _stale_warning(match):
    captured = match.get("_captured_at")
    if not captured:
        return None
    try:
        stamp = datetime.fromisoformat(str(captured).replace("Z","+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()/3600
        match_day = str(match.get("date") or "")
        today = datetime.now(timezone.utc).date().isoformat()
        if match_day >= today and age_h > 12:
            return f"stale_live_snapshot:{age_h:.1f}h"
    except Exception:
        return "captured_at_unparseable"
    return None


def data_quality_gate(match: dict, probability: dict) -> dict:
    errors, warnings = [], []

    for key in ("match_id","home_team","away_team","league"):
        if not str(match.get(key,"")).strip():
            errors.append(f"missing:{key}")

    market = match.get("market") or {}
    odds = {}
    for key in ("home_odds","draw_odds","away_odds"):
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
        if abs(total-1.0) > 0.001:
            errors.append("probability_not_normalized")
        if max(probs.values()) > 0.90:
            warnings.append("extreme_probability")

    if match.get("home_team") and match.get("home_team") == match.get("away_team"):
        errors.append("same_team")

    factors = match.get("research_factors") or {}
    eight = [
        factors.get("home_attack"), factors.get("away_attack"),
        factors.get("home_defense"), factors.get("away_defense"),
        factors.get("home_h2h"), factors.get("away_h2h"),
        factors.get("home_form"), factors.get("away_form"),
    ]
    numeric = [_finite_number(x) for x in eight]
    if all(x is None or x == 0 for x in numeric):
        warnings.append("team_modules_missing_or_zero")

    possession = match.get("possession") or {}
    if _finite_number(possession.get("home")) is None or _finite_number(possession.get("away")) is None:
        warnings.append("possession_missing")

    page = probability.get("page_probability") or {}
    if len(page) != 3:
        warnings.append("page_probability_missing")

    stale = _stale_warning(match)
    if stale:
        warnings.append(stale)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "market": odds,
        "formal_source": "HH520_10027s_ONLY",
    }
