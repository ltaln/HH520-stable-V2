import json,sys
from pathlib import Path
from collector.service import collect_date
from collector.goal_timing_service import enrich_matches_with_goal_timing
from collector.firecrawl_client import firecrawl_runtime_status
from candidate.v35.core import evaluate_match

def main(date, output):
    data=collect_date(date)
    timing=enrich_matches_with_goal_timing(date,data.get("matches") or [])
    rows=[]
    for m in data.get("matches") or []:
        row=evaluate_match(m)
        gt=m.get("goal_timing") or {}
        row["goal_timing_diagnostic"]={
            "available":gt.get("available"),
            "reason":gt.get("reason"),
            "timing_mode":gt.get("timing_mode"),
            "source_domain":gt.get("source_domain"),
            "candidate_count":gt.get("candidate_count"),
            "home_candidate_count":gt.get("home_candidate_count"),
            "away_candidate_count":gt.get("away_candidate_count"),
            "errors":gt.get("errors"),
            "cache_hit":gt.get("cache_hit"),
            "discovery_mode":gt.get("discovery_mode"),
        }
        rows.append(row)
    payload={"status":"READY","kind":"v35_shadow","date":date,
             "stable_mutated":False,"historical_goal_timing_collection":False,
             "prediction_goal_timing_required":True,"goal_timing_summary":timing,
             "firecrawl_runtime":firecrawl_runtime_status(),"matches":rows}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
if __name__=="__main__":
    main(sys.argv[1],sys.argv[2])
