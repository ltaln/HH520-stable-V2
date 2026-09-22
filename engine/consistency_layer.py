"""Cross-layer consistency for HH520 Stable V3.4.

User-facing HTFT and score candidates must inherit the selected FT direction.
Risk can downgrade trust, but cannot create contradictory downstream outcomes.
"""
from __future__ import annotations

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}


def consistency_layer(probability: dict, state: dict, htft: dict, score: dict, decision: dict = None) -> dict:
    primary = probability.get("direction")
    primary_code = FT_MAP.get(primary)
    raw_htft = htft.get("distribution") or []
    raw_score = score.get("all_scores") or score.get("top_scores") or []

    htft_top = [r for r in raw_htft if r.get("ft") == primary_code][:2]
    score_top = [r for r in raw_score if r.get("outcome") == primary_code][:2]

    warnings = []
    if len(htft_top) < 2:
        warnings.append("htft_candidates_incomplete")
    if len(score_top) < 2:
        warnings.append("score_candidates_incomplete")
    tier = (decision or {}).get("decision")
    if tier in {"TAIL_ALERT", "PASS"}:
        warnings.append("market_reliability_downgraded")

    return {
        "valid": bool(primary and len(htft_top) >= 2 and len(score_top) >= 2),
        "primary_direction": primary,
        "alternate_direction": None,
        "htft_top": htft_top,
        "score_top": score_top,
        "tail_alert": tier in {"TAIL_ALERT", "PASS"},
        "warnings": warnings,
        "probability_conservation": {
            "wdl_anchor_unchanged": True,
            "htft_ft_marginal_preserved": bool(htft.get("ft_marginal_preserved", True)),
            "score_distribution_unchanged": True,
        },
    }
