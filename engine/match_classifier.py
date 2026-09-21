"""Deterministic match-type classifier used only for risk calibration."""

_CUP_WORDS = ("杯", "cup", "champions league", "europa", "亚冠", "欧冠", "欧联", "世界杯", "欧洲杯", "美洲杯", "亚洲杯")


def classify_match(match: dict, probability: dict) -> dict:
    probs = probability.get("probabilities") or {}
    ordered = sorted(probs.values(), reverse=True)
    top = ordered[0] if ordered else 0.0
    margin = (ordered[0] - ordered[1]) if len(ordered) >= 2 else 0.0
    league = str(match.get("league", "")).lower()

    if any(word.lower() in league for word in _CUP_WORDS):
        match_type = "cup"
    elif top >= 0.60 and margin >= 0.20:
        match_type = "strong_favorite"
    elif margin < 0.08:
        match_type = "balanced"
    else:
        match_type = "standard"

    return {
        "type": match_type,
        "top_probability": top,
        "probability_margin": margin,
    }
