"""Deterministic offline evaluation of the market baseline."""
import argparse
import json
import math
from pathlib import Path
from datetime import datetime
from engine.market_baseline import dejuice_1x2


def log_loss(prob, hit, eps=1e-12):
    p = min(max(prob, eps), 1 - eps)
    return -math.log(p if hit else 1 - p)


def brier_score(probs, actual):
    return sum((probs[k] - (1.0 if k == actual else 0.0)) ** 2
               for k in ("home", "draw", "away"))


def _actual(record):
    actual = record.get("actual", record.get("outcome"))
    if actual in ("home", "draw", "away"):
        return actual
    result = record.get("result")
    if isinstance(result, str):
        try:
            home, away = (int(x.strip()) for x in result.split(":", 1))
            return "home" if home > away else "away" if home < away else "draw"
        except (ValueError, TypeError):
            pass
    return None


def _records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("matches", "records", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("input JSON must be a list or contain matches/records")


def _candidate_probabilities(value):
    if not isinstance(value, dict):
        return None
    try:
        values = {key: float(value[key]) for key in ("home", "draw", "away")}
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(number) or not 0 <= number <= 1 for number in values.values()):
        return None
    total = sum(values.values())
    return {key: number / total for key, number in values.items()} if total > 0 else None


def _metric(scored):
    if not scored:
        return {"count": 0, "accuracy": None, "log_loss": None, "brier": None}
    return {
        "count": len(scored),
        "accuracy": sum(pred == actual for _, actual, pred in scored) / len(scored),
        "log_loss": sum(log_loss(p[actual], True) for p, actual, _ in scored) / len(scored),
        "brier": sum(brier_score(p, actual) for p, actual, _ in scored) / len(scored),
    }


def evaluate_records(payload):
    records = _records(payload)
    records = sorted(records, key=lambda r: str(r.get("date", "")) if isinstance(r, dict) else "")
    scored = []
    candidate_scored = []
    paired_baseline_scored = []
    invalid_or_unlabelled_count = 0
    invalid_candidate_count = 0
    pass_count = 0
    for record in records:
        if not isinstance(record, dict):
            invalid_or_unlabelled_count += 1
            continue
        market = record.get("market", record)
        try:
            probs = dejuice_1x2(market["home_odds"], market["draw_odds"], market["away_odds"])
        except (KeyError, TypeError, ValueError):
            invalid_or_unlabelled_count += 1
            continue
        actual = _actual(record)
        if actual is None:
            invalid_or_unlabelled_count += 1
            continue
        prediction = max(("home", "draw", "away"), key=probs.get)
        scored.append((probs, actual, prediction))
        candidate = _candidate_probabilities(record.get("probabilities"))
        if record.get("status") == "PASS":
            pass_count += 1
        elif candidate is not None:
            candidate_scored.append((candidate, actual,
                                     max(("home", "draw", "away"), key=candidate.get)))
            paired_baseline_scored.append((probs, actual, prediction))
        elif record.get("probabilities") is not None:
            invalid_candidate_count += 1
    n = len(scored)
    coverage = n / len(records) if records else 0.0
    candidate_coverage = len(candidate_scored) / n if n else 0.0
    dates = [str(r.get("date")) for r in records if isinstance(r, dict) and r.get("date")]
    result = {"baseline": _metric(scored), "coverage": coverage,
              "coverage_definition": "valid odds and labelled outcome / input records",
              "pass_rate": pass_count / n if n else 0.0,
              "pass_count": pass_count,
              "invalid_or_unlabelled_count": invalid_or_unlabelled_count,
              "input_count": len(records),
              "candidate": _metric(candidate_scored),
              "candidate_coverage": candidate_coverage,
              "invalid_candidate_count": invalid_candidate_count,
              "baseline_on_candidate": _metric(paired_baseline_scored)}
    if dates:
        result["date_range"] = {"from": min(dates), "to": max(dates)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline JSON 1X2 baseline evaluation")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = evaluate_records(json.loads(args.input.read_text(encoding="utf-8")))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return result


if __name__ == "__main__":
    main()
