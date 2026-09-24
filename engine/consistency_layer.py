"""Cross-layer consistency for HH520 Stable V3.5 Phase 2.

Score and HT/FT are independent of the FT hard direction. FT×Score remains the
formal downgrade gate validated in Phase 1. HT/FT agreement is diagnostic in
Phase 2 because live Goal Timing is a required same-day input and was not used
to tune the historical FT core.
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
    primary = (decision or {}).get("resolved_direction") or probability.get("direction")
    primary_code = FT_MAP.get(primary)
    raw_htft = htft.get("distribution") or []
    raw_score = score.get("all_scores") or score.get("top_scores") or []

    htft_top = (htft.get("top") or raw_htft[:3])[:2] if htft.get("valid") else []
    score_top = raw_score[:2]

    tier = (decision or {}).get("decision", "PASS")
    authorized = bool((decision or {}).get("ft_direction_authorized", True))
    score_primary = score_top[0].get("outcome") if score_top else None
    htft_primary_ft = htft_top[0].get("ft") if htft_top else None

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

    htft_status = "UNAVAILABLE"
    if primary_code and htft_primary_ft:
        htft_status = "AGREE" if primary_code == htft_primary_ft else "CONFLICT"

    warnings = []
    if not htft.get("valid"):
        warnings.append("htft_timing_required_or_unavailable")
    elif len(htft_top) < 2:
        warnings.append("htft_candidates_incomplete")
    if len(score_top) < 2:
        warnings.append("score_candidates_incomplete")
    if tier in {"TAIL_ALERT", "PASS"}:
        warnings.append("market_reliability_downgraded")
    if cross_status == "CONFLICT":
        warnings.append("ft_score_direction_conflict")
    if cross_status == "FT_BALANCED":
        warnings.append("ft_below_55_no_forced_direction")
    if htft_status == "CONFLICT":
        warnings.append("ft_htft_direction_conflict_diagnostic")

    return {
        "valid": bool(primary and len(score_top) >= 2),
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
        "htft_gate": {
            "status": htft_status,
            "formal_downgrade": False,
            "ft_direction": primary_code,
            "htft_top_ft": htft_primary_ft,
            "timing_used": bool(htft.get("timing_used")),
        },
        "effective_decision": effective,
        "probability_conservation": {
            "wdl_anchor_unchanged": True,
            "htft_ft_marginal_preserved": bool(htft.get("ft_marginal_preserved", False)),
            "htft_ft_core_unchanged": bool(htft.get("ft_core_unchanged", True)),
            "score_distribution_unchanged": True,
        },
    }
