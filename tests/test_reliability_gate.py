from engine.reliability_gate import reliability_gate


def _base_probability():
    return {
        "valid": True,
        "probabilities": {"home": 0.68, "draw": 0.20, "away": 0.12},
        "pmax": 0.68,
        "direction": "home",
        "data_mode": "FULL_DATA",
    }


def _quality(warnings=None):
    return {"valid": True, "warnings": warnings or [], "errors": []}


def test_reliability_gate_rewards_agreement_and_full_data():
    result = reliability_gate(
        _base_probability(),
        {"decision": "CONFIRM", "risk_score": 5},
        {
            "effective_decision": "CONFIRM",
            "cross_gate": {"status": "AGREE"},
            "htft_gate": {"status": "AGREE"},
        },
        _quality(),
        {"score": 5},
        {"mode": "FULL_DATA"},
    )
    assert result["valid"] is True
    assert result["trust_grade"] in {"A", "B"}
    assert result["trust_score"] >= 60
    assert result["upset_risk"] < 55
    assert result["changes_prediction"] is False


def test_reliability_gate_downgrades_cross_layer_conflict():
    result = reliability_gate(
        _base_probability(),
        {"decision": "TAIL_ALERT", "risk_score": 65},
        {
            "effective_decision": "TAIL_ALERT",
            "cross_gate": {"status": "CONFLICT"},
            "htft_gate": {"status": "CONFLICT"},
        },
        _quality(["possession_missing", "team_modules_missing_or_zero"]),
        {"score": 65},
        {"mode": "10027_ONLY"},
    )
    assert result["trust_grade"] in {"C", "D"}
    assert result["conflict_score"] >= 50
    assert result["upset_risk"] >= 55


def test_reliability_gate_invalid_probability_is_pass():
    result = reliability_gate(
        {"valid": False, "probabilities": {}},
        {},
        {},
        _quality(),
        {},
        {"mode": "10027_ONLY"},
    )
    assert result["trust_grade"] == "D"
    assert result["recommended_action"] == "PASS"
