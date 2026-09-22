"""Legacy pmax diagnostic retained inside HH520 Stable V3.3.

V3.3 no longer exposes S/NORMAL in the formal table. The historical pmax
threshold is preserved as internal evidence for the State Engine.
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
        "formal_output": False,
    }
