"""HT/FT-conditioned score template layer for HH520 Stable V3.4."""
from __future__ import annotations

TEMPLATES = {
    ("HOME", "HOME"): [("2:1", .30), ("2:0", .25), ("3:0", .12), ("3:1", .12), ("1:0", .08), ("3:2", .08), ("4:0", .05)],
    ("DRAW", "HOME"): [("2:1", .40), ("1:0", .32), ("3:2", .12), ("3:1", .08), ("3:0", .04), ("4:1", .04)],
    ("AWAY", "AWAY"): [("1:3", .28), ("0:2", .18), ("1:2", .16), ("2:3", .12), ("2:4", .08), ("0:1", .08), ("1:4", .05), ("0:3", .05)],
    ("DRAW", "AWAY"): [("0:1", .48), ("1:2", .20), ("0:2", .14), ("1:3", .06), ("0:3", .06), ("1:4", .03), ("0:4", .03)],
    ("DRAW", "DRAW"): [("0:0", .476), ("1:1", .476), ("2:2", .048)],
    ("HOME", "DRAW"): [("1:1", .636), ("2:2", .364)],
    ("AWAY", "DRAW"): [("1:1", .60), ("2:2", .30), ("3:3", .10)],
    ("AWAY", "HOME"): [("2:1", .60), ("1:0", .25), ("3:2", .15)],
    ("HOME", "AWAY"): [("1:2", .60), ("0:1", .25), ("2:3", .15)],
}
OUTCOME_ZH = {"HOME": "主胜", "DRAW": "平", "AWAY": "客胜"}


def _parse(score):
    h, a = score.split(":")
    return int(h), int(a)


def _outcome(h, a):
    return "HOME" if h > a else "AWAY" if h < a else "DRAW"


def score_layer(match: dict, probability: dict, htft: dict = None) -> dict:
    if not probability.get("valid"):
        return {"valid": False, "model": "HTFT_SCORE_TEMPLATE_V1", "top_scores": [], "all_scores": []}
    if not htft or not htft.get("valid"):
        return {"valid": False, "model": "HTFT_SCORE_TEMPLATE_V1", "top_scores": [], "all_scores": []}

    score_mass = {}
    totals = {}
    for joint in htft.get("distribution", []):
        template = TEMPLATES.get((joint["ht"], joint["ft"]), [])
        for score, cond in template:
            mass = float(joint["probability"]) * float(cond)
            score_mass[score] = score_mass.get(score, 0.0) + mass
            h, a = _parse(score)
            totals[h + a] = totals.get(h + a, 0.0) + mass

    total_mass = sum(score_mass.values()) or 1.0
    rows = []
    for score, mass in score_mass.items():
        h, a = _parse(score)
        outcome = _outcome(h, a)
        rows.append({
            "score": score, "home": h, "away": a, "outcome": outcome,
            "direction": OUTCOME_ZH[outcome],
            "probability": mass / total_mass,
        })
    rows.sort(key=lambda x: x["probability"], reverse=True)

    total_rows = [{"goals": g, "probability": m / total_mass} for g, m in totals.items()]
    total_rows.sort(key=lambda x: x["probability"], reverse=True)
    primary = probability.get("direction")
    code = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}.get(primary)
    primary_rows = [r for r in rows if r["outcome"] == code]
    primary_rows.sort(key=lambda x: x["probability"], reverse=True)

    goal_pick = total_rows[0]["goals"] if total_rows else None
    high = [r for r in rows if r["home"] + r["away"] >= 5 or max(r["home"], r["away"]) >= 3]
    return {
        "valid": True,
        "model": "HTFT_SCORE_TEMPLATE_V1",
        "top_scores": primary_rows[:5],
        "all_scores": rows,
        "tail_scores": high[:5],
        "high_score_mass": sum(r["probability"] for r in high),
        "top_totals": total_rows[:5],
        "total_goals_pick": None if goal_pick is None else f"{goal_pick}球",
        "total_goals_pick_probability": total_rows[0]["probability"] if total_rows else None,
        "lambda_home": None,
        "lambda_away": None,
        "feature_snapshot": {"source": "htft_template"},
        "high_variance_challenger_promoted": False,
    }
