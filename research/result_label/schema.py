"""Result labels are isolated from Stable inputs.

The canonical Research contract uses explicit actual_* names while retaining
legacy aliases for compatibility with existing evaluators and saved reports.
"""


def create_result_label(**kwargs):
    actual_half_score = kwargs.get("actual_half_score", kwargs.get("half_score"))
    actual_score = kwargs.get("actual_score", kwargs.get("full_score"))
    actual_outcome = kwargs.get("actual_outcome", kwargs.get("result"))
    actual_total_goals = kwargs.get("actual_total_goals", kwargs.get("goals"))
    return {
        "match_id": kwargs.get("match_id", ""),
        "date": kwargs.get("date", ""),
        "league": kwargs.get("league", ""),
        "home_team": kwargs.get("home_team", ""),
        "away_team": kwargs.get("away_team", ""),
        "actual_half_score": actual_half_score,
        "actual_score": actual_score,
        "actual_outcome": actual_outcome,
        "actual_total_goals": actual_total_goals,
        # Legacy aliases retained for existing Research consumers.
        "half_score": actual_half_score,
        "full_score": actual_score,
        "result": actual_outcome,
        "goals": actual_total_goals,
        "source": kwargs.get("source", ""),
        "verified": bool(kwargs.get("verified", False)),
    }
