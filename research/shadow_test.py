"""Out-of-sample Shadow Test for frozen HH520 candidate rules.

Discovery rules are read from a completed Research report. Validation records
must be strictly later than the discovery window end. No rules are regenerated
or tuned on validation data. Stable access is forbidden.
"""
from collections import defaultdict
from datetime import date

from research.hidden_model_reverse import _factor_pairs
from research.error_attribution import attribute_errors
from research.result_label.matcher import match_results
from research.sanitizer import sanitize_records
from research.score_inference import attach_research_score_predictions
from research.htft_inference import attach_research_htft_predictions
from research.result_label.collector import collect_result_labels
from research.lab import _prediction_snapshots, _restore_research_predictions

MIN_SHADOW_SAMPLE = 10
MIN_SHADOW_DATES = 2
MIN_RETAINED_DELTA = 0.0


def _index_errors(error_report):
    return {
        (str(x.get("date") or ""), str(x.get("match_id") or "")): x
        for x in (error_report or {}).get("matches") or []
    }


def _metric_baseline(error_report, metric):
    data = ((error_report or {}).get("summary") or {}).get(metric) or {}
    return data.get("accuracy")


def _validate_discovery_window(discovery_report, validation_start):
    end = ((discovery_report or {}).get("window") or {}).get("to")
    if not end:
        raise ValueError("discovery report missing window.to")
    if date.fromisoformat(validation_start) <= date.fromisoformat(end):
        raise ValueError("shadow validation must start strictly after discovery window")


def evaluate_frozen_rules(discovery_report, validation_records, validation_start, validation_end):
    _validate_discovery_window(discovery_report, validation_start)

    rules = list((discovery_report or {}).get("candidate_rules") or [])
    if not rules:
        raise ValueError("discovery report has no candidate rules")

    labels = collect_result_labels(validation_records)
    enriched = attach_research_score_predictions(validation_records)
    enriched = attach_research_htft_predictions(enriched)

    snapshots = _prediction_snapshots(enriched)
    clean, audit = sanitize_records(enriched)
    joined = match_results(clean, labels)
    joined = _restore_research_predictions(joined, snapshots)
    errors = attribute_errors(joined)
    error_index = _index_errors(errors)

    rule_results = []
    for rule in rules:
        factor = rule.get("factor")
        value = str(rule.get("value") or "")
        metric = rule.get("metric")
        sample = hits = 0
        dates = set()
        leagues = set()

        for item in joined:
            pairs = _factor_pairs(item)
            if str(pairs.get(factor) or "") != value:
                continue
            key = (str(item.get("date") or ""), str(item.get("match_id") or ""))
            row = error_index.get(key)
            if not row:
                continue
            state = row.get(metric)
            if state not in {"HIT", "MISS"}:
                continue
            sample += 1
            hits += int(state == "HIT")
            if item.get("date"):
                dates.add(str(item["date"]))
            leagues.add(str(item.get("league") or "UNKNOWN"))

        accuracy = hits / sample if sample else None
        baseline = _metric_baseline(errors, metric)
        delta = (
            accuracy - baseline
            if accuracy is not None and baseline is not None
            else None
        )
        discovery_accuracy = rule.get("accuracy")
        degradation = (
            accuracy - discovery_accuracy
            if accuracy is not None and discovery_accuracy is not None
            else None
        )

        reasons = []
        if sample < MIN_SHADOW_SAMPLE:
            reasons.append("SHADOW_SAMPLE_LT_10")
        if len(dates) < MIN_SHADOW_DATES:
            reasons.append("SHADOW_DATES_LT_2")
        if delta is None or delta < MIN_RETAINED_DELTA:
            reasons.append("NO_POSITIVE_DELTA_VS_SHADOW_BASELINE")

        status = "SHADOW_PASS" if not reasons else "SHADOW_HOLD"
        rule_results.append({
            "id": rule.get("id"),
            "factor": factor,
            "value": rule.get("value"),
            "metric": metric,
            "discovery_sample_count": rule.get("sample_count"),
            "discovery_accuracy": discovery_accuracy,
            "shadow_sample_count": sample,
            "shadow_hits": hits,
            "shadow_accuracy": accuracy,
            "shadow_baseline_accuracy": baseline,
            "shadow_delta_vs_baseline": delta,
            "accuracy_change_vs_discovery": degradation,
            "shadow_date_count": len(dates),
            "shadow_league_count": len(leagues),
            "status": status,
            "hold_reasons": reasons,
            "next_stage": "MANUAL_REVIEW" if status == "SHADOW_PASS" else "MORE_SHADOW_DATA",
            "stable_access": "FORBIDDEN",
        })

    rule_results.sort(
        key=lambda x: (
            x["status"] == "SHADOW_PASS",
            x.get("shadow_delta_vs_baseline") or -999,
            x.get("shadow_sample_count") or 0,
        ),
        reverse=True,
    )

    return {
        "kind": "shadow_test",
        "system": "HH520 Research Lab V3.2 Shadow Test",
        "status": "READY",
        "stable_access": "FORBIDDEN",
        "discovery": {
            "request_id": ((discovery_report or {}).get("_action") or {}).get("request_id"),
            "window": (discovery_report or {}).get("window"),
            "candidate_rule_count": len(rules),
        },
        "validation_window": {"from": validation_start, "to": validation_end},
        "validation_input_count": len(validation_records),
        "validation_matched_count": ((errors.get("summary") or {}).get("matches")),
        "sanitizer_pollution_events": len(audit),
        "shadow_policy": {
            "strictly_after_discovery": True,
            "rules_frozen": True,
            "min_shadow_sample": MIN_SHADOW_SAMPLE,
            "min_shadow_dates": MIN_SHADOW_DATES,
            "min_delta_vs_shadow_baseline": MIN_RETAINED_DELTA,
            "automatic_stable_promotion": False,
        },
        "shadow_pass_count": sum(1 for x in rule_results if x["status"] == "SHADOW_PASS"),
        "shadow_hold_count": sum(1 for x in rule_results if x["status"] == "SHADOW_HOLD"),
        "rules": rule_results,
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
