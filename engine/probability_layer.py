"""HH520 Stable V3.4 probability layer.

V3.4 separates draw anchoring from the non-draw home/away share:
- official 1X2 odds remain the only formal probability source;
- draw probability is mildly shrunk toward the empirically observed center;
- home/away split is taken from the market conditional on a non-draw result;
- 10027S fusion probability is diagnostic only and never overrides direction.
"""
import math
from .market_baseline import dejuice_1x2

_OUTCOMES = ("home", "draw", "away")
DRAW_MARKET_WEIGHT = 0.789
DRAW_CENTER_WEIGHT = 0.211
DRAW_CENTER = 0.2574


def _valid_probabilities(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in _OUTCOMES:
        try:
            number = float(value.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and 0.0 <= number <= 1.0:
            out[key] = number
    if len(out) != 3 or sum(out.values()) <= 0:
        return {}
    total = sum(out.values())
    return {key: out[key] / total for key in _OUTCOMES}


def _home_share(market):
    home = float(market["home_odds"])
    away = float(market["away_odds"])
    qh, qa = 1.0 / home, 1.0 / away
    return qh / (qh + qa)


def probability_layer(match: dict) -> dict:
    market = match.get("market", {})
    try:
        base = dejuice_1x2(market["home_odds"], market["draw_odds"], market["away_odds"])
        home_share = _home_share(market)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        base, home_share = {}, None

    page_prob = _valid_probabilities(match.get("page_probability"))
    if not base or home_share is None:
        return {
            "baseline": base, "market_probabilities": base, "probabilities": {},
            "direction": None, "concentration": None, "pmax": None, "valid": False,
            "source": "market_draw_anchor_side_share_v3_4",
            "page_probability": page_prob,
            "page_probability_used_for_direction": False,
            "page_probability_used_for_state": False,
        }

    draw_anchor = DRAW_MARKET_WEIGHT * float(base["draw"]) + DRAW_CENTER_WEIGHT * DRAW_CENTER
    draw_anchor = max(0.05, min(0.55, draw_anchor))
    side_pool = 1.0 - draw_anchor
    final = {
        "home": side_pool * home_share,
        "draw": draw_anchor,
        "away": side_pool * (1.0 - home_share),
    }

    ordered = sorted(final.items(), key=lambda x: x[1], reverse=True)
    market_side = "home" if float(base["home"]) >= float(base["away"]) else "away"
    page_vals = sorted(page_prob.items(), key=lambda x: x[1], reverse=True)
    return {
        "baseline": base,
        "market_probabilities": base,
        "probabilities": final,
        "direction": ordered[0][0],
        "concentration": ordered[0][1] - ordered[1][1],
        "pmax": ordered[0][1],
        "valid": True,
        "source": "market_draw_anchor_side_share_v3_4",
        "draw_market_probability": float(base["draw"]),
        "draw_anchor": draw_anchor,
        "draw_anchor_formula": "0.789*market_draw + 0.211*0.2574",
        "home_share": home_share,
        "side_pool": side_pool,
        "market_side_favorite": market_side,
        "market_side_favorite_probability": float(base[market_side]),
        "page_probability": page_prob,
        "page_pmax": page_vals[0][1] if page_vals else None,
        "page_direction": page_vals[0][0] if page_vals else None,
        "page_probability_used_for_direction": False,
        "page_probability_used_for_state": False,
    }
