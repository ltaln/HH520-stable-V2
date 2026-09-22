def confidence_from_probability(probability: dict, decision: dict = None) -> int:
    """Display confidence is the market top probability.

    Selection/PASS is handled separately by the research confidence and
    decision layers. A normal prediction must not become 0% merely because it
    is outside the S-grade selective subset.
    """
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or not probs:
        return 0
    top = max(float(x) for x in probs.values())
    return max(1, min(99, int(round(top * 100))))
