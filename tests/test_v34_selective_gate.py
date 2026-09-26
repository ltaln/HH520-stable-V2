from engine.decision_filter import decision_filter
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer


def _base_match():
    return {
        "match_id": "t1",
        "home_team": "A",
        "away_team": "B",
        "league": "TEST",
        "market": {"home_odds": 2.40, "draw_odds": 3.10, "away_odds": 2.55},
        "possession": {"home": 51, "away": 49},
        "research_factors": {
            "home_attack": 1, "away_attack": 1,
            "home_defense": 1, "away_defense": 1,
            "home_h2h": 1, "away_h2h": 1,
            "home_form": 1, "away_form": 1,
        },
    }


def test_close_probability_margin_is_not_confirm():
    m = _base_match()
    p = probability_layer(m)
    v = value_layer(m, p)
    d = decision_filter(m, p, v)
    assert d["probability_margin"] is not None
    if d["probability_margin"] < 0.04:
        assert d["decision"] in {"TAIL_ALERT", "PASS"}
    elif d["probability_margin"] < 0.08:
        assert d["decision"] in {"BALANCED", "TAIL_ALERT", "PASS"}


def test_missing_structural_data_is_advisory_not_hard_pass():
    m = _base_match()
    m["possession"] = {}
    m["research_factors"] = {}
    p = probability_layer(m)
    v = value_layer(m, p)
    d = decision_filter(m, p, v)
    assert d["allow_prediction"] is True
    assert d["decision"] != "PASS" or "optional_structural_data_missing_advisory" in d["reasons"]
    assert d["draw_rule_promoted"] is False
    assert "missing_features" in d["draw_rule_metrics"] or d["draw_rule_metrics"].get("score") is None
    assert "optional_structural_data_missing_advisory" in d["reasons"]


def test_draw_is_first_class_direction():
    m = _base_match()
    m["market"] = {"home_odds": 3.2, "draw_odds": 2.1, "away_odds": 3.2}
    p = probability_layer(m)
    assert p["direction"] == "draw"
    v = value_layer(m, p)
    d = decision_filter(m, p, v)
    assert d["primary_direction"] == "draw"
    assert d["failure_detector"]["favorite"] == "draw"
