"""Research-derived confidence layer for HH520 Stable V3.2.

This layer never changes WDL direction. It only separates the historically
validated high-confidence market subset from ordinary predictions.
"""
from __future__ import annotations
from .model_artifact import load_model_artifact


def research_confidence_layer(probability: dict) -> dict:
    probs = probability.get("probabilities") or {}
    artifact = load_model_artifact()
    cfg = artifact["confidence"]
    if not probability.get("valid") or len(probs) != 3:
        return {
            "valid": False,
            "tier": "PASS",
            "pmax": 0.0,
            "threshold": float(cfg["s_threshold"]),
            "high_confidence": False,
            "model": cfg["model"],
        }

    pmax = max(float(x) for x in probs.values())
    threshold = float(cfg["s_threshold"])
    high = pmax >= threshold
    return {
        "valid": True,
        "tier": "S" if high else "NORMAL",
        "pmax": pmax,
        "threshold": threshold,
        "high_confidence": high,
        "model": cfg["model"],
        "factor_vote_required": bool(cfg.get("factor_vote_required", False)),
        "evidence": cfg.get("evidence", {}),
        "direction_override": False,
    }
