import json, math, os, re, sys
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer
from engine.decision_filter import decision_filter
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer, _poisson

FT_CLASSES=["HOME","DRAW","AWAY"]
HTFT_CLASSES=[f"{a}_{b}" for a in FT_CLASSES for b in FT_CLASSES]
POSTMATCH={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome","actual_total_goals","result_label","label_status","label_match_method"}

GROUPS={
 "XG":["xg_for","xg_against"],
 "SHOTS":["shots","shots_on_target","shots_off_target","shot_conversion","shots_per_goal","sot_per_goal"],
 "GOAL_RATE":["scored_per_match","conceded_per_match","clean_sheet","failed_to_score"],
 "RESULT_STABILITY":["wins","draws","losses"],
 "BTTS_TOTALS":["btts","btts_win","btts_draw","over_05","over_15","over_25","over_35"],
 "HALF_TIMING":["scored_1h","scored_2h","failed_score_1h","failed_score_2h","scored_both_halves","conceded_avg_1h","conceded_avg_2h","clean_sheet_1h","clean_sheet_2h"],
 "POSSESSION":["possession"],
}
GROUP_NAMES=list(GROUPS)
SUBSETS=[combo for n in range(1,len(GROUP_NAMES)+1) for combo in combinations(GROUP_NAMES,n)]

def parse_score(v):
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

def outcome(p):
    if not p:return None
    return "HOME" if p[0]>p[1] else "AWAY" if p[0]<p[1] else "DRAW"

def load_matches():
    out=[]
    for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
        day=p.stem.replace("10027s_","")
        if not ("2026-09-01"<=day<="2026-09-20"):continue
        try:
            payload=json.loads(p.read_text(encoding="utf-8"))
            md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
            matches=parse_10027s_markdown(md or "")
        except Exception:
            continue
        for m in matches:
            half=parse_score(m.get("half_score"));full=parse_score(m.get("result") or m.get("full_score"))
            if not half or not full:continue
            prematch=deepcopy(m)
            for k in POSTMATCH:prematch.pop(k,None)
            prob=probability_layer(prematch)
            if not prob.get("valid"):continue
            dec=decision_filter(prematch,prob,prematch.get("value") or {})
            ht=htft_layer(prob,prematch,dec)
            sc=score_layer(prematch,prob,ht)
            if not ht.get("valid") or not sc.get("valid"):continue
            out.append({
              "date":day,"home_team":m.get("home_team"),"away_team":m.get("away_team"),
              "actual_score":full,"actual_ft":outcome(full),"actual_htft":f"{outcome(half)}_{outcome(full)}",
              "ft_probs":prob.get("probabilities"),"ft_current":str(dec.get("resolved_direction") or prob.get("direction") or "").upper(),
              "htft_dist":{x["ht"]+"_"+x["ft"]:float(x["probability"]) for x in ht.get("distribution",[])},
              "score_dist":{x["score"]:float(x["probability"]) for x in sc.get("all_scores",[])},
              "lambda_home":float(sc["lambda_home"]),"lambda_away":float(sc["lambda_away"]),
            })
    return out

def value(stat,side):
    if not isinstance(stat,dict):return None
    v=stat.get(side)
    if v is None:v=stat.get("overall")
    try:
        v=float(v)
        return v if math.isfinite(v) else None
    except Exception:return None

def build_profile_features(home,away):
    hcore=(home or {}).get("core_stats") or {}; acore=(away or {}).get("core_stats") or {}
    f={}
    for key in set(hcore)|set(acore):
        hv=value(hcore.get(key),"home"); av=value(acore.get(key),"away")
        f[f"h_{key}"]=hv;f[f"a_{key}"]=av
        f[f"d_{key}"]=(hv-av) if hv is not None and av is not None else None
        f[f"s_{key}"]=(hv+av) if hv is not None and av is not None else None
    # Matchup expected-goal composites
    hxf=value(hcore.get("xg_for"),"home"); hxa=value(hcore.get("xg_against"),"home")
    axf=value(acore.get("xg_for"),"away"); axa=value(acore.get("xg_against"),"away")
    if None not in (hxf,axa):f["xg_home_matchup"]=(hxf+axa)/2
    else:f["xg_home_matchup"]=None
    if None not in (axf,hxa):f["xg_away_matchup"]=(axf+hxa)/2
    else:f["xg_away_matchup"]=None
    if f["xg_home_matchup"] is not None and f["xg_away_matchup"] is not None:
        f["xg_matchup_diff"]=f["xg_home_matchup"]-f["xg_away_matchup"]
        f["xg_matchup_total"]=f["xg_home_matchup"]+f["xg_away_matchup"]
    else:
        f["xg_matchup_diff"]=None;f["xg_matchup_total"]=None
    # Six-bin timing features: side values, diff, balance/late summaries.
    for prefix,p in (("h",home),("a",away)):
        timing=(p or {}).get("timing") or {}
        for typ in ("goals_for","goals_against"):
            arr=((timing.get(typ) or {}).get("percent")) or []
            for i in range(6):
                f[f"{prefix}_{typ}_t{i}"]=float(arr[i]) if i<len(arr) else None
            if len(arr)>=6:
                f[f"{prefix}_{typ}_1h"]=sum(arr[:3])
                f[f"{prefix}_{typ}_2h"]=sum(arr[3:])
                f[f"{prefix}_{typ}_late"]=arr[5]
            else:
                f[f"{prefix}_{typ}_1h"]=None;f[f"{prefix}_{typ}_2h"]=None;f[f"{prefix}_{typ}_late"]=None
    return f

def quality_rows(matches,collection):
    mappings=collection.get("team_mappings") or {}
    profiles=collection.get("profiles") or {}
    owners=defaultdict(set)
    for team,mp in mappings.items():
        u=(mp or {}).get("url")
        if u:owners[u].add(team)
    ambiguous={u for u,x in owners.items() if len(x)>1}
    rows=[];reject=defaultdict(int)
    for r in matches:
        h=r["home_team"];a=r["away_team"];hm=mappings.get(h) or {};am=mappings.get(a) or {}
        try:hs=float(hm.get("score") or 0);aas=float(am.get("score") or 0)
        except Exception:hs=aas=0
        hu=hm.get("url");au=am.get("url")
        if hs<.85 or aas<.85 or not hu or not au:
            reject["mapping_low_confidence"]+=1;continue
        if hu in ambiguous or au in ambiguous:
            reject["ambiguous_profile_url"]+=1;continue
        hp=profiles.get(h) or {};ap=profiles.get(a) or {}
        if not hp.get("available") or not ap.get("available"):
            reject["profile_unavailable"]+=1;continue
        x=dict(r);x["features"]=build_profile_features(hp,ap);rows.append(x)
    return rows,{"accepted":len(rows),"rejected":dict(reject),"ambiguous_profile_url_groups":len(ambiguous),"mapping_score_min":.85}

def group_feature_names(group_tuple):
    names=[]
    for g in group_tuple:
        if g=="HALF_TIMING":
            for key in GROUPS[g]:
                names += [f"h_{key}",f"a_{key}",f"d_{key}",f"s_{key}"]
            for side in ("h","a"):
                for typ in ("goals_for","goals_against"):
                    names += [f"{side}_{typ}_t{i}" for i in range(6)]
                    names += [f"{side}_{typ}_1h",f"{side}_{typ}_2h",f"{side}_{typ}_late"]
        else:
            for key in GROUPS[g]:
                names += [f"h_{key}",f"a_{key}",f"d_{key}",f"s_{key}"]
            if g=="XG":names += ["xg_home_matchup","xg_away_matchup","xg_matchup_diff","xg_matchup_total"]
    return list(dict.fromkeys(names))

class Encoder:
    def __init__(self,names):self.names=names
    def fit(self,rows):
        self.stats={}
        for k in self.names:
            vals=np.array([float(r["features"][k]) for r in rows if r["features"].get(k) is not None],dtype=float)
            mu=float(vals.mean()) if len(vals) else 0.0;sd=float(vals.std()) if len(vals) else 1.0
            if sd<1e-8:sd=1.0
            self.stats[k]=(mu,sd)
        return self
    def transform(self,rows):
        cols=[]
        for k in self.names:
            mu,sd=self.stats[k];v=[];miss=[]
            for r in rows:
                x=r["features"].get(k)
                v.append(mu if x is None else float(x));miss.append(1.0 if x is None else 0.0)
            cols.append((np.asarray(v)-mu)/sd);cols.append(np.asarray(miss))
        return np.column_stack(cols) if cols else np.zeros((len(rows),0))

def softmax(z):
    z=z-z.max(axis=1,keepdims=True);e=np.exp(np.clip(z,-50,50));return e/e.sum(axis=1,keepdims=True)

def fit_residual(X,y,offset,nclass,l2,epochs=260):
    X1=np.column_stack([np.ones(len(X)),X]);W=np.zeros((X1.shape[1],nclass));Y=np.zeros((len(y),nclass));Y[np.arange(len(y)),y]=1
    for ep in range(epochs):
        P=softmax(offset+X1@W);G=X1.T@(P-Y)/len(y);G[1:]+=l2*W[1:]/len(y)
        W-=0.08/(1+ep/350)*G
    return W

def pred_residual(X,offset,W):
    return softmax(offset+np.column_stack([np.ones(len(X)),X])@W)

def offset(rows,kind,classes):
    eps=1e-9;out=[]
    for r in rows:
        d={k.upper():v for k,v in r["ft_probs"].items()} if kind=="ft" else r["htft_dist"]
        out.append([math.log(max(eps,float(d.get(c,eps)))) for c in classes])
    return np.asarray(out)

def metric(probs,y,topns):
    order=np.argsort(-probs,axis=1);o={"n":len(y)}
    for n in topns:
        h=sum(int(y[i] in order[i,:n]) for i in range(len(y)));o[f"top{n}_hits"]=h;o[f"top{n}_accuracy"]=h/len(y) if len(y) else None
    return o

def ft_baseline(rows):
    h=sum(int(r["ft_current"]==r["actual_ft"]) for r in rows);return {"n":len(rows),"top1_hits":h,"top1_accuracy":h/len(rows) if rows else None}

def htft_baseline(rows):
    P=np.asarray([[r["htft_dist"].get(c,0) for c in HTFT_CLASSES] for r in rows]);y=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in rows])
    return metric(P,y,(1,2,3))

def score_matrix(rows,lams=None):
    keys=[f"{h}:{a}" for h in range(9) for a in range(9)];allp=[]
    for i,r in enumerate(rows):
        if lams is None:d=r["score_dist"];allp.append([float(d.get(k,0)) for k in keys]);continue
        lh,la=lams[i];hp,ap=_poisson(lh,8),_poisson(la,8);v=[hp[h]*ap[a] for h in range(9) for a in range(9)];s=sum(v) or 1;allp.append([x/s for x in v])
    return np.asarray(allp),keys

def score_metric(P,keys,rows):
    order=np.argsort(-P,axis=1);o={"n":len(rows)}
    actual=[f"{r['actual_score'][0]}:{r['actual_score'][1]}" for r in rows]
    for n in (1,2,3,5):
        h=sum(int(actual[i] in [keys[j] for j in order[i,:n]]) for i in range(len(rows)));o[f"top{n}_hits"]=h;o[f"top{n}_accuracy"]=h/len(rows) if rows else None
    return o

def ridge(X,y,l2):
    X1=np.column_stack([np.ones(len(X)),X]);A=X1.T@X1;R=np.eye(A.shape[0])*l2;R[0,0]=0
    return np.linalg.solve(A+R,X1.T@y)

def blocks(rows):
    ranges=[("2026-09-01","2026-09-04"),("2026-09-05","2026-09-07"),("2026-09-08","2026-09-10"),("2026-09-11","2026-09-14")]
    return [[r for r in rows if a<=r["date"]<=b] for a,b in ranges]

def evaluate_ft(train,valid,groups,l2):
    names=group_feature_names(groups);enc=Encoder(names).fit(train);Xt=enc.transform(train);Xv=enc.transform(valid)
    y=np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in train]);W=fit_residual(Xt,y,offset(train,"ft",FT_CLASSES),3,l2)
    P=pred_residual(Xv,offset(valid,"ft",FT_CLASSES),W);yv=np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in valid]);m=metric(P,yv,(1,))
    b=ft_baseline(valid);m["baseline"]=b;m["net_top1"]=m["top1_hits"]-b["top1_hits"];return m

def evaluate_htft(train,valid,groups,l2):
    names=group_feature_names(groups);enc=Encoder(names).fit(train);Xt=enc.transform(train);Xv=enc.transform(valid)
    y=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in train]);W=fit_residual(Xt,y,offset(train,"htft",HTFT_CLASSES),9,l2)
    P=pred_residual(Xv,offset(valid,"htft",HTFT_CLASSES),W);yv=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in valid]);m=metric(P,yv,(1,2,3))
    b=htft_baseline(valid);m["baseline"]=b
    for n in (1,2,3):m[f"net_top{n}"]=m[f"top{n}_hits"]-b[f"top{n}_hits"]
    return m

def evaluate_score(train,valid,groups,l2,shrink):
    names=group_feature_names(groups);enc=Encoder(names).fit(train);Xt=enc.transform(train);Xv=enc.transform(valid)
    yh=np.asarray([math.log((r["actual_score"][0]+.35)/(r["lambda_home"]+.35)) for r in train])
    ya=np.asarray([math.log((r["actual_score"][1]+.35)/(r["lambda_away"]+.35)) for r in train])
    wh=ridge(Xt,yh,l2);wa=ridge(Xt,ya,l2)
    dh=np.clip(np.column_stack([np.ones(len(Xv)),Xv])@wh,-.8,.8)*shrink
    da=np.clip(np.column_stack([np.ones(len(Xv)),Xv])@wa,-.8,.8)*shrink
    lams=[(max(.15,min(5.5,r["lambda_home"]*math.exp(dh[i]))),max(.15,min(5.5,r["lambda_away"]*math.exp(da[i])))) for i,r in enumerate(valid)]
    P,k=score_matrix(valid,lams);m=score_metric(P,k,valid);B,bk=score_matrix(valid);b=score_metric(B,bk,valid);m["baseline"]=b
    for n in (1,2,3,5):m[f"net_top{n}"]=m[f"top{n}_hits"]-b[f"top{n}_hits"]
    return m

def cv_candidates(selection,kind):
    bs=blocks(selection);res=[]
    if kind=="ft":params=[(x,) for x in (.1,1.0,5.0)]
    elif kind=="htft":params=[(x,) for x in (.5,2.0,8.0)]
    else:params=[(l,s) for l in (3.0,10.0,30.0) for s in (.25,.5,.75)]
    for groups in SUBSETS:
        for param in params:
            folds=[]
            for i,val in enumerate(bs):
                train=[r for j,b in enumerate(bs) if j!=i for r in b]
                if not train or not val:continue
                if kind=="ft":m=evaluate_ft(train,val,groups,param[0])
                elif kind=="htft":m=evaluate_htft(train,val,groups,param[0])
                else:m=evaluate_score(train,val,groups,param[0],param[1])
                folds.append(m)
            if not folds:continue
            row={"groups":groups,"params":param,"folds":folds}
            if kind=="ft":
                nets=[x["net_top1"] for x in folds];row.update(min_primary=min(nets),total_primary=sum(nets),total_secondary=0)
            elif kind=="htft":
                n1=[x["net_top1"] for x in folds];n2=[x["net_top2"] for x in folds];n3=[x["net_top3"] for x in folds]
                row.update(min_primary=min(n2),total_primary=sum(n2),min_top1=min(n1),min_top3=min(n3),total_secondary=sum(n1)+sum(n3))
            else:
                n1=[x["net_top1"] for x in folds];n2=[x["net_top2"] for x in folds]
                row.update(min_primary=min(n2),total_primary=sum(n2),min_top1=min(n1),total_secondary=sum(n1))
            res.append(row)
    if kind=="ft":safe=[x for x in res if x["min_primary"]>=0 and x["total_primary"]>0]
    elif kind=="htft":safe=[x for x in res if x["min_primary"]>=0 and x["min_top1"]>=0 and x["min_top3"]>=0 and x["total_primary"]>0]
    else:safe=[x for x in res if x["min_primary"]>=0 and x["min_top1"]>=0 and x["total_primary"]>0]
    ranked=sorted(safe if safe else res,key=lambda x:(x["min_primary"],x["total_primary"],x.get("min_top1",0),x.get("min_top3",0),x["total_secondary"]),reverse=True)
    return res,safe,ranked[0] if ranked else None

def final_eval(selection,holdout,kind,best):
    groups=tuple(best["groups"]);p=best["params"]
    if kind=="ft":return evaluate_ft(selection,holdout,groups,p[0])
    if kind=="htft":return evaluate_htft(selection,holdout,groups,p[0])
    return evaluate_score(selection,holdout,groups,p[0],p[1])

def summarize_all(res,kind):
    # Keep every tested combination/parameter, but trim fold baseline duplication.
    out=[]
    for x in res:
        y={k:v for k,v in x.items() if k!="folds"}
        y["fold_nets"]=[]
        for f in x["folds"]:
            if kind=="ft":y["fold_nets"].append({"n":f["n"],"top1":f["net_top1"]})
            elif kind=="htft":y["fold_nets"].append({"n":f["n"],"top1":f["net_top1"],"top2":f["net_top2"],"top3":f["net_top3"]})
            else:y["fold_nets"].append({"n":f["n"],"top1":f["net_top1"],"top2":f["net_top2"],"top3":f["net_top3"],"top5":f["net_top5"]})
        out.append(y)
    return out

def feature_availability(rows):
    allnames=group_feature_names(tuple(GROUP_NAMES));o={}
    for k in allnames:
        p=sum(1 for r in rows if r["features"].get(k) is not None);o[k]={"present":p,"coverage":p/len(rows) if rows else 0}
    return o

def main():
    if os.getenv("HH520_COLLECTION1_ABLATION_OFFLINE_ONLY")!="1":raise SystemExit("offline-only guard missing")
    collection=json.loads(Path("_collection1_profiles.json").read_text(encoding="utf-8"))
    matches=load_matches();rows,gate=quality_rows(matches,collection)
    selection=[r for r in rows if r["date"]<="2026-09-14"];holdout=[r for r in rows if r["date"]>="2026-09-15"]
    results={}
    for kind in ("ft","htft","score"):
        allres,safe,best=cv_candidates(selection,kind)
        results[kind]={
          "tested_candidates":len(allres),"safe_candidates":len(safe),
          "selected_on_sep1_14_cv":best,
          "holdout_sep15_20":final_eval(selection,holdout,kind,best) if best else None,
          "all_candidates":summarize_all(allres,kind),
        }
    out={
      "mode":"RETROSPECTIVE_COLLECTION1_FULL_PROFILE_ABLATION",
      "source_summary":collection.get("summary"),
      "matches_total":len(matches),"quality_gate":gate,
      "selection_n":len(selection),"holdout_n":len(holdout),
      "selection_window":"2026-09-01..2026-09-14","holdout_window":"2026-09-15..2026-09-20",
      "groups":GROUPS,"group_subset_count":len(SUBSETS),
      "feature_availability":feature_availability(rows),
      "methodology":{
        "all_nonempty_group_combinations_tested":True,
        "selection":"4 blocked CV folds inside Sep1-14; choose on CV only",
        "holdout_labels_used_for_selection":False,
        "ft_model":"multinomial residual correction on formal H/D/A",
        "htft_model":"9-class multinomial residual correction on formal HTFT distribution",
        "score_model":"regularized log-lambda residual correction on formal Poisson score model",
        "quality":"both teams profile available; mapping score>=0.85; ambiguous URLs rejected",
        "warning":"FootyStats snapshot is 2026-09-25 current-season aggregate. This is retrospective feature-value research, not leakage-clean point-in-time validation."
      },
      **results,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED_AUTOMATICALLY"
    }
    Path("_collection1_full_ablation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "source_summary":out["source_summary"],"quality_gate":gate,"selection_n":len(selection),"holdout_n":len(holdout),
      "ft":{"tested":out["ft"]["tested_candidates"],"safe":out["ft"]["safe_candidates"],"selected":out["ft"]["selected_on_sep1_14_cv"],"holdout":out["ft"]["holdout_sep15_20"]},
      "htft":{"tested":out["htft"]["tested_candidates"],"safe":out["htft"]["safe_candidates"],"selected":out["htft"]["selected_on_sep1_14_cv"],"holdout":out["htft"]["holdout_sep15_20"]},
      "score":{"tested":out["score"]["tested_candidates"],"safe":out["score"]["safe_candidates"],"selected":out["score"]["selected_on_sep1_14_cv"],"holdout":out["score"]["holdout_sep15_20"]},
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
