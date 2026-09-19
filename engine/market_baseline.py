import math


def dejuice_1x2(home_odds: float, draw_odds: float, away_odds: float):
    """Return a normalized 1X2 market baseline.

    Odds are deliberately validated here, at the boundary.  Silently turning
    zero, negative, NaN, or infinite odds into probabilities makes a model
    appear to have coverage when it does not.
    """
    odds = (home_odds, draw_odds, away_odds)
    try:
        odds = tuple(float(x) for x in odds)
    except (TypeError, ValueError) as exc:
        raise ValueError("1X2 odds must be numeric") from exc
    if any(not math.isfinite(x) or x <= 1.0 for x in odds):
        raise ValueError("1X2 odds must be finite and greater than 1")
    inv = [1/x for x in odds]
    s = sum(inv)
    return {
        "home": inv[0]/s,
        "draw": inv[1]/s,
        "away": inv[2]/s,
        "overround": s - 1.0,
    }
