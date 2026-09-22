"""Calibration diagnostics for Stable V3.3.

The historical reliability bands are diagnostic only; they never replace the
market probability. This prevents double-counting development data.
"""
from __future__ import annotations

from .model_artifact import load_model_artifact


def calibration_layer(probability: dict, state: dict) -> dict:
    artifact = load_model_artifact()
    cfg = artifact["calibration"]
    if not probability.get("valid"):
        return {"valid": False, "diagnostic_only": True}

    band = None
    empirical = None
    page_pmax = state.get("page_pmax")
    if page_pmax is not None and page_pmax < cfg["page_low_threshold"]:
        band = "PAGE_LT_40"
        empirical = cfg["empirical_reliability"]["page_lt_40"]
    elif page_pmax is not None and page_pmax >= cfg["page_high_threshold"]:
        band = "PAGE_GE_60"
        empirical = cfg["empirical_reliability"]["page_ge_60"]
    elif state.get("base_state") == "BALANCED":
        band = "BALANCED"
        empirical = cfg["empirical_reliability"]["balanced"]

    return {
        "valid": True,
        "diagnostic_only": True,
        "market_probability": state.get("market_pmax"),
        "reliability_band": band,
        "historical_direction_accuracy": empirical,
        "development_period": cfg["development_period"],
        "changes_prediction_probability": False,
    }
