import json, math, os, re, subprocess, sys
from copy import deepcopy
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer

ARCHIVES = {
    "dev1": "archive/hh520-research-20260501-0630-v35d.json",
    "dev2": "archive/hh520-research-20260701-0831-v35e.json",
    "stress": "archive/hh520-research-20260901-0920-v35d.json",
}
POSTMATCH_KEYS = {
    "result","half_score","full_score","actual_score","actual_half_score",
    "actual_outcome","actual_total_goals","result_label","label_status",
    "label_match_method",
}

def load_branch(path):
    raw=subprocess.check_output(["git","show",f"origin/research-results:{path}"],text=True)
    return json.loads(raw)

def metric(rows, fn):
    n=h=0
    for r in rows:
        pred=fn(r)
        if pred is None: continue
        n+=1; h+=int(pred==str(r.get("actual_outcome") or "").upper())
    return {"n":n,"hits":h,"accuracy":h/n if n else None}

def wilson(h,n,z=1.96):
    if not n: return [None,None]
    p=h/n; den=1+z*z/n
    c=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,c-half),min(1,c+half)]

def features(r):
    p=r.get("probabilities") or {}; m=r.get("market_probabilities") or {}
    ph,pd,pa=[float(p.get(k,0)) for k in ("home","draw","away")]
    md=float(m.get("draw",0))
    hs=float(r.get("home_share") or 0.5)
    return {"ph":ph,"pd":pd,"pa":pa,"market_pd":md,"side_gap":abs(ph-pa),
            "draw_top_gap":max(ph,pa)-pd,"pmax":max(ph,pd,pa),
            "home_share_dev":abs(hs-0.5)}

def rule_from_params(q):
    def fn(r):
        f=features(r)
        if f["pd"]<q["pd_min"]: return None
        if f["side_gap"]>q["side_gap_max"]: return None
        if f["draw_top_gap"]>q["draw_top_gap_max"]: return None
        if f["pmax"]>q.get("pmax_max",1): return None
        if f["market_pd"]<q.get("market_pd_min",0): return None
        if f["home_share_dev"]>q.get("home_share_dev_max",.5): return None
        return "DRAW"
    return fn

def combine(a,b):
    n=a["n"]+b["n"]; h=a["hits"]+b["hits"]
    return {"n":n,"hits":h,"accuracy":h/n if n else None,"wilson95":wilson(h,n)}

def draw_search(rows):
    baseline={}
    for split,rr in rows.items():
        n=len(rr); h=sum(str(x.get("actual_outcome")).upper()=="DRAW" for x in rr)
        baseline[split]={"n":n,"draws":h,"rate":h/n if n else None,"wilson95":wilson(h,n)}
    base=[]
    for pd_min in [x/100 for x in range(22,35)]:
      for sg in [x/100 for x in range(4,21,2)]:
       for tg in [x/100 for x in range(2,19,2)]:
        q={"pd_min":pd_min,"side_gap_max":sg,"draw_top_gap_max":tg}
        fn=rule_from_params(q); a=metric(rows["dev1"],fn); b=metric(rows["dev2"],fn)
        if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=50:
            c=combine(a,b); base.append({"params":q,"dev1":a,"dev2":b,"dev":c,
                                        "stability":min(a["accuracy"],b["accuracy"])})
    base.sort(key=lambda x:(x["stability"],x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
    expanded=[]
    for seed in base[:60]:
      for pmax,mpd,hsd in product([.36,.38,.40,.42,.45,.50,1.0],[0,.24,.26,.28,.30],[.08,.12,.16,.20,.30,.50]):
        q=dict(seed["params"],pmax_max=pmax,market_pd_min=mpd,home_share_dev_max=hsd)
        fn=rule_from_params(q); a=metric(rows["dev1"],fn); b=metric(rows["dev2"],fn)
        if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=50:
            c=combine(a,b); expanded.append({"params":q,"dev1":a,"dev2":b,"dev":c,
                                              "stability":min(a["accuracy"],b["accuracy"])})
    dedup={tuple(sorted(x["params"].items())):x for x in expanded}
    candidates=list(dedup.values())
    candidates.sort(key=lambda x:((x["dev"]["wilson95"][0] or 0),x["stability"],x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
    def finish(x):
        if not x:return None
        y=json.loads(json.dumps(x)); fn=rule_from_params(y["params"])
        y["stress"]=metric(rows["stress"],fn)
        y["stress"]["wilson95"]=wilson(y["stress"]["hits"],y["stress"]["n"])
        override_compare={}
        for split, rr in rows.items():
            selected=draw_hits=base_hits=0
            for r in rr:
                if fn(r)!="DRAW":
                    continue
                selected+=1
                actual=str(r.get("actual_outcome") or "").upper()
                p=r.get("probabilities") or {}
                base=max(("home","draw","away"), key=lambda k: float(p.get(k,0.0))).upper()
                draw_hits+=int(actual=="DRAW")
                base_hits+=int(actual==base)
            override_compare[split]={
                "n":selected,
                "draw_hits":draw_hits,
                "draw_accuracy":draw_hits/selected if selected else None,
                "base_argmax_hits":base_hits,
                "base_argmax_accuracy":base_hits/selected if selected else None,
                "net_hits_if_override":draw_hits-base_hits,
            }
        y["override_compare"]=override_compare
        return y
    return {"baseline":baseline,"candidate_count":len(candidates),
            "final_selected_on_dev_only":finish(candidates[0] if candidates else None),
            "top10_dev_only":[finish(x) for x in candidates[:10]],"stress_used_for_selection":False}

def parse_score(v):
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

def outcome(pair):
    if not pair:return None
    return "HOME" if pair[0]>pair[1] else "AWAY" if pair[0]<pair[1] else "DRAW"

def split_for_day(day):
    if "2026-05-01"<=day<="2026-06-30": return "dev1"
    if "2026-07-01"<=day<="2026-08-31": return "dev2"
    if "2026-09-01"<=day<="2026-09-20": return "stress"
    return None

def load_cache_rows():
    out={"dev1":[],"dev2":[],"stress":[]}
    files=sorted(Path("cache").glob("10027s_2026-*.json"))
    parsed_files=0
    for path in files:
        day=path.stem.replace("10027s_","")
        split=split_for_day(day)
        if not split: continue
        try:
            payload=json.loads(path.read_text(encoding="utf-8"))
            raw=payload.get("raw") or {}
            markdown=((raw.get("data") or {}).get("markdown"))
            if not isinstance(markdown,str): continue
            matches=parse_10027s_markdown(markdown)
            parsed_files+=1
        except Exception:
            continue
        for m in matches:
            half=parse_score(m.get("half_score"))
            full=parse_score(m.get("result") or m.get("full_score"))
            if not half or not full: continue
            prematch=deepcopy(m)
            for k in POSTMATCH_KEYS: prematch.pop(k,None)
            p=probability_layer(prematch)
            if not p.get("valid"): continue
            out[split].append({
                "date":day,"match_id":m.get("match_id"),
                "home_team":m.get("home_team"),"away_team":m.get("away_team"),
                "actual_htft":f"{outcome(half)}_{outcome(full)}",
                "actual_half":outcome(half),"actual_full":outcome(full),
                "probabilities":p.get("probabilities"),
                "market_probabilities":p.get("market_probabilities"),
            })
    return out,{"cache_files_seen":len(files),"cache_files_parsed":parsed_files,
                "rows":{k:len(v) for k,v in out.items()}}

def pois(lam,n):
    arr=[math.exp(-lam)]
    for k in range(1,n+1): arr.append(arr[-1]*lam/k)
    return arr

GRID=[]
for ih in range(44):
    lh=.2+.1*ih
    hp=pois(lh,8)
    for ia in range(44):
        la=.2+.1*ia; ap=pois(la,8)
        w={"home":0.0,"draw":0.0,"away":0.0}
        for h,ph in enumerate(hp):
          for a,pa in enumerate(ap):
            w["home" if h>a else "away" if h<a else "draw"]+=ph*pa
        s=sum(w.values()) or 1
        GRID.append((lh,la,{k:v/s for k,v in w.items()}))

def fit_lambdas(p):
    return min(GRID,key=lambda g:sum((g[2][k]-float(p[k]))**2 for k in ("home","draw","away")))[:2]

_JOINT_CACHE={}
def joint_htft(lh,la,home_half_share,away_half_share):
    key=(lh,la,home_half_share,away_half_share)
    if key in _JOINT_CACHE:return _JOINT_CACHE[key]
    h1,a1=pois(lh*home_half_share,5),pois(la*away_half_share,5)
    h2,a2=pois(lh*(1-home_half_share),6),pois(la*(1-away_half_share),6)
    dist={f"{x}_{y}":0.0 for x in ("HOME","DRAW","AWAY") for y in ("HOME","DRAW","AWAY")}
    for hh,phh in enumerate(h1):
      for ah,pah in enumerate(a1):
       ht=outcome((hh,ah))
       for hs,phs in enumerate(h2):
        for aas,pas in enumerate(a2):
         ft=outcome((hh+hs,ah+aas))
         dist[f"{ht}_{ft}"]+=phh*pah*phs*pas
    s=sum(dist.values()) or 1
    ans={k:v/s for k,v in dist.items()}
    _JOINT_CACHE[key]=ans
    return ans

def prep_ht_rows(cache_rows):
    out={}
    for split,rr in cache_rows.items():
        vals=[]
        for r in rr:
            lh,la=fit_lambdas(r["probabilities"])
            vals.append(dict(r,lh=lh,la=la))
        out[split]=vals
    return out

def eval_ht(rows,hs,as_):
    n=h1=h2=0; by_actual={}
    for r in rows:
        dist=joint_htft(r["lh"],r["la"],hs,as_)
        ranked=sorted(dist,key=dist.get,reverse=True)
        actual=r["actual_htft"]; n+=1
        h1+=int(actual==ranked[0]); h2+=int(actual in ranked[:2])
        b=by_actual.setdefault(actual,{"n":0,"top1_hits":0,"top2_hits":0})
        b["n"]+=1;b["top1_hits"]+=int(actual==ranked[0]);b["top2_hits"]+=int(actual in ranked[:2])
    for b in by_actual.values():
        b["top1_accuracy"]=b["top1_hits"]/b["n"] if b["n"] else None
        b["top2_accuracy"]=b["top2_hits"]/b["n"] if b["n"] else None
    return {"n":n,"top1_hits":h1,"top1_accuracy":h1/n if n else None,
            "top2_hits":h2,"top2_accuracy":h2/n if n else None,"by_actual":by_actual}

def htft_search(cache_rows,cache_meta,data):
    rows=prep_ht_rows(cache_rows)
    counts={k:len(v) for k,v in rows.items()}
    existing={k:((v.get("backtest") or {}).get("metrics") or {}).get("half_time") for k,v in data.items()}
    if min(counts["dev1"],counts["dev2"])<30:
        return {"status":"INSUFFICIENT_RESTORED_CACHE_LABELS","label_counts":counts,
                "cache_meta":cache_meta,"existing_aggregate_metrics":existing,
                "formal_promotion_recommended":False}
    common=[]
    for s in [x/100 for x in range(32,59)]:
        a=eval_ht(rows["dev1"],s,s); b=eval_ht(rows["dev2"],s,s)
        common.append({"home_half_share":s,"away_half_share":s,"dev1":a,"dev2":b,
                       "stability_top2":min(a["top2_accuracy"],b["top2_accuracy"]),
                       "stability_top1":min(a["top1_accuracy"],b["top1_accuracy"])})
    common.sort(key=lambda x:(x["stability_top2"],x["stability_top1"],
                              x["dev1"]["top2_hits"]+x["dev2"]["top2_hits"]),reverse=True)
    center=common[0]["home_half_share"]
    vals=sorted(set(max(.25,min(.65,round(center+d,2))) for d in (-.08,-.06,-.04,-.02,0,.02,.04,.06,.08)))
    combos=[]
    for hs in vals:
      for aas in vals:
        a=eval_ht(rows["dev1"],hs,aas); b=eval_ht(rows["dev2"],hs,aas)
        combos.append({"home_half_share":hs,"away_half_share":aas,"dev1":a,"dev2":b,
                       "stability_top2":min(a["top2_accuracy"],b["top2_accuracy"]),
                       "stability_top1":min(a["top1_accuracy"],b["top1_accuracy"])})
    combos.sort(key=lambda x:(x["stability_top2"],x["stability_top1"],
                              x["dev1"]["top2_hits"]+x["dev2"]["top2_hits"]),reverse=True)
    best=json.loads(json.dumps(combos[0]))
    best["stress"]=eval_ht(rows["stress"],best["home_half_share"],best["away_half_share"])
    return {"status":"READY","model":"INDEPENDENT_POISSON_SPLIT_HTFT_V2",
            "label_counts":counts,"cache_meta":cache_meta,
            "selected_on_dev_only":best,"top10_dev_only":combos[:10],
            "stress_used_for_selection":False,
            "existing_aggregate_metrics":existing,
            "formal_base_promotion_recommended":True,
            "goal_timing_policy":{
                "historical_timing_collection":False,
                "formal_prediction_day_timing_required":True,
                "timing_role":"bounded first-half intensity adjustment only",
                "missing_or_abnormal_timing":"HTFT_PASS",
                "may_change_ft_core":False
            }}

if os.getenv("HH520_OPTIMIZER_OFFLINE_ONLY")!="1":
    raise SystemExit("offline-only guard missing")

data={k:load_branch(v) for k,v in ARCHIVES.items()}
archive_rows={k:((v.get("v35_ft_dataset") or {}).get("rows") or []) for k,v in data.items()}
cache_rows,cache_meta=load_cache_rows()
out={
 "mode":"OFFLINE_EXISTING_ARCHIVES_AND_ACTIONS_CACHE_ONLY",
 "recollection":False,"goal_timing_collected":False,
 "archive_paths":ARCHIVES,
 "sample_counts":{k:len(v) for k,v in archive_rows.items()},
 "draw_optimizer":draw_search(archive_rows),
 "htft_optimizer":htft_search(cache_rows,cache_meta,data),
}
Path("_draw_htft_final.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({
 "draw":out["draw_optimizer"]["final_selected_on_dev_only"],
 "htft_status":out["htft_optimizer"].get("status"),
 "htft_counts":out["htft_optimizer"].get("label_counts"),
 "htft_selected":out["htft_optimizer"].get("selected_on_dev_only"),
},ensure_ascii=False,indent=2))
