"""CLI and collection runner for HH520 Research Lab V2."""
import argparse
import json
from pathlib import Path

from collector.service import collect_date
from research.lab import date_range, build_research_report
from research.result_label.collector import collect_result_labels


def _present(value):
    return value not in (None, "", [], {}, "-", "--", "—")


def _prediction_coverage(records):
    coverage = {
        "records": len(records),
        "single": 0,
        "htft": 0,
        "scores": 0,
        "total_goals": 0,
        "page_probability": 0,
        "actual_half_score": 0,
        "actual_full_score": 0,
        "actual_total_goals": 0,
    }
    for record in records:
        prediction = (record.get("page_prediction") or {}) if isinstance(record, dict) else {}
        coverage["single"] += int(_present(prediction.get("single")))
        coverage["htft"] += int(_present(prediction.get("htft")))
        coverage["scores"] += int(bool(prediction.get("score_options")) or _present(prediction.get("scores")))
        coverage["total_goals"] += int(_present(prediction.get("total_goals")))
        coverage["page_probability"] += int(_present(record.get("page_probability")))
        coverage["actual_half_score"] += int(_present(record.get("half_score")))
        coverage["actual_full_score"] += int(_present(record.get("result")))
        result_text = str(record.get("result") or "")
        import re
        match = re.search(r"(\d+)\s*[-:：]\s*(\d+)", result_text)
        if match:
            coverage["actual_total_goals"] += 1
    coverage["source_note"] = (
        "10027s exposes actual HT/FT scores; actual total goals are derived from the full-time score. "
        "It also exposes fusion WDL/HTFT fields. Its page and 10024 copy-prediction payload do not "
        "expose score-prediction or total-goals-prediction fields; zero prediction coverage is a source "
        "limitation, not a matcher failure."
    )
    return coverage


def collect_window(start, end):
    records = []
    collection = []
    for day in date_range(start, end):
        data = collect_date(day)
        matches = data.get("matches", [])
        for match in matches:
            if not isinstance(match, dict):
                raise ValueError("collector returned a non-object match")
            record = dict(match)
            # Collection day is authoritative and also prevents multi-day
            # match_id collisions in the Result Label Layer.
            record["date"] = day
            records.append(record)
        collection.append({
            "date": day,
            "captured_at": data.get("captured_at"),
            "source_url": data.get("url"),
            "match_count": len(matches),
        })

    # Extract post-match labels before sanitizer removes result/scores.
    # Labels stay separate and are only re-joined inside Research.
    result_labels = collect_result_labels(records)
    report = build_research_report(
        records, start, end, result_labels=result_labels
    )
    report["collection"] = collection
    report["prediction_coverage"] = _prediction_coverage(records)
    report["result_collection"] = {
        "source": "HH520_10027s_RESULT_LABEL",
        "collected": len(result_labels),
        "stable_access": "FORBIDDEN",
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="HH520 Research Lab V2")
    parser.add_argument("start")
    parser.add_argument("end", nargs="?")
    parser.add_argument("--input", type=Path, help="Optional offline JSON records instead of Firecrawl collection")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    end = args.end or args.start
    date_range(args.start, end)

    if args.input:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else payload.get("records", payload.get("matches", []))
        for record in records:
            if isinstance(record, dict) and not record.get("date") and args.start == end:
                record["date"] = args.start
        labels = collect_result_labels(records)
        report = build_research_report(
            records, args.start, end, source="OFFLINE_INPUT", result_labels=labels
        )
        report["result_collection"] = {
            "source": "OFFLINE_INPUT_RESULT_LABEL",
            "collected": len(labels),
            "stable_access": "FORBIDDEN",
        }
    else:
        report = collect_window(args.start, end)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
