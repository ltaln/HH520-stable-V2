"""Independent HT/FT model for HH520 Stable V3.5 Phase 2.

Historical calibration (May-Aug development, Sep 1-20 stress) fixed the base
first-half goal shares at home=0.36 and away=0.44. Formal predictions require
same-day Goal Timing. Timing is used only as a bounded adjustment to first-half
intensity and never changes the FT H/D/A core.
"""
from __future__ import annotations

from .score_layer import _fit_lambdas, _poisson

ZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}
BASE_HOME_HALF_SHARE = 0.36
BASE_AWAY_HALF_SHARE = 0.44
TIMING_WEIGHT = 0.25
MAX_TIMING_DELTA = 0.08
MIN_HALF_SHARE = 0.25
MAX_HALF_SHARE = 0.60


def _outcome(h, a):
    return "HOME" if h > a else "AWAY" if h < a else "DRAW"


def _rate(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x > 1.0:
        x /= 100.0
    return x if 0.0 <= x <= 1.0 else None


def _average(values):
    values = [x for x in values if x is not None]
    return sum(values) / len(values) if values else None


def _timing_targets(match):
    timing = (match or {}).get("goal_timing") or {}
    if not timing.get("available"):
        return None, None, timing
    home = timing.get("home") or {}
    away = timing.get("away") or {}
    home_target = _average([
        _rate(home.get("first_half_gf_signal")),
        _rate(away.get("first_half_ga_signal")),
    ])
    away_target = _average([
        _rate(away.get("first_half_gf_signal")),
        _rate(home.get("first_half_ga_signal")),
    ])
    return home_target, away_target, timing


def _adjust_share(base, target):
    if target is None:
        return None
    value = (1.0 - TIMING_WEIGHT) * base + TIMING_WEIGHT * target
    value = max(base - MAX_TIMING_DELTA, min(base + MAX_TIMING_DELTA, value))
    return max(MIN_HALF_SHARE, min(MAX_HALF_SHARE, value))


def _invalid(reason, timing=None):
    timing = timing or {}
    return {
        "valid": False,
        "status": "PASS",
        "reason": reason,
        "model": "INDEPENDENT_POISSON_SPLIT_HTFT_V2_TIMING_REQUIRED",
        "top": [],
        "distribution": [],
        "timing_used": False,
        "timing_source": timing.get("source_domain"),
        "timing_mode": timing.get("timing_mode"),
        "ft_core_unchanged": True,
        "ft_marginal_preserved": False,
    }


def htft_layer(probability: dict, match: dict = None, decision: dict = None) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return _invalid("invalid_ft_probability")

    home_target, away_target, timing = _timing_targets(match or {})
    home_share = _adjust_share(BASE_HOME_HALF_SHARE, home_target)
    away_share = _adjust_share(BASE_AWAY_HALF_SHARE, away_target)
    if home_share is None or away_share is None:
        return _invalid("goal_timing_required_or_invalid", timing)

    fitted = _fit_lambdas(probs)
    if fitted is None:
        return _invalid("lambda_fit_failed", timing)
    _, lambda_home, lambda_away = fitted

    home_first = _poisson(lambda_home * home_share, 6)
    away_first = _poisson(lambda_away * away_share, 6)
    home_second = _poisson(lambda_home * (1.0 - home_share), 7)
    away_second = _poisson(lambda_away * (1.0 - away_share), 7)

    mass = {}
    for hh, phh in enumerate(home_first):
        for ah, pah in enumerate(away_first):
            ht = _outcome(hh, ah)
            for hs, phs in enumerate(home_second):
                for aas, pas in enumerate(away_second):
                    ft = _outcome(hh + hs, ah + aas)
                    key = (ht, ft)
                    mass[key] = mass.get(key, 0.0) + phh * pah * phs * pas

    total = sum(mass.values()) or 1.0
    rows = [{
        "selection": f"{ZH[ht]}/{ZH[ft]}",
        "ht": ht,
        "ft": ft,
        "probability": value / total,
    } for (ht, ft), value in mass.items()]
    rows.sort(key=lambda r: r["probability"], reverse=True)

    return {
        "valid": True,
        "status": "READY",
        "model": "INDEPENDENT_POISSON_SPLIT_HTFT_V2_TIMING_REQUIRED",
        "top": rows[:3],
        "distribution": rows,
        "timing_used": True,
        "timing_source": timing.get("source_domain"),
        "timing_mode": timing.get("timing_mode"),
        "timing_source_url": timing.get("source_url"),
        "base_home_half_share": BASE_HOME_HALF_SHARE,
        "base_away_half_share": BASE_AWAY_HALF_SHARE,
        "home_timing_target": home_target,
        "away_timing_target": away_target,
        "home_half_share": home_share,
        "away_half_share": away_share,
        "timing_weight": TIMING_WEIGHT,
        "max_timing_delta": MAX_TIMING_DELTA,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "ft_core_unchanged": True,
        "ft_marginal_preserved": False,
        "risk_tier": (decision or {}).get("decision"),
    }
