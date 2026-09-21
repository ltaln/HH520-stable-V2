"""HH520 Decision Filter V2 research candidate.

Derived from Aug 2026 discovery + Sep 1-20 historical shadow/joint factor stability.
This module is RESEARCH_ONLY. It must never modify Stable or auto-promote rules.
"""
from research.hidden_model_reverse import _factor_pairs

STABLE_ACCESS = "FORBIDDEN"
VERSION = "HH520 Decision Filter V2.0 Candidate"

# WDL-only robust signals: positive in both Aug and Sep windows.
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

# WDL-only robust negative signals: below baseline in both Aug and Sep windows.
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

MIN_DECISION_SCORE = 0.12
HARD_PASS = {
    ("probability_concentration", "<40%"),
    ("pattern", "⚡ 极端"),
}


def evaluate_record(record):
    """Return a research-only BET/PASS gate for one pre-match record."""
    pairs = _factor_pairs(record)
    pos = []
    neg = []
    score = 0.0

    for key, weight in POSITIVE.items():
        if str(pairs.get(key[0]) or "") == key[1]:
            pos.append({"factor": key[0], "value": key[1], "weight": weight})
            score += weight

    hard_pass = False
    for key, weight in NEGATIVE.items():
        if str(pairs.get(key[0]) or "") == key[1]:
            neg.append({"factor": key[0], "value": key[1], "weight": weight})
            score += weight
            if key in HARD_PASS:
                hard_pass = True

    decision = "PASS"
    if not hard_pass and pos and score >= MIN_DECISION_SCORE:
        decision = "BET_CANDIDATE"

    return {
        "version": VERSION,
        "stable_access": STABLE_ACCESS,
        "decision": decision,
        "decision_score": round(score, 4),
        "positive_evidence": pos,
        "negative_evidence": neg,
        "hard_pass": hard_pass,
        "policy": "RESEARCH_ONLY_MANUAL_REVIEW_REQUIRED",
    }
