def confidence_from_probability(probability: dict, decision: dict) -> int:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or not decision.get("allow_prediction", True):
        return 0
    top = max(probs.values()) if probs else 0.0
    base = int(round(top * 100))
    if decision.get("risk") == "high":
        base -= 8
    elif decision.get("risk") == "low":
        base += 3
    return max(1, min(99, base))
