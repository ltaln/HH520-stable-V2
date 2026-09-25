import json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.htft_transition_research import load_rows, STATES, fit_multinomial, predict_conditional, build_joint, evaluate
from engine.htft_layer import htft_layer

def formal_mass(row):
    fake={"probability":{"valid":True,"probabilities":{
        "home":row["features"]["ph"],"draw":row["features"]["pd"],"away":row["features"]["pa"]
    }}}
    pred=htft_layer(fake["probability"])
    mass={}
    for x in pred.get("distribution",[]):
        code=f'{x["ht"]}_{x["ft"]}'
        mass[code]=float(x["probability"])
    return mass

def eval_rankings(rows, rankings):
    top1=top2=top3=0
    by={}
    for r,ranked in zip(rows,rankings):
        a=r["actual_htft"]; by.setdefault(a,{"n":0,"top1":0,"top2":0,"top3":0})
        z=by[a];z["n"]+=1
        top1+=a==ranked[0];top2+=a in ranked[:2];top3+=a in ranked[:3]
        z["top1"]+=a==ranked[0];z["top2"]+=a in ranked[:2];z["top3"]+=a in ranked[:3]
    n=len(rows)
    for z in by.values():
        z["top1_rate"]=z["top1"]/z["n"];z["top2_rate"]=z["top2"]/z["n"];z["top3_rate"]=z["top3"]/z["n"]
    return {"n":n,"top1_hits":top1,"top1_accuracy":top1/n,"top2_hits":top2,"top2_accuracy":top2/n,
            "top3_hits":top3,"top3_accuracy":top3/n,"by_actual":by}

def main():
    if os.getenv("HH520_HTFT_TRANSITION_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    dev=rows["dev1"]+rows["dev2"]
    stress=rows["stress"]
    l2=1.0
    models={ht:fit_multinomial(dev,ht,l2) for ht in STATES}
    probs={ht:predict_conditional(models[ht],stress) for ht in STATES}
    trans=build_joint(stress,probs)

    formal=[]; hybrid=[]; trans_rank=[]
    third_sources={}
    for r,tm in zip(stress,trans):
        fm=formal_mass(r)
        fr=sorted(fm,key=fm.get,reverse=True)
        tr=sorted(tm,key=tm.get,reverse=True)
        formal.append(fr)
        trans_rank.append(tr)
        third=next((x for x in tr if x not in fr[:2]), fr[2])
        hybrid.append(fr[:2]+[third])
        third_sources[third]=third_sources.get(third,0)+1

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "stress_window":"2026-09-01..2026-09-20",
      "selection_used_stress":False,
      "formal_baseline":eval_rankings(stress,formal),
      "transition_only":eval_rankings(stress,trans_rank),
      "hybrid_keep_formal_top2_transition_third":eval_rankings(stress,hybrid),
      "third_candidate_distribution":third_sources,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"
    }
    Path("_htft_transition_hybrid.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
