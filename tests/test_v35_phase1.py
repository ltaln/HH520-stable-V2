from engine.decision_filter import decision_filter
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.score_layer import score_layer
from engine.consistency_layer import consistency_layer


def _match(home=1.70, draw=3.50, away=4.80):
    return {
        "match_id": "v35t",
        "home_team": "A",
        "away_team": "B",
        "league": "TEST",
        "market": {"home_odds": home, "draw_odds": draw, "away_odds": away},
        "possession": {"home": 52, "away": 48},
        "research_factors": {
            "home_attack": 1, "away_attack": 1,
            "home_defense": 1, "away_defense": 1,
            "home_h2h": 1, "away_h2h": 1,
            "home_form": 1, "away_form": 1,
        },
    }


def _decision(m):
    p = probability_layer(m)
    v = value_layer(m, p)
    return p, decision_filter(m, p, v)


def test_ft_below_55_is_not_authorized_side():
    p, d = _decision(_match(2.25, 3.20, 3.05))
    if p["direction"] in {"home", "away"} and p["pmax"] < 0.55:
        assert d["ft_grade"] == "BALANCED"
        assert d["ft_direction_authorized"] is False
        assert d["decision"] in {"BALANCED", "TAIL_ALERT", "PASS"}


def test_ft_threshold_grades():
    assert decision_filter({}, {"valid": False}, {}, quality={"valid": False, "errors": []},
                           classification={}, risk={}, state={})["decision"] == "PASS"
    from engine.decision_filter import _ft_grade
    assert _ft_grade("home", 0.5499) == "BALANCED"
    assert _ft_grade("home", 0.55) == "STANDARD"
    assert _ft_grade("away", 0.60) == "STRONG"
    assert _ft_grade("home", 0.65) == "HIGH"


def test_score_is_independent_of_selected_ft_direction():
    m = _match()
    p = probability_layer(m)
    score = score_layer(m, p)
    assert score["valid"]
    assert score["model"] == "HDA_POISSON_V1"
    assert len(score["top_scores"]) >= 2
    assert score["feature_snapshot"]["ft_direction_lock"] is False
    # Global score ranking is not filtered to the FT primary outcome.
    assert score["top_scores"] == score["all_scores"][:5]


def test_cross_gate_conflict_downgrades():
    p = {"direction": "home"}
    htft = {
        "distribution": [
            {"ft": "HOME", "selection": "主/主"},
            {"ft": "HOME", "selection": "平/主"},
        ],
        "ft_marginal_preserved": True,
    }
    score = {
        "all_scores": [
            {"score": "1:1", "outcome": "DRAW", "probability": 0.2},
            {"score": "1:0", "outcome": "HOME", "probability": 0.15},
        ]
    }
    decision = {"decision": "CONFIRM", "ft_direction_authorized": True}
    c = consistency_layer(p, {}, htft, score, decision)
    assert c["cross_gate"]["status"] == "CONFLICT"
    assert c["effective_decision"] == "TAIL_ALERT"
