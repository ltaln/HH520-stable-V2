from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.decision_filter import decision_filter
from .confidence import confidence_from_probability

def analyze_match(match: dict) -> dict:
    p = probability_layer(match)
    v = value_layer(match, p)
    d = decision_filter(match, p, v)
    c = confidence_from_probability(p, d)
    return {"probability": p, "value": v, "decision": d, "confidence": c}
