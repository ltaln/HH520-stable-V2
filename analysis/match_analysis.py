from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
from engine.decision_filter import decision_filter
from .confidence import confidence_from_probability


def analyze_match(match: dict) -> dict:
    probability = probability_layer(match)
    value = value_layer(match, probability)
    quality = data_quality_gate(match, probability)
    classification = classify_match(match, probability)
    risk = assess_risk(match, probability, value, quality, classification)
    decision = decision_filter(match, probability, value, quality, classification, risk)
    confidence = confidence_from_probability(probability, decision)
    return {
        "probability": probability,
        "value": value,
        "quality": quality,
        "classification": classification,
        "risk": risk,
        "decision": decision,
        "confidence": confidence,
    }
