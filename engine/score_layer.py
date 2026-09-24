"""Independent H/D/A-fitted score model for HH520 Stable V3.5 Phase 1.

This layer is intentionally independent of the selected FT direction and HT/FT.
It fits home/away Poisson intensities to the formal H/D/A probability vector,
then ranks the full score distribution globally.
"""
from __future__ import annotations

import math

OUTCOME_ZH = {"HOME": "主胜", "DRAW": "平", "AWAY": "客胜"}
MAX_GOALS = 8


def _poisson(lmbda, n=MAX_GOALS):
    values = [math.exp(-lmbda)]
    for k in range(1, n + 1):
        values.append(values[-1] * lmbda / k)
    return values


def _outcome(h, a):
    return "HOME" if h > a else "AWAY" if h < a else "DRAW"


def _wdl(lh, la):
    hp, ap = _poisson(lh), _poisson(la)
    w = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for h, ph in enumerate(hp):
        for a, pa in enumerate(ap):
            p = ph * pa
            if h > a:
                w["home"] += p
            elif h < a:
                w["away"] += p
            else:
                w["draw"] += p
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


# Small deterministic grid, precomputed once at import.
_FIT_GRID = []
for _ih in range(44):
    _lh = 0.2 + 0.1 * _ih
    for _ia in range(44):
        _la = 0.2 + 0.1 * _ia
        _FIT_GRID.append((_lh, _la, _wdl(_lh, _la)))


def _fit_lambdas(target):
    best = None
    for lh, la, w in _FIT_GRID:
        err = sum((float(w[k]) - float(target[k])) ** 2 for k in ("home", "draw", "away"))
        if best is None or err < best[0]:
            best = (err, lh, la)
    return best


def score_layer(match: dict, probability: dict, htft: dict = None) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {"valid": False, "model": "HDA_POISSON_V1", "top_scores": [], "all_scores": []}

    fitted = _fit_lambdas(probs)
    if fitted is None:
        return {"valid": False, "model": "HDA_POISSON_V1", "top_scores": [], "all_scores": []}

    fit_error, lh, la = fitted
    hp, ap = _poisson(lh), _poisson(la)
    rows, totals = [], {}
    mass_total = 0.0
    for h, ph in enumerate(hp):
        for a, pa in enumerate(ap):
            mass = ph * pa
            mass_total += mass
            totals[h + a] = totals.get(h + a, 0.0) + mass
            outcome = _outcome(h, a)
            rows.append({
                "score": f"{h}:{a}",
                "home": h,
                "away": a,
                "outcome": outcome,
                "direction": OUTCOME_ZH[outcome],
                "probability": mass,
            })

    mass_total = mass_total or 1.0
    for row in rows:
        row["probability"] /= mass_total
    rows.sort(key=lambda x: x["probability"], reverse=True)

    total_rows = [{"goals": g, "probability": m / mass_total} for g, m in totals.items()]
    total_rows.sort(key=lambda x: x["probability"], reverse=True)

    goal_pick = total_rows[0]["goals"] if total_rows else None
    high = [r for r in rows if r["home"] + r["away"] >= 5 or max(r["home"], r["away"]) >= 3]
    return {
        "valid": True,
        "model": "HDA_POISSON_V1",
        "top_scores": rows[:5],
        "all_scores": rows,
        "tail_scores": high[:5],
        "high_score_mass": sum(r["probability"] for r in high),
        "top_totals": total_rows[:5],
        "total_goals_pick": None if goal_pick is None else f"{goal_pick}球",
        "total_goals_pick_probability": total_rows[0]["probability"] if total_rows else None,
        "lambda_home": lh,
        "lambda_away": la,
        "fit_error": fit_error,
        "feature_snapshot": {"source": "formal_hda_probabilities", "ft_direction_lock": False},
        "high_variance_challenger_promoted": False,
    }
