"""HH520 Stable V3.4 value diagnostics.

Page/fusion probability and EV/Kelly fields may be inspected for value/audit
purposes only. They never confirm, reject, or override the formal FT direction
or Market Failure Detector tier.
"""

_OUTCOMES = ("home","draw","away")


def value_layer(match: dict, probability: dict) -> dict:
    page_value = match.get("value") or {}
    page_probs = probability.get("page_probability") or {}
    baseline = probability.get("baseline") or {}
    direction = probability.get("direction")

    edges = {}
    for key in _OUTCOMES:
        if key in page_probs and key in baseline:
            edges[key] = float(page_probs[key]) - float(baseline[key])

    directional_edge = edges.get(direction) if direction else None
    independent_direction = (
        max(_OUTCOMES, key=lambda k: float(page_probs.get(k,0.0)))
        if len(page_probs) == 3 else None
    )

    return {
        "ev": page_value.get("ev"),
        "kelly": page_value.get("kelly"),
        "market_baseline": baseline,
        "independent_probability": page_probs,
        "independent_direction": independent_direction,
        "probability_edges": edges,
        "directional_edge": directional_edge,
        "used_for_direction": False,
        "used_for_confirmation": False,
        "diagnostic_only": True,
        "forbidden_advice_fields_used": False,
    }
