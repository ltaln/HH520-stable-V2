import json, math, os, re, sys
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown
from engine.probability_layer import probability_layer
from engine.decision_filter import decision_filter
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer, _fit_lambdas, _poisson

POSTMATCH_KEYS={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome","actual_total_goals","result_label","label_status","label_match_method"}
SPLITS={"dev1":("2026-05-01","2026-06-30"),"dev2":("2026-07-01","2026-08-31"),"stress":("2026-09-01","2026-09-20")}
FT_CLASSES=["HOME","DRAW","AWAY"]
HTFT_CLASSES=[f"{h}_{f}" for h in FT_CLASSES for f in FT_CLASSES]

GROUPS={
 "DRAW_FUSION":{
   "num":["draw_odds","fusion_draw","advantage_diff","draw_composite_score"],
   "cat":[]
 },
 "HANDICAP_WATER":{
   "num":["home_water","away_water"],
   "cat":["handicap_side","handicap_primary_line","handicap_primary_water","handicap_secondary_line","handicap_secondary_water","water_level"]
 },
 "META_STRUCTURE":{
   "num":["rating_score"],
   "cat":["odds_judgement","advantage_side","structure","consistency","pattern","rating","risk"]
 },
 "VALUE":{
   "num":["ev","kelly"],
   "cat":[]
 },
}
CANDIDATES=[
 ("DRAW_FUSION",),("HANDICAP_WATER",),("META_STRUCTURE",),("VALUE",),
 ("DRAW_FUSION","HANDICAP_WATER"),("DRAW_FUSION","META_STRUCTURE"),
 ("HANDICAP_WATER","META_STRUCTURE"),("DRAW_FUSION","VALUE"),
 ("HANDICAP_WATER","VALUE"),("META_STRUCTURE","VALUE"),
 ("DRAW_FUSION","HANDICAP_WATER","META_STRUCTURE"),
 ("DRAW_FUSION","HANDICAP_WATER","VALUE"),
 ("DRAW_FUSION","META_STRUCTURE","VALUE"),
 ("HANDICAP_WATER","META_STRUCTURE","VALUE"),
 ("DRAW_FUSION","HANDICAP_WATER","META_STRUCTURE","VALUE"),
]

def split_for_day(day):
    for k,(a,b) in SPLITS.items():
        if a<=day<=b:return k
    return None

def score_pair(v):
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

def outcome(pair):
    if pair is None:return None
    return "HOME" if pair[0]>pair[1] else "AWAY" if pair[0]<pair[1] else "DRAW"

def fnum(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:return None

def row_fields(match):
    f=match.get("research_factors") or {}
    h=f.get("handicap_features") or {}
    v=match.get("value") or {}
    return {
      "draw_odds":fnum(f.get("draw_odds")),
      "fusion_draw":fnum(f.get("fusion_draw")),
      "advantage_diff":fnum(f.get("advantage_diff")),
      "draw_composite_score":fnum(f.get("draw_composite_score")),
      "home_water":fnum(f.get("home_water")),
      "away_water":fnum(f.get("away_water")),
      "rating_score":fnum(f.get("rating_score")),
      "ev":fnum(v.get("ev")),
      "kelly":fnum(v.get("kelly")),
      "odds_judgement":str(f.get("odds_judgement") or "").strip(),
      "advantage_side":str(f.get("advantage_side") or "").strip(),
      "structure":str(f.get("structure") or "").strip(),
      "consistency":str(f.get("consistency") or "").strip(),
      "pattern":str(f.get("pattern") or "").strip(),
      "rating":str(f.get("rating") or "").strip(),
      "risk":str(f.get("risk") or "").strip(),
      "water_level":str(f.get("water_level") or "").strip(),
      "handicap_side":str(h.get("side") or "").strip(),
      "handicap_primary_line":str(h.get("primary_line") or "").strip(),
      "handicap_primary_water":str(h.get("primary_water") or "").strip(),
      "handicap_secondary_line":str(h.get("secondary_line") or "").strip(),
      "handicap_secondary_water":str(h.get("secondary_water") or "").strip(),
    }

def load_rows():
    out={k:[] for k in SPLITS}
    files=sorted(Path("cache").glob("10027s_2026-*.json"))
    parsed=0
    for pth in files:
        day=pth.stem.replace("10027s_","")
        sp=split_for_day(day)
        if not sp:continue
        try:
            payload=json.loads(pth.read_text(encoding="utf-8"))
            raw=payload.get("raw") or {}
            md=((raw.get("data") or {}).get("markdown"))
            if not isinstance(md,str):continue
            matches=parse_10027s_markdown(md)
            parsed+=1
        except Exception:
            continue
        for m in matches:
            half=score_pair(m.get("half_score"))
            full=score_pair(m.get("result") or m.get("full_score"))
            if half is None or full is None:continue
            prematch=deepcopy(m)
            for k in POSTMATCH_KEYS:prematch.pop(k,None)
            prob=probability_layer(prematch)
            if not prob.get("valid"):continue
            dec=decision_filter(prematch,prob,prematch.get("value") or {})
            ht=htft_layer(prob,prematch,dec)
            sc=score_layer(prematch,prob,ht)
            if not ht.get("valid") or not sc.get("valid"):continue
            ft=outcome(full); hh=outcome(half)
            out[sp].append({
              "date":day,"match_id":m.get("match_id"),
              "home_team":m.get("home_team"),"away_team":m.get("away_team"),
              "actual_ft":ft,"actual_htft":f"{hh}_{ft}","actual_score":full,
              "fields":row_fields(m),
              "ft_probs":prob.get("probabilities"),
              "ft_current":str(dec.get("resolved_direction") or prob.get("direction") or "").upper(),
              "htft_dist":{x["ht"]+"_"+x["ft"]:float(x["probability"]) for x in ht.get("distribution",[])},
              "score_dist":{x["score"]:float(x["probability"]) for x in sc.get("all_scores",[])},
              "lambda_home":float(sc["lambda_home"]),"lambda_away":float(sc["lambda_away"]),
            })
    return out,{"cache_files":len(files),"parsed_files":parsed,"rows":{k:len(v) for k,v in out.items()}}

class Encoder:
    def __init__(self,groups):
        self.groups=groups
    def fit(self,rows):
        nums=[];cats=[]
        for g in self.groups:
            nums+=GROUPS[g]["num"]; cats+=GROUPS[g]["cat"]
        self.nums=list(dict.fromkeys(nums)); self.cats=list(dict.fromkeys(cats))
        self.num_stats={}
        for k in self.nums:
            vals=[r["fields"].get(k) for r in rows]
            vals=np.array([x for x in vals if x is not None],dtype=float)
            mu=float(vals.mean()) if len(vals) else 0.0
            sd=float(vals.std()) if len(vals) else 1.0
            if sd<1e-8:sd=1.0
            self.num_stats[k]=(mu,sd)
        self.cat_vocab={}
        for k in self.cats:
            counts={}
            for r in rows:
                v=r["fields"].get(k) or ""
                if v: counts[v]=counts.get(v,0)+1
            self.cat_vocab[k]=[v for v,n in sorted(counts.items()) if n>=3][:40]
        return self
    def transform(self,rows):
        cols=[]
        names=[]
        for k in self.nums:
            mu,sd=self.num_stats[k]
            vals=[];miss=[]
            for r in rows:
                v=r["fields"].get(k)
                vals.append((mu if v is None else float(v)-0.0))
                miss.append(1.0 if v is None else 0.0)
            vals=(np.asarray(vals,dtype=float)-mu)/sd
            cols.extend([vals,np.asarray(miss,dtype=float)])
            names.extend([k,k+"__missing"])
        for k in self.cats:
            vocab=self.cat_vocab[k]
            for v in vocab:
                cols.append(np.asarray([1.0 if (r["fields"].get(k) or "")==v else 0.0 for r in rows]))
                names.append(k+"="+v)
            cols.append(np.asarray([1.0 if (r["fields"].get(k) or "") and (r["fields"].get(k) or "") not in vocab else 0.0 for r in rows]))
            names.append(k+"=__OTHER")
        X=np.column_stack(cols) if cols else np.zeros((len(rows),0),dtype=float)
        return X,names

def base_logits(rows,kind,classes):
    arr=[]
    eps=1e-8
    for r in rows:
        if kind=="ft":
            d={k.upper():float(v) for k,v in r["ft_probs"].items()}
        else:
            d=r["htft_dist"]
        arr.append([math.log(max(eps,float(d.get(c,eps)))) for c in classes])
    return np.asarray(arr,dtype=float)

def softmax(z):
    z=z-z.max(axis=1,keepdims=True)
    e=np.exp(np.clip(z,-50,50))
    return e/e.sum(axis=1,keepdims=True)

def fit_residual(X,y,offset,nclass,l2=1.0,epochs=500,lr=0.08):
    X1=np.column_stack([np.ones(len(X)),X])
    W=np.zeros((X1.shape[1],nclass),dtype=float)
    Y=np.zeros((len(y),nclass),dtype=float);Y[np.arange(len(y)),y]=1.0
    best=None
    for ep in range(epochs):
        P=softmax(offset+X1@W)
        G=(X1.T@(P-Y))/len(y)
        G[1:]+=l2*W[1:]/len(y)
        step=lr/(1.0+ep/500)
        W-=step*G
        if ep%100==0:
            loss=-np.log(np.maximum(P[np.arange(len(y)),y],1e-12)).mean()+0.5*l2*np.sum(W[1:]**2)/len(y)
            if not np.isfinite(loss):break
    return W

def predict_residual(X,offset,W):
    X1=np.column_stack([np.ones(len(X)),X])
    return softmax(offset+X1@W)

def rank_metrics(probs,y,topn=(1,2,3)):
    order=np.argsort(-probs,axis=1)
    out={"n":len(y)}
    for n in topn:
        hits=sum(int(y[i] in order[i,:n]) for i in range(len(y)))
        out[f"top{n}_hits"]=hits;out[f"top{n}_accuracy"]=hits/len(y) if len(y) else None
    return out

def ft_baseline(rows):
    hits=sum(int(r["ft_current"]==r["actual_ft"]) for r in rows)
    return {"n":len(rows),"top1_hits":hits,"top1_accuracy":hits/len(rows) if rows else None}

def htft_baseline(rows):
    probs=np.asarray([[r["htft_dist"].get(c,0.0) for c in HTFT_CLASSES] for r in rows],dtype=float)
    y=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in rows],dtype=int)
    return rank_metrics(probs,y,(1,2,3))

def score_probs(rows,lams=None):
    out=[]
    keys=[f"{h}:{a}" for h in range(9) for a in range(9)]
    for i,r in enumerate(rows):
        if lams is None:
            d=r["score_dist"]
            out.append([float(d.get(k,0.0)) for k in keys])
        else:
            lh,la=lams[i]
            hp,ap=_poisson(lh,8),_poisson(la,8)
            vals=[];tot=0.0
            for h in range(9):
                for a in range(9):
                    v=hp[h]*ap[a]; vals.append(v);tot+=v
            out.append([v/(tot or 1.0) for v in vals])
    return np.asarray(out,dtype=float),keys

def score_metrics(probs,keys,rows):
    order=np.argsort(-probs,axis=1)
    ykeys=[f"{r['actual_score'][0]}:{r['actual_score'][1]}" for r in rows]
    out={"n":len(rows)}
    for n in (1,2,3,5):
        hits=0
        for i,k in enumerate(ykeys):
            preds=[keys[j] for j in order[i,:n]]
            hits+=int(k in preds)
        out[f"top{n}_hits"]=hits;out[f"top{n}_accuracy"]=hits/len(rows) if rows else None
    return out

def ridge_fit(X,y,l2=10.0):
    X1=np.column_stack([np.ones(len(X)),X])
    A=X1.T@X1
    reg=np.eye(A.shape[0])*l2;reg[0,0]=0
    return np.linalg.solve(A+reg,X1.T@y)

def ridge_pred(X,w):
    return np.column_stack([np.ones(len(X)),X])@w

def ft_crossfit(train,valid,groups,l2):
    enc=Encoder(groups).fit(train);Xt,_=enc.transform(train);Xv,_=enc.transform(valid)
    y=np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in train],dtype=int)
    ov=base_logits(train,"ft",FT_CLASSES); vv=base_logits(valid,"ft",FT_CLASSES)
    W=fit_residual(Xt,y,ov,3,l2=l2,epochs=450)
    P=predict_residual(Xv,vv,W)
    m=rank_metrics(P,np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in valid],dtype=int),(1,2))
    m["baseline_current"]=ft_baseline(valid)
    m["net_top1"]=m["top1_hits"]-m["baseline_current"]["top1_hits"]
    return m

def htft_crossfit(train,valid,groups,l2):
    enc=Encoder(groups).fit(train);Xt,_=enc.transform(train);Xv,_=enc.transform(valid)
    y=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in train],dtype=int)
    ot=base_logits(train,"htft",HTFT_CLASSES);ov=base_logits(valid,"htft",HTFT_CLASSES)
    W=fit_residual(Xt,y,ot,9,l2=l2,epochs=500)
    P=predict_residual(Xv,ov,W)
    m=rank_metrics(P,np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in valid],dtype=int),(1,2,3))
    b=htft_baseline(valid);m["baseline_current"]=b
    for n in (1,2,3):m[f"net_top{n}"]=m[f"top{n}_hits"]-b[f"top{n}_hits"]
    return m

def score_crossfit(train,valid,groups,l2,shrink):
    enc=Encoder(groups).fit(train);Xt,_=enc.transform(train);Xv,_=enc.transform(valid)
    yh=np.asarray([math.log((r["actual_score"][0]+0.35)/(r["lambda_home"]+0.35)) for r in train])
    ya=np.asarray([math.log((r["actual_score"][1]+0.35)/(r["lambda_away"]+0.35)) for r in train])
    wh=ridge_fit(Xt,yh,l2);wa=ridge_fit(Xt,ya,l2)
    ch=np.clip(ridge_pred(Xv,wh),-0.7,0.7)*shrink
    ca=np.clip(ridge_pred(Xv,wa),-0.7,0.7)*shrink
    lams=[(max(.15,min(5.5,r["lambda_home"]*math.exp(ch[i]))),
           max(.15,min(5.5,r["lambda_away"]*math.exp(ca[i])))) for i,r in enumerate(valid)]
    P,keys=score_probs(valid,lams); m=score_metrics(P,keys,valid)
    BP,bk=score_probs(valid);b=score_metrics(BP,bk,valid);m["baseline_current"]=b
    for n in (1,2,3,5):m[f"net_top{n}"]=m[f"top{n}_hits"]-b[f"top{n}_hits"]
    return m

def run_ft(rows):
    res=[]
    for groups in CANDIDATES:
      for l2 in (0.1,1.0,5.0):
        a=ft_crossfit(rows["dev1"],rows["dev2"],groups,l2)
        b=ft_crossfit(rows["dev2"],rows["dev1"],groups,l2)
        res.append({"groups":groups,"l2":l2,"dev2_from_dev1":a,"dev1_from_dev2":b,
                    "min_net":min(a["net_top1"],b["net_top1"]),"total_net":a["net_top1"]+b["net_top1"]})
    safe=[x for x in res if x["min_net"]>=0 and x["total_net"]>0]
    ranked=sorted(safe if safe else res,key=lambda x:(x["min_net"],x["total_net"]),reverse=True)
    best=ranked[0]
    dev=rows["dev1"]+rows["dev2"];enc=Encoder(best["groups"]).fit(dev);Xd,names=enc.transform(dev);Xs,_=enc.transform(rows["stress"])
    y=np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in dev],dtype=int)
    W=fit_residual(Xd,y,base_logits(dev,"ft",FT_CLASSES),3,l2=best["l2"],epochs=550)
    P=predict_residual(Xs,base_logits(rows["stress"],"ft",FT_CLASSES),W)
    stress=rank_metrics(P,np.asarray([FT_CLASSES.index(r["actual_ft"]) for r in rows["stress"]],dtype=int),(1,2))
    stress["baseline_current"]=ft_baseline(rows["stress"]);stress["net_top1"]=stress["top1_hits"]-stress["baseline_current"]["top1_hits"]
    return {"candidate_count":len(res),"safe_count":len(safe),"selected_on_dev_only":best,"stress":stress,"feature_names":names,"stress_used_for_selection":False}

def run_htft(rows):
    res=[]
    for groups in CANDIDATES:
      for l2 in (0.5,2.0,8.0):
        a=htft_crossfit(rows["dev1"],rows["dev2"],groups,l2)
        b=htft_crossfit(rows["dev2"],rows["dev1"],groups,l2)
        res.append({"groups":groups,"l2":l2,"dev2_from_dev1":a,"dev1_from_dev2":b,
                    "min_top1":min(a["net_top1"],b["net_top1"]),"min_top2":min(a["net_top2"],b["net_top2"]),
                    "min_top3":min(a["net_top3"],b["net_top3"]),
                    "total_top2":a["net_top2"]+b["net_top2"]})
    safe=[x for x in res if x["min_top1"]>=0 and x["min_top2"]>=0 and x["min_top3"]>=0 and x["total_top2"]>0]
    ranked=sorted(safe if safe else res,key=lambda x:(x["min_top2"],x["total_top2"],x["min_top1"],x["min_top3"]),reverse=True)
    best=ranked[0]
    dev=rows["dev1"]+rows["dev2"];enc=Encoder(best["groups"]).fit(dev);Xd,names=enc.transform(dev);Xs,_=enc.transform(rows["stress"])
    y=np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in dev],dtype=int)
    W=fit_residual(Xd,y,base_logits(dev,"htft",HTFT_CLASSES),9,l2=best["l2"],epochs=650)
    P=predict_residual(Xs,base_logits(rows["stress"],"htft",HTFT_CLASSES),W)
    stress=rank_metrics(P,np.asarray([HTFT_CLASSES.index(r["actual_htft"]) for r in rows["stress"]],dtype=int),(1,2,3))
    b=htft_baseline(rows["stress"]);stress["baseline_current"]=b
    for n in (1,2,3):stress[f"net_top{n}"]=stress[f"top{n}_hits"]-b[f"top{n}_hits"]
    return {"candidate_count":len(res),"safe_count":len(safe),"selected_on_dev_only":best,"stress":stress,"feature_names":names,"stress_used_for_selection":False}

def run_score(rows):
    res=[]
    for groups in CANDIDATES:
      for l2 in (3.0,10.0,30.0):
       for shrink in (0.25,0.5,0.75):
        a=score_crossfit(rows["dev1"],rows["dev2"],groups,l2,shrink)
        b=score_crossfit(rows["dev2"],rows["dev1"],groups,l2,shrink)
        res.append({"groups":groups,"l2":l2,"shrink":shrink,"dev2_from_dev1":a,"dev1_from_dev2":b,
                    "min_top1":min(a["net_top1"],b["net_top1"]),"min_top2":min(a["net_top2"],b["net_top2"]),
                    "total_top2":a["net_top2"]+b["net_top2"],"total_top1":a["net_top1"]+b["net_top1"]})
    safe=[x for x in res if x["min_top1"]>=0 and x["min_top2"]>=0 and x["total_top2"]>0]
    ranked=sorted(safe if safe else res,key=lambda x:(x["min_top2"],x["total_top2"],x["total_top1"]),reverse=True)
    best=ranked[0]
    dev=rows["dev1"]+rows["dev2"];enc=Encoder(best["groups"]).fit(dev);Xd,names=enc.transform(dev);Xs,_=enc.transform(rows["stress"])
    yh=np.asarray([math.log((r["actual_score"][0]+0.35)/(r["lambda_home"]+0.35)) for r in dev])
    ya=np.asarray([math.log((r["actual_score"][1]+0.35)/(r["lambda_away"]+0.35)) for r in dev])
    wh=ridge_fit(Xd,yh,best["l2"]);wa=ridge_fit(Xd,ya,best["l2"])
    ch=np.clip(ridge_pred(Xs,wh),-0.7,0.7)*best["shrink"];ca=np.clip(ridge_pred(Xs,wa),-0.7,0.7)*best["shrink"]
    lams=[(max(.15,min(5.5,r["lambda_home"]*math.exp(ch[i]))),max(.15,min(5.5,r["lambda_away"]*math.exp(ca[i])))) for i,r in enumerate(rows["stress"])]
    P,keys=score_probs(rows["stress"],lams);stress=score_metrics(P,keys,rows["stress"])
    BP,bk=score_probs(rows["stress"]);b=score_metrics(BP,bk,rows["stress"]);stress["baseline_current"]=b
    for n in (1,2,3,5):stress[f"net_top{n}"]=stress[f"top{n}_hits"]-b[f"top{n}_hits"]
    return {"candidate_count":len(res),"safe_count":len(safe),"selected_on_dev_only":best,"stress":stress,"feature_names":names,"stress_used_for_selection":False}

def availability(rows):
    allr=rows["dev1"]+rows["dev2"]+rows["stress"]
    out={}
    for g,spec in GROUPS.items():
        fields=spec["num"]+spec["cat"]
        out[g]={}
        for f in fields:
            present=sum(1 for r in allr if r["fields"].get(f) not in (None,""))
            out[g][f]={"present":present,"coverage":present/len(allr) if allr else 0}
    return out

def main():
    if os.getenv("HH520_FIELD_ABLATION_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    rows,load=load_rows()
    ft=run_ft(rows)
    ht=run_htft(rows)
    sc=run_score(rows)
    out={
      "mode":"OFFLINE_EXISTING_10027S_CACHE_ONLY",
      "new_collection":False,
      "goal_timing_used":False,
      "periods":SPLITS,
      "load_summary":load,
      "field_groups":GROUPS,
      "field_availability":availability(rows),
      "methodology":{
        "selection":"symmetric May-Jun <-> Jul-Aug crossfit",
        "stress":"Sep1-20 untouched until final selected candidate",
        "ft":"multinomial residual calibration on top of formal H/D/A probabilities; compare locked current FT decision",
        "htft":"9-class residual calibration on top of formal 9-cell HTFT distribution",
        "score":"ridge residual correction of formal home/away Poisson lambdas; exact-score ranking",
        "missing":"numeric mean+missing indicator; categorical train-vocabulary one-hot",
        "promotion":"research only; no Stable modification"
      },
      "ft":ft,"htft":ht,"score":sc,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"
    }
    Path("_field_ablation_full.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "load":load,
      "ft":{"selected":ft["selected_on_dev_only"],"stress":ft["stress"],"safe":ft["safe_count"]},
      "htft":{"selected":ht["selected_on_dev_only"],"stress":ht["stress"],"safe":ht["safe_count"]},
      "score":{"selected":sc["selected_on_dev_only"],"stress":sc["stress"],"safe":sc["safe_count"]},
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
