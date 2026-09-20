"""Extract isolated post-match labels from raw HH520 records before sanitizing.

This module is Research-only. Labels must never be fed back into Stable inputs.
"""
import re

from research.result_label.schema import create_result_label

# Accept common HH520 historical score renderings such as:
# "2-1", "2:1", "2：1", "2-1 (1-0)" and text surrounding a score.
_SCORE_RE = re.compile(r"(\d+)\s*[-:：]\s*(\d+)")


def _score(text):
    """Return the first parseable score pair from a historical result field."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw or raw in {"-", "--", "—"}:
        return None
    match = _SCORE_RE.search(raw)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _outcome(home, away):
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def collect_result_labels(records):
    """Build verified result labels from raw HH520 historical result fields.

    Raw records are never mutated. Result labels are extracted before the
    Historical Sanitizer removes post-match fields, then kept on the
    Research-only side of the pipeline.

    Only an independently parseable full-time score from result creates a
    label. Prediction score fields are deliberately ignored so they can never
    be mistaken for actual results.
    """
    labels = []

    for record in records:
        if not isinstance(record, dict):
            continue

        score = _score(record.get("result"))
        if score is None:
            continue

        home_goals, away_goals = score
        match_id = str(record.get("match_id") or "").strip()
        day = str(record.get("date") or "").strip()

        # HH520 match IDs restart each day, so date is required for safe joins.
        if not day:
            continue

        labels.append(
            create_result_label(
                match_id=match_id,
                date=day,
                league=str(record.get("league") or ""),
                home_team=str(record.get("home_team") or record.get("home") or ""),
                away_team=str(record.get("away_team") or record.get("away") or ""),
                half_score=None,
                full_score=f"{home_goals}-{away_goals}",
                result=_outcome(home_goals, away_goals),
                goals=home_goals + away_goals,
                source="HH520_10023s_RESULT_LABEL",
                verified=True,
            )
        )

    return labels
