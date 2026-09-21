"""CLI and collection runner for HH520 Research Lab V2."""
import argparse
import json
from pathlib import Path

from collector.service import collect_date
from research.lab import date_range, build_research_report
from research.result_label.collector import collect_result_labels
from research.score_inference import attach_research_score_predictions
from research.htft_inference import attach_research_htft_predictions\nfrom research.calibration.report import render_calibration_report


def _present(value):
    return value not in (None, "", [], {}, "-", "--", "—")


def _prediction_coverage(records):
    coverage = {
        "records": len(records),
        "single": 0,
        "htft": 0,
        "predicted_score": 0,
        "predicted_total_goals": 0,
        "predicted_total_goals_explicit": 0,
        "predicted_total_goals_derived_from_score": 0,
        "research_derived_score": 0,
        "research_derived_total_goals": 0,
        "research_derived_htft": 0,
        "raw_actionable_htft": 0,
        "page_probability": 0,
        "actual_half_score": 0,
        "actual_score": 0,
        "actual_total_goals": 0,
    }
    for record in records:
        prediction = (record.get("page_prediction") or {}) if isinstance(record, dict) else {}
        coverage["single"] += int(_present(prediction.get("single")))
        coverage["htft"] += int(_present(prediction.get("htft")))
        coverage["research_derived_htft"] += int(
            prediction.get("htft_source") == "RESEARCH_DERIVED_POISSON"
        )
        coverage["raw_actionable_htft"] += int(
            prediction.get("htft_source") == "HH520_RAW"
        )
        has_predicted_score = bool(prediction.get("score_options")) or _present(prediction.get("scores"))
        has_explicit_total_goals = _present(prediction.get("total_goals"))
        coverage["predicted_score"] += int(has_predicted_score)
        coverage["predicted_total_goals_explicit"] += int(has_explicit_total_goals)
        coverage["predicted_total_goals_derived_from_score"] += int(has_predicted_score and not has_explicit_total_goals)
        coverage["predicted_total_goals"] += int(has_explicit_total_goals or has_predicted_score)
        coverage["research_derived_score"] += int(prediction.get("score_source") == "RESEARCH_DERIVED")
        coverage["research_derived_total_goals"] += int(
            prediction.get("total_goals_source") == "RESEARCH_DERIVED_FROM_SCORE"
        )
        coverage["page_probability"] += int(_present(record.get("page_probability")))
        coverage["actual_half_score"] += int(_present(record.get("half_score")))
        coverage["actual_score"] += int(_present(record.get("result")))
        result_text = str(record.get("result") or "")
        import re
        match = re.search(r"(\d+)\s*[-:：]\s*(\d+)", result_text)
        if match:
            coverage["actual_total_goals"] += 1
    coverage["legacy_aliases"] = {
        "scores": coverage["predicted_score"],
        "total_goals": coverage["predicted_total_goals"],
        "actual_full_score": coverage["actual_score"],
    }
    coverage["source_note"] = (
        "actual_score and actual_total_goals are Result Labels. predicted_score and predicted_total_goals "
        "are Prediction fields used only for accuracy evaluation. If raw predicted_score is absent, Research "
        "may derive it from pre-match 1X2 probabilities using the RESEARCH_POISSON_1X2 layer. "
        "predicted_total_goals is derived from predicted_score when no explicit total-goals prediction exists."
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

    # Add Research-only score predictions from pre-match 1X2 information.
    # This layer never changes Stable and never overwrites explicit raw predictions.
    records = attach_research_score_predictions(records)
    records = attach_research_htft_predictions(records)

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
    parser.add_argument("--calibration-md", type=Path, help="Optional Stable V3 calibration Markdown report")
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
        records = attach_research_score_predictions(records)
        records = attach_research_htft_predictions(records)
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
    if args.calibration_md:
        args.calibration_md.parent.mkdir(parents=True, exist_ok=True)
        args.calibration_md.write_text(
            render_calibration_report(report.get("stable_v3_calibration") or {}, args.start, end),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
