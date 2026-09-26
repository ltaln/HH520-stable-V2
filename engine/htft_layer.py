"""Formal HT/FT model for HH520 Stable V3.5.1.

The model is calibrated only from already-collected historical 10027S records
with real half-time and full-time labels. It does not collect or require any
new goal-timing information.

Calibration window:
- 2026-05-01..2026-06-30: 538 labelled matches
- 2026-07-01..2026-08-31: 592 labelled matches
- 2026-09-01..2026-09-20: 302 stress-test matches

The frozen first-half shares selected on development data are:
- home: 0.36
- away: 0.44

The full-time H/D/A probability core is not changed. The fitted Poisson goal
intensities are split into first/second-half intensities and converted to a
9-cell HT/FT distribution.
"""
from __future__ import annotations

from .score_layer import _fit_lambdas, _poisson
from .full_data_layer import half_share_adjustments, data_mode

ZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}
BASE_HOME_HALF_SHARE = 0.36
BASE_AWAY_HALF_SHARE = 0.44
HISTORICAL_LABELS = 1432
MODEL_NAME = "INDEPENDENT_POISSON_SPLIT_HTFT_V3_EXISTING_DATA"


def _outcome(h, a):
    return "HOME" if h > a else "AWAY" if h < a else "DRAW"


def _invalid(reason):
    return {
        "valid": False,
        "status": "PASS",
        "reason": reason,
        "model": MODEL_NAME + ("+COLLECTION1_1" if data_mode(match or {})["full_data"] else ""),
        "top": [],
        "distribution": [],
        "timing_used": timing_used,
        "timing_source": ((match or {}).get("goal_timing") or {}).get("source_domain") if timing_used else None,
        "timing_mode": ((match or {}).get("goal_timing") or {}).get("timing_mode") if timing_used else None,
        "new_timing_collection_required": False,
        "historical_labels": HISTORICAL_LABELS,
        "ft_core_unchanged": True,
        "ft_marginal_preserved": False,
    }


def htft_layer(probability: dict, match: dict = None, decision: dict = None) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return _invalid("invalid_ft_probability")

    fitted = _fit_lambdas(probs)
    if fitted is None:
        return _invalid("lambda_fit_failed")
    _, lambda_home, lambda_away = fitted

    home_share, away_share, timing_used = half_share_adjustments(
        match or {}, BASE_HOME_HALF_SHARE, BASE_AWAY_HALF_SHARE
    )

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
        "model": MODEL_NAME,
        "top": rows[:3],
        "distribution": rows,
        "timing_used": False,
        "timing_source": None,
        "timing_mode": None,
        "new_timing_collection_required": False,
        "historical_labels": HISTORICAL_LABELS,
        "base_home_half_share": home_share,
        "base_away_half_share": away_share,
        "home_half_share": home_share,
        "away_half_share": away_share,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "ft_core_unchanged": True,
        "ft_marginal_preserved": False,
        "risk_tier": (decision or {}).get("decision"),
        "calibration": {
            "dev1_top1": 0.3215613382899628,
            "dev1_top2": 0.533457249070632,
            "dev2_top1": 0.34290540540540543,
            "dev2_top2": 0.527027027027027,
            "stress_top1": 0.31125827814569534,
            "stress_top2": 0.4867549668874172,
            "stress_used_for_selection": False,
        },
    }
