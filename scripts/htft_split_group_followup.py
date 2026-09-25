import json, os, sys
import numpy as np
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.htft_split_group_research import (
    load_rows, GROUPS, PROTECTED, fit_binary, pred, evaluate, default_cfg
)

SELECTED={
 "DRAW_FINISH":{"l2":0.1,"threshold":0.35,"gamma":0.2},
 "REVERSAL":{"l2":0.1,"threshold":0.35,"gamma":0.6},
 "DRAW_AWAY":{"l2":0.1,"threshold":0.35,"gamma":0.3},
}

def main():
    if os.getenv("HH520_SPLIT_HTFT_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    dev=rows["dev1"]+rows["dev2"]
    stress=rows["stress"]
    scores={}
    for g,cfg in SELECTED.items():
        model=fit_binary(dev,GROUPS[g],cfg["l2"])
        scores[g]=pred(model,stress)

    zero={g:np.zeros(len(stress)) for g in GROUPS}
    tests={}
    combos=[
      ("BASE",()),
      ("DRAW_FINISH_ONLY",("DRAW_FINISH",)),
      ("REVERSAL_ONLY",("REVERSAL",)),
      ("DRAW_AWAY_ONLY",("DRAW_AWAY",)),
      ("DRAW_FINISH_PLUS_DRAW_AWAY",("DRAW_FINISH","DRAW_AWAY")),
      ("REVERSAL_PLUS_DRAW_AWAY",("REVERSAL","DRAW_AWAY")),
      ("ALL_THREE",("DRAW_FINISH","REVERSAL","DRAW_AWAY")),
    ]
    for name,active in combos:
        cfg=default_cfg()
        sm={g:zero[g].copy() for g in GROUPS}
        for g in active:
            cfg[g]={"threshold":SELECTED[g]["threshold"],"gamma":SELECTED[g]["gamma"]}
            sm[g]=scores[g]
        tests[name]=evaluate(stress,sm,cfg)

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "stress_window":"2026-09-01..2026-09-20",
      "selection_used_stress":False,
      "selected_parameters_source":"development-only split-group study",
      "selected_parameters":SELECTED,
      "stress_comparison":tests,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED",
    }
    Path("_htft_split_followup.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={}
    for k,v in tests.items():
        summary[k]={
          "top1":v["new_top1_accuracy"],"top2":v["new_top2_accuracy"],
          "top1_net":v["top1_net_hits"],"top2_net":v["top2_net_hits"],"changed":v["changed"],
          "groups":v["groups"],
          "protected":{t:v["by_actual"][t] for t in sorted(PROTECTED)}
        }
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
