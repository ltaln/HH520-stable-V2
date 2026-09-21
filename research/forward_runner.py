"""CLI runner for HH520 Research Forward Test."""
import argparse
import json
from pathlib import Path

from research.shadow_runner import collect_validation_window
from research.lab import date_range
from research.forward_test import evaluate_forward_rules


def main(argv=None):
    parser = argparse.ArgumentParser(description="HH520 Research Forward Test")
    parser.add_argument("shadow_report", type=Path)
    parser.add_argument("start")
    parser.add_argument("end", nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    end = args.end or args.start
    date_range(args.start, end)

    shadow = json.loads(args.shadow_report.read_text(encoding="utf-8"))
    records, collection = collect_validation_window(args.start, end)
    report = evaluate_forward_rules(
        shadow,
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
