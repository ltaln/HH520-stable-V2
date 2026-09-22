"""FT-conditioned HT/FT layer for HH520 Stable V3.4."""
from __future__ import annotations

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}
ZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}


def _factor_diff(match, name, side):
    f = (match or {}).get("research_factors") or {}
    try:
        d = float(f.get("home_" + name)) - float(f.get("away_" + name))
    except (TypeError, ValueError):
        return None
    return d if side == "home" else -d


def _row(ft_key, ht_code, cond, p_ft):
    ft = FT_MAP[ft_key]
    return {
        "selection": f"{ZH[ht_code]}/{ZH[ft]}",
        "ht": ht_code,
        "ft": ft,
        "conditional_probability": cond,
        "probability": float(p_ft) * cond,
    }


def _conditional(ft_key, probability, match):
    if ft_key == "draw":
        hs = float(probability.get("home_share", 0.5))
        if hs >= 0.5:
            return [("DRAW", 0.50), ("HOME", 0.27), ("AWAY", 0.23)]
        return [("DRAW", 0.50), ("AWAY", 0.27), ("HOME", 0.23)]

    p_market = float((probability.get("market_probabilities") or {}).get(ft_key, 0.0))
    defense = _factor_diff(match, "defense", ft_key)
    strong = p_market >= 0.55 or (defense is not None and defense >= 0.5)
    side = "HOME" if ft_key == "home" else "AWAY"
    reverse = "AWAY" if side == "HOME" else "HOME"
    if strong:
        return [(side, 0.70), ("DRAW", 0.28), (reverse, 0.02)]
    return [("DRAW", 0.46), (side, 0.50), (reverse, 0.04)]


def htft_layer(probability: dict, match: dict = None, decision: dict = None) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {"valid": False, "model": "FT_CONDITIONAL_TEMPLATE_V1", "top": [], "distribution": []}

    rows = []
    for ft_key in ("home", "draw", "away"):
        for ht, cond in _conditional(ft_key, probability, match or {}):
            rows.append(_row(ft_key, ht, cond, probs[ft_key]))
    rows.sort(key=lambda x: x["probability"], reverse=True)

    primary = probability.get("direction")
    primary_ft = FT_MAP.get(primary)
    primary_rows = [r for r in rows if r["ft"] == primary_ft]
    primary_rows.sort(key=lambda x: x["probability"], reverse=True)
    return {
        "valid": True,
        "model": "FT_CONDITIONAL_TEMPLATE_V1",
        "top": primary_rows[:3],
        "distribution": rows,
        "timing_used": False,
        "timing_source": None,
        "timing_mode": None,
        "ft_marginal_preserved": True,
        "risk_tier": (decision or {}).get("decision"),
    }
