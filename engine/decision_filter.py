"""HH520 Stable V3.2 Decision Filter.

Research result:
- WDL direction comes from the market baseline.
- The only promoted selective rule is market pmax >= the frozen S threshold.
- Risk/value/team factors remain advisory and never flip direction.
"""
from .data_quality import data_quality_gate
from .match_classifier import classify_match
from .risk_engine import assess_risk
from .model_artifact import load_model_artifact

VERSION = "HH520 Decision Filter V3.2"


def decision_filter(match: dict, probability: dict, value: dict,
                    quality: dict = None, classification: dict = None,
                    risk: dict = None) -> dict:
    quality = quality or data_quality_gate(match, probability)
    classification = classification or classify_match(match, probability)
    risk = risk or assess_risk(match, probability, value, quality, classification)

    artifact = load_model_artifact()
    threshold = float(artifact["confidence"]["s_threshold"])
    probs = probability.get("probabilities") or {}
    top = max(probs.values()) if probs else 0.0

    reasons = []
    hard_pass = False
    if not quality.get("valid"):
        hard_pass = True
        reasons.append("Data Quality Gate失败: " + ",".join(quality.get("errors", [])))
    if not probability.get("valid"):
        hard_pass = True
        reasons.append("无有效市场概率")

    allow = (not hard_pass) and top >= threshold
    if allow:
        reasons.append(f"市场最高概率达到S级阈值{threshold:.2f}")
    elif not hard_pass:
        reasons.append(f"市场最高概率低于S级阈值{threshold:.2f}")

    return {
        "version": VERSION,
        "decision": "BET_CANDIDATE" if allow else "PASS",
        "allow_prediction": allow,
        "decision_score": round(top, 4),
        "hard_pass": hard_pass,
        "risk": risk.get("level", "unknown"),
        "risk_score": risk.get("score"),
        "risk_reasons": risk.get("reasons", []),
        "risk_is_advisory": True,
        "match_type": classification.get("type"),
        "reasons": reasons,
        "evidence": ["market_pmax>=S_threshold"] if allow else [],
        "source": "HH520_10027s",
        "selection_rule": "MARKET_PMAX",
        "selection_threshold": threshold,
        "forbidden_advice_fields_used": False,
        "value_layer_used_for_direction": False,
    }
