"""One-shot long-window calibration runner.

Research Lab's normal 31-day guardrail remains unchanged. This runner is only
for a predeclared calibration window and still keeps Stable read-only.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from collector.service import collect_date
from research.result_label.collector import collect_result_labels
from research.score_inference import attach_research_score_predictions
from research.htft_inference import attach_research_htft_predictions
from research.lab import build_research_report
from research.calibration.report import render_calibration_report


def _days(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a:
        raise ValueError("end date must be >= start date")
    return [(a + timedelta(days=i)).isoformat() for i in range((b-a).days+1)]


def run_window(start, end):
    records=[]
    collection=[]
    for day in _days(start,end):
        data=collect_date(day)
        matches=data.get("matches",[])
        for match in matches:
            row=dict(match)
            row["date"]=day
            records.append(row)
        collection.append({"date":day,"match_count":len(matches),"source_url":data.get("url")})
    labels=collect_result_labels(records)
    enriched=attach_research_score_predictions(records)
    enriched=attach_research_htft_predictions(enriched)
    report=build_research_report(enriched,start,end,result_labels=labels)
    report["collection"]=collection
    report["long_window_calibration"]={
        "enabled":True,
        "days":len(collection),
        "stable_access":"READ_ONLY",
        "normal_research_guardrail_days":31,
    }
    return report


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--markdown",type=Path,required=True)
    args=p.parse_args(argv)
    report=run_window(args.start,args.end)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    args.markdown.write_text(render_calibration_report(report.get("stable_v3_calibration") or {},args.start,args.end),encoding="utf-8")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
