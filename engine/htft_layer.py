"""Conditional HTFT model with optional goal-timing reweight for Stable V3.3."""
from __future__ import annotations
from .model_artifact import load_model_artifact

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}
ZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}


def _timing_signal(match):
    timing = (match or {}).get("goal_timing") or {}
    if not timing.get("available"):
        return None
    home = timing.get("home") or {}
    away = timing.get("away") or {}
    try:
        home_signal = (float(home["first_half_gf_share"]) + float(away["first_half_ga_share"])) / 2
        away_signal = (float(away["first_half_gf_share"]) + float(home["first_half_ga_share"])) / 2
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= home_signal <= 1 and 0 <= away_signal <= 1):
        return None
    return home_signal, away_signal


def _conditional_row(base_row, timing, weight):
    row = {k: float(v) for k, v in base_row.items()}
    if timing is None:
        total = sum(row.values())
        return {k: v / total for k, v in row.items()}
    home_signal, away_signal = timing
    delta = max(-1.0, min(1.0, home_signal - away_signal))
    multipliers = {
        "HOME": max(0.5, 1.0 + weight * delta),
        "AWAY": max(0.5, 1.0 - weight * delta),
        "DRAW": max(0.5, 1.0 - weight * abs(delta) * 0.5),
    }
    adjusted = {k: row[k] * multipliers[k] for k in row}
    total = sum(adjusted.values())
    return {k: v / total for k, v in adjusted.items()}


def htft_layer(probability: dict, match: dict = None) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {"valid": False, "model": "CONDITIONAL_HT_GIVEN_FT", "top": [], "distribution": []}

    artifact = load_model_artifact()
    matrix = artifact["htft"]["matrix"]
    timing_cfg = artifact.get("timing") or {}
    timing = _timing_signal(match)
    weight = float(timing_cfg.get("weight", 0.0)) if timing is not None else 0.0

    rows = []
    for ft_key, p_ft in probs.items():
        ft = FT_MAP[ft_key]
        cond = _conditional_row(matrix[ft], timing, weight)
        for ht in ("HOME", "DRAW", "AWAY"):
            p = float(p_ft) * float(cond[ht])
            rows.append({
                "selection": f"{ZH[ht]}/{ZH[ft]}",
                "ht": ht,
                "ft": ft,
                "probability": p,
            })

    rows.sort(key=lambda x: x["probability"], reverse=True)
    return {
        "valid": True,
        "model": artifact["htft"]["model"] + ("+TIMING_REWEIGHT" if timing is not None else ""),
        "top": rows[:3],
        "distribution": rows,
        "timing_used": timing is not None,
        "timing_weight": weight,
        "timing_source": ((match or {}).get("goal_timing") or {}).get("source_domain"),
        "ft_marginal_preserved": True,
    }
