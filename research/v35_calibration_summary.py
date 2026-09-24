"""Compact Research-only calibration summary for HH520 V3.5 candidates.

Historical research must not collect goal-timing data. This module only uses
pre-match H/D/A probabilities plus isolated result labels, and the already
computed Research Poisson score model.
"""
import re


PROB_THRESHOLDS = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
MARGIN_THRESHOLDS = (0.03, 0.05, 0.08, 0.10, 0.12, 0.15)
DRAW_THRESHOLDS = (0.22, 0.24, 0.26, 0.28, 0.30, 0.32)
SIDE_GAPS = (0.03, 0.05, 0.08, 0.10, 0.12)
DRAW_TOP_GAPS = (0.02, 0.04, 0.06, 0.08, 0.10)


def _bucket():
    return {"evaluable": 0, "hits": 0, "accuracy": None}


def _finish(bucket):
    n = bucket["evaluable"]
    bucket["accuracy"] = bucket["hits"] / n if n else None
    return bucket


def _score_pair(value):
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _label_key(label):
    raw = str(label.get("match_id") or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    mid = str(int(digits)) if digits else raw
    return (str(label.get("date") or "")[:10], mid)


def _record_key(record):
    raw = str(record.get("match_id") or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    mid = str(int(digits)) if digits else raw
    return (str(record.get("date") or "")[:10], mid)


def _metric_row(kind, **kwargs):
    row = {"kind": kind}
    row.update(kwargs)
    row["evaluable"] = 0
    row["hits"] = 0
    row["accuracy"] = None
    return row


def _finish_rows(rows):
    for row in rows:
        n = row["evaluable"]
        row["accuracy"] = row["hits"] / n if n else None
    return rows


def _ft_grid(rows):
    home = [
        _metric_row("HOME", probability_threshold=p, margin_threshold=m)
        for p in PROB_THRESHOLDS for m in MARGIN_THRESHOLDS
    ]
    away = [
        _metric_row("AWAY", probability_threshold=p, margin_threshold=m)
        for p in PROB_THRESHOLDS for m in MARGIN_THRESHOLDS
    ]
    draw = [
        _metric_row(
            "DRAW",
            draw_probability_threshold=p,
            side_gap_threshold=sg,
            draw_to_side_top_gap_threshold=tg,
        )
        for p in DRAW_THRESHOLDS for sg in SIDE_GAPS for tg in DRAW_TOP_GAPS
    ]

    for item in rows:
        probs = item.get("probabilities") or {}
        try:
            ph, pd, pa = float(probs["home"]), float(probs["draw"]), float(probs["away"])
        except (KeyError, TypeError, ValueError):
            continue
        actual = item.get("actual_outcome")
        home_margin = ph - max(pd, pa)
        away_margin = pa - max(pd, ph)
        side_gap = abs(ph - pa)
        draw_to_side_top = max(ph, pa) - pd

        for row in home:
            if ph >= row["probability_threshold"] and home_margin >= row["margin_threshold"]:
                row["evaluable"] += 1
                row["hits"] += int(actual == "HOME")

        for row in away:
            if pa >= row["probability_threshold"] and away_margin >= row["margin_threshold"]:
                row["evaluable"] += 1
                row["hits"] += int(actual == "AWAY")

        for row in draw:
            if (
                pd >= row["draw_probability_threshold"]
                and side_gap <= row["side_gap_threshold"]
                and draw_to_side_top <= row["draw_to_side_top_gap_threshold"]
            ):
                row["evaluable"] += 1
                row["hits"] += int(actual == "DRAW")

    return {
        "home": _finish_rows(home),
        "away": _finish_rows(away),
        "draw": _finish_rows(draw),
    }


def _independent_score(records, labels):
    label_map = {_label_key(x): x for x in labels if isinstance(x, dict)}
    top1 = _bucket()
    top2 = _bucket()
    total = _bucket()
    source_counts = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        label = label_map.get(_record_key(record))
        if not label:
            continue

        source = record.get("research_source_prediction") or {}
        model = source.get("research_score_model") or {}
        top_scores = model.get("top_scores") or []
        if not top_scores:
            continue

        probability_source = str(model.get("probability_source") or "UNKNOWN")
        source_counts[probability_source] = source_counts.get(probability_source, 0) + 1

        actual = _score_pair(label.get("actual_score"))
        if actual:
            options = []
            for row in top_scores[:2]:
                try:
                    options.append((int(row["home"]), int(row["away"])))
                except (KeyError, TypeError, ValueError):
                    pass
            if options:
                top1["evaluable"] += 1
                top1["hits"] += int(actual == options[0])
                top2["evaluable"] += 1
                top2["hits"] += int(actual in options[:2])

        actual_total = label.get("actual_total_goals")
        try:
            actual_total = int(actual_total)
        except (TypeError, ValueError):
            actual_total = None
        if actual_total is not None:
            try:
                predicted_total = int(top_scores[0]["home"]) + int(top_scores[0]["away"])
            except (KeyError, TypeError, ValueError):
                predicted_total = None
            if predicted_total is not None:
                total["evaluable"] += 1
                total["hits"] += int(actual_total == predicted_total)

    return {
        "model": "RESEARCH_POISSON_1X2_INDEPENDENT_OF_SELECTED_FT_DIRECTION",
        "top1": _finish(top1),
        "top2": _finish(top2),
        "total_goals": _finish(total),
        "probability_source_counts": source_counts,
        "stable_access": "FORBIDDEN",
    }


def build_v35_research_summary(records, labels, ft_dataset):
    return {
        "version": "HH520 V3.5 Candidate Research Summary V1",
        "isolation": "RESEARCH_ONLY",
        "historical_goal_timing_collection": False,
        "ft_grid": _ft_grid((ft_dataset or {}).get("rows") or []),
        "independent_score": _independent_score(records, labels or []),
        "promotion_policy": "SHADOW_VALIDATE_BEFORE_STABLE",
    }
