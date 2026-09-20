"""CLI and collection runner for HH520 Research Lab V2."""
import argparse
import json
from pathlib import Path

from collector.service import collect_date
from research.lab import date_range, build_research_report
from research.result_label.collector import collect_result_labels
from research.fusion_extractor import attach_research_predictions


def collect_window(start, end):
    records = []
    collection = []
    prediction_debug = []
    for day in date_range(start, end):
        data = collect_date(day)
        matches = data.get("matches", [])
        raw = data.get("raw") or {}
        markdown = ((raw.get("data") or {}).get("markdown") if isinstance(raw, dict) else None) or ""
        matches, day_debug = attach_research_predictions(matches, markdown)
        day_debug["date"] = day
        prediction_debug.append(day_debug)
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
    report["prediction_debug"] = prediction_debug
    report["result_collection"] = {
        "source": "HH520_10023s_RESULT_LABEL",
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
