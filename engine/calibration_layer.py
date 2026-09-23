"""Diagnostic-only calibration metadata for Stable V3.4.

This layer never changes FT probability, Failure Detector tier, HT/FT, or score.
It remains only for audit/backward-compatible diagnostics.
"""
from __future__ import annotations

from .model_artifact import load_model_artifact


def calibration_layer(probability: dict, state: dict) -> dict:
    artifact = load_model_artifact()
    cfg = artifact.get("calibration") or {}
    if not probability.get("valid"):
        return {"valid": False, "diagnostic_only": True}

    band = None
    empirical = None
    page_pmax = state.get("page_pmax")
    low = cfg.get("page_low_threshold")
    high = cfg.get("page_high_threshold")
    reliability = cfg.get("empirical_reliability") or {}

    if low is not None and page_pmax is not None and page_pmax < low:
        band = "PAGE_LT_40"
        empirical = reliability.get("page_lt_40")
    elif high is not None and page_pmax is not None and page_pmax >= high:
        band = "PAGE_GE_60"
        empirical = reliability.get("page_ge_60")
    elif state.get("base_state") == "BALANCED":
        band = "BALANCED"
        empirical = reliability.get("balanced")

    return {
        "valid": True,
        "diagnostic_only": True,
        "model_version": "HH520 Stable V3.4",
        "market_probability": state.get("market_pmax"),
        "reliability_band": band,
        "historical_direction_accuracy": empirical,
        "development_period": cfg.get("development_period"),
        "changes_prediction_probability": False,
        "changes_failure_tier": False,
    }
