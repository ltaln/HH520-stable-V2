"""Candidate Rule Generator for HH520 Research Lab.

Promotes only Research signals into CANDIDATE_ONLY shadow-test proposals.
It never changes Stable or marks a rule as production-ready.
"""
from collections import defaultdict

from research.hidden_model_reverse import _factor_pairs

MIN_SAMPLE = 20
MIN_DATES = 3
MIN_DELTA = 0.08
MIN_POSITIVE_DATE_RATIO = 0.60
MIN_LEAGUES_FOR_GLOBAL = 2


def _error_index(error_report):
    return {
        (str(row.get("date") or ""), str(row.get("match_id") or "")): row
        for row in (error_report or {}).get("matches") or []
    }


def _evidence_stats(joined, error_report, signal):
    factor = signal.get("factor")
    value = str(signal.get("value") or "")
    metric = signal.get("metric")
    baseline = signal.get("baseline_accuracy")
    errors = _error_index(error_report)

    dates = defaultdict(lambda: {"sample_count": 0, "hits": 0})
    leagues = set()
    total = hits = 0

    for item in joined or []:
        pairs = _factor_pairs(item)
        if str(pairs.get(factor) or "") != value:
            continue
        key = (str(item.get("date") or ""), str(item.get("match_id") or ""))
        row = errors.get(key)
        if not row:
            continue
        state = row.get(metric)
        if state not in {"HIT", "MISS"}:
            continue

        day = str(item.get("date") or "")
        league = str(item.get("league") or "UNKNOWN")
        if day:
            dates[day]["sample_count"] += 1
            dates[day]["hits"] += int(state == "HIT")
        leagues.add(league)
        total += 1
        hits += int(state == "HIT")

    positive_dates = 0
    date_detail = {}
    for day, stat in sorted(dates.items()):
        acc = stat["hits"] / stat["sample_count"] if stat["sample_count"] else None
        date_detail[day] = {**stat, "accuracy": acc}
        if acc is not None and baseline is not None and acc >= baseline:
            positive_dates += 1

    date_count = len(dates)
    positive_ratio = positive_dates / date_count if date_count else 0.0
    return {
        "sample_count": total,
        "hits": hits,
        "accuracy": hits / total if total else None,
        "date_count": date_count,
        "positive_date_count": positive_dates,
        "positive_date_ratio": positive_ratio,
        "league_count": len(leagues),
        "leagues": sorted(leagues),
        "date_detail": date_detail,
    }


def generate_candidate_rules(joined, error_report, hidden_model_reverse):
    rules = []
    rejected = []
    signals = (hidden_model_reverse or {}).get("signals") or []

    for signal in signals:
        if signal.get("direction") != "ABOVE_BASELINE":
            continue

        evidence = _evidence_stats(joined, error_report, signal)
        delta = signal.get("delta_vs_baseline")
        factor = signal.get("factor")
        reasons = []

        if evidence["sample_count"] < MIN_SAMPLE:
            reasons.append("SAMPLE_LT_20")
        if evidence["date_count"] < MIN_DATES:
            reasons.append("DATES_LT_3")
        if delta is None or delta < MIN_DELTA:
            reasons.append("DELTA_LT_8PP")
        if evidence["positive_date_ratio"] < MIN_POSITIVE_DATE_RATIO:
            reasons.append("DATE_STABILITY_LT_60PCT")
        if factor != "league" and evidence["league_count"] < MIN_LEAGUES_FOR_GLOBAL:
            reasons.append("GLOBAL_RULE_SINGLE_LEAGUE")

        proposal = {
            "factor": factor,
            "value": signal.get("value"),
            "metric": signal.get("metric"),
            "sample_count": evidence["sample_count"],
            "hits": evidence["hits"],
            "accuracy": evidence["accuracy"],
            "baseline_accuracy": signal.get("baseline_accuracy"),
            "delta_vs_baseline": delta,
            "date_count": evidence["date_count"],
            "positive_date_ratio": evidence["positive_date_ratio"],
            "league_count": evidence["league_count"],
            "leagues": evidence["leagues"],
            "rule_scope": "LEAGUE_DNA" if factor == "league" else "GLOBAL_FACTOR",
            "stable_access": "FORBIDDEN",
        }

        if reasons:
            proposal["status"] = "RESEARCH_SIGNAL_ONLY"
            proposal["rejection_reasons"] = reasons
            rejected.append(proposal)
            continue

        proposal["id"] = f"CR-{len(rules)+1:03d}"
        proposal["status"] = "CANDIDATE_ONLY"
        proposal["next_stage"] = "SHADOW_TEST"
        proposal["statement"] = (
            f"When {factor}={signal.get('value')}, evaluate {signal.get('metric')} "
            f"as a candidate filter; observed delta vs baseline is {delta:.3f}."
        )
        rules.append(proposal)

    rules.sort(key=lambda x: (x["delta_vs_baseline"], x["sample_count"]), reverse=True)
    for idx, rule in enumerate(rules, start=1):
        rule["id"] = f"CR-{idx:03d}"

    rejected.sort(
        key=lambda x: (
            x.get("delta_vs_baseline") or 0,
            x.get("sample_count") or 0,
        ),
        reverse=True,
    )

    return {
        "status": "CANDIDATE_ONLY" if rules else "RESEARCH_ONLY",
        "stable_access": "FORBIDDEN",
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
        "thresholds": {
            "min_sample": MIN_SAMPLE,
            "min_dates": MIN_DATES,
            "min_delta_vs_baseline": MIN_DELTA,
            "min_positive_date_ratio": MIN_POSITIVE_DATE_RATIO,
            "min_leagues_for_global": MIN_LEAGUES_FOR_GLOBAL,
        },
        "candidate_count": len(rules),
        "rules": rules,
        "rejected_signal_count": len(rejected),
        "top_rejected": rejected[:30],
    }
