"""HH520 Hidden Formula V3 walk-forward research harness.

Cache-only: never spends Firecrawl credits. Stable remains untouched.
"""
from __future__ import annotations
import argparse, datetime as dt, json, math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

from collector.cache_manager import load_cache
from collector.service import collect_date
from research.export_10027_full import build_row

CLASSES = ["HOME","DRAW","AWAY"]
CLS = {c:i for i,c in enumerate(CLASSES)}
FEATURES = ["home_pos_diff","attack_diff","defense_diff","h2h_diff","form_diff"]

def softmax(z):
    z=np.asarray(z,float); z=z-z.max(axis=1,keepdims=True)
    e=np.exp(z); return e/e.sum(axis=1,keepdims=True)

def market_probs(df):
    inv=np.column_stack([1/df.home_odds,1/df.draw_odds,1/df.away_odds]).astype(float)
    return inv/inv.sum(axis=1,keepdims=True)

def logloss(p,y):
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)),y],1e-12,1))))

def brier(p,y):
    oh=np.eye(3)[y]; return float(np.mean(np.sum((p-oh)**2,axis=1)))

def rps(p,y):
    oh=np.eye(3)[y]
    return float(np.mean(np.sum((np.cumsum(p,axis=1)[:,:-1]-np.cumsum(oh,axis=1)[:,:-1])**2,axis=1)/2))

def acc(p,y): return float(np.mean(np.argmax(p,axis=1)==y))

def wilson(k,n,z=1.96):
    if n<=0:return 0.0
    ph=k/n; d=1+z*z/n
    return float((ph+z*z/(2*n)-z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n)))/d)

def prep(start="2026-05-01",end="2026-09-20"):
    rows=[]; missing=[]; d=dt.date.fromisoformat(start); z=dt.date.fromisoformat(end)
    while d<=z:
        day=d.isoformat()
        if load_cache(day,source="10027s") is None:
            missing.append(day)
        else:
            payload=collect_date(day)
            for m in payload.get("matches",[]): rows.append(build_row(m))
        d+=dt.timedelta(days=1)
    df=pd.DataFrame(rows)
    if df.empty: return df,missing
    df["date"]=pd.to_datetime(df["date"])
    df=df[df["ft_outcome"].isin(CLASSES)].copy()
    # Historical all-zero factor blocks are missing modules, not genuine zero strength.
    eight=["home_attack","away_attack","home_defense","away_defense","home_h2h","away_h2h","home_form","away_form"]
    allzero=np.ones(len(df),dtype=bool)
    for c in eight:
        v=pd.to_numeric(df[c],errors="coerce")
        allzero &= v.fillna(0).eq(0).to_numpy()
    df["team_modules_missing"]=allzero.astype(int)
    df.loc[allzero,eight]=np.nan
    for c in ["home_possession","away_possession"]+eight:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df["home_pos_diff"]=df.home_possession-df.away_possession
    df["attack_diff"]=df.home_attack-df.away_attack
    df["defense_diff"]=df.home_defense-df.away_defense
    df["h2h_diff"]=df.home_h2h-df.away_h2h
    df["form_diff"]=df.home_form-df.away_form
    p=market_probs(df)
    df[["p_home","p_draw","p_away"]]=p
    df["market_pred"]=[CLASSES[i] for i in np.argmax(p,axis=1)]
    df["market_pmax"]=p.max(axis=1)
    df["actual_y"]=df.ft_outcome.map(CLS)
    def parse_score(s):
        try:
            a,b=str(s).replace(":","-").split("-")[:2]; return int(a),int(b)
        except:return (np.nan,np.nan)
    scores=df.full_score.apply(parse_score)
    df["home_goals"]=[x[0] for x in scores]; df["away_goals"]=[x[1] for x in scores]
    df["ht_y"]=df.ht_outcome.map(CLS)
    return df.reset_index(drop=True),missing

def orientation(train):
    signs={}
    side=np.where(train.market_pred.eq("HOME"),1,np.where(train.market_pred.eq("AWAY"),-1,0))
    correct=train.market_pred.eq(train.ft_outcome).to_numpy()
    for f in FEATURES:
        edge=pd.to_numeric(train[f],errors="coerce").to_numpy()*side
        ok=np.isfinite(edge)&(side!=0)&(edge!=0)
        pos=correct[ok&(edge>0)]; neg=correct[ok&(edge<0)]
        rp=pos.mean() if len(pos) else -1; rn=neg.mean() if len(neg) else -1
        signs[f]=1 if rp>=rn else -1
    return signs

def confirmations(df,signs):
    side=np.where(df.market_pred.eq("HOME"),1,np.where(df.market_pred.eq("AWAY"),-1,0))
    votes=np.zeros(len(df),float); avail=np.zeros(len(df),float)
    for f,s in signs.items():
        e=pd.to_numeric(df[f],errors="coerce").to_numpy()*side
        ok=np.isfinite(e)&(side!=0)
        avail += ok
        votes += ok & ((e*s)>0)
    return votes,avail

def select_gate(train):
    signs=orientation(train); votes,avail=confirmations(train,signs)
    correct=train.market_pred.eq(train.ft_outcome).to_numpy()
    candidates=[]
    for th in [.55,.58,.60,.62,.64,.66,.68,.70,.73,.76]:
        for mv in [2,3,4,5]:
            mask=(train.market_pmax.to_numpy()>=th)&(avail>=mv)&(votes>=mv)
            n=int(mask.sum()); k=int(correct[mask].sum())
            if n>=20:
                candidates.append((wilson(k,n),k/n,n,th,mv))
    if not candidates:return {"pmax":.66,"min_votes":3,"signs":signs}
    # lower Wilson bound first; minimum support prevents tiny cherry-picked groups.
    candidates.sort(reverse=True)
    _,_,_,th,mv=candidates[0]
    return {"pmax":th,"min_votes":mv,"signs":signs}

def eval_gate(test,gate):
    v,a=confirmations(test,gate["signs"])
    mask=(test.market_pmax.to_numpy()>=gate["pmax"])&(a>=gate["min_votes"])&(v>=gate["min_votes"])
    correct=test.market_pred.eq(test.ft_outcome).to_numpy()
    n=int(mask.sum()); k=int(correct[mask].sum())
    return {"n":n,"correct":k,"accuracy":(k/n if n else None),"coverage":float(n/len(test)) if len(test) else 0,
            "pmax":gate["pmax"],"min_votes":gate["min_votes"]}

def residual_features(train,test):
    cols=FEATURES+["p_home","p_draw","p_away","team_modules_missing"]
    tr=train[cols].astype(float).copy(); te=test[cols].astype(float).copy()
    med=tr.median(numeric_only=True).fillna(0)
    tr=tr.fillna(med); te=te.fillna(med)
    mu=tr.mean(); sd=tr.std().replace(0,1).fillna(1)
    # do not standardize probability/missingness less critically; consistent transform is fine.
    return ((tr-mu)/sd).to_numpy(),((te-mu)/sd).to_numpy()

def fit_residual(train,test,l2=100.0):
    Xtr,Xte=residual_features(train,test); y=train.actual_y.to_numpy(int)
    pm_tr=market_probs(train); pm_te=market_probs(test)
    F=Xtr.shape[1]
    def unpack(w):
        B=w.reshape(2,F)
        z=np.log(np.clip(pm_tr,1e-12,1))
        z[:,0]+=Xtr@B[0]; z[:,2]+=Xtr@B[1]
        return z,B
    def obj(w):
        z,B=unpack(w); p=softmax(z)
        return -np.sum(np.log(np.clip(p[np.arange(len(y)),y],1e-12,1))) + .5*l2*np.sum(B*B)
    res=minimize(obj,np.zeros(2*F),method="L-BFGS-B",options={"maxiter":500})
    B=res.x.reshape(2,F)
    z=np.log(np.clip(pm_te,1e-12,1)); z[:,0]+=Xte@B[0]; z[:,2]+=Xte@B[1]
    return softmax(z)

def wdl_metrics(p,df):
    y=df.actual_y.to_numpy(int)
    return {"n":len(df),"accuracy":acc(p,y),"log_loss":logloss(p,y),"brier":brier(p,y),"rps":rps(p,y)}

def htft_eval(train,test,pft):
    counts=np.ones((3,3),float) # FT x HT Laplace
    good=train.dropna(subset=["actual_y","ht_y"])
    for _,r in good.iterrows(): counts[int(r.actual_y),int(r.ht_y)]+=1
    cond=counts/counts.sum(axis=1,keepdims=True)
    top=[0,0,0]; n=0; ll=[]
    ht_hit=0
    for i,(_,r) in enumerate(test.iterrows()):
        if pd.isna(r.ht_y): continue
        joint=np.zeros(9)
        for f in range(3):
            for h in range(3): joint[f*3+h]=pft[i,f]*cond[f,h]
        actual=int(r.actual_y)*3+int(r.ht_y)
        order=np.argsort(joint)[::-1]
        for k in range(3):
            top[k]+=int(actual in order[:k+1])
        ll.append(-math.log(max(joint[actual],1e-12)))
        htprob=joint.reshape(3,3).sum(axis=0)
        ht_hit += int(np.argmax(htprob)==int(r.ht_y))
        n+=1
    return {"n":n,"ht_accuracy":ht_hit/n if n else None,"top1":top[0]/n if n else None,
            "top2":top[1]/n if n else None,"top3":top[2]/n if n else None,
            "log_loss":float(np.mean(ll)) if ll else None}

def poisson_design(train,test):
    cols=["p_home","p_draw","p_away"]+FEATURES+["team_modules_missing"]
    tr=train[cols].astype(float).copy(); te=test[cols].astype(float).copy()
    med=tr.median(numeric_only=True).fillna(0); tr=tr.fillna(med); te=te.fillna(med)
    mu=tr.mean(); sd=tr.std().replace(0,1).fillna(1)
    A=((tr-mu)/sd).to_numpy(); B=((te-mu)/sd).to_numpy()
    A=np.column_stack([np.ones(len(A)),A]); B=np.column_stack([np.ones(len(B)),B])
    return A,B

def fit_poisson(X,y,l2=1.0):
    def obj(w):
        eta=np.clip(X@w,-5,5); lam=np.exp(eta)
        return float(np.sum(lam-y*eta)+.5*l2*np.sum(w[1:]**2))
    r=minimize(obj,np.zeros(X.shape[1]),method="L-BFGS-B",options={"maxiter":500})
    return r.x

def poisson_pmf(k,lam):
    return math.exp(k*math.log(max(lam,1e-12))-lam-gammaln(k+1))

def score_eval(train,test,pft,blend=.15,maxg=10):
    tr=train.dropna(subset=["home_goals","away_goals"])
    te=test.dropna(subset=["home_goals","away_goals"]).copy()
    if len(tr)<30 or len(te)==0:return {"n":0}
    Xtr,Xte=poisson_design(train,test)
    wh=fit_poisson(Xtr,train.home_goals.fillna(train.home_goals.median()).to_numpy(float))
    wa=fit_poisson(Xtr,train.away_goals.fillna(train.away_goals.median()).to_numpy(float))
    lh=np.exp(np.clip(Xte@wh,-5,5)); la=np.exp(np.clip(Xte@wa,-5,5))
    # empirical score prior by FT class, training only
    prior=np.full((3,maxg+1,maxg+1),0.1,float)
    for _,r in tr.iterrows():
        h,a=int(r.home_goals),int(r.away_goals)
        if h<=maxg and a<=maxg: prior[int(r.actual_y),h,a]+=1
    prior/=prior.sum(axis=(1,2),keepdims=True)
    hits=[0,0,0,0]; n=0; nll=[]
    for i,(_,r) in enumerate(test.iterrows()):
        if pd.isna(r.home_goals) or pd.isna(r.away_goals): continue
        mat=np.zeros((maxg+1,maxg+1))
        for h in range(maxg+1):
            ph=poisson_pmf(h,lh[i])
            for a in range(maxg+1): mat[h,a]=ph*poisson_pmf(a,la[i])
        mat/=mat.sum()
        ep=sum(pft[i,f]*prior[f] for f in range(3))
        mat=(1-blend)*mat+blend*ep; mat/=mat.sum()
        h,a=int(r.home_goals),int(r.away_goals)
        if h>maxg or a>maxg: continue
        flat=mat.ravel(); actual=h*(maxg+1)+a; order=np.argsort(flat)[::-1]
        for j,k in enumerate([1,2,3,5]): hits[j]+=int(actual in order[:k])
        nll.append(-math.log(max(flat[actual],1e-12))); n+=1
    return {"n":n,"top1":hits[0]/n if n else None,"top2":hits[1]/n if n else None,
            "top3":hits[2]/n if n else None,"top5":hits[3]/n if n else None,
            "score_nll":float(np.mean(nll)) if nll else None,"blend":blend}

def fold(train,test,name):
    pm=market_probs(test)
    res=fit_residual(train,test,100.0)
    gate=select_gate(train)
    return {"fold":name,"train_n":len(train),"test_n":len(test),
            "market":wdl_metrics(pm,test),"residual":wdl_metrics(res,test),
            "gate":eval_gate(test,gate),"gate_orientation":gate["signs"],
            "htft":htft_eval(train,test,pm),
            "score_base":score_eval(train,test,pm,0.0),
            "score_blend15":score_eval(train,test,pm,0.15)}

def run():
    df,missing=prep()
    if df.empty: raise SystemExit("no cached V3 rows")
    month_counts={str(k):int(v) for k,v in df.groupby(df.date.dt.strftime("%Y-%m")).size().items()}
    folds=[]
    boundaries=[
      ("MAY_to_JUN","2026-05-01","2026-05-31","2026-06-01","2026-06-30"),
      ("MAYJUN_to_JUL","2026-05-01","2026-06-30","2026-07-01","2026-07-31"),
      ("MAYJUL_to_AUG","2026-05-01","2026-07-31","2026-08-01","2026-08-31"),
      ("MAYAUG_to_SEP","2026-05-01","2026-08-31","2026-09-01","2026-09-20"),
    ]
    for name,ts,te,vs,ve in boundaries:
        tr=df[(df.date>=ts)&(df.date<=te)].copy(); ho=df[(df.date>=vs)&(df.date<=ve)].copy()
        if len(tr)>=30 and len(ho)>=10: folds.append(fold(tr,ho,name))
    return {"system":"HH520 Hidden Formula V3 Walk-Forward","stable_access":"READ_ONLY",
            "rows":len(df),"month_counts":month_counts,"missing_cache_dates":missing,
            "missing_cache_count":len(missing),"folds":folds,"status":"CANDIDATE_ONLY"}

def render(r):
    L=["# HH520 Hidden Formula V3 — Walk-Forward Result","",
       f"- Rows: **{r['rows']}**",f"- Missing cache dates: **{r['missing_cache_count']}**",
       "- Stable access: **READ_ONLY**",""]
    L+=["## Month counts",""]
    for m,n in r["month_counts"].items():L.append(f"- {m}: {n}")
    for f in r["folds"]:
        L+=["",f"## {f['fold']}","",f"- Train/Test: {f['train_n']} / {f['test_n']}",
            f"- Market WDL: **{f['market']['accuracy']:.1%}**, LogLoss {f['market']['log_loss']:.4f}, RPS {f['market']['rps']:.4f}",
            f"- Residual WDL: **{f['residual']['accuracy']:.1%}**, LogLoss {f['residual']['log_loss']:.4f}, RPS {f['residual']['rps']:.4f}"]
        g=f["gate"]; ga="N/A" if g["accuracy"] is None else f"{g['accuracy']:.1%}"
        L.append(f"- Selected confidence gate: pmax>={g['pmax']:.2f}, votes>={g['min_votes']}, n={g['n']}, accuracy={ga}, coverage={g['coverage']:.1%}")
        h=f["htft"]; L.append(f"- HTFT: Top1 {h['top1']:.1%}, Top2 {h['top2']:.1%}, Top3 {h['top3']:.1%}, LogLoss {h['log_loss']:.4f}")
        s=f["score_blend15"]; L.append(f"- Score blend15: Top1 {s.get('top1',0):.1%}, Top2 {s.get('top2',0):.1%}, Top3 {s.get('top3',0):.1%}, NLL {s.get('score_nll',float('nan')):.4f}")
    L+=["","## Decision","","This is Research-only. Promotion requires stability across multiple forward folds and a fresh untouched shadow period."]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--json",type=Path,required=True); ap.add_argument("--md",type=Path,required=True); a=ap.parse_args()
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    a.md.write_text(render(r),encoding="utf-8")
    print(render(r))
if __name__=="__main__": main()
