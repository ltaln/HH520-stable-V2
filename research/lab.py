"""HH520 Research Lab V2.2. Stable is read-only; outputs are candidate research only."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from copy import deepcopy

from research.sanitizer import sanitize_records
from research.backtest_engine import evaluate
from research.result_label.matcher import match_results

MAX_DAYS = 31


def date_range(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a:
        raise ValueError("end date must be >= start date")
    days = (b - a).days + 1
    if days > MAX_DAYS:
        raise ValueError(f"research window must be <= {MAX_DAYS} days")
    return [(a + timedelta(days=i)).isoformat() for i in range(days)]


def _key(record):
    return (str(record.get("date") or ""), str(record.get("match_id") or ""))


def _prediction_snapshots(records):
    """Capture prediction-only fields before sanitizer removes score-like keys.

    This is Research-only and never contains actual result labels.
    """
    snapshots = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        prediction = deepcopy(record.get("page_prediction") or {})
        snapshots[_key(record)] = {
            "page_probability": deepcopy(record.get("page_probability")),
            "page_prediction": prediction,
        }
    return snapshots


def _restore_research_predictions(joined, snapshots):
    output = []
    for record in joined:
        item = dict(record)
        snap = snapshots.get(_key(record), {})
        item["research_prediction"] = {
            "page_probability": deepcopy(snap.get("page_probability")),
            "page_prediction": deepcopy(snap.get("page_prediction") or {}),
        }
        output.append(item)
    return output


def _league_dna(records):
    leagues = defaultdict(lambda: {"matches": 0, "ready": 0})
    for r in records:
        league = str(r.get("league") or r.get("competition") or "UNKNOWN")
        leagues[league]["matches"] += 1
        if r.get("label_status") == "MATCHED":
            leagues[league]["ready"] += 1
    return dict(leagues)


def _team_dna(records):
    teams = Counter()
    for r in records:
        for key in ("home_team", "away_team", "home", "away"):
            if r.get(key):
                teams[str(r[key])] += 1
    return [{"team": k, "sample_count": v} for k, v in teams.most_common()]


def _candidate_rules(records):
    return [{
        "id": "CR-SAMPLE-001",
        "status": "CANDIDATE_ONLY",
        "statement": "Sample supports segmented review only; no Stable change authorized.",
        "evidence_count": len(records),
    }] if len(records) >= 20 else []


def build_research_report(records, start=None, end=None, source="HH520_10023s", result_labels=None):
    prediction_snapshots = _prediction_snapshots(records)
    clean, audit = sanitize_records(records)
    joined = match_results(clean, result_labels or [])
    joined = _restore_research_predictions(joined, prediction_snapshots)
    backtest = evaluate(joined)
    matched_count = backtest.get("matched_results", 0)

    return {
        "system": "HH520 Research Lab V2.2",
        "stable_access": "READ_ONLY",
        "source": source,
        "window": {"from": start, "to": end},
        "input_count": len(records),
        "clean_count": len(clean),
        "sanitizer": {"pollution_events": len(audit), "audit": audit},
        "league_dna": _league_dna(joined),
        "team_dna": _team_dna(clean),
        "backtest": backtest,
        "prediction_snapshot_layer": {
            "enabled": True,
            "count": len(prediction_snapshots),
            "isolation": "RESEARCH_ONLY",
            "contains_actual_results": False,
            "stable_access": "FORBIDDEN",
        },
        "result_label_layer": {
            "enabled": True,
            "collected": len(result_labels or []),
            "matched": matched_count,
            "unmatched": max(0, len(clean) - matched_count),
            "isolation": "RESEARCH_ONLY",
            "stable_access": "FORBIDDEN",
        },
        "hidden_model_reverse": {"status": "RESEARCH_ONLY"},
        "risk_analysis": {"status": "RESEARCH_ONLY"},
        "causal_analysis": {"status": "HYPOTHESIS_ONLY"},
        "confidence_analysis": {"status": "RESEARCH_ONLY", "sample_count": len(clean)},
        "candidate_rules": _candidate_rules(clean),
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
