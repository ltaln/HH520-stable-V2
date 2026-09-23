"""Legacy diagnostic state engine retained for Stable V3.4 audit compatibility.

Formal V3.4 prediction decisions are made by Market Failure Detector V1.
This module may summarize older 10027S structural signals for diagnostics only;
its output cannot override FT direction or the V3.4 risk tier.
"""
from __future__ import annotations

from .model_artifact import load_model_artifact

OUTCOMES = ("home", "draw", "away")


def _direction(probs):
    if not probs:
        return None
    return max(OUTCOMES, key=lambda k: float(probs.get(k, 0.0)))


def _selected_odds(match, direction):
    key = {"home":"home_odds","draw":"draw_odds","away":"away_odds"}.get(direction)
    return (match.get("market") or {}).get(key) if key else None


def build_state(match: dict, probability: dict) -> dict:
    artifact = load_model_artifact()
    cfg = artifact.get("state_engine") or {}
    probs = probability.get("probabilities") or {}
    page = probability.get("page_probability") or {}

    if not probability.get("valid") or len(probs) != 3:
        return {
            "valid": False, "diagnostic_only": True, "state": "INVALID",
            "base_state": "INVALID", "primary_direction": None,
            "alternate_direction": None, "tail_alert": False,
            "draw_candidate": False, "confirmations": [],
            "conflicts": ["invalid_probability"],
        }

    ordered = sorted(OUTCOMES, key=lambda k: float(probs[k]), reverse=True)
    primary, alternate = ordered[0], ordered[1]
    pmax = float(probs[primary])
    margin = pmax - float(probs[alternate])

    page_dir = _direction(page)
    page_pmax = max((float(page.get(k,0.0)) for k in OUTCOMES), default=0.0)
    page_aligned = bool(page_dir and page_dir == primary)

    # Keep legacy labels for diagnostics only. Missing legacy thresholds are
    # tolerated because V3.4 does not use this state for formal decisions.
    balanced_margin = float(cfg.get("balanced_margin", 0.08))
    weak_market_pmax = float(cfg.get("weak_market_pmax", 0.50))
    draw_margin = float(cfg.get("draw_near_top_margin", 0.08))
    balanced = margin < balanced_margin or pmax < weak_market_pmax
    draw_candidate = float(probs.get("draw",0.0)) >= pmax - draw_margin
    base_state = "BALANCED" if balanced else "STANDARD"

    return {
        "valid": True,
        "diagnostic_only": True,
        "state": base_state,
        "base_state": base_state,
        "primary_direction": primary,
        "alternate_direction": alternate,
        "market_pmax": pmax,
        "market_margin": margin,
        "page_direction": page_dir,
        "page_pmax": page_pmax if page else None,
        "page_aligned": page_aligned if page else None,
        "draw_candidate": draw_candidate,
        "tail_alert": False,
        "confirmations": [],
        "conflicts": [],
        "changes_prediction": False,
    }
