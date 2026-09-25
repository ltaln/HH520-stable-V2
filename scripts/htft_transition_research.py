import json, os, re, sys
import numpy as np
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer
from engine.score_layer import _fit_lambdas, _poisson

STATES=("HOME","DRAW","AWAY")
TRANSITIONS=tuple(f"{h}_{f}" for h in STATES for f in STATES)
POSTMATCH_KEYS={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome",
                "actual_total_goals","result_label","label_status","label_match_method"}

FEATURES=(
 "ph","pd","pa","market_ph","market_pd","market_pa","pmax","side_gap","draw_top_gap",
 "home_share_dev","lambda_total","lambda_gap",
 "attack_gap","defense_gap","h2h_gap","form_gap","possession_gap",
 "ht_home_base","ht_draw_base","ht_away_base"
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

def ht_probs(lh,la,hs=.36,as_=.44):
    h=_poisson(lh*hs,7); a=_poisson(la*as_,7)
    out={s:0.0 for s in STATES}
    for i,pi in enumerate(h):
      for j,pj in enumerate(a):
        out[outcome((i,j))]+=pi*pj
    s=sum(out.values()) or 1.0
    return {k:v/s for k,v in out.items()}

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
            market=p.get("market_probabilities") or {}
            fitted=_fit_lambdas(probs)
            if not fitted:continue
            _,lh,la=fitted
            hp=ht_probs(lh,la)
            rf=deepcopy(m.get("research_factors") or {})
            pos=deepcopy(m.get("possession") or {})
            hpos,apos=_num(pos.get("home")),_num(pos.get("away"))
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
              "possession_gap":abs(hpos-apos) if hpos is not None and apos is not None else 0.0,
              "ht_home_base":hp["HOME"],"ht_draw_base":hp["DRAW"],"ht_away_base":hp["AWAY"]
            }
            out[split].append({
              "date":day,"home_team":m.get("home_team"),"away_team":m.get("away_team"),
              "actual_ht":outcome(half),"actual_ft":outcome(full),
              "actual_htft":f"{outcome(half)}_{outcome(full)}","features":feat
            })
    return out

def matrix(rows, feats=FEATURES):
    return np.asarray([[r["features"][k] for k in feats] for r in rows],dtype=float)

def fit_multinomial(rows, condition_ht, l2=.5):
    subset=[r for r in rows if r["actual_ht"]==condition_ht]
    X=matrix(subset)
    mean=X.mean(0); std=X.std(0); std[std<1e-8]=1.0
    X=(X-mean)/std
    X=np.column_stack([np.ones(len(X)),X])
    Y=np.zeros((len(subset),3))
    for i,r in enumerate(subset):
        Y[i,STATES.index(r["actual_ft"])]=1.0
    W=np.zeros((X.shape[1],3))
    for _ in range(2200):
        Z=X@W; Z-=Z.max(axis=1,keepdims=True)
        P=np.exp(Z); P/=P.sum(axis=1,keepdims=True)
        grad=(X.T@(P-Y))/len(X)
        grad[1:]+=l2*W[1:]/len(X)
        W-=0.04*grad
    return {"ht":condition_ht,"mean":mean,"std":std,"W":W,"n":len(subset),"l2":l2}

def predict_conditional(model, rows):
    X=matrix(rows)
    X=(X-model["mean"])/model["std"]
    X=np.column_stack([np.ones(len(X)),X])
    Z=X@model["W"]; Z-=Z.max(axis=1,keepdims=True)
    P=np.exp(Z); P/=P.sum(axis=1,keepdims=True)
    return P

def build_joint(rows, models, ht_weight_mode="base"):
    # P(HT) from frozen existing half-share Poisson; P(FT|HT,x) from transition models.
    joints=[]
    for idx,r in enumerate(rows):
        htbase=np.array([r["features"]["ht_home_base"],r["features"]["ht_draw_base"],r["features"]["ht_away_base"]],dtype=float)
        mass={}
        for hi,ht in enumerate(STATES):
            cond=models[ht][idx]
            for fi,ft in enumerate(STATES):
                mass[f"{ht}_{ft}"]=float(htbase[hi]*cond[fi])
        s=sum(mass.values()) or 1.0
        joints.append({k:v/s for k,v in mass.items()})
    return joints

def evaluate(rows,joints):
    top1=top2=top3=0
    by={t:{"n":0,"top1":0,"top2":0,"top3":0} for t in TRANSITIONS}
    for r,mass in zip(rows,joints):
        ranked=sorted(mass,key=mass.get,reverse=True)
        actual=r["actual_htft"]
        top1+=int(actual==ranked[0]); top2+=int(actual in ranked[:2]); top3+=int(actual in ranked[:3])
        z=by[actual];z["n"]+=1;z["top1"]+=int(actual==ranked[0]);z["top2"]+=int(actual in ranked[:2]);z["top3"]+=int(actual in ranked[:3])
    n=len(rows)
    for z in by.values():
        if z["n"]:
            z["top1_rate"]=z["top1"]/z["n"];z["top2_rate"]=z["top2"]/z["n"];z["top3_rate"]=z["top3"]/z["n"]
        else:
            z["top1_rate"]=z["top2_rate"]=z["top3_rate"]=None
    return {"n":n,"top1_hits":top1,"top1_accuracy":top1/n,"top2_hits":top2,"top2_accuracy":top2/n,"top3_hits":top3,"top3_accuracy":top3/n,"by_actual":by}

def base_joint(rows,hs=.36,as_=.44):
    out=[]
    for r in rows:
        # recreate formal independent Poisson-split HTFT baseline from existing prematch probabilities
        # use fitted lambdas derived from full-time probabilities encoded through features is not possible directly,
        # so use current formal module instead.
        from engine.htft_layer import htft_layer
        # create minimal match object accepted by layer
        fake={"probability":{"valid":True,"probabilities":{"home":r["features"]["ph"],"draw":r["features"]["pd"],"away":r["features"]["pa"]}}}
        pred=htft_layer(fake)
        mass={x["label"].replace("/","_").replace("主","HOME").replace("平","DRAW").replace("客","AWAY"):x["probability"] for x in pred.get("full_distribution",[])}
        # if labels are canonical already, fallback
        if not mass:
            mass={x["code"]:x["probability"] for x in pred.get("full_distribution",[])}
        out.append(mass)
    return out

def main():
    if os.getenv("HH520_HTFT_TRANSITION_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows=load_rows()
    candidates=[]
    for l2 in (0.05,0.1,0.25,0.5,1.0,2.0):
        # symmetric cross-fit selection
        m1={ht:fit_multinomial(rows["dev1"],ht,l2) for ht in STATES}
        m2={ht:fit_multinomial(rows["dev2"],ht,l2) for ht in STATES}
        p1={ht:predict_conditional(m2[ht],rows["dev1"]) for ht in STATES}
        p2={ht:predict_conditional(m1[ht],rows["dev2"]) for ht in STATES}
        j1=build_joint(rows["dev1"],p1);j2=build_joint(rows["dev2"],p2)
        e1=evaluate(rows["dev1"],j1);e2=evaluate(rows["dev2"],j2)
        candidates.append({"l2":l2,"dev1":e1,"dev2":e2,
                           "min_top2":min(e1["top2_accuracy"],e2["top2_accuracy"]),
                           "avg_top2":(e1["top2_accuracy"]+e2["top2_accuracy"])/2,
                           "avg_top3":(e1["top3_accuracy"]+e2["top3_accuracy"])/2})
    candidates.sort(key=lambda x:(x["min_top2"],x["avg_top2"],x["avg_top3"]),reverse=True)
    best=candidates[0]
    dev=rows["dev1"]+rows["dev2"]
    models={ht:fit_multinomial(dev,ht,best["l2"]) for ht in STATES}
    stress_probs={ht:predict_conditional(models[ht],rows["stress"]) for ht in STATES}
    stress_joint=build_joint(rows["stress"],stress_probs)
    stress_eval=evaluate(rows["stress"],stress_joint)

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_collected":False,
      "sample_counts":{k:len(v) for k,v in rows.items()},
      "selection_used_stress":False,
      "model":"P_HT_BASE_X_P_FT_GIVEN_HT_MULTINOMIAL",
      "feature_names":list(FEATURES),
      "selected_on_dev_only":{"l2":best["l2"],"dev1":best["dev1"],"dev2":best["dev2"]},
      "stress":stress_eval,
      "transition_counts":{
        split:{t:sum(1 for r in rs if r["actual_htft"]==t) for t in TRANSITIONS}
        for split,rs in rows.items()
      },
      "frozen_candidate":{
        "l2":best["l2"],
        "models":{
          ht:{
            "n":models[ht]["n"],
            "mean":[float(x) for x in models[ht]["mean"]],
            "std":[float(x) for x in models[ht]["std"]],
            "weights":[[float(v) for v in row] for row in models[ht]["W"]],
          } for ht in STATES
        }
      },
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED",
    }
    Path("_htft_transition_research.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "sample_counts":out["sample_counts"],
      "selected_l2":best["l2"],
      "dev1":{k:best["dev1"][k] for k in ("top1_accuracy","top2_accuracy","top3_accuracy")},
      "dev2":{k:best["dev2"][k] for k in ("top1_accuracy","top2_accuracy","top3_accuracy")},
      "stress":stress_eval
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
