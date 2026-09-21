"""HH520 Risk Engine V3.1.

Only the risk module changes. Probability, Value and Decision Filter contracts
remain unchanged. HH520 advice fields are never read.
"""
from .match_classifier import classify_match
from .data_quality import data_quality_gate

VERSION = "HH520 Risk Engine V3.1"


def _selected_odds(match, direction):
    market = match.get("market") or {}
    return market.get({"home": "home_odds", "draw": "draw_odds", "away": "away_odds"}.get(direction, ""))


def _base_risk(match, probability, value, quality, classification, *, v31=False):
    if not quality["valid"]:
        return 100, ["数据质量门禁失败"] + quality["errors"]

    score = 0
    reasons = []
    top = classification["top_probability"]
    margin = classification["probability_margin"]

    if top < 0.40:
        score += 40
        reasons.append("最高概率低于40%")
    elif top < 0.50:
        score += 18
        reasons.append("最高概率不足50%")

    if margin < 0.05:
        score += 30
        reasons.append("概率方向高度接近")
    elif margin < 0.10:
        score += 16
        reasons.append("概率集中度偏低")

    # V3 legacy modifiers are preserved for exact comparison.
    if not v31:
        if classification["type"] == "balanced":
            score += 15
            reasons.append("均衡型比赛")
        elif classification["type"] == "cup":
            score += 8
            reasons.append("杯赛/淘汰赛波动修正")
    else:
        # V3.1: explicit dispersion + balance + match-type modifiers.
        if margin < 0.10:
            score += 15
            reasons.append("V3.1概率分散风险")
        if classification["type"] == "balanced":
            score += 15
            reasons.append("V3.1均衡比赛风险")
        modifiers = {"strong_favorite": -5, "standard": 0, "cup": 5, "balanced": 15}
        modifier = modifiers.get(classification["type"], 0)
        score += modifier
        if modifier:
            reasons.append(f"V3.1比赛类型修正:{modifier:+d}")

    edge = value.get("directional_edge")
    if edge is not None:
        if edge < -0.03:
            score += 25
            reasons.append("模型方向弱于市场基线")
        elif edge < 0:
            score += 10
            reasons.append("模型方向无正价值")

    try:
        odds = float(_selected_odds(match, probability.get("direction")))
    except (TypeError, ValueError):
        odds = None
    if odds is not None and 1.80 <= odds < 3.00:
        score += 10
        reasons.append("主方向处于中高赔率风险区")

    factors = match.get("research_factors") or {}
    page_risk = str(factors.get("risk", "")).strip()
    if page_risk in {"高", "很高"}:
        score += 25
        reasons.append("10027s风险字段偏高")
    elif page_risk in {"中高", "中"}:
        score += 12
        reasons.append("10027s风险字段非低风险")

    pattern = str(factors.get("pattern", "")).strip()
    if "极端" in pattern:
        score += 25
        reasons.append("极端结构")
    elif "边缘" in pattern:
        score += 15
        reasons.append("边缘结构")

    return max(0, min(100, score)), reasons


def _format(score, reasons, version):
    level = "low" if score < 25 else "medium" if score < 55 else "high"
    return {
        "version": version,
        "score": score,
        "level": level,
        "reasons": reasons,
        "hard_pass": score >= 70,
    }


def assess_risk_v3(match: dict, probability: dict, value: dict, quality=None, classification=None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    score, reasons = _base_risk(match, probability, value, quality, classification, v31=False)
    return _format(score, reasons, "HH520 Risk Engine V3.0")


def assess_risk_v31(match: dict, probability: dict, value: dict, quality=None, classification=None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    score, reasons = _base_risk(match, probability, value, quality, classification, v31=True)
    return _format(score, reasons, VERSION)


def assess_risk(match: dict, probability: dict, value: dict, quality=None, classification=None) -> dict:
    """Production default remains V3.0 until a candidate wins validation."""
    return assess_risk_v3(match, probability, value, quality, classification)


def assess_risk_v32(match: dict, probability: dict, value: dict, quality=None, classification=None) -> dict:
    """Research candidate: simplified 3-factor risk model.

    Core factors only:
    - top_probability
    - odds_zone
    - value_conflict
    """
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    if not quality["valid"]:
        return _format(100, ["数据质量门禁失败"] + quality["errors"], "HH520 Risk Engine V3.2 Candidate")

    score = 0
    reasons = []
    top = classification["top_probability"]
    if top < 0.40:
        score += 40
        reasons.append("最高概率低于40%")
    elif top < 0.50:
        score += 18
        reasons.append("最高概率不足50%")

    edge = value.get("directional_edge")
    if edge is not None:
        if edge < -0.03:
            score += 25
            reasons.append("模型方向弱于市场基线")
        elif edge < 0:
            score += 10
            reasons.append("模型方向无正价值")

    try:
        odds = float(_selected_odds(match, probability.get("direction")))
    except (TypeError, ValueError):
        odds = None
    if odds is not None and 1.80 <= odds < 3.00:
        score += 10
        reasons.append("主方向处于中高赔率风险区")

    score = max(0, min(100, score))
    return _format(score, reasons, "HH520 Risk Engine V3.2 Candidate")
