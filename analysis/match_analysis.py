from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
from engine.decision_filter import decision_filter
from engine.research_confidence_layer import research_confidence_layer
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer
from .confidence import confidence_from_probability


def analyze_match(match: dict) -> dict:
    probability = probability_layer(match)
    value = value_layer(match, probability)
    quality = data_quality_gate(match, probability)
    classification = classify_match(match, probability)
    risk = assess_risk(match, probability, value, quality, classification)
    research_confidence = research_confidence_layer(probability)
    decision = decision_filter(match, probability, value, quality, classification, risk)
    confidence = confidence_from_probability(probability, decision)
    htft = htft_layer(probability)
    score = score_layer(match, probability)
    return {
        "probability": probability,
        "value": value,
        "quality": quality,
        "classification": classification,
        "risk": risk,
        "research_confidence": research_confidence,
        "decision": decision,
        "confidence": confidence,
        "htft": htft,
        "score": score,
    }
