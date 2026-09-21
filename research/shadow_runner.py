"""CLI runner for HH520 Research Shadow Test."""
import argparse
import json
from pathlib import Path

from collector.service import collect_date
from research.lab import date_range
from research.shadow_test import evaluate_frozen_rules


def collect_validation_window(start, end):
    records = []
    collection = []
    for day in date_range(start, end):
        data = collect_date(day)
        matches = data.get("matches", [])
        for match in matches:
            if not isinstance(match, dict):
                raise ValueError("collector returned a non-object match")
            item = dict(match)
            item["date"] = day
            records.append(item)
        collection.append({
            "date": day,
            "captured_at": data.get("captured_at"),
            "source_url": data.get("url"),
            "match_count": len(matches),
        })
    return records, collection


def main(argv=None):
    parser = argparse.ArgumentParser(description="HH520 Research Shadow Test")
    parser.add_argument("discovery_report", type=Path)
    parser.add_argument("start")
    parser.add_argument("end", nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    end = args.end or args.start
    date_range(args.start, end)

    discovery = json.loads(args.discovery_report.read_text(encoding="utf-8"))
    records, collection = collect_validation_window(args.start, end)
    report = evaluate_frozen_rules(
        discovery,
        records,
        validation_start=args.start,
        validation_end=end,
    )
    report["collection"] = collection

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
