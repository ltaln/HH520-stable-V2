"""HH520 Hidden Model Reverse Engine (Research-only).

Aggregates error-attribution outcomes against pre-match 10027s factors.
All conclusions are descriptive research signals, never Stable rules.
"""
from collections import defaultdict


METRICS = ("wdl", "score_exact", "score_top2", "htft", "htft_top2", "goals")


def _bucket_odds(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x < 1.5:
        return "<1.50"
    if x < 1.8:
        return "1.50-1.79"
    if x < 2.2:
        return "1.80-2.19"
    if x < 3.0:
        return "2.20-2.99"
    return ">=3.00"


def _bucket_probability_concentration(probs):
    if not isinstance(probs, dict):
        return None
    vals = []
    for key in ("home", "draw", "away"):
        try:
            vals.append(float(probs[key]))
        except (KeyError, TypeError, ValueError):
            return None
    top = max(vals)
    if top < 0.40:
        return "<40%"
    if top < 0.50:
        return "40-49%"
    if top < 0.60:
        return "50-59%"
    return ">=60%"


def _factor_pairs(item):
    factors = item.get("research_factors") or {}
    market = item.get("market") or {}
    probs = (item.get("research_prediction") or {}).get("page_probability") or item.get("page_probability") or {}

    pairs = {
        "league": item.get("league") or "UNKNOWN",
        "risk": factors.get("risk"),
        "rating": factors.get("rating"),
        "structure": factors.get("structure"),
        "consistency": factors.get("consistency"),
        "pattern": factors.get("pattern"),
        "advantage_side": factors.get("advantage_side"),
        "handicap": factors.get("handicap"),
        "odds_judgement": factors.get("odds_judgement"),
        "probability_concentration": _bucket_probability_concentration(probs),
        "home_odds_bucket": _bucket_odds(market.get("home_odds")),
        "draw_odds_bucket": _bucket_odds(market.get("draw_odds")),
        "away_odds_bucket": _bucket_odds(market.get("away_odds")),
    }
    return {k: str(v).strip() for k, v in pairs.items() if v not in (None, "", "-", "--", "—")}


def _baseline(error_report):
    out = {}
    summary = (error_report or {}).get("summary") or {}
    for metric in METRICS:
        data = summary.get(metric) or {}
        out[metric] = data.get("accuracy")
    return out


def build_hidden_model_reverse(joined, error_report, min_bucket_sample=3):
    by_key = defaultdict(lambda: defaultdict(lambda: {
        metric: {"sample_count": 0, "hits": 0} for metric in METRICS
    }))

    error_by_key = {}
    for row in (error_report or {}).get("matches") or []:
        error_by_key[(str(row.get("date") or ""), str(row.get("match_id") or ""))] = row

    for item in joined or []:
        key = (str(item.get("date") or ""), str(item.get("match_id") or ""))
        error_row = error_by_key.get(key)
        if not error_row:
            continue
        for factor, value in _factor_pairs(item).items():
            bucket = by_key[factor][value]
            for metric in METRICS:
                state = error_row.get(metric)
                if state not in {"HIT", "MISS"}:
                    continue
                bucket[metric]["sample_count"] += 1
                bucket[metric]["hits"] += int(state == "HIT")

    baseline = _baseline(error_report)
    factor_report = {}
    signals = []

    for factor, values in by_key.items():
        factor_report[factor] = {}
        for value, metrics in values.items():
            metric_out = {}
            for metric, stat in metrics.items():
                n = stat["sample_count"]
                hits = stat["hits"]
                acc = hits / n if n else None
                base = baseline.get(metric)
                delta = (acc - base) if (acc is not None and base is not None) else None
                metric_out[metric] = {
                    "sample_count": n,
                    "hits": hits,
                    "accuracy": acc,
                    "baseline_accuracy": base,
                    "delta_vs_baseline": delta,
                }
                if n >= min_bucket_sample and delta is not None:
                    signals.append({
                        "factor": factor,
                        "value": value,
                        "metric": metric,
                        "sample_count": n,
                        "accuracy": acc,
                        "baseline_accuracy": base,
                        "delta_vs_baseline": delta,
                        "direction": "ABOVE_BASELINE" if delta > 0 else ("BELOW_BASELINE" if delta < 0 else "AT_BASELINE"),
                        "status": "RESEARCH_SIGNAL_ONLY",
                    })
            factor_report[factor][value] = metric_out

    signals.sort(key=lambda x: (abs(x["delta_vs_baseline"]), x["sample_count"]), reverse=True)

    return {
        "status": "RESEARCH_ONLY",
        "stable_access": "FORBIDDEN",
        "baseline": baseline,
        "min_bucket_sample": min_bucket_sample,
        "factors": factor_report,
        "signals": signals,
        "top_signals": signals[:30],
        "note": (
            "Descriptive reverse-engineering only. Small samples may be unstable. "
            "No signal may modify Stable without later validation and manual review."
        ),
    }
