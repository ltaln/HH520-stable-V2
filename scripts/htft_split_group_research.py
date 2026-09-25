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
GROUPS={
  "DRAW_FINISH": ("DRAW_DRAW","HOME_DRAW","AWAY_DRAW"),
  "REVERSAL": ("HOME_AWAY","AWAY_HOME"),
  "DRAW_AWAY": ("DRAW_AWAY",),
}
ALL_TARGETS=tuple(t for g in GROUPS.values() for t in g)
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
    for path in sorted(Path("cache").glob("10027s_2026-*.json")):
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

def fit_binary(rows, positives, l2=.5):
    X=matrix(rows); y=np.asarray([1.0 if r["actual_htft"] in positives else 0.0 for r in rows])
    mean=X.mean(0); std=X.std(0); std[std<1e-8]=1.0
    X=(X-mean)/std; X=np.column_stack([np.ones(len(X)),X])
    w=np.zeros(X.shape[1])
    pos=max(1.0,y.sum()); neg=max(1.0,len(y)-pos)
    pos_weight=min(8.0,neg/pos)
    weights=np.where(y>0.5,pos_weight,1.0)
    for _ in range(1800):
        z=np.clip(X@w,-30,30); pr=1/(1+np.exp(-z))
        grad=(X.T@((pr-y)*weights))/len(y); grad[1:]+=l2*w[1:]/len(y)
        w-=0.04*grad
    return {"mean":mean,"std":std,"w":w,"l2":l2,"positives":tuple(positives)}

def pred(model, rows):
    X=matrix(rows); X=(X-model["mean"])/model["std"]; X=np.column_stack([np.ones(len(X)),X])
    return 1/(1+np.exp(-np.clip(X@model["w"],-30,30)))

def choose_subtype(group, row):
    # subtype selection is kept deterministic and prematch-only.
    if group=="DRAW_FINISH":
        candidates=GROUPS[group]
    elif group=="REVERSAL":
        candidates=GROUPS[group]
    else:
        candidates=GROUPS[group]
    return max(candidates,key=lambda t:row["base"].get(t,0.0))

def rerank(row, group_scores, cfg):
    base=row["base"]
    ranked=sorted(base,key=base.get,reverse=True)
    base_top=ranked[:2]
    locked=[x for x in base_top if x in PROTECTED]
    slots=2-len(locked)
    if slots<=0:
        return base_top,False,None
    pool=[x for x in base_top if x not in PROTECTED]
    fired=[]
    for g in ("DRAW_FINISH","REVERSAL","DRAW_AWAY"):
        sc=group_scores.get(g,0.0)
        if sc>=cfg[g]["threshold"]:
            subtype=choose_subtype(g,row)
            pool.append(subtype)
            fired.append((g,subtype,sc))
    def adjusted(t):
        bonus=0.0
        for g,sub,sc in fired:
            if t==sub:
                bonus=max(bonus,cfg[g]["gamma"]*sc)
        return base.get(t,0.0)+bonus
    chosen=sorted(set(pool),key=adjusted,reverse=True)[:slots]
    final=[]
    for x in base_top:
        if x in PROTECTED and x not in final:final.append(x)
    for x in chosen:
        if x not in final:final.append(x)
    for x in ranked:
        if len(final)>=2:break
        if x not in final:final.append(x)
    if base_top[0] in PROTECTED and final[0]!=base_top[0]:
        final.remove(base_top[0]);final.insert(0,base_top[0])
    return final[:2],final[:2]!=base_top,fired

def evaluate(rows, scoremaps, cfg):
    b1=b2=n1=n2=changed=0
    by={t:{"n":0,"base_top1":0,"base_top2":0,"new_top1":0,"new_top2":0} for t in tuple(ALL_TARGETS)+tuple(PROTECTED)}
    group_stats={g:{"actual_n":0,"base_top2":0,"new_top2":0,"triggered":0,"trigger_hits":0} for g in GROUPS}
    for i,r in enumerate(rows):
        base_rank=sorted(r["base"],key=r["base"].get,reverse=True)[:2]
        gs={g:float(scoremaps[g][i]) for g in GROUPS}
        new_rank,ch,fired=rerank(r,gs,cfg)
        actual=r["actual_htft"];changed+=int(ch)
        b1+=int(actual==base_rank[0]);b2+=int(actual in base_rank)
        n1+=int(actual==new_rank[0]);n2+=int(actual in new_rank)
        if actual in by:
            z=by[actual];z["n"]+=1;z["base_top1"]+=int(actual==base_rank[0]);z["base_top2"]+=int(actual in base_rank)
            z["new_top1"]+=int(actual==new_rank[0]);z["new_top2"]+=int(actual in new_rank)
        for g,types in GROUPS.items():
            if actual in types:
                group_stats[g]["actual_n"]+=1
                group_stats[g]["base_top2"]+=int(actual in base_rank)
                group_stats[g]["new_top2"]+=int(actual in new_rank)
        for item in (fired or []):
            g,sub,sc=item
            group_stats[g]["triggered"]+=1
            group_stats[g]["trigger_hits"]+=int(actual==sub)
    n=len(rows)
    for z in by.values():
        nn=z["n"] or 1
        for k in ("base_top1","base_top2","new_top1","new_top2"):
            z[k+"_rate"]=z[k]/nn if z["n"] else None
    for z in group_stats.values():
        an=z["actual_n"] or 1;tr=z["triggered"] or 1
        z["base_top2_rate"]=z["base_top2"]/an if z["actual_n"] else None
        z["new_top2_rate"]=z["new_top2"]/an if z["actual_n"] else None
        z["trigger_precision"]=z["trigger_hits"]/tr if z["triggered"] else None
    return {"n":n,"changed":changed,
      "base_top1_hits":b1,"base_top1_accuracy":b1/n if n else None,
      "base_top2_hits":b2,"base_top2_accuracy":b2/n if n else None,
      "new_top1_hits":n1,"new_top1_accuracy":n1/n if n else None,
      "new_top2_hits":n2,"new_top2_accuracy":n2/n if n else None,
      "top1_net_hits":n1-b1,"top2_net_hits":n2-b2,"by_actual":by,"groups":group_stats}

def protected_ok(e):
    for t in PROTECTED:
        if e["by_actual"][t]["new_top2"]<e["by_actual"][t]["base_top2"]:
            return False
    return True

def weak_net(e, group):
    return sum(e["by_actual"][t]["new_top2"]-e["by_actual"][t]["base_top2"] for t in GROUPS[group])

def frozen_group_models(rows,l2):
    return {g:fit_binary(rows,GROUPS[g],l2) for g in GROUPS}

def scoremaps(models,rows):
    return {g:pred(models[g],rows) for g in GROUPS}

def default_cfg():
    return {g:{"threshold":1.1,"gamma":0.0} for g in GROUPS}

def main():
    if os.getenv("HH520_SPLIT_HTFT_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    grid_threshold=(0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70)
    grid_gamma=(0.10,0.15,0.20,0.30,0.40,0.60,0.80)
    l2_grid=(0.1,0.5,1.0,2.0)

    # symmetric cross-fit score maps for each l2
    cache={}
    for l2 in l2_grid:
        m1=frozen_group_models(rows["dev1"],l2)
        m2=frozen_group_models(rows["dev2"],l2)
        cache[l2]=(scoremaps(m2,rows["dev1"]),scoremaps(m1,rows["dev2"]))

    selected_groups={}
    for group in ("DRAW_FINISH","REVERSAL","DRAW_AWAY"):
        cand=[]
        for l2 in l2_grid:
            s1,s2=cache[l2]
            for th in grid_threshold:
                for gamma in grid_gamma:
                    cfg=default_cfg();cfg[group]={"threshold":th,"gamma":gamma}
                    e1=evaluate(rows["dev1"],s1,cfg);e2=evaluate(rows["dev2"],s2,cfg)
                    if not protected_ok(e1) or not protected_ok(e2):continue
                    wn1,wn2=weak_net(e1,group),weak_net(e2,group)
                    if wn1<0 or wn2<0:continue
                    cand.append({"group":group,"l2":l2,"threshold":th,"gamma":gamma,
                                 "dev1":e1,"dev2":e2,"weak_net_dev1":wn1,"weak_net_dev2":wn2,
                                 "min_weak_net":min(wn1,wn2),"total_weak_net":wn1+wn2,
                                 "total_top2_net":e1["top2_net_hits"]+e2["top2_net_hits"],
                                 "changed":e1["changed"]+e2["changed"]})
        cand.sort(key=lambda x:(x["min_weak_net"],x["total_weak_net"],x["total_top2_net"],-x["changed"]),reverse=True)
        selected_groups[group]=cand[0] if cand else None

    # Compose independently selected group rules. Each group keeps its own l2.
    final_cfg=default_cfg()
    final_models_dev={}
    final_score_dev1={};final_score_dev2={}
    for g,sel in selected_groups.items():
        if not sel:continue
        final_cfg[g]={"threshold":sel["threshold"],"gamma":sel["gamma"]}
        m1=fit_binary(rows["dev1"],GROUPS[g],sel["l2"])
        m2=fit_binary(rows["dev2"],GROUPS[g],sel["l2"])
        final_score_dev1[g]=pred(m2,rows["dev1"])
        final_score_dev2[g]=pred(m1,rows["dev2"])
    # fill missing groups with zeros
    for g in GROUPS:
        if g not in final_score_dev1:
            final_score_dev1[g]=np.zeros(len(rows["dev1"]))
            final_score_dev2[g]=np.zeros(len(rows["dev2"]))
    composed_dev1=evaluate(rows["dev1"],final_score_dev1,final_cfg)
    composed_dev2=evaluate(rows["dev2"],final_score_dev2,final_cfg)

    # Freeze on dev1+dev2 and evaluate stress only once.
    stress_scores={}
    frozen={}
    dev=rows["dev1"]+rows["dev2"]
    for g,sel in selected_groups.items():
        if sel:
            m=fit_binary(dev,GROUPS[g],sel["l2"])
            stress_scores[g]=pred(m,rows["stress"])
            frozen[g]={"l2":sel["l2"],"threshold":sel["threshold"],"gamma":sel["gamma"],
                       "mean":[float(x) for x in m["mean"]],"std":[float(x) for x in m["std"]],
                       "weights":[float(x) for x in m["w"]]}
        else:
            stress_scores[g]=np.zeros(len(rows["stress"]))
    stress=evaluate(rows["stress"],stress_scores,final_cfg)

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "sample_counts":{k:len(v) for k,v in rows.items()},
      "protected_types":sorted(PROTECTED),
      "groups":{k:list(v) for k,v in GROUPS.items()},
      "selection_used_stress":False,
      "selection_objective":"separate_group_optimization_with_zero_protected_top2_loss_on_both_dev_splits",
      "selected_groups":selected_groups,
      "composed_dev1":composed_dev1,
      "composed_dev2":composed_dev2,
      "stress":stress,
      "frozen_candidate":frozen,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED",
    }
    Path("_htft_split_group_research.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "sample_counts":out["sample_counts"],
      "selected_groups":{g:(None if s is None else {k:s[k] for k in ("l2","threshold","gamma","weak_net_dev1","weak_net_dev2","total_top2_net")}) for g,s in selected_groups.items()},
      "composed_dev1":{k:composed_dev1[k] for k in ("base_top2_accuracy","new_top2_accuracy","top2_net_hits","top1_net_hits","changed")},
      "composed_dev2":{k:composed_dev2[k] for k in ("base_top2_accuracy","new_top2_accuracy","top2_net_hits","top1_net_hits","changed")},
      "stress":stress
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
