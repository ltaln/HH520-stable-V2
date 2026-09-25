import json, os, sys
import numpy as np
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.htft_split_group_research import load_rows, PROTECTED, FEATURES, matrix

TARGET="DRAW_AWAY"

FEATURE_SETS={
  "ALL": FEATURES,
  "CORE": (
    "ph","pd","pa","market_ph","market_pd","market_pa","pmax","side_gap","draw_top_gap",
    "home_share_dev","lambda_total","lambda_gap","base_draw_away","base_away_away","base_draw_draw"
  ),
  "MARKET_POISSON": (
    "ph","pd","pa","market_ph","market_pd","market_pa","pmax","side_gap","draw_top_gap",
    "home_share_dev","lambda_total","lambda_gap","base_draw_away","base_away_away","base_draw_draw",
    "base_draw_home","base_home_home"
  ),
  "STRUCTURE": (
    "ph","pd","pa","pmax","side_gap","draw_top_gap","home_share_dev","lambda_total","lambda_gap",
    "attack_gap","defense_gap","h2h_gap","form_gap","possession_gap","base_draw_away","base_away_away"
  ),
}

def mat(rows, feats):
    return np.asarray([[r["features"][k] for k in feats] for r in rows],dtype=float)

def fit(rows, feats, l2=1.0):
    X=mat(rows,feats)
    y=np.asarray([1.0 if r["actual_htft"]==TARGET else 0.0 for r in rows])
    mean=X.mean(0); std=X.std(0); std[std<1e-8]=1.0
    X=(X-mean)/std; X=np.column_stack([np.ones(len(X)),X])
    w=np.zeros(X.shape[1])
    pos=max(1.0,y.sum()); neg=max(1.0,len(y)-pos)
    pos_weight=min(12.0,neg/pos)
    weights=np.where(y>0.5,pos_weight,1.0)
    for _ in range(2200):
        z=np.clip(X@w,-30,30); pr=1/(1+np.exp(-z))
        grad=(X.T@((pr-y)*weights))/len(y)
        grad[1:]+=l2*w[1:]/len(y)
        w-=0.035*grad
    return {"mean":mean,"std":std,"w":w,"features":tuple(feats),"l2":l2}

def score(model, rows):
    X=mat(rows,model["features"])
    X=(X-model["mean"])/model["std"]
    X=np.column_stack([np.ones(len(X)),X])
    return 1/(1+np.exp(-np.clip(X@model["w"],-30,30)))

def evaluate(rows,scores,threshold,base_prob_min,base_prob_max,pd_min,pa_min,lambda_gap_max,second_prob_max,target_gap_max,require_second_mutable):
    base_top2_hits=new_top2_hits=0
    target_n=target_base=target_new=0
    triggers=trigger_hits=0
    losses=gains=0
    changed=0
    protected_loss=0
    detail=[]
    for i,r in enumerate(rows):
        base=r["base"]
        ranked=sorted(base,key=base.get,reverse=True)
        top1,top2=ranked[:2]
        actual=r["actual_htft"]
        base_hit=actual in (top1,top2)
        base_top2_hits+=int(base_hit)
        if actual==TARGET:
            target_n+=1
            target_base+=int(base_hit)

        sc=float(scores[i])
        eligible=(
            sc>=threshold and
            base.get(TARGET,0.0)>=base_prob_min and
            base.get(TARGET,0.0)<=base_prob_max and
            r["features"]["pd"]>=pd_min and
            r["features"]["pa"]>=pa_min and
            r["features"]["lambda_gap"]<=lambda_gap_max and
            base.get(top2,0.0)<=second_prob_max and
            (base.get(top2,0.0)-base.get(TARGET,0.0))<=target_gap_max
        )
        if require_second_mutable:
            eligible=eligible and top2 not in PROTECTED
        # High-specificity rule: never alter top1; replace only second slot.
        new2=top2
        if eligible and TARGET not in (top1,top2) and top2 not in PROTECTED:
            new2=TARGET
            triggers+=1
            trigger_hits+=int(actual==TARGET)
            changed+=1
        new_hit=actual in (top1,new2)
        new_top2_hits+=int(new_hit)
        if actual==TARGET:
            target_new+=int(new_hit)
        gains+=int((not base_hit) and new_hit)
        losses+=int(base_hit and (not new_hit))
        if actual in PROTECTED and base_hit and not new_hit:
            protected_loss+=1
        if eligible:
            detail.append({
              "date":r["date"],"home_team":r["home_team"],"away_team":r["away_team"],
              "actual":actual,"score":sc,"base_top2":[top1,top2],
              "base_draw_away":base.get(TARGET,0.0),"pd":r["features"]["pd"],"pa":r["features"]["pa"],
              "lambda_gap":r["features"]["lambda_gap"],"new_top2":[top1,new2]
            })
    n=len(rows)
    return {
      "n":n,"base_top2_hits":base_top2_hits,"base_top2_accuracy":base_top2_hits/n,
      "new_top2_hits":new_top2_hits,"new_top2_accuracy":new_top2_hits/n,
      "top2_net_hits":new_top2_hits-base_top2_hits,
      "changed":changed,"gains":gains,"losses":losses,"protected_loss":protected_loss,
      "target_n":target_n,"target_base_hits":target_base,"target_new_hits":target_new,
      "target_base_rate":target_base/target_n if target_n else None,
      "target_new_rate":target_new/target_n if target_n else None,
      "triggers":triggers,"trigger_hits":trigger_hits,
      "trigger_precision":trigger_hits/triggers if triggers else None,
      "trigger_recall":trigger_hits/target_n if target_n else None,
      "details":detail,
    }

def main():
    if os.getenv("HH520_DRAW_AWAY_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    dev1,dev2,stress=rows["dev1"],rows["dev2"],rows["stress"]

    candidates=[]
    for fs_name in ("CORE",):
      feats=FEATURE_SETS[fs_name]
      for l2 in (0.1,0.5):
        m1=fit(dev1,feats,l2); m2=fit(dev2,feats,l2)
        s1=score(m2,dev1); s2=score(m1,dev2)
        for th in (0.75,0.80,0.85,0.90):
          for bpmin in (0.04,0.06):
            for bpmax in (0.20,0.25):
              if bpmax<=bpmin: continue
              for pdmin in (0.22,0.24):
                for pamin in (0.30,0.35):
                  for lgmax in (0.40,0.60):
                    for spmax in (0.16,0.20):
                      for gapmax in (0.02,0.04,0.06):
                        e1=evaluate(dev1,s1,th,bpmin,bpmax,pdmin,pamin,lgmax,spmax,gapmax,True)
                        e2=evaluate(dev2,s2,th,bpmin,bpmax,pdmin,pamin,lgmax,spmax,gapmax,True)
                        if e1["protected_loss"] or e2["protected_loss"]: continue
                        # Require no overall Top2 loss in either split.
                        if e1["top2_net_hits"]<0 or e2["top2_net_hits"]<0: continue
                        # Require at least one target gain in both splits.
                        if e1["target_new_hits"]<=e1["target_base_hits"] or e2["target_new_hits"]<=e2["target_base_hits"]: continue
                        # High-specificity: minimum precision across splits >= 25%.
                        p1=e1["trigger_precision"] or 0; p2=e2["trigger_precision"] or 0
                        if min(p1,p2)<0.25: continue
                        candidates.append({
                          "feature_set":fs_name,"l2":l2,"threshold":th,
                          "base_prob_min":bpmin,"base_prob_max":bpmax,
                          "pd_min":pdmin,"pa_min":pamin,"lambda_gap_max":lgmax,
                          "second_prob_max":spmax,"target_gap_max":gapmax,
                          "dev1":e1,"dev2":e2,
                          "min_precision":min(p1,p2),
                          "total_net":e1["top2_net_hits"]+e2["top2_net_hits"],
                          "total_target_gain":(e1["target_new_hits"]-e1["target_base_hits"])+(e2["target_new_hits"]-e2["target_base_hits"]),
                          "total_triggers":e1["triggers"]+e2["triggers"],
                        })
    candidates.sort(key=lambda x:(x["total_net"],x["total_target_gain"],x["min_precision"],-x["total_triggers"]),reverse=True)
    best=candidates[0] if candidates else None

    stress_result=None; frozen=None
    if best:
        feats=FEATURE_SETS[best["feature_set"]]
        model=fit(dev1+dev2,feats,best["l2"])
        ss=score(model,stress)
        stress_result=evaluate(
          stress,ss,best["threshold"],best["base_prob_min"],best["base_prob_max"],
          best["pd_min"],best["pa_min"],best["lambda_gap_max"],best["second_prob_max"],best["target_gap_max"],True
        )
        frozen={
          "feature_set":best["feature_set"],"features":list(feats),"l2":best["l2"],
          "threshold":best["threshold"],"base_prob_min":best["base_prob_min"],"base_prob_max":best["base_prob_max"],
          "pd_min":best["pd_min"],"pa_min":best["pa_min"],"lambda_gap_max":best["lambda_gap_max"],
          "second_prob_max":best["second_prob_max"],"target_gap_max":best["target_gap_max"],
          "mean":[float(x) for x in model["mean"]],
          "std":[float(x) for x in model["std"]],
          "weights":[float(x) for x in model["w"]],
          "policy":"top1_locked; replace_second_slot_only; protected_second_slot_locked"
        }

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "target":"DRAW_AWAY",
      "sample_counts":{k:len(v) for k,v in rows.items()},
      "selection_used_stress":False,
      "candidate_count":len(candidates),
      "selection_objective":"high_specificity_draw_away_with_nonnegative_overall_top2_on_each_dev_split",
      "selected_on_dev_only":best,
      "stress":stress_result,
      "frozen_candidate":frozen,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED",
    }
    Path("_draw_away_high_specificity.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "sample_counts":out["sample_counts"],"candidate_count":len(candidates),
      "selected":None if best is None else {k:best[k] for k in ("feature_set","l2","threshold","base_prob_min","base_prob_max","pd_min","pa_min","lambda_gap_max","second_prob_max","target_gap_max","min_precision","total_net","total_target_gain","total_triggers")},
      "dev1":None if best is None else {k:best["dev1"][k] for k in ("top2_net_hits","target_base_hits","target_new_hits","trigger_precision","triggers","gains","losses")},
      "dev2":None if best is None else {k:best["dev2"][k] for k in ("top2_net_hits","target_base_hits","target_new_hits","trigger_precision","triggers","gains","losses")},
      "stress":stress_result
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
