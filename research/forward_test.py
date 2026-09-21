"""Forward validation for frozen HH520 rules that passed Historical Shadow.

Only rules with SHADOW_PASS are eligible. Forward validation must start
strictly after the historical shadow window. Stable access is forbidden.
"""
from datetime import date

from research.shadow_test import evaluate_frozen_rules


def _forward_discovery_view(shadow_report):
    window = (shadow_report or {}).get("validation_window") or {}
    if not window.get("to"):
        raise ValueError("shadow report missing validation_window.to")

    passed = [
        x for x in ((shadow_report or {}).get("rules") or [])
        if x.get("status") == "SHADOW_PASS"
    ]
    if not passed:
        raise ValueError("shadow report has no SHADOW_PASS rules")

    rules = []
    for item in passed:
        rules.append({
            "id": item.get("id"),
            "factor": item.get("factor"),
            "value": item.get("value"),
            "metric": item.get("metric"),
            "sample_count": item.get("shadow_sample_count"),
            "accuracy": item.get("shadow_accuracy"),
        })
    return {"window": window, "candidate_rules": rules}


def evaluate_forward_rules(shadow_report, validation_records, validation_start, validation_end):
    shadow_end = ((shadow_report or {}).get("validation_window") or {}).get("to")
    if not shadow_end:
        raise ValueError("shadow report missing validation_window.to")
    if date.fromisoformat(validation_start) <= date.fromisoformat(shadow_end):
        raise ValueError("forward validation must start strictly after shadow window")

    frozen = _forward_discovery_view(shadow_report)
    report = evaluate_frozen_rules(
        frozen,
        validation_records,
        validation_start=validation_start,
        validation_end=validation_end,
    )

    for item in report.get("rules") or []:
        if item.get("status") == "SHADOW_PASS":
            item["status"] = "FORWARD_PASS"
            item["next_stage"] = "MANUAL_REVIEW"
        else:
            item["status"] = "FORWARD_HOLD"
            item["next_stage"] = "MORE_FORWARD_DATA"
        item["stable_access"] = "FORBIDDEN"

    report["kind"] = "forward_test"
    report["system"] = "HH520 Research Lab V3.3 Forward Test"
    report["stable_access"] = "FORBIDDEN"
    report["source_shadow"] = {
        "request_id": ((shadow_report or {}).get("_action") or {}).get("request_id"),
        "validation_window": (shadow_report or {}).get("validation_window"),
        "eligible_rule_count": len(frozen["candidate_rules"]),
    }
    report["forward_window"] = report.pop("validation_window")
    report["forward_input_count"] = report.pop("validation_input_count")
    report["forward_matched_count"] = report.pop("validation_matched_count")
    report["forward_pass_count"] = sum(
        1 for x in report.get("rules") or [] if x.get("status") == "FORWARD_PASS"
    )
    report["forward_hold_count"] = sum(
        1 for x in report.get("rules") or [] if x.get("status") == "FORWARD_HOLD"
    )
    report.pop("shadow_pass_count", None)
    report.pop("shadow_hold_count", None)
    report["forward_policy"] = {
        "rules_source": "SHADOW_PASS_ONLY",
        "rules_frozen": True,
        "automatic_stable_promotion": False,
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
    report["promotion_policy"] = "MANUAL_REVIEW_REQUIRED"
    return report
