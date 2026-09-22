"""Cross-layer scenario consistency for Stable V3.3.

Raw model distributions are preserved. Only the user-facing Top2 selections
are scenario-aware, preventing mutually contradictory outputs from being
presented as equal-status primary predictions.
"""
from __future__ import annotations

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}


def _pick_two(rows, primary, alternate, key):
    primary_code = FT_MAP.get(primary)
    alternate_code = FT_MAP.get(alternate)
    first = next((r for r in rows if r.get(key) == primary_code), None)
    if first is None and rows:
        first = rows[0]

    second = None
    if alternate_code and alternate_code != primary_code:
        second = next((r for r in rows if r is not first and r.get(key) == alternate_code), None)
    if second is None:
        second = next((r for r in rows if r is not first), None)
    return [x for x in (first, second) if x is not None]


def consistency_layer(probability: dict, state: dict, htft: dict, score: dict) -> dict:
    primary = state.get("primary_direction") or probability.get("direction")
    alternate = state.get("alternate_direction")
    raw_htft = htft.get("distribution") or []
    raw_score = score.get("all_scores") or score.get("top_scores") or []

    if state.get("base_state") == "CONFIRMED":
        alt = primary
    else:
        alt = alternate

    htft_top = _pick_two(raw_htft, primary, alt, "ft")
    score_top = _pick_two(raw_score, primary, alt, "outcome")

    warnings = []
    if len(htft_top) < 2:
        warnings.append("htft_candidates_incomplete")
    if len(score_top) < 2:
        warnings.append("score_candidates_incomplete")
    if state.get("base_state") in {"BALANCED", "CONFLICT"}:
        warnings.append("multi_scenario_match")
    if state.get("tail_alert"):
        warnings.append("tail_scenario_active")

    return {
        "valid": bool(primary and htft_top and score_top),
        "primary_direction": primary,
        "alternate_direction": alt,
        "htft_top": htft_top,
        "score_top": score_top,
        "tail_alert": bool(state.get("tail_alert")),
        "warnings": warnings,
        "probability_conservation": {
            "wdl_anchor_unchanged": True,
            "htft_ft_marginal_preserved": bool(htft.get("ft_marginal_preserved", True)),
            "score_distribution_unchanged": True,
        },
    }
