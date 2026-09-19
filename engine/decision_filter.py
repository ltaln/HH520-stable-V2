def decision_filter(match: dict, probability: dict, value: dict) -> dict:
    reasons = []
    risk = "medium"
    if not probability.get("valid"):
        return {
            "risk": "high",
            "reasons": ["无有效概率，PASS"],
            "allow_prediction": False,
        }
    concentration = probability.get("concentration")

    if concentration is not None:
        if concentration < 0.08:
            risk = "high"
            reasons.append("概率高度分散")
        elif concentration >= 0.20:
            risk = "low"
            reasons.append("概率集中度较高")

    # DNA 规则暂不硬编码权重，等待离线验证后再启用
    dna = match.get("team_dna", {})
    if dna:
        reasons.append("球队DNA已读取，但权重待离线验证")

    return {
        "risk": risk,
        "reasons": reasons,
        "allow_prediction": True,
    }
