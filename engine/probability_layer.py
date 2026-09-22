import math
from .market_baseline import dejuice_1x2

_OUTCOMES = ("home", "draw", "away")


def _valid_probabilities(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in _OUTCOMES:
        raw = value.get(key)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and 0.0 <= number <= 1.0:
            out[key] = number
    if len(out) != 3 or sum(out.values()) <= 0:
        return {}
    total = sum(out.values())
    return {key: out[key] / total for key in _OUTCOMES}


def probability_layer(match: dict) -> dict:
    market = match.get("market", {})
    try:
        base = dejuice_1x2(market["home_odds"], market["draw_odds"], market["away_odds"])
    except (KeyError, TypeError, ValueError):
        base = {}

    # V3.3: market remains the full-coverage WDL anchor. 10027s page
    # probability is independent evidence for State/Conflict/Value only.
    page_prob = _valid_probabilities(match.get("page_probability"))
    final = {k: base[k] for k in _OUTCOMES} if base else {}

    vals = sorted(
        [(k, final.get(k)) for k in _OUTCOMES if final.get(k) is not None],
        key=lambda x: x[1],
        reverse=True,
    )
    concentration = vals[0][1] - vals[1][1] if len(vals) >= 2 else None
    pmax = vals[0][1] if vals else None

    page_vals = sorted(page_prob.items(), key=lambda x: x[1], reverse=True)
    return {
        "baseline": base,
        "probabilities": final,
        "direction": vals[0][0] if vals else None,
        "concentration": concentration,
        "pmax": pmax,
        "valid": bool(final),
        "source": "market_proportional_devig",
        "page_probability": page_prob,
        "page_pmax": page_vals[0][1] if page_vals else None,
        "page_direction": page_vals[0][0] if page_vals else None,
        "page_probability_used_for_direction": False,
        "page_probability_used_for_state": bool(page_prob),
    }
