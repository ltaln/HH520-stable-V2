"""Extract isolated post-match labels from raw HH520 records before sanitizing.

This module is Research-only. Labels must never be fed back into Stable inputs.
"""
import re
from research.result_label.schema import create_result_label

_SCORE_RE = re.compile(r"^\s*(\d+)\s*[-:：]\s*(\d+)\s*$")


def _score(text):
    if text is None:
        return None
    m = _SCORE_RE.match(str(text))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _outcome(home, away):
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def collect_result_labels(records):
    """Build verified result labels from the raw page result field.

    The raw records are not modified. Only records with a parseable final score
    become labels. Half-time score remains None unless an independent field is
    available in the future.
    """
    labels = []
    for record in records:
        score = _score(record.get("result"))
        if score is None:
            continue
        home_goals, away_goals = score
        labels.append(create_result_label(
            match_id=str(record.get("match_id") or ""),
            date=str(record.get("date") or ""),
            league=str(record.get("league") or ""),
            home_team=str(record.get("home_team") or record.get("home") or ""),
            away_team=str(record.get("away_team") or record.get("away") or ""),
            half_score=None,
            full_score=f"{home_goals}-{away_goals}",
            result=_outcome(home_goals, away_goals),
            goals=home_goals + away_goals,
            source="HH520_10023s_RESULT_LABEL",
            verified=True,
        ))
    return labels
