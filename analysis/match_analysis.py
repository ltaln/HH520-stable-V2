from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
from engine.decision_filter import decision_filter
from engine.research_confidence_layer import research_confidence_layer
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer
from engine.state_engine import build_state
from engine.consistency_layer import consistency_layer
from engine.calibration_layer import calibration_layer
from engine.full_data_layer import enhance_probability, data_mode
from .confidence import confidence_from_probability


def analyze_match(match: dict) -> dict:
    base_probability = probability_layer(match)
    probability = enhance_probability(match, base_probability)
    match["_data_mode"] = data_mode(match)
    value = value_layer(match, probability)
    quality = data_quality_gate(match, probability)
    classification = classify_match(match, probability)
    risk = assess_risk(match, probability, value, quality, classification)
    research_confidence = research_confidence_layer(probability)
    state = build_state(match, probability)  # legacy diagnostic only
    decision = decision_filter(match, probability, value, quality, classification, risk, state)
    confidence = confidence_from_probability(probability, decision)
    htft = htft_layer(probability, match, decision)
    score = score_layer(match, probability, htft)
    consistency = consistency_layer(probability, state, htft, score, decision)
    calibration = calibration_layer(probability, state)
    return {
        "probability": probability,
        "base_probability": base_probability,
        "data_mode": match.get("_data_mode"),
        "value": value,
        "quality": quality,
        "classification": classification,
        "risk": risk,
        "research_confidence": research_confidence,
        "state": state,
        "decision": decision,
        "confidence": confidence,
        "htft": htft,
        "score": score,
        "consistency": consistency,
        "calibration": calibration,
    }
