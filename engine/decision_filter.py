"""HH520 Stable V3 Decision Filter.

Inputs: probability + value + quality + match classification + independent risk.
Forbidden inputs: HH520 '建议下注' and '是否下注'.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk

VERSION = "HH520 Decision Filter V3.0"
MIN_MARGIN = 0.08
MAX_RISK_SCORE = 54


def decision_filter(match: dict, probability: dict, value: dict,
                    quality: dict = None, classification: dict = None,
                    risk: dict = None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    risk = risk or assess_risk(match, probability, value, quality, classification)

    reasons = []
    hard_pass = False

    if not quality["valid"]:
        hard_pass = True
        reasons.append("Data Quality Gate失败: " + ",".join(quality["errors"]))

    if not probability.get("valid"):
        hard_pass = True
        reasons.append("无有效概率")

    margin = classification.get("probability_margin", 0.0)
    top = classification.get("top_probability", 0.0)
    edge = value.get("directional_edge")

    if top < 0.40:
        hard_pass = True
        reasons.append("最高概率低于40%")
    if margin < 0.03:
        hard_pass = True
        reasons.append("概率方向无法有效区分")
    if risk.get("hard_pass") or risk.get("score", 100) > MAX_RISK_SCORE:
        hard_pass = True
        reasons.append("Risk Engine高风险")

    evidence = []
    if top >= 0.50:
        evidence.append("top_probability>=50%")
    if margin >= MIN_MARGIN:
        evidence.append("probability_margin>=8%")
    if edge is not None and edge >= 0.03:
        evidence.append("directional_edge>=3%")
    if classification.get("type") == "strong_favorite":
        evidence.append("strong_favorite")

    allow = (
        not hard_pass
        and margin >= MIN_MARGIN
        and bool(evidence)
        and risk.get("score", 100) <= MAX_RISK_SCORE
    )

    if not allow and not hard_pass:
        if margin < MIN_MARGIN:
            reasons.append("概率集中度不足8%")
        if not evidence:
            reasons.append("缺少有效放行证据")

    decision_score = round(
        max(0.0, min(1.0,
            0.55 * top
            + 0.25 * min(1.0, margin / 0.30)
            + 0.20 * max(0.0, min(1.0, ((edge or 0.0) + 0.05) / 0.15))
            - 0.35 * (risk.get("score", 100) / 100.0)
        )),
        4,
    )

    return {
        "version": VERSION,
        "decision": "BET_CANDIDATE" if allow else "PASS",
        "allow_prediction": allow,
        "decision_score": decision_score,
        "hard_pass": hard_pass,
        "risk": risk.get("level", "high"),
        "risk_score": risk.get("score", 100),
        "risk_reasons": risk.get("reasons", []),
        "match_type": classification.get("type"),
        "reasons": reasons,
        "evidence": evidence,
        "source": "HH520_10027s",
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": bool(value.get("used_for_direction")),
    }
