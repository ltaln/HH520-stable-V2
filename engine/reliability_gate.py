"""HH520 Reliability Gate V1.

This layer answers a different question from the predictor: "how much should we
trust this prediction?"  It is intentionally conservative and advisory.  It
never changes FT probabilities, score candidates, HT/FT candidates, or the
Stable decision itself.

The gate combines:
- probability strength and separation
- FT x score and FT x HTFT agreement
- existing market-failure/risk signals
- data-quality warnings
- enrichment completeness

The output score is a reliability index (0-100), NOT a win probability.
"""

from __future__ import annotations

VERSION = "HH520 Reliability Gate V1"

_GRADE_LABEL = {
    "A": "SAFE",
    "B": "USABLE",
    "C": "UPSET_RISK",
    "D": "PASS",
}


def _clip(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(value)))


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def reliability_gate(
    probability: dict,
    decision: dict,
    consistency: dict,
    quality: dict,
    risk: dict,
    data_mode: dict | None = None,
) -> dict:
    """Return prediction trust diagnostics without changing model outputs."""
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {
            "version": VERSION,
            "valid": False,
            "trust_score": 0.0,
            "trust_grade": "D",
            "trust_label": _GRADE_LABEL["D"],
            "conflict_score": 100.0,
            "upset_risk": 100.0,
            "probability_strength": 0.0,
            "agreement_score": 0.0,
            "recommended_action": "PASS",
            "reasons": ["invalid_probability"],
            "advisory_only": True,
        }

    ordered = sorted((float(v), k) for k, v in probs.items())
    pmax = max(v for v, _ in ordered)
    values = sorted((float(v) for v in probs.values()), reverse=True)
    margin = values[0] - values[1]

    # Probability strength: strong only when both absolute probability and
    # separation are healthy.  This prevents a nominally-high top probability
    # with a close challenger from being treated as safe.
    p_strength = _clip(((pmax - 0.34) / 0.36) * 70.0 + (margin / 0.25) * 30.0)

    cross = (consistency.get("cross_gate") or {}).get("status", "UNAVAILABLE")
    htft = (consistency.get("htft_gate") or {}).get("status", "UNAVAILABLE")

    agreement = 50.0
    conflict = 0.0
    reasons = []

    if cross == "AGREE":
        agreement += 25
    elif cross == "CONFLICT":
        agreement -= 35
        conflict += 45
        reasons.append("ft_score_conflict")
    elif cross == "FT_BALANCED":
        agreement -= 10
        conflict += 15
        reasons.append("ft_balanced")

    if htft == "AGREE":
        agreement += 15
    elif htft == "CONFLICT":
        agreement -= 20
        conflict += 30
        reasons.append("ft_htft_conflict")

    tier = consistency.get("effective_decision") or decision.get("decision") or "PASS"
    tier_adj = {"CONFIRM": 12, "BALANCED": 0, "TAIL_ALERT": -18, "PASS": -30}.get(tier, -20)
    if tier in {"TAIL_ALERT", "PASS"}:
        conflict += 15
        reasons.append("stable_tail_or_pass")

    risk_score = _num(decision.get("risk_score"))
    if risk_score is None:
        risk_score = _num((risk or {}).get("score"), 0.0)
    risk_score = _clip(risk_score or 0.0)

    warnings = list((quality or {}).get("warnings") or [])
    warning_penalty = min(18.0, 4.5 * len(warnings))
    if warnings:
        reasons.append("data_quality_warnings")

    dm = data_mode or {}
    mode = dm.get("mode") or probability.get("data_mode") or "10027_ONLY"
    enrichment_adj = 7.0 if mode == "FULL_DATA" else 0.0
    if mode != "FULL_DATA":
        reasons.append("no_full_data_enrichment")

    agreement = _clip(agreement)
    conflict = _clip(conflict + 0.25 * risk_score + warning_penalty)

    # Reliability index.  Existing Stable logic remains dominant; external
    # enrichment only provides a small positive adjustment.
    trust = (
        0.44 * p_strength
        + 0.34 * agreement
        + 0.22 * (100.0 - risk_score)
        + tier_adj
        + enrichment_adj
        - warning_penalty
        - 0.15 * conflict
    )
    trust = _clip(trust)

    # Upset risk focuses on "the model may be directionally wrong", therefore
    # it weights conflict and weak separation more heavily than generic risk.
    upset = _clip(
        0.42 * (100.0 - p_strength)
        + 0.38 * conflict
        + 0.20 * risk_score
        + (8.0 if tier == "TAIL_ALERT" else 0.0)
        + (12.0 if tier == "PASS" else 0.0)
    )

    if trust >= 76 and upset < 35 and cross != "CONFLICT":
        grade = "A"
    elif trust >= 60 and upset < 55:
        grade = "B"
    elif trust >= 42:
        grade = "C"
    else:
        grade = "D"

    recommended = {
        "A": "SAFE",
        "B": "USE_WITH_COVER",
        "C": "UPSET_OR_DRAW_COVER",
        "D": "PASS",
    }[grade]

    return {
        "version": VERSION,
        "valid": True,
        "trust_score": round(trust, 1),
        "trust_grade": grade,
        "trust_label": _GRADE_LABEL[grade],
        "conflict_score": round(conflict, 1),
        "upset_risk": round(upset, 1),
        "probability_strength": round(p_strength, 1),
        "agreement_score": round(agreement, 1),
        "recommended_action": recommended,
        "effective_decision": tier,
        "cross_status": cross,
        "htft_status": htft,
        "data_mode": mode,
        "reasons": reasons,
        "advisory_only": True,
        "changes_prediction": False,
    }
