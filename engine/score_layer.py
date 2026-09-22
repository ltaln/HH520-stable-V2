"""Frozen pooled-Poisson score layer for HH520 Stable V3.2."""
from __future__ import annotations
import math
from .model_artifact import load_model_artifact

_OUTCOME_ZH = {"HOME": "主胜", "DRAW": "平", "AWAY": "客胜"}


def _finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _diff(a, b):
    a = _finite(a)
    b = _finite(b)
    return None if a is None or b is None else a - b


def _score_direction(home: int, away: int) -> str:
    return "HOME" if home > away else "AWAY" if home < away else "DRAW"


def _features(match: dict, probability: dict) -> dict:
    probs = probability.get("probabilities") or {}
    possession = match.get("possession") or {}
    factors = match.get("research_factors") or {}

    eight = [
        factors.get("home_attack"), factors.get("away_attack"),
        factors.get("home_defense"), factors.get("away_defense"),
        factors.get("home_h2h"), factors.get("away_h2h"),
        factors.get("home_form"), factors.get("away_form"),
    ]
    numeric = [_finite(x) for x in eight]
    all_zero_or_missing = all(x is None or x == 0 for x in numeric)

    return {
        "p_home": _finite(probs.get("home")),
        "p_draw": _finite(probs.get("draw")),
        "p_away": _finite(probs.get("away")),
        "home_pos_diff": _diff(possession.get("home"), possession.get("away")),
        "attack_diff": None if all_zero_or_missing else _diff(factors.get("home_attack"), factors.get("away_attack")),
        "defense_diff": None if all_zero_or_missing else _diff(factors.get("home_defense"), factors.get("away_defense")),
        "h2h_diff": None if all_zero_or_missing else _diff(factors.get("home_h2h"), factors.get("away_h2h")),
        "form_diff": None if all_zero_or_missing else _diff(factors.get("home_form"), factors.get("away_form")),
        "team_modules_missing": 1.0 if all_zero_or_missing else 0.0,
    }


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))


def score_layer(match: dict, probability: dict) -> dict:
    if not probability.get("valid"):
        return {"valid": False, "model": "POOLED_POISSON", "top_scores": []}

    artifact = load_model_artifact()
    cfg = artifact["score"]
    raw = _features(match, probability)
    z = []
    for name in cfg["feature_columns"]:
        value = raw.get(name)
        if value is None or not math.isfinite(float(value)):
            value = float(cfg["median"][name])
        mean = float(cfg["mean"][name])
        std = float(cfg["std"][name]) or 1.0
        z.append((float(value) - mean) / std)

    home_coef = [float(x) for x in cfg["home_coef"]]
    away_coef = [float(x) for x in cfg["away_coef"]]
    eta_home = home_coef[0] + sum(c * x for c, x in zip(home_coef[1:], z))
    eta_away = away_coef[0] + sum(c * x for c, x in zip(away_coef[1:], z))
    lambda_home = math.exp(max(-5.0, min(5.0, eta_home)))
    lambda_away = math.exp(max(-5.0, min(5.0, eta_away)))

    max_goals = int(cfg.get("max_goals", 10))
    rows = []
    total_mass = 0.0
    totals = {}
    for home in range(max_goals + 1):
        ph = _poisson_pmf(home, lambda_home)
        for away in range(max_goals + 1):
            p = ph * _poisson_pmf(away, lambda_away)
            total_mass += p
            totals[home + away] = totals.get(home + away, 0.0) + p
            outcome = _score_direction(home, away)
            rows.append({
                "score": f"{home}:{away}",
                "home": home,
                "away": away,
                "outcome": outcome,
                "direction": _OUTCOME_ZH[outcome],
                "probability": p,
            })

    if total_mass <= 0:
        return {"valid": False, "model": cfg["model"], "top_scores": []}

    for row in rows:
        row["probability"] /= total_mass
    for key in list(totals):
        totals[key] /= total_mass

    rows.sort(key=lambda x: x["probability"], reverse=True)
    total_ranked = sorted(
        [{"goals": int(k), "probability": float(v)} for k, v in totals.items()],
        key=lambda x: x["probability"],
        reverse=True,
    )
    goal_pick = total_ranked[0]["goals"] if total_ranked else None

    return {
        "valid": True,
        "model": cfg["model"],
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "top_scores": rows[:5],
        "top_totals": total_ranked[:5],
        "total_goals_pick": None if goal_pick is None else f"{goal_pick}球",
        "feature_snapshot": raw,
    }
