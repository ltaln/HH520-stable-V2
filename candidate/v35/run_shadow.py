import json,sys
from pathlib import Path
from collector.service import collect_date
from collector.goal_timing_service import enrich_matches_with_goal_timing
from candidate.v35.core import evaluate_match

def main(date, output):
    data=collect_date(date)
    timing=enrich_matches_with_goal_timing(date,data.get("matches") or [])
    rows=[evaluate_match(m) for m in data.get("matches") or []]
    payload={"status":"READY","kind":"v35_shadow","date":date,
             "stable_mutated":False,"historical_goal_timing_collection":False,
             "prediction_goal_timing_required":True,"goal_timing_summary":timing,"matches":rows}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
if __name__=="__main__":
    main(sys.argv[1],sys.argv[2])
