"""Empirical market reliability filter for HH520 Stable V3.4.

The detector never rewrites H/D/A probabilities. It only classifies how much
the selected FT direction should be trusted. V3.4.1 keeps the original
probability model frozen while making draw handling symmetric.
"""
import math

VERSION = "HH520 Market Failure Detector V1.1"


def _num(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _diff(a, b):
    a, b = _num(a), _num(b)
    return None if a is None or b is None else a - b


def _orient(value, favorite):
    if value is None:
        return None
    if favorite == "home":
        return value
    if favorite == "away":
        return -value
    return None


def market_failure_detector(match: dict, probability: dict) -> dict:
    if not probability.get("valid"):
        return {
            "version": VERSION, "tier": "PASS", "risk_score": 99,
            "favorite": None, "favorite_probability": None,
            "signals": ["invalid_probability"], "valid": False,
        }

    favorite = probability.get("direction")
    market_probs = probability.get("market_probabilities") or {}
    pfav = _num(market_probs.get(favorite))
    possession = match.get("possession") or {}
    factors = match.get("research_factors") or {}

    # Side-specific structural signals are meaningful only for HOME/AWAY.
    pos = _orient(_diff(possession.get("home"), possession.get("away")), favorite)
    attack = _orient(_diff(factors.get("home_attack"), factors.get("away_attack")), favorite)
    defense = _orient(_diff(factors.get("home_defense"), factors.get("away_defense")), favorite)
    h2h = _orient(_diff(factors.get("home_h2h"), factors.get("away_h2h")), favorite)
    form = _orient(_diff(factors.get("home_form"), factors.get("away_form")), favorite)

    score = 0
    signals = []

    if favorite in {"home", "away"}:
        if defense is not None and defense <= -0.5:
            score += 3
            signals.append("defense_diff<=-0.5")
        if attack is not None and h2h is not None and attack <= -2 and h2h >= 3:
            score += 2
            signals.append("attack_diff<=-2_and_h2h_diff>=3")
        if pfav is not None and form is not None and pfav < 0.60 and form >= 0.5:
            score += 2
            signals.append("pfav<60%_and_form_diff>=0.5")
        if pfav is not None and h2h is not None and pfav < 0.55 and h2h >= 3:
            score += 2
            signals.append("pfav<55%_and_h2h_diff>=3")
        if pos is not None and pos <= -8:
            score += 1
            signals.append("possession_diff<=-8")

        if pfav is not None and pfav >= 0.65:
            score -= 2
            signals.append("strong_market_protection>=65%")
        elif pfav is not None and pfav >= 0.60:
            score -= 1
            signals.append("market_protection>=60%")
    else:
        # Draw is a first-class FT outcome. Do not force it through a
        # home/away-oriented factor transform.
        signals.append("draw_direction_symmetric_mode")

    tier = "CONFIRM" if score <= 0 else "BALANCED" if score == 1 else "TAIL_ALERT" if score <= 4 else "PASS"
    return {
        "version": VERSION,
        "valid": True,
        "tier": tier,
        "risk_score": score,
        "favorite": favorite,
        "favorite_probability": pfav,
        "oriented_features": {
            "possession": pos, "attack": attack, "defense": defense,
            "h2h": h2h, "form": form,
        },
        "signals": signals,
        "probability_overridden": False,
        "development_note": "candidate thresholds; forward validation required",
    }
