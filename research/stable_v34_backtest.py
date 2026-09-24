"""Historical replay of the current HH520 Stable V3.4 chain.

This module is Research-only. It removes all known post-match fields before
calling Stable, then compares the locked prediction to isolated Result Labels.
"""
from copy import deepcopy

from prediction.builder import prepare_match

POSTMATCH_KEYS = {
    "result", "half_score", "full_score", "actual_score", "actual_half_score",
    "actual_outcome", "actual_total_goals", "result_label", "label_status",
    "label_match_method",
}

OUTCOME_MAP = {"主胜": "HOME", "平": "DRAW", "客胜": "AWAY"}


def _norm_match_id(value):
    raw = str(value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return str(int(digits)) if digits else raw


def _key(item):
    return (str(item.get("date") or "")[:10], _norm_match_id(item.get("match_id")))


def _score_pair(value):
    import re
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _empty_bucket():
    return {"evaluable": 0, "hits": 0, "accuracy": None}


def _finish(bucket):
    n = bucket["evaluable"]
    bucket["accuracy"] = bucket["hits"] / n if n else None
    return bucket


def evaluate_stable_v34(records, labels):
    label_map = {_key(x): x for x in labels if isinstance(x, dict)}
    rows = []
    summary = {
        "matched_results": 0,
        "predicted": 0,
        "wdl": _empty_bucket(),
        "score_top2": _empty_bucket(),
        "total_goals": _empty_bucket(),
        "by_tier": {},
        "by_direction": {},
        "pass_count": 0,
        "confirm_count": 0,
        "data_quality_pass_count": 0,
    }

    for record in records:
        if not isinstance(record, dict):
            continue
        label = label_map.get(_key(record))
        if not label:
            continue
        summary["matched_results"] += 1

        prematch = deepcopy(record)
        for key in POSTMATCH_KEYS:
            prematch.pop(key, None)

        pred = prepare_match(prematch)
        if pred.get("status") != "PREDICTED":
            continue

        summary["predicted"] += 1
        tier = pred.get("state") or "UNKNOWN"
        direction = pred.get("direction")
        if tier == "PASS":
            summary["pass_count"] += 1
        if tier == "CONFIRM":
            summary["confirm_count"] += 1
        if not pred.get("quality_warnings"):
            summary["data_quality_pass_count"] += 1

        actual = str(label.get("actual_outcome") or "").upper()
        predicted = OUTCOME_MAP.get(direction)
        hit = actual in {"HOME", "DRAW", "AWAY"} and predicted == actual

        if actual in {"HOME", "DRAW", "AWAY"} and predicted:
            summary["wdl"]["evaluable"] += 1
            summary["wdl"]["hits"] += int(hit)

            tier_bucket = summary["by_tier"].setdefault(
                tier, {"evaluable": 0, "hits": 0, "accuracy": None}
            )
            tier_bucket["evaluable"] += 1
            tier_bucket["hits"] += int(hit)

            direction_bucket = summary["by_direction"].setdefault(
                direction, {"evaluable": 0, "hits": 0, "accuracy": None}
            )
            direction_bucket["evaluable"] += 1
            direction_bucket["hits"] += int(hit)

        actual_score = _score_pair(label.get("actual_score"))
        score_options = [
            _score_pair(pred.get("score1")),
            _score_pair(pred.get("score2")),
        ]
        score_options = [x for x in score_options if x]
        if actual_score and score_options:
            summary["score_top2"]["evaluable"] += 1
            summary["score_top2"]["hits"] += int(actual_score in score_options[:2])

        actual_goals = label.get("actual_total_goals")
        try:
            actual_goals = int(actual_goals)
        except (TypeError, ValueError):
            actual_goals = None
        predicted_goals = str(pred.get("total_goals") or "").replace("球", "")
        try:
            predicted_goals = int(predicted_goals)
        except (TypeError, ValueError):
            predicted_goals = None
        if actual_goals is not None and predicted_goals is not None:
            summary["total_goals"]["evaluable"] += 1
            summary["total_goals"]["hits"] += int(actual_goals == predicted_goals)

        rows.append({
            "date": record.get("date"),
            "match_id": record.get("match_id"),
            "league": record.get("league"),
            "home_team": record.get("home_team"),
            "away_team": record.get("away_team"),
            "prediction": {
                "direction": direction,
                "state": tier,
                "market_probability": pred.get("market_probability"),
                "model_probability": pred.get("model_probability"),
                "score1": pred.get("score1"),
                "score2": pred.get("score2"),
                "htft1": pred.get("htft1"),
                "htft2": pred.get("htft2"),
                "total_goals": pred.get("total_goals"),
                "probability_margin": (pred.get("decision_filter") or {}).get("probability_margin"),
                "quality_warnings": pred.get("quality_warnings") or [],
            },
            "actual": {
                "outcome": actual,
                "score": label.get("actual_score"),
                "total_goals": label.get("actual_total_goals"),
            },
            "wdl_hit": bool(hit) if predicted and actual in {"HOME", "DRAW", "AWAY"} else None,
        })

    _finish(summary["wdl"])
    _finish(summary["score_top2"])
    _finish(summary["total_goals"])
    for bucket in summary["by_tier"].values():
        _finish(bucket)
    for bucket in summary["by_direction"].values():
        _finish(bucket)

    return {
        "version": "HH520 Stable V3.4.1 Historical Replay",
        "isolation": "RESEARCH_ONLY",
        "postmatch_fields_removed_before_prediction": True,
        "stable_model_mutated": False,
        "summary": summary,
        "matches": rows,
    }
