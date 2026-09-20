"""Result labels are isolated from Stable inputs."""


def create_result_label(**kwargs):
    return {
        "match_id": kwargs.get("match_id", ""),
        "date": kwargs.get("date", ""),
        "league": kwargs.get("league", ""),
        "home_team": kwargs.get("home_team", ""),
        "away_team": kwargs.get("away_team", ""),
        "half_score": kwargs.get("half_score"),
        "full_score": kwargs.get("full_score"),
        "result": kwargs.get("result"),
        "goals": kwargs.get("goals"),
        "source": kwargs.get("source", ""),
        "verified": bool(kwargs.get("verified", False)),
    }
