"""Cross-layer consistency for HH520 Stable V3.5 Phase 1.

HT/FT remains the existing V3.4 conditional model in Phase 1.
Score is independent. FT/Score agreement is used as a reliability gate:
agreement never upgrades a prediction, while conflict downgrades or passes it.
"""
from __future__ import annotations

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}


def _cross_downgrade(tier):
    return {
        "CONFIRM": "TAIL_ALERT",
        "BALANCED": "PASS",
        "TAIL_ALERT": "PASS",
        "PASS": "PASS",
    }.get(tier, "PASS")


def consistency_layer(probability: dict, state: dict, htft: dict, score: dict, decision: dict = None) -> dict:
    primary = probability.get("direction")
    primary_code = FT_MAP.get(primary)
    raw_htft = htft.get("distribution") or []
    raw_score = score.get("all_scores") or score.get("top_scores") or []

    # HT/FT remains V3.4 in Phase 1 and is still FT-conditioned internally.
    htft_top = [r for r in raw_htft if r.get("ft") == primary_code][:2]
    # Score is now global and independent of the FT selected direction.
    score_top = raw_score[:2]

    tier = (decision or {}).get("decision", "PASS")
    authorized = bool((decision or {}).get("ft_direction_authorized", True))
    score_primary = score_top[0].get("outcome") if score_top else None
    cross_status = "UNAVAILABLE"
    effective = tier

    if not authorized and primary in {"home", "away"}:
        cross_status = "FT_BALANCED"
    elif primary_code and score_primary:
        if primary_code == score_primary:
            cross_status = "AGREE"
        else:
            cross_status = "CONFLICT"
            effective = _cross_downgrade(tier)

    warnings = []
    if len(htft_top) < 2:
        warnings.append("htft_candidates_incomplete")
    if len(score_top) < 2:
        warnings.append("score_candidates_incomplete")
    if tier in {"TAIL_ALERT", "PASS"}:
        warnings.append("market_reliability_downgraded")
    if cross_status == "CONFLICT":
        warnings.append("ft_score_direction_conflict")
    if cross_status == "FT_BALANCED":
        warnings.append("ft_below_55_no_forced_direction")

    return {
        "valid": bool(primary and len(htft_top) >= 2 and len(score_top) >= 2),
        "primary_direction": primary,
        "alternate_direction": None,
        "htft_top": htft_top,
        "score_top": score_top,
        "tail_alert": effective in {"TAIL_ALERT", "PASS"},
        "warnings": warnings,
        "cross_gate": {
            "status": cross_status,
            "base_decision": tier,
            "effective_decision": effective,
            "ft_direction": primary_code,
            "score_direction": score_primary,
            "agreement_can_upgrade": False,
            "conflict_downgrades": True,
        },
        "effective_decision": effective,
        "probability_conservation": {
            "wdl_anchor_unchanged": True,
            "htft_ft_marginal_preserved": bool(htft.get("ft_marginal_preserved", True)),
            "score_distribution_unchanged": True,
        },
    }
