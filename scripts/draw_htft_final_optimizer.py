import json, math, subprocess
from pathlib import Path
from itertools import product

ARCHIVES = {
    "dev1": "archive/hh520-research-20260501-0630-v35d.json",
    "dev2": "archive/hh520-research-20260701-0831-v35e.json",
    "stress": "archive/hh520-research-20260901-0920-v35d.json",
}

def load_branch(path):
    raw = subprocess.check_output(["git","show",f"origin/research-results:{path}"], text=True)
    return json.loads(raw)

def metric(rows, fn):
    n = h = 0
    for r in rows:
        pred = fn(r)
        if pred is None:
            continue
        n += 1
        h += int(pred == str(r.get("actual_outcome") or "").upper())
    return {"n": n, "hits": h, "accuracy": h/n if n else None}

def wilson(h, n, z=1.96):
    if not n:
        return [None, None]
    p = h/n
    den = 1 + z*z/n
    center = (p + z*z/(2*n))/den
    half = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,center-half), min(1,center+half)]

def features(r):
    p = r.get("probabilities") or {}
    m = r.get("market_probabilities") or {}
    ph,pd,pa = (float(p.get("home",0)), float(p.get("draw",0)), float(p.get("away",0)))
    mh,md,ma = (float(m.get("home",0)), float(m.get("draw",0)), float(m.get("away",0)))
    pmax = max(ph,pd,pa)
    return {
        "ph":ph,"pd":pd,"pa":pa,
        "market_pd":md,
        "side_gap":abs(ph-pa),
        "draw_top_gap":max(ph,pa)-pd,
        "pmax":pmax,
        "home_share":float(r.get("home_share") or 0.5),
        "home_share_dev":abs(float(r.get("home_share") or 0.5)-0.5),
    }

def rule_from_params(params):
    def fn(r):
        f = features(r)
        if f["pd"] < params["pd_min"]: return None
        if f["side_gap"] > params["side_gap_max"]: return None
        if f["draw_top_gap"] > params["draw_top_gap_max"]: return None
        if f["pmax"] > params.get("pmax_max", 1.0): return None
        if f["market_pd"] < params.get("market_pd_min", 0.0): return None
        if f["home_share_dev"] > params.get("home_share_dev_max", 0.5): return None
        return "DRAW"
    return fn

def combined(a,b):
    n=a["n"]+b["n"]; h=a["hits"]+b["hits"]
    return {"n":n,"hits":h,"accuracy":h/n if n else None,"wilson95":wilson(h,n)}

def draw_search(rows):
    baseline={}
    for split, rr in rows.items():
        n=len(rr); h=sum(1 for r in rr if str(r.get("actual_outcome")).upper()=="DRAW")
        baseline[split]={"n":n,"draws":h,"rate":h/n if n else None,"wilson95":wilson(h,n)}

    base=[]
    for pd_min in [x/100 for x in range(22,35)]:
        for side_gap in [x/100 for x in range(4,21,2)]:
            for top_gap in [x/100 for x in range(2,19,2)]:
                params={"pd_min":pd_min,"side_gap_max":side_gap,"draw_top_gap_max":top_gap}
                fn=rule_from_params(params)
                a=metric(rows["dev1"],fn); b=metric(rows["dev2"],fn)
                if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=50:
                    c=combined(a,b)
                    base.append({"params":params,"dev1":a,"dev2":b,"dev":c,
                                 "stability":min(a["accuracy"],b["accuracy"])})
    base.sort(key=lambda x:(x["stability"],x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
    seeds=base[:60]

    expanded=[]
    for seed in seeds:
        p0=seed["params"]
        for pmax_max,market_pd_min,hsdev in product(
            [0.36,0.38,0.40,0.42,0.45,0.50,1.0],
            [0.0,0.24,0.26,0.28,0.30],
            [0.08,0.12,0.16,0.20,0.30,0.50]
        ):
            params=dict(p0,pmax_max=pmax_max,market_pd_min=market_pd_min,home_share_dev_max=hsdev)
            fn=rule_from_params(params)
            a=metric(rows["dev1"],fn); b=metric(rows["dev2"],fn)
            if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=50:
                c=combined(a,b)
                expanded.append({"params":params,"dev1":a,"dev2":b,"dev":c,
                                 "stability":min(a["accuracy"],b["accuracy"])})
    # dedupe
    seen=set(); uniq=[]
    for x in expanded:
        key=tuple(sorted(x["params"].items()))
        if key in seen: continue
        seen.add(key); uniq.append(x)
    expanded=uniq

    # Three objectives; stress never used for selection.
    precision=sorted(expanded,key=lambda x:(x["stability"],x["dev"]["accuracy"],x["dev"]["wilson95"][0] or 0,x["dev"]["n"]),reverse=True)
    balanced=sorted(expanded,key=lambda x:(
        (x["dev"]["wilson95"][0] or 0),
        x["stability"],
        x["dev"]["accuracy"],
        min(x["dev"]["n"]/150,1.0)
    ),reverse=True)
    coverage=sorted(expanded,key=lambda x:(
        x["dev"]["n"] if x["stability"]>=0.36 else 0,
        x["stability"],
        x["dev"]["accuracy"]
    ),reverse=True)

    def finish(x):
        if not x: return None
        y=json.loads(json.dumps(x))
        fn=rule_from_params(y["params"])
        y["stress"]=metric(rows["stress"],fn)
        y["stress"]["wilson95"]=wilson(y["stress"]["hits"],y["stress"]["n"])
        return y

    candidates={
        "precision":finish(precision[0] if precision else None),
        "balanced":finish(balanced[0] if balanced else None),
        "coverage":finish(coverage[0] if coverage else None),
    }
    # Choose final without using stress: balanced Wilson-LB candidate.
    final=candidates["balanced"]
    return {
        "baseline":baseline,
        "candidate_count":len(expanded),
        "objectives":candidates,
        "final_selected_on_dev_only":final,
        "top10_dev_only":[finish(x) for x in balanced[:10]],
        "stress_used_for_selection":False,
    }

def walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_dicts(v)

def norm_id(v):
    raw=str(v or "").strip()
    digits="".join(ch for ch in raw if ch.isdigit())
    return str(int(digits)) if digits else raw

def key(d):
    return (str(d.get("date") or "")[:10], norm_id(d.get("match_id")))

def parse_score(v):
    import re
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

def outcome(pair):
    if not pair: return None
    return "HOME" if pair[0]>pair[1] else "AWAY" if pair[0]<pair[1] else "DRAW"

def extract_ht_labels(archive):
    labels={}
    for d in walk_dicts(archive):
        half=d.get("actual_half_score") or d.get("half_score")
        full=d.get("actual_score") or d.get("full_score")
        if half and full and d.get("match_id") is not None:
            hp,fp=parse_score(half),parse_score(full)
            if hp and fp:
                labels[key(d)]={"half":hp,"full":fp,"actual_htft":f"{outcome(hp)}_{outcome(fp)}"}
    return labels

def pois(lam,n=7):
    out=[math.exp(-lam)]
    for k in range(1,n+1): out.append(out[-1]*lam/k)
    return out

GRID=[]
for ih in range(44):
    lh=.2+.1*ih
    for ia in range(44):
        la=.2+.1*ia
        hp,ap=pois(lh,8),pois(la,8)
        w={"home":0.0,"draw":0.0,"away":0.0}
        for h,ph in enumerate(hp):
            for a,pa in enumerate(ap):
                w["home" if h>a else "away" if h<a else "draw"] += ph*pa
        s=sum(w.values()) or 1
        GRID.append((lh,la,{k:v/s for k,v in w.items()}))

def fit_lambdas(p):
    return min(GRID,key=lambda g:sum((g[2][k]-float(p[k]))**2 for k in ("home","draw","away")))[:2]

def joint_htft(lh,la,share):
    h1,a1=pois(lh*share,6),pois(la*share,6)
    h2,a2=pois(lh*(1-share),7),pois(la*(1-share),7)
    dist={f"{x}_{y}":0.0 for x in ("HOME","DRAW","AWAY") for y in ("HOME","DRAW","AWAY")}
    for hh,phh in enumerate(h1):
        for ah,pah in enumerate(a1):
            ht=outcome((hh,ah))
            for hs,phs in enumerate(h2):
                for aas,pas in enumerate(a2):
                    ft=outcome((hh+hs,ah+aas))
                    dist[f"{ht}_{ft}"] += phh*pah*phs*pas
    s=sum(dist.values()) or 1.0
    return {k:v/s for k,v in dist.items()}

def htft_search(data, rows):
    labels={split:extract_ht_labels(data[split]) for split in data}
    joined={}
    for split,rr in rows.items():
        out=[]
        for r in rr:
            lab=labels[split].get(key(r))
            if not lab: continue
            p=r.get("probabilities") or {}
            if not all(k in p for k in ("home","draw","away")): continue
            lh,la=fit_lambdas(p)
            out.append({"actual":lab["actual_htft"],"lh":lh,"la":la})
        joined[split]=out

    result={"label_counts":{k:len(v) for k,v in joined.items()}}

    if min((len(joined["dev1"]),len(joined["dev2"]))) < 30:
        # Historical archives do not retain enough half-time labels for a defensible new formal fit.
        existing={}
        for split,archive in data.items():
            existing[split]=((archive.get("backtest") or {}).get("metrics") or {}).get("half_time")
        result.update({
            "status":"INSUFFICIENT_RETAINED_HALF_TIME_LABELS",
            "existing_aggregate_metrics":existing,
            "formal_promotion_recommended":False,
            "reason":"Existing archives do not retain per-match half-time labels joined to pre-match H/D/A features.",
        })
        return result

    candidates=[]
    for share in [x/100 for x in range(30,61)]:
        rec={"half_share":share}
        for split in ("dev1","dev2"):
            n=h1=h2=0
            for r in joined[split]:
                dist=joint_htft(r["lh"],r["la"],share)
                ranked=sorted(dist,key=dist.get,reverse=True)
                n+=1; h1+=int(r["actual"]==ranked[0]); h2+=int(r["actual"] in ranked[:2])
            rec[split]={"n":n,"top1_hits":h1,"top1_accuracy":h1/n if n else None,
                        "top2_hits":h2,"top2_accuracy":h2/n if n else None}
        rec["stability_top2"]=min(rec["dev1"]["top2_accuracy"],rec["dev2"]["top2_accuracy"])
        rec["stability_top1"]=min(rec["dev1"]["top1_accuracy"],rec["dev2"]["top1_accuracy"])
        candidates.append(rec)

    candidates.sort(key=lambda x:(x["stability_top2"],x["stability_top1"],
                                  x["dev1"]["top2_hits"]+x["dev2"]["top2_hits"]),reverse=True)
    best=candidates[0]
    share=best["half_share"]
    n=h1=h2=0
    for r in joined["stress"]:
        dist=joint_htft(r["lh"],r["la"],share)
        ranked=sorted(dist,key=dist.get,reverse=True)
        n+=1; h1+=int(r["actual"]==ranked[0]); h2+=int(r["actual"] in ranked[:2])
    best=json.loads(json.dumps(best))
    best["stress"]={"n":n,"top1_hits":h1,"top1_accuracy":h1/n if n else None,
                    "top2_hits":h2,"top2_accuracy":h2/n if n else None}
    result.update({
        "status":"READY",
        "formal_promotion_recommended":True,
        "selected_on_dev_only":best,
        "top10":candidates[:10],
        "stress_used_for_selection":False,
        "model":"INDEPENDENT_POISSON_SPLIT_HTFT_V2",
    })
    return result

data={k:load_branch(v) for k,v in ARCHIVES.items()}
rows={k:((v.get("v35_ft_dataset") or {}).get("rows") or []) for k,v in data.items()}

out={
    "mode":"OFFLINE_EXISTING_ARCHIVES_ONLY",
    "recollection":False,
    "goal_timing_collected":False,
    "archive_paths":ARCHIVES,
    "sample_counts":{k:len(v) for k,v in rows.items()},
    "draw_optimizer":draw_search(rows),
    "htft_optimizer":htft_search(data,rows),
}
Path("_draw_htft_final.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({
    "sample_counts":out["sample_counts"],
    "draw_final":out["draw_optimizer"]["final_selected_on_dev_only"],
    "htft_status":out["htft_optimizer"].get("status"),
    "htft_labels":out["htft_optimizer"].get("label_counts"),
    "htft_selected":out["htft_optimizer"].get("selected_on_dev_only"),
},ensure_ascii=False,indent=2))
