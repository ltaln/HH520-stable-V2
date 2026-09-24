"""HH520 Research Lab V3.3. Stable is read-only; outputs are candidate research only."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from copy import deepcopy

from research.sanitizer import sanitize_records
from research.backtest_engine import evaluate
from research.result_label.matcher import match_results
from research.error_attribution import attribute_errors
from research.hidden_model_reverse import build_hidden_model_reverse
from research.dna import build_dna
from research.candidate_rules import generate_candidate_rules
from research.chronology import classify_window, canonical_timeline
from research.calibration import calibrate
from research.stable_v34_backtest import evaluate_stable_v34
from research.v35_ft_dataset import build_v35_ft_dataset
from research.v35_calibration_summary import build_v35_research_summary

MAX_DAYS = 62


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
        source_prediction = deepcopy(record.get("research_source_prediction") or {})
        prediction = deepcopy(source_prediction.get("page_prediction") or record.get("page_prediction") or {})
        probability = deepcopy(source_prediction.get("page_probability"))
        if probability is None:
            probability = deepcopy(record.get("page_probability"))
        snapshots[_key(record)] = {
            "page_probability": probability,
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


def build_research_report(records, start=None, end=None, source="HH520_10027s", result_labels=None):
    prediction_snapshots = _prediction_snapshots(records)
    stable_v34_backtest = evaluate_stable_v34(records, result_labels or [])
    v35_ft_dataset = build_v35_ft_dataset(records, result_labels or [])
    v35_research_summary = build_v35_research_summary(records, result_labels or [], v35_ft_dataset)
    clean, audit = sanitize_records(records)
    joined = match_results(clean, result_labels or [])
    joined = _restore_research_predictions(joined, prediction_snapshots)
    backtest = evaluate(joined)
    error_attribution = attribute_errors(joined)
    hidden_model_reverse = build_hidden_model_reverse(joined, error_attribution)
    dna = build_dna(error_attribution)
    candidate_rule_engine = generate_candidate_rules(
        joined, error_attribution, hidden_model_reverse
    )
    calibration = calibrate(joined, error_attribution)
    matched_count = backtest.get("matched_results", 0)

    return {
        "system": "HH520 Research Lab V3.1",
        "stable_access": "READ_ONLY",
        "source": source,
        "window": {"from": start, "to": end},
        "research_phase": classify_window(start, end) if start and end else "UNSPECIFIED",
        "canonical_timeline": canonical_timeline(),
        "input_count": len(records),
        "clean_count": len(clean),
        "sanitizer": {"pollution_events": len(audit), "audit": audit},
        "league_dna": dna["league_dna"],
        "team_dna": dna["team_dna"],
        "data_contract": {
            "actual_score": "RESULT_LABEL_ONLY",
            "actual_total_goals": "DERIVED_FROM_ACTUAL_SCORE",
            "predicted_score": "RAW_SOURCE_OR_RESEARCH_POISSON_1X2",
            "predicted_total_goals": "EXPLICIT_OR_DERIVED_FROM_PREDICTED_SCORE",
            "research_derived_predictions": "RESEARCH_ONLY",
            "predicted_htft": "HH520_RAW_OR_RESEARCH_POISSON_HTFT",
            "stable_access": "FORBIDDEN",
        },
        "backtest": backtest,
        "stable_v34_backtest": stable_v34_backtest,
        "v35_ft_dataset": v35_ft_dataset,
        "v35_research_summary": v35_research_summary,
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
        "error_attribution": error_attribution,
        "hidden_model_reverse": hidden_model_reverse,
        "risk_analysis": {"status": "RESEARCH_ONLY"},
        "causal_analysis": {"status": "HYPOTHESIS_ONLY"},
        "confidence_analysis": {"status": "RESEARCH_ONLY", "sample_count": len(clean)},
        "candidate_rule_engine": candidate_rule_engine,
        "candidate_rules": candidate_rule_engine["rules"],
        "stable_v3_calibration": calibration,
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
