"""HH520 Stable V3.3 state engine.

Market remains the WDL anchor. Independent 10027s page probability and
historically observed structural signals are used to classify reliability,
not to blindly flip the market direction.
"""
from __future__ import annotations

from .model_artifact import load_model_artifact

OUTCOMES = ("home", "draw", "away")


def _direction(probs):
    if not probs:
        return None
    return max(OUTCOMES, key=lambda k: float(probs.get(k, 0.0)))


def _selected_odds(match, direction):
    key = {"home": "home_odds", "draw": "draw_odds", "away": "away_odds"}.get(direction)
    return (match.get("market") or {}).get(key) if key else None


def build_state(match: dict, probability: dict) -> dict:
    artifact = load_model_artifact()
    cfg = artifact["state_engine"]
    probs = probability.get("probabilities") or {}
    page = probability.get("page_probability") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {
            "valid": False, "state": "INVALID", "base_state": "INVALID",
            "primary_direction": None, "alternate_direction": None,
            "tail_alert": False, "draw_candidate": False,
            "confirmations": [], "conflicts": ["invalid_probability"],
        }

    ordered = sorted(OUTCOMES, key=lambda k: float(probs[k]), reverse=True)
    primary = ordered[0]
    alternate = ordered[1]
    pmax = float(probs[primary])
    margin = pmax - float(probs[alternate])

    page_dir = _direction(page)
    page_pmax = max((float(page.get(k, 0.0)) for k in OUTCOMES), default=0.0)
    page_aligned = bool(page_dir and page_dir == primary)

    factors = match.get("research_factors") or {}
    structure = str(factors.get("structure") or "").strip()
    risk = str(factors.get("risk") or "").strip()
    pattern = str(factors.get("pattern") or "").strip()
    odds = _selected_odds(match, primary)
    try:
        odds = float(odds)
    except (TypeError, ValueError):
        odds = None

    confirmations = []
    conflicts = []

    if pmax >= float(cfg["market_strong_threshold"]):
        confirmations.append("market_pmax_strong")
    if page_pmax >= float(cfg["page_confirm_threshold"]) and page_aligned:
        confirmations.append("page_probability_confirmed")
    if odds is not None and odds < float(cfg["strong_odds_threshold"]):
        confirmations.append("strong_odds_zone")
    if "强优" in structure:
        confirmations.append("structure_strong")
    if "风控赔率" in pattern:
        confirmations.append("pattern_risk_control")

    if page and page_pmax < float(cfg["page_conflict_threshold"]):
        conflicts.append("page_probability_low_concentration")
    if page_dir and page_dir != primary and page_pmax >= float(cfg["page_conflict_threshold"]):
        conflicts.append("page_direction_disagrees")
    if risk in {"中高", "高", "很高"}:
        conflicts.append("page_risk_elevated")
    if "极端" in pattern:
        conflicts.append("extreme_pattern")
    if odds is not None and float(cfg["risky_odds_low"]) <= odds < float(cfg["risky_odds_high"]):
        conflicts.append("historically_weak_odds_zone")

    balanced = (
        margin < float(cfg["balanced_margin"])
        or pmax < float(cfg["weak_market_pmax"])
        or structure == "均衡"
    )
    draw_candidate = (
        float(probs.get("draw", 0.0)) >= pmax - float(cfg["draw_near_top_margin"])
        or (
            page
            and float(page.get("draw", 0.0))
            >= page_pmax - float(cfg["draw_near_top_margin"])
        )
    )

    if len(conflicts) >= int(cfg["conflict_evidence_required"]):
        base_state = "CONFLICT"
    elif balanced:
        base_state = "BALANCED"
    elif len(confirmations) >= int(cfg["confirmation_evidence_required"]):
        base_state = "CONFIRMED"
    else:
        base_state = "STANDARD"

    tail_alert = base_state in {"BALANCED", "CONFLICT"} and (
        "historically_weak_odds_zone" in conflicts
        or "page_direction_disagrees" in conflicts
        or "extreme_pattern" in conflicts
        or risk in {"中高", "高", "很高"}
    )

    if page_dir and page_dir != primary and page_pmax >= float(cfg["page_conflict_threshold"]):
        alternate = page_dir
    elif draw_candidate and primary != "draw":
        alternate = "draw"

    return {
        "valid": True,
        "state": "TAIL_ALERT" if tail_alert else base_state,
        "base_state": base_state,
        "primary_direction": primary,
        "alternate_direction": alternate,
        "market_pmax": pmax,
        "market_margin": margin,
        "page_direction": page_dir,
        "page_pmax": page_pmax if page else None,
        "page_aligned": page_aligned if page else None,
        "draw_candidate": draw_candidate,
        "tail_alert": tail_alert,
        "confirmations": confirmations,
        "conflicts": conflicts,
    }
