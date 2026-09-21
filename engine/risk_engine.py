"""Stable V3 independent risk engine.

It never reads HH520 '建议下注' / '是否下注' fields.
"""
from .match_classifier import classify_match
from .data_quality import data_quality_gate


def _selected_odds(match, direction):
    market = match.get("market") or {}
    return market.get({"home": "home_odds", "draw": "draw_odds", "away": "away_odds"}.get(direction, ""))


def assess_risk(match: dict, probability: dict, value: dict, quality=None, classification=None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    score = 0
    reasons = []

    if not quality["valid"]:
        return {
            "score": 100,
            "level": "high",
            "reasons": ["数据质量门禁失败"] + quality["errors"],
            "hard_pass": True,
        }

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

    if classification["type"] == "balanced":
        score += 15
        reasons.append("均衡型比赛")
    elif classification["type"] == "cup":
        score += 8
        reasons.append("杯赛/淘汰赛波动修正")

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

    score = min(100, score)
    level = "low" if score < 25 else "medium" if score < 55 else "high"
    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "hard_pass": score >= 70,
    }
