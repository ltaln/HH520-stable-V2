import json, math, os, re, sys
import numpy as np
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer
from engine.score_layer import _fit_lambdas, _poisson

PROTECTED={"HOME_HOME","AWAY_AWAY","DRAW_HOME"}
WEAK=("DRAW_DRAW","HOME_DRAW","AWAY_DRAW","DRAW_AWAY","HOME_AWAY","AWAY_HOME")
POSTMATCH_KEYS={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome",
                "actual_total_goals","result_label","label_status","label_match_method"}

FEATURES=(
 "ph","pd","pa","market_ph","market_pd","market_pa","pmax","side_gap","draw_top_gap",
 "home_share_dev","lambda_total","lambda_gap","attack_gap","defense_gap","h2h_gap","form_gap",
 "possession_gap","base_home_home","base_away_away","base_draw_home","base_draw_draw",
 "base_home_draw","base_away_draw","base_draw_away","base_home_away","base_away_home"
)

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

def _num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def _gap(f,name):
    h=_num(f.get("home_"+name)); a=_num(f.get("away_"+name))
    return abs(h-a) if h is not None and a is not None else 0.0

def joint_htft(lh,la,hs=.36,as_=.44):
    h1,a1=_poisson(lh*hs,6),_poisson(la*as_,6)
    h2,a2=_poisson(lh*(1-hs),7),_poisson(la*(1-as_),7)
    mass={f"{h}_{f}":0.0 for h in ("HOME","DRAW","AWAY") for f in ("HOME","DRAW","AWAY")}
    for hh,phh in enumerate(h1):
      for ah,pah in enumerate(a1):
       ht=outcome((hh,ah))
       for hs2,phs in enumerate(h2):
        for as2,pas in enumerate(a2):
         ft=outcome((hh+hs2,ah+as2))
         mass[f"{ht}_{ft}"]+=phh*pah*phs*pas
    s=sum(mass.values()) or 1
    return {k:v/s for k,v in mass.items()}

def load_rows():
    out={"dev1":[],"dev2":[],"stress":[]}
    files=sorted(Path("cache").glob("10027s_2026-*.json"))
    for path in files:
        day=path.stem.replace("10027s_","")
        split=split_for_day(day)
        if not split:continue
        try:
            payload=json.loads(path.read_text(encoding="utf-8"))
            md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
            if not isinstance(md,str):continue
            matches=parse_10027s_markdown(md)
        except Exception:
            continue
        for m in matches:
            half=parse_score(m.get("half_score"))
            full=parse_score(m.get("result") or m.get("full_score"))
            if not half or not full:continue
            prematch=deepcopy(m)
            for k in POSTMATCH_KEYS: prematch.pop(k,None)
            p=probability_layer(prematch)
            if not p.get("valid"):continue
            probs=p.get("probabilities") or {}
            fitted=_fit_lambdas(probs)
            if not fitted:continue
            _,lh,la=fitted
            base=joint_htft(lh,la)
            rf=deepcopy(m.get("research_factors") or {})
            pos=deepcopy(m.get("possession") or {})
            hp,ap=_num(pos.get("home")),_num(pos.get("away"))
            market=p.get("market_probabilities") or {}
            ph,pd,pa=[float(probs.get(k,0)) for k in ("home","draw","away")]
            feat={
              "ph":ph,"pd":pd,"pa":pa,
              "market_ph":float(market.get("home",0)),"market_pd":float(market.get("draw",0)),
              "market_pa":float(market.get("away",0)),"pmax":max(ph,pd,pa),
              "side_gap":abs(ph-pa),"draw_top_gap":max(ph,pa)-pd,
              "home_share_dev":abs(float(p.get("home_share") or .5)-.5),
              "lambda_total":lh+la,"lambda_gap":abs(lh-la),
              "attack_gap":_gap(rf,"attack"),"defense_gap":_gap(rf,"defense"),
              "h2h_gap":_gap(rf,"h2h"),"form_gap":_gap(rf,"form"),
              "possession_gap":abs(hp-ap) if hp is not None and ap is not None else 0.0,
            }
            for k in ("HOME_HOME","AWAY_AWAY","DRAW_HOME","DRAW_DRAW","HOME_DRAW","AWAY_DRAW","DRAW_AWAY","HOME_AWAY","AWAY_HOME"):
                feat["base_"+k.lower()]=float(base[k])
            out[split].append({
              "date":day,"match_id":m.get("match_id"),"home_team":m.get("home_team"),"away_team":m.get("away_team"),
              "actual_htft":f"{outcome(half)}_{outcome(full)}","features":feat,"base":base,
            })
    return out

def matrix(rows):
    return np.asarray([[r["features"][k] for k in FEATURES] for r in rows],dtype=float)

def fit_ovr(rows,target,l2=.5):
    X=matrix(rows); y=np.asarray([1.0 if r["actual_htft"]==target else 0.0 for r in rows])
    mean=X.mean(0); std=X.std(0); std[std<1e-8]=1.0
    X=(X-mean)/std; X=np.column_stack([np.ones(len(X)),X])
    w=np.zeros(X.shape[1])
    for _ in range(1600):
        z=np.clip(X@w,-30,30); pr=1/(1+np.exp(-z))
        grad=(X.T@(pr-y))/len(y); grad[1:]+=l2*w[1:]/len(y)
        w-=0.06*grad
    return {"mean":mean,"std":std,"w":w,"target":target,"l2":l2}

def score(model,rows):
    X=matrix(rows); X=(X-model["mean"])/model["std"]; X=np.column_stack([np.ones(len(X)),X])
    return 1/(1+np.exp(-np.clip(-(X@model["w"]),-30,30)))

def scores_by_type(models,rows):
    return {t:score(models[t],rows) for t in WEAK}

def rerank(row, weak_scores, gamma, min_score):
    base=row["base"]
    ranked=sorted(base,key=base.get,reverse=True)
    top1,top2=ranked[:2]
    locked=[x for x in (top1,top2) if x in PROTECTED]
    slots=2-len(locked)
    if slots<=0:
        final=[top1,top2]
        return final,False
    candidates=[x for x in (top1,top2) if x not in PROTECTED]
    # Weak types can compete only for non-protected slots.
    pool=set(candidates)
    for t in WEAK:
        if weak_scores.get(t,0)>=min_score:
            pool.add(t)
    def adj(t):
        return base.get(t,0.0)+gamma*weak_scores.get(t,0.0)
    chosen=sorted(pool,key=adj,reverse=True)[:slots]
    final=[]
    for x in (top1,top2):
        if x in PROTECTED and x not in final:
            final.append(x)
    for x in chosen:
        if x not in final: final.append(x)
    for x in ranked:
        if len(final)>=2:break
        if x not in final:final.append(x)
    # Preserve protected top1 exactly.
    if top1 in PROTECTED and final[0]!=top1:
        final.remove(top1); final.insert(0,top1)
    changed=final[:2]!=[top1,top2]
    return final[:2],changed

def evaluate(rows, scoremap, gamma=0.0, min_score=1.0):
    b1=b2=n1=n2=changed=0
    by={t:{"n":0,"base_top1":0,"base_top2":0,"new_top1":0,"new_top2":0} for t in WEAK+tuple(PROTECTED)}
    for i,r in enumerate(rows):
        base_rank=sorted(r["base"],key=r["base"].get,reverse=True)[:2]
        ws={t:float(scoremap[t][i]) for t in WEAK}
        new_rank,ch=rerank(r,ws,gamma,min_score)
        actual=r["actual_htft"]; changed+=int(ch)
        b1+=int(actual==base_rank[0]); b2+=int(actual in base_rank)
        n1+=int(actual==new_rank[0]); n2+=int(actual in new_rank)
        if actual in by:
            z=by[actual];z["n"]+=1;z["base_top1"]+=int(actual==base_rank[0]);z["base_top2"]+=int(actual in base_rank)
            z["new_top1"]+=int(actual==new_rank[0]);z["new_top2"]+=int(actual in new_rank)
    n=len(rows)
    for z in by.values():
        nn=z["n"] or 1
        for k in ("base_top1","base_top2","new_top1","new_top2"):
            z[k+"_rate"]=z[k]/nn if z["n"] else None
    return {"n":n,"changed":changed,
      "base_top1_hits":b1,"base_top1_accuracy":b1/n if n else None,
      "base_top2_hits":b2,"base_top2_accuracy":b2/n if n else None,
      "new_top1_hits":n1,"new_top1_accuracy":n1/n if n else None,
      "new_top2_hits":n2,"new_top2_accuracy":n2/n if n else None,
      "top1_net_hits":n1-b1,"top2_net_hits":n2-b2,"by_actual":by}

def main():
    if os.getenv("HH520_WEAK_HTFT_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    # Symmetric cross-fit for parameter selection.
    candidates=[]
    for l2 in (.1,.5,1.0,2.0):
      m12={t:fit_ovr(rows["dev1"],t,l2) for t in WEAK}
      m21={t:fit_ovr(rows["dev2"],t,l2) for t in WEAK}
      s2=scores_by_type(m12,rows["dev2"]); s1=scores_by_type(m21,rows["dev1"])
      for gamma in (0.15,0.25,0.35,0.5,0.75,1.0,1.5):
       for min_score in (0.08,0.10,0.12,0.15,0.18,0.22,0.26):
        e1=evaluate(rows["dev1"],s1,gamma,min_score); e2=evaluate(rows["dev2"],s2,gamma,min_score)
        # Strong protected structures must not lose any Top2 hits on either dev split.
        protected_ok=True
        for t in PROTECTED:
            if e1["by_actual"][t]["new_top2"]<e1["by_actual"][t]["base_top2"]:protected_ok=False
            if e2["by_actual"][t]["new_top2"]<e2["by_actual"][t]["base_top2"]:protected_ok=False
        if not protected_ok:continue
        weak_base=e1["by_actual"]; weak2=e2["by_actual"]
        weak_net1=sum(weak_base[t]["new_top2"]-weak_base[t]["base_top2"] for t in WEAK)
        weak_net2=sum(weak2[t]["new_top2"]-weak2[t]["base_top2"] for t in WEAK)
        if weak_net1<0 or weak_net2<0:continue
        candidates.append({"l2":l2,"gamma":gamma,"min_score":min_score,"dev1":e1,"dev2":e2,
                           "weak_net_dev1":weak_net1,"weak_net_dev2":weak_net2,
                           "min_weak_net":min(weak_net1,weak_net2),
                           "total_weak_net":weak_net1+weak_net2,
                           "total_top2_net":e1["top2_net_hits"]+e2["top2_net_hits"]})
    candidates.sort(key=lambda x:(x["min_weak_net"],x["total_weak_net"],x["total_top2_net"],
                                  -(x["dev1"]["changed"]+x["dev2"]["changed"])),reverse=True)
    best=candidates[0] if candidates else None
    stress=None; frozen=None
    if best:
        dev=rows["dev1"]+rows["dev2"]
        models={t:fit_ovr(dev,t,best["l2"]) for t in WEAK}
        ss=scores_by_type(models,rows["stress"])
        stress=evaluate(rows["stress"],ss,best["gamma"],best["min_score"])
        frozen={"l2":best["l2"],"gamma":best["gamma"],"min_score":best["min_score"],
                "feature_names":FEATURES,
                "models":{t:{
                  "mean":[float(x) for x in models[t]["mean"]],
                  "std":[float(x) for x in models[t]["std"]],
                  "weights":[float(x) for x in models[t]["w"]],
                } for t in WEAK}}
    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "target_weak_types":WEAK,
      "protected_types":sorted(PROTECTED),
      "sample_counts":{k:len(v) for k,v in rows.items()},
      "candidate_count":len(candidates),
      "selection_used_stress":False,
      "selection_objective":"increase_weak_type_top2_on_both_dev_splits_without_any_protected_top2_loss",
      "selected_on_dev_only":best,
      "stress":stress,
      "frozen_candidate":frozen,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED",
    }
    Path("_htft_weak_compensation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"sample_counts":out["sample_counts"],"candidate_count":len(candidates),
                      "selected":best and {k:best[k] for k in ("l2","gamma","min_score","weak_net_dev1","weak_net_dev2","total_top2_net")},
                      "stress":stress},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
