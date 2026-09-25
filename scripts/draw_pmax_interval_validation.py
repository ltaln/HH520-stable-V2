import json, math, os, re, sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer
from engine.score_layer import _fit_lambdas
from engine.decision_filter import DRAW_FEATURES,DRAW_MEAN,DRAW_STD,DRAW_WEIGHTS,DRAW_THRESHOLD
POSTMATCH_KEYS={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome","actual_total_goals","result_label","label_status","label_match_method"}
SPLITS={"dev1":("2026-05-01","2026-06-30"),"dev2":("2026-07-01","2026-08-31"),"stress":("2026-09-01","2026-09-20")}
def split_for_day(day):
    for k,(a,b) in SPLITS.items():
        if a<=day<=b:return k
def parse_score(v):
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None
def outcome(p):
    if not p:return None
    return "HOME" if p[0]>p[1] else "AWAY" if p[0]<p[1] else "DRAW"
def num(v):
    try:return float(v)
    except Exception:return None
def gap(factors,name):
    h=num(factors.get("home_"+name));a=num(factors.get("away_"+name))
    return abs(h-a) if h is not None and a is not None else 0.0
def draw_values(match,p):
    probs=p["probabilities"];market=p["market_probabilities"];fit=_fit_lambdas(probs)
    if fit is None:return None
    _,lh,la=fit;f=match.get("research_factors") or {};pos=match.get("possession") or {}
    hp,ap=num(pos.get("home")),num(pos.get("away"));ph,pd,pa=(float(probs[k]) for k in ("home","draw","away"))
    return {"pd":pd,"side_gap":abs(ph-pa),"draw_top_gap":max(ph,pa)-pd,"pmax":max(ph,pd,pa),
      "market_pd":float(market.get("draw",0.0)),"home_share_dev":abs(float(p.get("home_share",.5))-.5),
      "lambda_total":lh+la,"lambda_gap":abs(lh-la),"attack_gap":gap(f,"attack"),"defense_gap":gap(f,"defense"),
      "h2h_gap":gap(f,"h2h"),"form_gap":gap(f,"form"),"possession_gap":abs(hp-ap) if hp is not None and ap is not None else 0.0}
def draw_score(vals):
    z=DRAW_WEIGHTS[0]
    for i,name in enumerate(DRAW_FEATURES):z+=DRAW_WEIGHTS[i+1]*((vals[name]-DRAW_MEAN[i])/DRAW_STD[i])
    z=max(-30,min(30,z));return 1/(1+math.exp(-z))
def load():
    out={k:[] for k in SPLITS}
    for pth in sorted(Path("cache").glob("10027s_2026-*.json")):
        day=pth.stem.replace("10027s_","");sp=split_for_day(day)
        if not sp:continue
        try:
            payload=json.loads(pth.read_text(encoding="utf-8"));md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
            matches=parse_10027s_markdown(md or "")
        except Exception:continue
        for m in matches:
            full=parse_score(m.get("result") or m.get("full_score"))
            if not full:continue
            prem=deepcopy(m)
            for k in POSTMATCH_KEYS:prem.pop(k,None)
            pr=probability_layer(prem)
            if not pr.get("valid"):continue
            vals=draw_values(prem,pr)
            if not vals:continue
            probs=pr["probabilities"];base=max(("home","draw","away"),key=lambda k:float(probs[k]))
            if base=="draw":continue
            out[sp].append({"date":day,"actual":outcome(full),"base":base.upper(),"pmax":vals["pmax"],"score":draw_score(vals)})
    return out
def evaluate(rows,lo,hi,threshold=DRAW_THRESHOLD):
    n=draw=base=0
    for r in rows:
        if not (lo<=r["pmax"]<=hi) or r["score"]<threshold:continue
        n+=1;draw+=int(r["actual"]=="DRAW");base+=int(r["actual"]==r["base"])
    return {"n":n,"draw_hits":draw,"draw_acc":draw/n if n else None,"base_hits":base,"base_acc":base/n if n else None,
            "net_hits":draw-base,"net_rate":(draw-base)/n if n else None}
def main():
    if os.getenv("HH520_DRAW_INTERVAL_OFFLINE_ONLY")!="1":raise SystemExit("offline-only guard missing")
    rows=load();grid=[];vals=[x/100 for x in range(35,61)]
    for i,lo in enumerate(vals):
      for hi in vals[i:]:
        a=evaluate(rows["dev1"],lo,hi);b=evaluate(rows["dev2"],lo,hi)
        if a["n"]<8 or b["n"]<8:continue
        grid.append({"pmax_lo":lo,"pmax_hi":hi,"threshold":DRAW_THRESHOLD,"dev1":a,"dev2":b,
                     "min_net_rate":min(a["net_rate"],b["net_rate"]),"total_net_hits":a["net_hits"]+b["net_hits"],"coverage_dev":a["n"]+b["n"]})
    safe=[x for x in grid if x["dev1"]["net_hits"]>0 and x["dev2"]["net_hits"]>0]
    ranked=sorted(safe if safe else grid,key=lambda x:(x["min_net_rate"],x["total_net_hits"],x["coverage_dev"]),reverse=True)
    best=json.loads(json.dumps(ranked[0])) if ranked else None
    if best:best["stress"]=evaluate(rows["stress"],best["pmax_lo"],best["pmax_hi"])
    bands=[]
    for lo,hi in [(0.35,0.40),(0.40,0.45),(0.45,0.50),(0.50,0.55),(0.55,0.60),(0.35,0.45),(0.40,0.50),(0.45,0.55),(0.50,0.60)]:
        bands.append({"band":[lo,hi],"dev1":evaluate(rows["dev1"],lo,hi),"dev2":evaluate(rows["dev2"],lo,hi),"stress":evaluate(rows["stress"],lo,hi)})
    out={"mode":"OFFLINE_EXISTING_MAY_SEP_CACHE_ONLY","threshold_fixed":DRAW_THRESHOLD,"sample_counts":{k:len(v) for k,v in rows.items()},
         "candidate_intervals":len(grid),"safe_positive_both_dev":len(safe),"selected_on_may_aug_only":best,"stress_used_for_selection":False,
         "fixed_bands":bands,"note":"Frozen V3.5.1 draw logistic score; only pmax eligibility interval is varied."}
    Path("_draw_pmax_interval.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
