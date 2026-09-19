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
    # A direction requires a complete probability distribution. Partial page
    # values must not quietly replace the complete market baseline.
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

    page_prob = _valid_probabilities(match.get("page_probability"))
    final = page_prob or ({k: base[k] for k in _OUTCOMES} if base else {})

    vals = [(k, final.get(k)) for k in ("home","draw","away") if final.get(k) is not None]
    vals = sorted(vals, key=lambda x: x[1], reverse=True)
    concentration = None
    if len(vals) >= 2:
        concentration = vals[0][1] - vals[1][1]

    return {
        "baseline": base,
        "probabilities": final,
        "direction": vals[0][0] if vals else None,
        "concentration": concentration,
        "valid": bool(final),
    }
