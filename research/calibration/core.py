"""Research-only Stable V3 parameter calibration.

Consumes isolated Research records + result labels. It never writes Stable
configuration and never uses HH520 betting/advice columns.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import re

from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk

RISK_THRESHOLDS = (20, 30, 40, 50, 55, 60, 70)
MARGIN_THRESHOLDS = (0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20)
EDGE_THRESHOLDS = (0.00, 0.03, 0.05, 0.08, 0.10)
MIN_CANDIDATE_SAMPLE = 20
MIN_COVERAGE = 0.20


def _actual_outcome(label):
    raw = str(label.get("actual_outcome") or label.get("result") or "").upper()
    if raw in {"HOME", "DRAW", "AWAY"}:
        return raw.lower()
    score = str(label.get("actual_score") or label.get("full_score") or "")
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", score)
    if not m:
        return None
    home, away = map(int, m.groups())
    return "home" if home > away else "away" if home < away else "draw"


def _prematch_view(item):
    match = deepcopy(item)
    research = item.get("research_prediction") or {}
    if research.get("page_probability") is not None:
        match["page_probability"] = deepcopy(research["page_probability"])
    # Result labels are never prediction features.
    for key in ("result", "half_score", "full_score", "result_label", "label_status"):
        match.pop(key, None)
    value = match.get("value") or {}
    if "signal" in value:
        value = dict(value)
        value.pop("signal", None)
        match["value"] = value
    return match


def _row(item):
    label = item.get("result_label") or {}
    actual = _actual_outcome(label)
    if actual is None:
        return None
    match = _prematch_view(item)
    probability = probability_layer(match)
    if not probability.get("valid") or not probability.get("direction"):
        return None
    value = value_layer(match, probability)
    quality = data_quality_gate(match, probability)
    classification = classify_match(match, probability)
    risk = assess_risk(match, probability, value, quality, classification)
    return {
        "date": str(item.get("date") or ""),
        "match_id": str(item.get("match_id") or ""),
        "actual": actual,
        "direction": probability["direction"],
        "hit": probability["direction"] == actual,
        "top_probability": classification["top_probability"],
        "margin": classification["probability_margin"],
        "edge": value.get("directional_edge"),
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "match_type": classification["type"],
        "quality_valid": quality["valid"],
    }


def _metric(rows):
    if not rows:
        return {"sample_count": 0, "hits": 0, "accuracy": None, "coverage": 0.0}
    hits = sum(int(r["hit"]) for r in rows)
    return {
        "sample_count": len(rows),
        "hits": hits,
        "accuracy": hits / len(rows),
    }


def _bucket(rows, key, buckets):
    out = []
    for name, lo, hi in buckets:
        chosen = []
        for r in rows:
            value = r.get(key)
            if value is None:
                continue
            if (lo is None or value >= lo) and (hi is None or value < hi):
                chosen.append(r)
        metric = _metric(chosen)
        metric["bucket"] = name
        out.append(metric)
    return out


def _threshold_scan(rows, key, thresholds, mode):
    out = []
    total = len(rows)
    for threshold in thresholds:
        chosen = [
            r for r in rows
            if r.get(key) is not None and (
                r[key] <= threshold if mode == "max" else r[key] >= threshold
            )
        ]
        metric = _metric(chosen)
        metric.update({
            "threshold": threshold,
            "operator": "<=" if mode == "max" else ">=",
            "coverage": len(chosen) / total if total else 0.0,
        })
        out.append(metric)
    return out


def _candidate(scan, overall_accuracy):
    eligible = [
        x for x in scan
        if x["sample_count"] >= MIN_CANDIDATE_SAMPLE
        and x["coverage"] >= MIN_COVERAGE
        and x["accuracy"] is not None
    ]
    if not eligible:
        return None
    best = max(eligible, key=lambda x: (x["accuracy"], x["sample_count"]))
    delta = best["accuracy"] - overall_accuracy if overall_accuracy is not None else None
    return {
        "status": "CANDIDATE_ONLY",
        "threshold": best["threshold"],
        "operator": best["operator"],
        "sample_count": best["sample_count"],
        "coverage": best["coverage"],
        "accuracy": best["accuracy"],
        "delta_vs_all": delta,
        "manual_review_required": True,
    }


def _match_type_analysis(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["match_type"]].append(row)
    output = {}
    for name, subset in sorted(grouped.items()):
        overall = _metric(subset)
        overall["coverage"] = len(subset) / len(rows) if rows else 0.0
        risk_scan = _threshold_scan(subset, "risk_score", RISK_THRESHOLDS, "max")
        margin_scan = _threshold_scan(subset, "margin", MARGIN_THRESHOLDS, "min")
        edge_scan = _threshold_scan(subset, "edge", EDGE_THRESHOLDS, "min")
        output[name] = {
            "overall": overall,
            "risk_scan": risk_scan,
            "margin_scan": margin_scan,
            "edge_scan": edge_scan,
            "candidate": {
                "max_risk": _candidate(risk_scan, overall["accuracy"]),
                "min_margin": _candidate(margin_scan, overall["accuracy"]),
                "min_edge": _candidate(edge_scan, overall["accuracy"]),
            },
        }
    return output


def _output_error_analysis(error_attribution):
    summary = deepcopy((error_attribution or {}).get("summary") or {})
    rows = (error_attribution or {}).get("rows") or []
    counts = Counter()
    for row in rows:
        counts.update(row.get("errors") or [])
    return {
        "summary": summary,
        "error_counts": dict(counts.most_common()),
        "scope": ["win_draw_loss", "score", "half_time_full_time", "total_goals"],
        "note": "Output errors are Research-only diagnostics; they do not auto-change Stable generation logic.",
    }


def calibrate(joined, error_attribution=None):
    rows = []
    for item in joined or []:
        if item.get("label_status") != "MATCHED":
            continue
        row = _row(item)
        if row is not None:
            rows.append(row)

    overall = _metric(rows)
    overall["date_count"] = len({r["date"] for r in rows if r["date"]})

    risk_buckets = _bucket(rows, "risk_score", (
        ("0-9", 0, 10), ("10-19", 10, 20), ("20-29", 20, 30),
        ("30-39", 30, 40), ("40-49", 40, 50), ("50-59", 50, 60),
        ("60+", 60, None),
    ))
    margin_buckets = _bucket(rows, "margin", (
        ("0-3%", 0, .03), ("3-5%", .03, .05), ("5-8%", .05, .08),
        ("8-12%", .08, .12), ("12-20%", .12, .20), ("20%+", .20, None),
    ))
    edge_buckets = _bucket(rows, "edge", (
        ("<0", None, 0), ("0-3%", 0, .03), ("3-5%", .03, .05),
        ("5-8%", .05, .08), ("8%+", .08, None),
    ))

    risk_scan = _threshold_scan(rows, "risk_score", RISK_THRESHOLDS, "max")
    margin_scan = _threshold_scan(rows, "margin", MARGIN_THRESHOLDS, "min")
    edge_scan = _threshold_scan(rows, "edge", EDGE_THRESHOLDS, "min")

    return {
        "system": "HH520 Research Lab V1 - Stable V3 Calibration",
        "stable_access": "READ_ONLY",
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
        "sample": overall,
        "risk_score": {
            "buckets": risk_buckets,
            "threshold_scan": risk_scan,
            "candidate": _candidate(risk_scan, overall.get("accuracy")),
        },
        "probability_margin": {
            "buckets": margin_buckets,
            "threshold_scan": margin_scan,
            "candidate": _candidate(margin_scan, overall.get("accuracy")),
        },
        "value_edge": {
            "buckets": edge_buckets,
            "threshold_scan": edge_scan,
            "candidate": _candidate(edge_scan, overall.get("accuracy")),
        },
        "match_type": _match_type_analysis(rows),
        "output_error": _output_error_analysis(error_attribution),
        "guardrails": {
            "min_candidate_sample": MIN_CANDIDATE_SAMPLE,
            "min_coverage": MIN_COVERAGE,
            "forbidden_inputs": ["建议下注", "是否下注"],
            "automatic_stable_write": False,
        },
    }
