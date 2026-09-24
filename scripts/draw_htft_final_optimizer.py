import json, math, os, re, subprocess, sys
import numpy as np
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


def compare_override(rows, fn):
    selected=draw_hits=base_hits=0
    for r in rows:
        if fn(r)!="DRAW":
            continue
        selected+=1
        actual=str(r.get("actual_outcome") or "").upper()
        p=r.get("probabilities") or {}
        base=max(("home","draw","away"), key=lambda k: float(p.get(k,0.0))).upper()
        draw_hits+=int(actual=="DRAW")
        base_hits+=int(actual==base)
    return {
        "n":selected,
        "draw_hits":draw_hits,
        "draw_accuracy":draw_hits/selected if selected else None,
        "base_argmax_hits":base_hits,
        "base_argmax_accuracy":base_hits/selected if selected else None,
        "net_hits_if_override":draw_hits-base_hits,
        "net_rate":(draw_hits-base_hits)/selected if selected else None,
    }

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
            c=combine(a,b); ca=compare_override(rows["dev1"],fn); cb=compare_override(rows["dev2"],fn)
            base.append({"params":q,"dev1":a,"dev2":b,"dev":c,
                         "stability":min(a["accuracy"],b["accuracy"]),
                         "override_dev1":ca,"override_dev2":cb,
                         "override_min_net_rate":min(ca["net_rate"],cb["net_rate"]),
                         "override_total_net_hits":ca["net_hits_if_override"]+cb["net_hits_if_override"]})
    base.sort(key=lambda x:(x["override_min_net_rate"],x["override_total_net_hits"],
                            x["stability"],x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
    expanded=[]
    for seed in base[:120]:
      for pmax,mpd,hsd in product([.36,.38,.40,.42,.45,.50,1.0],[0,.24,.26,.28,.30],[.08,.12,.16,.20,.30,.50]):
        q=dict(seed["params"],pmax_max=pmax,market_pd_min=mpd,home_share_dev_max=hsd)
        fn=rule_from_params(q); a=metric(rows["dev1"],fn); b=metric(rows["dev2"],fn)
        if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=50:
            c=combine(a,b); ca=compare_override(rows["dev1"],fn); cb=compare_override(rows["dev2"],fn)
            expanded.append({"params":q,"dev1":a,"dev2":b,"dev":c,
                             "stability":min(a["accuracy"],b["accuracy"]),
                             "override_dev1":ca,"override_dev2":cb,
                             "override_min_net_rate":min(ca["net_rate"],cb["net_rate"]),
                             "override_total_net_hits":ca["net_hits_if_override"]+cb["net_hits_if_override"]})
    dedup={tuple(sorted(x["params"].items())):x for x in expanded}
    candidates=list(dedup.values())
    safe=[x for x in candidates
          if x["override_dev1"]["net_hits_if_override"]>0
          and x["override_dev2"]["net_hits_if_override"]>0]
    ranked=safe if safe else candidates
    ranked.sort(key=lambda x:(x["override_min_net_rate"],x["override_total_net_hits"],
                              (x["dev"]["wilson95"][0] or 0),x["stability"],
                              x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
    def finish(x):
        if not x:return None
        y=json.loads(json.dumps(x)); fn=rule_from_params(y["params"])
        y["stress"]=metric(rows["stress"],fn)
        y["stress"]["wilson95"]=wilson(y["stress"]["hits"],y["stress"]["n"])
        y["override_compare"]={split:compare_override(rr,fn) for split,rr in rows.items()}
        return y
    return {"baseline":baseline,"candidate_count":len(candidates),
            "safe_positive_net_candidate_count":len(safe),
            "selection_objective":"positive_net_hits_vs_base_argmax_in_both_dev_splits",
            "final_selected_on_dev_only":finish(ranked[0] if ranked else None),
            "top10_dev_only":[finish(x) for x in ranked[:10]],"stress_used_for_selection":False}

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
                "home_share":p.get("home_share"),
                "actual_outcome":outcome(full),
                "research_factors":deepcopy(m.get("research_factors") or {}),
                "possession":deepcopy(m.get("possession") or {}),
            })
    return out,{"cache_files_seen":len(files),"cache_files_parsed":parsed_files,
                "rows":{k:len(v) for k,v in out.items()}}


def _num(v):
    try:
        return float(v)
    except (TypeError,ValueError):
        return None

def factor_features(r):
    f=r.get("research_factors") or {}
    p=r.get("possession") or {}
    def gap(name):
        h=_num(f.get("home_"+name)); a=_num(f.get("away_"+name))
        return abs(h-a) if h is not None and a is not None else None
    hp=_num(p.get("home")); ap=_num(p.get("away"))
    return {
        "attack_gap":gap("attack"),
        "defense_gap":gap("defense"),
        "h2h_gap":gap("h2h"),
        "form_gap":gap("form"),
        "possession_gap":abs(hp-ap) if hp is not None and ap is not None else None,
    }

def factor_draw_search(rows):
    # Start from probability-balanced families, then refine by structural symmetry.
    prob_seeds=[]
    for pd_min in [0.26,0.27,0.28,0.29,0.30,0.31]:
      for sg in [0.08,0.10,0.12,0.14,0.16,0.18,0.20]:
       for tg in [0.08,0.10,0.12,0.14,0.16,0.18]:
        for pmax in [0.38,0.40,0.42,0.45,0.50]:
         q={"pd_min":pd_min,"side_gap_max":sg,"draw_top_gap_max":tg,
            "pmax_max":pmax,"market_pd_min":0.0,"home_share_dev_max":0.20}
         fn=rule_from_params(q)
         a=compare_override(rows["dev1"],fn); b=compare_override(rows["dev2"],fn)
         if a["n"]>=12 and b["n"]>=12:
            prob_seeds.append((min(a["net_rate"],b["net_rate"]),a["net_hits_if_override"]+b["net_hits_if_override"],q))
    prob_seeds.sort(reverse=True,key=lambda x:(x[0],x[1]))
    prob_seeds=prob_seeds[:80]

    thresholds={
      "attack_gap":[0.5,1.0,1.5,2.0,3.0,999.0],
      "defense_gap":[0.15,0.25,0.4,0.6,1.0,999.0],
      "h2h_gap":[1.0,2.0,3.0,4.0,6.0,999.0],
      "form_gap":[0.15,0.25,0.4,0.6,1.0,999.0],
      "possession_gap":[3.0,5.0,8.0,12.0,20.0,999.0],
    }

    candidates=[]
    # One or two structural symmetry gates; keep the search interpretable.
    names=list(thresholds)
    gate_sets=[(n,) for n in names]
    gate_sets += [(names[i],names[j]) for i in range(len(names)) for j in range(i+1,len(names))]
    for _,__,q in prob_seeds:
      basefn=rule_from_params(q)
      for gates in gate_sets:
        value_lists=[thresholds[g] for g in gates]
        for vals in product(*value_lists):
          limits=dict(zip(gates,vals))
          def fn(r,basefn=basefn,limits=limits):
            if basefn(r)!="DRAW": return None
            ff=factor_features(r)
            for k,lim in limits.items():
                v=ff.get(k)
                if v is None or v>lim: return None
            return "DRAW"
          a=compare_override(rows["dev1"],fn); b=compare_override(rows["dev2"],fn)
          if a["n"]<10 or b["n"]<10: continue
          if a["net_hits_if_override"]<=0 or b["net_hits_if_override"]<=0: continue
          da=metric(rows["dev1"],fn); db=metric(rows["dev2"],fn)
          candidates.append({
            "probability_params":q,"factor_limits":limits,
            "dev1":da,"dev2":db,
            "override_dev1":a,"override_dev2":b,
            "min_net_rate":min(a["net_rate"],b["net_rate"]),
            "total_net_hits":a["net_hits_if_override"]+b["net_hits_if_override"],
            "coverage":a["n"]+b["n"],
          })
    candidates.sort(key=lambda x:(x["min_net_rate"],x["total_net_hits"],x["coverage"]),reverse=True)
    def finalize(x):
        if not x:return None
        q=x["probability_params"]; limits=x["factor_limits"]; basefn=rule_from_params(q)
        def fn(r):
            if basefn(r)!="DRAW": return None
            ff=factor_features(r)
            for k,lim in limits.items():
                v=ff.get(k)
                if v is None or v>lim:return None
            return "DRAW"
        y=json.loads(json.dumps(x))
        y["stress"]=metric(rows["stress"],fn)
        y["override_stress"]=compare_override(rows["stress"],fn)
        return y
    return {
      "candidate_count":len(candidates),
      "selection_objective":"positive_net_hits_vs_base_argmax_in_both_dev_splits_with_structural_symmetry",
      "stress_used_for_selection":False,
      "final_selected_on_dev_only":finalize(candidates[0] if candidates else None),
      "top10_dev_only":[finalize(x) for x in candidates[:10]],
    }


DRAW_LOGISTIC_FEATURES = [
    "pd","side_gap","draw_top_gap","pmax","market_pd","home_share_dev",
    "lambda_total","lambda_gap","attack_gap","defense_gap","h2h_gap","form_gap","possession_gap",
]

def logistic_features(r):
    cached=r.get("_logistic_features")
    if cached is not None:
        return cached
    f=features(r); ff=factor_features(r)
    lh,la=fit_lambdas(r.get("probabilities") or {})
    values={
        "pd":f["pd"],"side_gap":f["side_gap"],"draw_top_gap":f["draw_top_gap"],
        "pmax":f["pmax"],"market_pd":f["market_pd"],"home_share_dev":f["home_share_dev"],
        "lambda_total":lh+la,"lambda_gap":abs(lh-la),
        **ff,
    }
    cached=[0.0 if values.get(k) is None else float(values[k]) for k in DRAW_LOGISTIC_FEATURES]
    r["_logistic_features"]=cached
    return cached

def _fit_logistic(rows, feature_idx, l2):
    X=np.asarray([[logistic_features(r)[i] for i in feature_idx] for r in rows],dtype=float)
    y=np.asarray([1.0 if str(r.get("actual_outcome")).upper()=="DRAW" else 0.0 for r in rows],dtype=float)
    mean=X.mean(axis=0); std=X.std(axis=0); std[std<1e-8]=1.0
    X=(X-mean)/std
    X=np.column_stack([np.ones(len(X)),X])
    w=np.zeros(X.shape[1],dtype=float)
    for _ in range(1800):
        z=np.clip(X@w,-30,30); p=1/(1+np.exp(-z))
        grad=(X.T@(p-y))/len(y)
        grad[1:]+=l2*w[1:]/len(y)
        w-=0.08*grad
    return {"mean":mean,"std":std,"w":w,"feature_idx":feature_idx,"l2":l2}

def _predict_logistic(model, rows):
    X=np.asarray([[logistic_features(r)[i] for i in model["feature_idx"]] for r in rows],dtype=float)
    X=(X-model["mean"])/model["std"]
    X=np.column_stack([np.ones(len(X)),X])
    z=np.clip(X@model["w"],-30,30)
    return 1/(1+np.exp(-z))

def _override_from_scores(rows,scores,threshold,pmax_limit):
    n=draw_hits=base_hits=0
    for r,s in zip(rows,scores):
        p=r.get("probabilities") or {}
        base=max(("home","draw","away"),key=lambda k:float(p.get(k,0.0)))
        if base=="draw": continue
        if max(float(p.get(k,0.0)) for k in ("home","draw","away"))>pmax_limit: continue
        if float(s)<threshold: continue
        n+=1; actual=str(r.get("actual_outcome") or "").upper()
        draw_hits+=int(actual=="DRAW"); base_hits+=int(actual==base.upper())
    return {"n":n,"draw_hits":draw_hits,"draw_accuracy":draw_hits/n if n else None,
            "base_argmax_hits":base_hits,"base_argmax_accuracy":base_hits/n if n else None,
            "net_hits_if_override":draw_hits-base_hits,
            "net_rate":(draw_hits-base_hits)/n if n else None}

def draw_logistic_search(rows):
    # Symmetric cross-fit: train May-Jun -> validate Jul-Aug and vice versa.
    sets=[
      list(range(8)),                       # probability + goal intensity only
      list(range(13)),                      # all structural features
      [0,1,2,3,4,5,6,7,8,11,12],          # attack/form/possession
      [0,1,2,3,4,5,6,7,9,10,11,12],       # defense/H2H/form/possession
    ]
    candidates=[]
    for idx in sets:
      for l2 in (0.01,0.05,0.1,0.5,1.0,2.0):
        m12=_fit_logistic(rows["dev1"],idx,l2)
        s2=_predict_logistic(m12,rows["dev2"])
        m21=_fit_logistic(rows["dev2"],idx,l2)
        s1=_predict_logistic(m21,rows["dev1"])
        for threshold in [x/100 for x in range(25,71)]:
          for pmax_limit in (0.42,0.45,0.50,0.55):
            a=_override_from_scores(rows["dev1"],s1,threshold,pmax_limit)
            b=_override_from_scores(rows["dev2"],s2,threshold,pmax_limit)
            if a["n"]<12 or b["n"]<12: continue
            if a["net_hits_if_override"]<=0 or b["net_hits_if_override"]<=0: continue
            candidates.append({
              "feature_names":[DRAW_LOGISTIC_FEATURES[i] for i in idx],
              "feature_idx":idx,"l2":l2,"threshold":threshold,"pmax_limit":pmax_limit,
              "crossfit_dev1":a,"crossfit_dev2":b,
              "min_net_rate":min(a["net_rate"],b["net_rate"]),
              "total_net_hits":a["net_hits_if_override"]+b["net_hits_if_override"],
              "coverage":a["n"]+b["n"],
            })
    candidates.sort(key=lambda x:(x["min_net_rate"],x["total_net_hits"],x["coverage"]),reverse=True)
    if not candidates:
        return {"candidate_count":0,"final_selected_on_dev_only":None,
                "stress_used_for_selection":False}
    best=candidates[0]
    dev=rows["dev1"]+rows["dev2"]
    final_model=_fit_logistic(dev,best["feature_idx"],best["l2"])
    stress_scores=_predict_logistic(final_model,rows["stress"])
    stress=_override_from_scores(rows["stress"],stress_scores,best["threshold"],best["pmax_limit"])
    # Export frozen coefficients in raw-standardized form for deterministic Stable implementation.
    export={
      "feature_names":best["feature_names"],
      "mean":[float(x) for x in final_model["mean"]],
      "std":[float(x) for x in final_model["std"]],
      "weights":[float(x) for x in final_model["w"]],
      "threshold":best["threshold"],"pmax_limit":best["pmax_limit"],"l2":best["l2"],
    }
    out=json.loads(json.dumps(best))
    out["stress"]=stress; out["frozen_model"]=export
    return {"candidate_count":len(candidates),
            "selection_objective":"positive_net_draw_override_in_both_crossfit_dev_splits",
            "stress_used_for_selection":False,
            "final_selected_on_dev_only":out,
            "top10_dev_only":candidates[:10]}

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
 "draw_factor_optimizer":factor_draw_search(cache_rows),
 "draw_logistic_optimizer":draw_logistic_search(cache_rows),
 "htft_optimizer":htft_search(cache_rows,cache_meta,data),
}
Path("_draw_htft_final.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({
 "draw":out["draw_optimizer"]["final_selected_on_dev_only"],
 "htft_status":out["htft_optimizer"].get("status"),
 "htft_counts":out["htft_optimizer"].get("label_counts"),
 "htft_selected":out["htft_optimizer"].get("selected_on_dev_only"),
},ensure_ascii=False,indent=2))
