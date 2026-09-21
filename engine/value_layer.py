"""Value layer independent from HH520 betting/advice columns."""

_OUTCOMES = ("home", "draw", "away")


def value_layer(match: dict, probability: dict) -> dict:
    page_value = match.get("value") or {}
    probs = probability.get("probabilities") or {}
    baseline = probability.get("baseline") or {}
    direction = probability.get("direction")

    edges = {}
    for key in _OUTCOMES:
        if key in probs and key in baseline:
            edges[key] = probs[key] - baseline[key]

    directional_edge = edges.get(direction) if direction else None

    return {
        "ev": page_value.get("ev"),
        "kelly": page_value.get("kelly"),
        "market_baseline": baseline,
        "probability_edges": edges,
        "directional_edge": directional_edge,
        "used_for_direction": False,
        "forbidden_advice_fields_used": False,
    }
