"""Stable V2.1 Decision Filter.

The upstream prediction/probability/value logic remains unchanged. This layer
only gates whether a candidate may proceed to final prediction, using factors
validated across Aug 2026 Discovery and Sep 1-20 Historical Shadow.

Source contract: HH520 10027s.
"""

VERSION = "HH520 Decision Filter V2.0"
MIN_DECISION_SCORE = 0.12

# Conservative WDL evidence. Weights are the weaker (minimum) uplift observed
# across the two validation windows, so one strong month cannot dominate.
POSITIVE = {
    ("away_odds_bucket", "<1.50"): 0.2539,
    ("probability_concentration", ">=60%"): 0.2357,
    ("structure", "强优"): 0.2298,
    ("pattern", "🔶风控赔率"): 0.1769,
    ("home_odds_bucket", "<1.50"): 0.1707,
    ("handicap", "客让半一低水/一球高水"): 0.1131,
    ("rating", "B+"): 0.1109,
    ("risk", "低"): 0.0985,
}

NEGATIVE = {
    ("pattern", "⚡ 极端"): -0.2202,
    ("probability_concentration", "<40%"): -0.1845,
    ("pattern", "⚠️ 边缘"): -0.1731,
    ("away_odds_bucket", "2.20-2.99"): -0.1605,
    ("home_odds_bucket", "2.20-2.99"): -0.1516,
    ("away_odds_bucket", "1.80-2.19"): -0.1452,
    ("home_odds_bucket", "1.80-2.19"): -0.1312,
    ("risk", "中高"): -0.1268,
    ("handicap", "主让平半低水/半球高水"): -0.1240,
}

HARD_PASS = {
    ("probability_concentration", "<40%"),
    ("pattern", "⚡ 极端"),
}


def _bucket_odds(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x < 1.5:
        return "<1.50"
    if x < 1.8:
        return "1.50-1.79"
    if x < 2.2:
        return "1.80-2.19"
    if x < 3.0:
        return "2.20-2.99"
    return ">=3.00"


def _bucket_probability_concentration(match, probability):
    probs = match.get("page_probability")
    if not isinstance(probs, dict):
        probs = probability.get("probabilities") or {}
    vals = []
    for key in ("home", "draw", "away"):
        try:
            vals.append(float(probs[key]))
        except (KeyError, TypeError, ValueError):
            return None
    top = max(vals)
    if top < 0.40:
        return "<40%"
    if top < 0.50:
        return "40-49%"
    if top < 0.60:
        return "50-59%"
    return ">=60%"


def _factor_pairs(match, probability):
    factors = match.get("research_factors") or {}
    market = match.get("market") or {}
    pairs = {
        "risk": factors.get("risk"),
        "rating": factors.get("rating"),
        "structure": factors.get("structure"),
        "pattern": factors.get("pattern"),
        "handicap": factors.get("handicap"),
        "probability_concentration": _bucket_probability_concentration(match, probability),
        "home_odds_bucket": _bucket_odds(market.get("home_odds")),
        "away_odds_bucket": _bucket_odds(market.get("away_odds")),
    }
    return {
        key: str(value).strip()
        for key, value in pairs.items()
        if value not in (None, "", "-", "--", "—")
    }


def decision_filter(match: dict, probability: dict, value: dict) -> dict:
    if not probability.get("valid"):
        return {
            "version": VERSION,
            "risk": "high",
            "reasons": ["无有效概率，PASS"],
            "allow_prediction": False,
            "decision": "PASS",
            "decision_score": 0.0,
            "positive_evidence": [],
            "negative_evidence": [],
            "hard_pass": True,
        }

    pairs = _factor_pairs(match, probability)
    positive = []
    negative = []
    score = 0.0
    hard_pass = False

    for key, weight in POSITIVE.items():
        if pairs.get(key[0]) == key[1]:
            positive.append({"factor": key[0], "value": key[1], "weight": weight})
            score += weight

    for key, weight in NEGATIVE.items():
        if pairs.get(key[0]) == key[1]:
            negative.append({"factor": key[0], "value": key[1], "weight": weight})
            score += weight
            if key in HARD_PASS:
                hard_pass = True

    reasons = []
    if positive:
        reasons.append("跨8月/9月稳定正向证据: " + "、".join(
            f"{x['factor']}={x['value']}" for x in positive
        ))
    if negative:
        reasons.append("跨8月/9月稳定负向证据: " + "、".join(
            f"{x['factor']}={x['value']}" for x in negative
        ))

    allow = bool(positive) and not hard_pass and score >= MIN_DECISION_SCORE
    if hard_pass:
        reasons.append("命中Hard PASS条件")
    elif not positive:
        reasons.append("无已验证正向证据")
    elif score < MIN_DECISION_SCORE:
        reasons.append("正负证据抵消后低于放行阈值")

    if hard_pass:
        risk = "high"
    elif negative:
        risk = "medium"
    else:
        risk = "low"

    return {
        "version": VERSION,
        "risk": risk,
        "reasons": reasons,
        "allow_prediction": allow,
        "decision": "BET_CANDIDATE" if allow else "PASS",
        "decision_score": round(score, 4),
        "positive_evidence": positive,
        "negative_evidence": negative,
        "hard_pass": hard_pass,
        "source": "HH520_10027s",
        "value_layer_used_for_direction": bool(value.get("used_for_direction")),
    }
