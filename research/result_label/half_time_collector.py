"""Research-only half time result label collector.

This layer is isolated from Stable. It accepts verified half-time scores from
external research sources and converts them into HT/FT labels.
"""

from research.result_label.schema import create_result_label


def build_half_time_label(record, source="external_half_time_source"):
    """Create a half-time label from a verified score record.

    Expected input fields:
    half_score, full_score, match_id, date, teams.
    """
    return create_result_label(
        match_id=record.get("match_id", ""),
        date=record.get("date", ""),
        league=record.get("league", ""),
        home_team=record.get("home_team", ""),
        away_team=record.get("away_team", ""),
        half_score=record.get("half_score"),
        full_score=record.get("full_score"),
        result=record.get("result"),
        goals=record.get("goals"),
        source=source,
        verified=True,
    )


def score_to_result(score):
    if not score or "-" not in str(score):
        return None
    h, a = [int(x) for x in str(score).split("-")[:2]]
    if h > a:
        return "HOME"
    if h < a:
        return "AWAY"
    return "DRAW"


def build_htft(half_score, full_score):
    half = score_to_result(half_score)
    full = score_to_result(full_score)
    if not half or not full:
        return None
    return f"{half}_{full}"
