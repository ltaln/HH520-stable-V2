"""HH520 Relationship Discovery + Multi-Formula Tournament V3.2.

Research-only, cache-only, no Firecrawl spend, Stable untouched.
Tests multiple market/team/handicap/league interaction architectures with
chronological outer folds and a September development stress test.
"""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.optimize import minimize, brentq
from scipy.special import gammaln

from research.hidden_formula_v3 import (
    prep, market_probs, wdl_metrics, htft_eval, score_eval, wilson,
    CLASSES, CLS, FEATURES
)

DEV_FOLDS = [
    ("MAY_to_JUN","2026-05-01","2026-05-31","2026-06-01","2026-06-30"),
    ("MAYJUN_to_JUL","2026-05-01","2026-06-30","2026-07-01","2026-07-31"),
    ("MAYJUL_to_AUG","2026-05-01","2026-07-31","2026-08-01","2026-08-31"),
]
L2_GRID=[1.0,10.0,50.0,100.0]
VARIANTS=["market","market_team","market_team_handicap","market_team_handicap_league"]

LINE_MAP={
    "平手":0.0,"平半":0.25,"半球":0.5,"半一":0.75,"一球":1.0,
    "一球球半":1.25,"球半":1.5,"球半两球":1.75,"两球":2.0,
    "两球两球半":2.25,"两球半":2.5,"两球半三球":2.75,"三球":3.0,
    "受让平半":0.25,"受让半球":0.5,"受让半一":0.75,"受让一球":1.0,
}
WATER_MAP={"低水":-1.0,"中水":0.0,"中低水":-0.5,"中高水":0.5,"高水":1.0}

def sigmoid(z):
    z=np.clip(np.asarray(z,float),-30,30)
    return 1/(1+np.exp(-z))

def entropy3(p):
    return -np.sum(p*np.log(np.clip(p,1e-12,1)),axis=1)

def power_devig(df):
    odds=np.column_stack([df.home_odds,df.draw_odds,df.away_odds]).astype(float)
    q=1/odds
    out=np.zeros_like(q)
    for i,row in enumerate(q):
        s=row.sum()
        if not np.isfinite(s) or s<=1:
            out[i]=row/s
            continue
        f=lambda k: float(np.sum(row**k)-1)
        try:k=brentq(f,1.0,8.0,maxiter=100)
        except Exception:k=1.0
        p=row**k; out[i]=p/p.sum()
    return out

def devig_compare(df):
    y=df.actual_y.to_numpy(int)
    prop=market_probs(df); power=power_devig(df)
    return {"proportional":wdl_metrics(prop,df),"power":wdl_metrics(power,df)}

def market_side(df,p=None):
    if p is None:p=market_probs(df)
    pred=np.argmax(p,axis=1)
    return np.where(pred==0,1,np.where(pred==2,-1,0))

def parse_line(x):
    if x is None or (isinstance(x,float) and np.isnan(x)):return np.nan
    s=str(x).strip()
    if s in LINE_MAP:return LINE_MAP[s]
    for k,v in sorted(LINE_MAP.items(),key=lambda z:len(z[0]),reverse=True):
        if k in s:return v
    m=re.search(r"(\d+(?:\.\d+)?)",s)
    return float(m.group(1)) if m else np.nan

def parse_water(x):
    if x is None or (isinstance(x,float) and np.isnan(x)):return np.nan
    s=str(x).strip()
    if s in WATER_MAP:return WATER_MAP[s]
    for k,v in WATER_MAP.items():
        if k in s:return v
    return np.nan

def handicap_numeric(df,side):
    hs=df.get("handicap_side",pd.Series([None]*len(df))).astype(str)
    align=np.where((side==1)&hs.str.lower().str.contains("home|主",regex=True),1.0,
          np.where((side==-1)&hs.str.lower().str.contains("away|客",regex=True),1.0,
          np.where(hs.str.contains("主|客",regex=True),-1.0,0.0)))
    depth=df.get("handicap_primary_line",pd.Series([None]*len(df))).map(parse_line).to_numpy(float)
    water=df.get("handicap_primary_water",pd.Series([None]*len(df))).map(parse_water).to_numpy(float)
    avail=np.isfinite(depth).astype(float)
    depth=np.nan_to_num(depth,nan=0.0)
    water=np.nan_to_num(water,nan=0.0)
    return align,depth,water,avail

def base_numeric(df,p):
    side=market_side(df,p)
    order=np.sort(p,axis=1)
    pmax=order[:,-1]; margin=order[:,-1]-order[:,-2]; ent=entropy3(p)
    feat={
      "pmax":pmax,"margin":margin,"entropy":ent,
      "p_home":p[:,0],"p_draw":p[:,1],"p_away":p[:,2],
      "pmax2":pmax*pmax,"margin2":margin*margin,
    }
    raw={
      "home_pos_diff":pd.to_numeric(df.home_pos_diff,errors="coerce").to_numpy(float),
      "attack_diff":pd.to_numeric(df.attack_diff,errors="coerce").to_numpy(float),
      "defense_diff":pd.to_numeric(df.defense_diff,errors="coerce").to_numpy(float),
      "h2h_diff":pd.to_numeric(df.h2h_diff,errors="coerce").to_numpy(float),
      "form_diff":pd.to_numeric(df.form_diff,errors="coerce").to_numpy(float),
    }
    for k,v in raw.items():
        fav=side*v
        feat["fav_"+k]=fav
        feat["abs_"+k]=np.abs(v)
        feat["pmax_x_"+k]=pmax*fav
    ha,hd,hw,hav=handicap_numeric(df,side)
    feat.update({
      "handicap_align":ha,"handicap_depth":hd,"handicap_water":hw,"handicap_available":hav,
      "pmax_x_handicap_align":pmax*ha,"depth_x_align":hd*ha,"water_x_align":hw*ha
    })
    return feat

def feature_matrix(train,test,variant,p_train=None,p_test=None):
    if p_train is None:p_train=market_probs(train)
    if p_test is None:p_test=market_probs(test)
    A=base_numeric(train,p_train); B=base_numeric(test,p_test)
    names=list(A)
    keep=["pmax","margin","entropy","p_home","p_draw","p_away","pmax2","margin2"]
    if variant in ("market_team","market_team_handicap","market_team_handicap_league"):
        keep += [n for n in names if n.startswith(("fav_","abs_","pmax_x_")) and "handicap" not in n]
    if variant in ("market_team_handicap","market_team_handicap_league"):
        keep += ["handicap_align","handicap_depth","handicap_water","handicap_available",
                 "pmax_x_handicap_align","depth_x_align","water_x_align"]
    Xtr=np.column_stack([A[n] for n in keep]).astype(float)
    Xte=np.column_stack([B[n] for n in keep]).astype(float)
    outnames=keep[:]
    if variant=="market_team_handicap_league":
        counts=train.league.astype(str).value_counts()
        leagues=sorted(counts[counts>=30].index.tolist())
        for lg in leagues:
            Xtr=np.column_stack([Xtr,(train.league.astype(str).to_numpy()==lg).astype(float)])
            Xte=np.column_stack([Xte,(test.league.astype(str).to_numpy()==lg).astype(float)])
            outnames.append("league="+lg)
    med=np.nanmedian(Xtr,axis=0)
    med=np.where(np.isfinite(med),med,0.0)
    ii=np.where(~np.isfinite(Xtr)); Xtr[ii]=np.take(med,ii[1])
    ii=np.where(~np.isfinite(Xte)); Xte[ii]=np.take(med,ii[1])
    mu=Xtr.mean(axis=0); sd=Xtr.std(axis=0); sd=np.where(sd>1e-9,sd,1.0)
    Xtr=(Xtr-mu)/sd; Xte=(Xte-mu)/sd
    Xtr=np.column_stack([np.ones(len(Xtr)),Xtr])
    Xte=np.column_stack([np.ones(len(Xte)),Xte])
    return Xtr,Xte,["intercept"]+outnames

def fit_binary(X,y,l2=10.0,offset=None):
    y=np.asarray(y,float)
    if offset is None:offset=np.zeros(len(y))
    offset=np.asarray(offset,float)
    def obj(w):
        z=offset+X@w
        loss=np.logaddexp(0,z)-y*z
        return float(loss.sum()+.5*l2*np.sum(w[1:]**2))
    r=minimize(obj,np.zeros(X.shape[1]),method="L-BFGS-B",options={"maxiter":400})
    return r.x

def calibration_split(train,frac=.70):
    dates=np.array(sorted(pd.to_datetime(train.date).dt.normalize().unique()))
    if len(dates)<4:
        cut=int(len(train)*frac)
        return train.iloc[:cut].copy(),train.iloc[cut:].copy()
    idx=max(1,min(len(dates)-1,int(len(dates)*frac)))
    d0=dates[idx]
    return train[train.date<d0].copy(),train[train.date>=d0].copy()

def choose_threshold(scores,correct,target=.80,min_n=20):
    scores=np.asarray(scores,float); correct=np.asarray(correct,bool)
    qs=np.unique(np.quantile(scores,np.linspace(.20,.98,80)))
    cand=[]
    for th in qs:
        m=scores>=th; n=int(m.sum())
        if n<min_n:continue
        k=int(correct[m].sum()); a=k/n
        cand.append((a>=target, n/len(scores), wilson(k,n), a, n, float(th)))
    if not cand:
        return float(np.quantile(scores,.90))
    good=[x for x in cand if x[0]]
    if good:
        good.sort(key=lambda x:(x[1],x[2],x[3],x[4]),reverse=True)
        return good[0][-1]
    cand.sort(key=lambda x:(x[2],x[3],x[4]),reverse=True)
    return cand[0][-1]

def reliability_fold(train,test,variant,l2):
    fit,cal=calibration_split(train)
    pfit=market_probs(fit); pcal=market_probs(cal); ptest=market_probs(test)
    Xfit,Xcal,_=feature_matrix(fit,cal,variant,pfit,pcal)
    yfit=(np.argmax(pfit,axis=1)==fit.actual_y.to_numpy(int)).astype(int)
    w=fit_binary(Xfit,yfit,l2)
    sc_cal=sigmoid(Xcal@w)
    corr_cal=np.argmax(pcal,axis=1)==cal.actual_y.to_numpy(int)
    th=choose_threshold(sc_cal,corr_cal,.80,max(20,int(.06*len(cal))))
    Xfit2,Xtest,names=feature_matrix(fit,test,variant,pfit,ptest)
    # Keep fit-only model so threshold and model are coherent and fully chronological.
    sc=sigmoid(Xtest@w)
    corr=np.argmax(ptest,axis=1)==test.actual_y.to_numpy(int)
    m=sc>=th; n=int(m.sum()); k=int(corr[m].sum())
    # equal-coverage pmax control
    nctrl=n
    order=np.argsort(ptest.max(axis=1))[::-1]
    ctrl=np.zeros(len(test),dtype=bool)
    if nctrl:ctrl[order[:nctrl]]=True
    kc=int(corr[ctrl].sum()) if nctrl else 0
    # coefficient map from the actually fitted feature set
    coef={n:float(c) for n,c in zip(names,w)}
    return {
      "n":n,"correct":k,"accuracy":k/n if n else None,"coverage":n/len(test) if len(test) else 0.0,
      "wilson_low":wilson(k,n) if n else None,"threshold":float(th),
      "pmax_control_n":nctrl,"pmax_control_accuracy":kc/nctrl if nctrl else None,
      "increment_vs_equal_coverage_pmax":(k-kc)/n if n else None,
      "coef":coef,
    }

def aggregate_rel(results):
    n=sum(r["n"] for r in results); k=sum(r["correct"] for r in results)
    ctrl=sum((r["pmax_control_accuracy"] or 0)*r["pmax_control_n"] for r in results)
    return {
      "n":n,"correct":k,"accuracy":k/n if n else None,
      "coverage_weighted":sum(r["coverage"]*r["pmax_control_n"] for r in results)/max(1,sum(r["pmax_control_n"] for r in results)),
      "wilson_low":wilson(k,n) if n else None,
      "min_fold_accuracy":min((r["accuracy"] for r in results if r["accuracy"] is not None),default=None),
      "pmax_control_accuracy":ctrl/n if n else None,
      "increment_vs_equal_coverage_pmax":(k-ctrl)/n if n else None,
    }

def reliability_tournament(df):
    rows=[]
    detail={}
    for variant in VARIANTS:
        for l2 in L2_GRID:
            folds=[]
            for name,ts,te,vs,ve in DEV_FOLDS:
                tr=df[(df.date>=ts)&(df.date<=te)].copy()
                ho=df[(df.date>=vs)&(df.date<=ve)].copy()
                r=reliability_fold(tr,ho,variant,l2); r["fold"]=name
                folds.append(r)
            agg=aggregate_rel(folds)
            rec={"variant":variant,"l2":l2,**agg}
            rows.append(rec); detail[(variant,l2)]=folds
    viable=[r for r in rows if r["n"]>=60 and (r["accuracy"] or 0)>=.80 and (r["min_fold_accuracy"] or 0)>=.72]
    if viable:
        viable.sort(key=lambda r:(r["coverage_weighted"],r["wilson_low"],r["accuracy"]),reverse=True)
        best=viable[0]
    else:
        rows.sort(key=lambda r:(r["wilson_low"] or 0,r["accuracy"] or 0,r["n"]),reverse=True)
        best=rows[0]
    best["folds"]=detail[(best["variant"],best["l2"])]
    return best,rows

def final_reliability_sep(df,best):
    # Freeze architecture on dev. Fit May-Jul, calibrate on Aug, test Sep.
    fit=df[(df.date>="2026-05-01")&(df.date<="2026-07-31")].copy()
    cal=df[(df.date>="2026-08-01")&(df.date<="2026-08-31")].copy()
    sep=df[(df.date>="2026-09-01")&(df.date<="2026-09-20")].copy()
    pf,pc,ps=market_probs(fit),market_probs(cal),market_probs(sep)
    Xf,Xc,_=feature_matrix(fit,cal,best["variant"],pf,pc)
    y=(np.argmax(pf,axis=1)==fit.actual_y.to_numpy(int)).astype(int)
    w=fit_binary(Xf,y,best["l2"])
    s_cal=sigmoid(Xc@w); c_cal=np.argmax(pc,axis=1)==cal.actual_y.to_numpy(int)
    th=choose_threshold(s_cal,c_cal,.80,max(20,int(.06*len(cal))))
    Xf2,Xs,names=feature_matrix(fit,sep,best["variant"],pf,ps)
    s=sigmoid(Xs@w); corr=np.argmax(ps,axis=1)==sep.actual_y.to_numpy(int)
    m=s>=th; n=int(m.sum()); k=int(corr[m].sum())
    order=np.argsort(ps.max(axis=1))[::-1]
    ctrl=np.zeros(len(sep),bool)
    if n:ctrl[order[:n]]=True
    kc=int(corr[ctrl].sum()) if n else 0
    return {
      "n":n,"correct":k,"accuracy":k/n if n else None,"coverage":n/len(sep),
      "wilson_low":wilson(k,n) if n else None,
      "equal_coverage_pmax_accuracy":kc/n if n else None,
      "increment_vs_equal_coverage_pmax":(k-kc)/n if n else None,
      "threshold":float(th),
      "top_coefficients":sorted(
        [{"feature":nm,"coef":float(c)} for nm,c in zip(names,w) if nm!="intercept"],
        key=lambda z:abs(z["coef"]),reverse=True
      )[:12]
    }

def v31_gate_increment(df):
    out={}
    # fixed final sign convention from V3.1: pos+, attack+, defense+, h2h+, form-
    sign={"home_pos_diff":1,"attack_diff":1,"defense_diff":1,"h2h_diff":1,"form_diff":-1}
    for label,start,end in [
      ("development_6_8","2026-06-01","2026-08-31"),
      ("september","2026-09-01","2026-09-20")
    ]:
        z=df[(df.date>=start)&(df.date<=end)].copy()
        p=market_probs(z); side=market_side(z,p)
        votes=np.zeros(len(z),int); avail=np.zeros(len(z),int)
        for f,s in sign.items():
            v=pd.to_numeric(z[f],errors="coerce").to_numpy(float)*side
            ok=np.isfinite(v)&(side!=0)
            avail+=ok; votes+=ok&(v*s>0)
        corr=np.argmax(p,axis=1)==z.actual_y.to_numpy(int)
        pmax=p.max(axis=1)
        m0=pmax>=.73
        m1=m0&(avail>=2)&(votes>=2)
        def one(m):
            n=int(m.sum());k=int(corr[m].sum())
            return {"n":n,"accuracy":k/n if n else None,"coverage":n/len(z) if len(z) else 0,"wilson_low":wilson(k,n) if n else None}
        out[label]={"pmax_only":one(m0),"pmax_plus_2of5":one(m1)}
    return out

def fit_draw_offset(train,test,l2=50.0):
    ptr=market_probs(train); pte=market_probs(test)
    Xtr,Xte,_=feature_matrix(train,test,"market_team_handicap",ptr,pte)
    # remove intercept duplication from market probability correction but retain all engineered terms
    yd=(train.actual_y.to_numpy(int)==1).astype(int)
    off=np.log(np.clip(ptr[:,1],1e-8,1-1e-8)/np.clip(1-ptr[:,1],1e-8,1))
    w=fit_binary(Xtr,yd,l2,off)
    offte=np.log(np.clip(pte[:,1],1e-8,1-1e-8)/np.clip(1-pte[:,1],1e-8,1))
    pd=sigmoid(offte+Xte@w)
    cond=pte[:,[0,2]]/np.clip((pte[:,0]+pte[:,2])[:,None],1e-12,None)
    out=np.column_stack([(1-pd)*cond[:,0],pd,(1-pd)*cond[:,1]])
    return out

def draw_tournament(df):
    folds=[]
    for name,ts,te,vs,ve in DEV_FOLDS:
        tr=df[(df.date>=ts)&(df.date<=te)].copy(); ho=df[(df.date>=vs)&(df.date<=ve)].copy()
        pm=market_probs(ho); pd=fit_draw_offset(tr,ho,50.0)
        folds.append({"fold":name,"market":wdl_metrics(pm,ho),"draw_adjusted":wdl_metrics(pd,ho)})
    tr=df[(df.date>="2026-05-01")&(df.date<="2026-08-31")].copy()
    sep=df[(df.date>="2026-09-01")&(df.date<="2026-09-20")].copy()
    return {"folds":folds,"september":{"market":wdl_metrics(market_probs(sep),sep),"draw_adjusted":wdl_metrics(fit_draw_offset(tr,sep,50.0),sep)}}

def fit_softmax(X,y,k,l2=50.0,offset=None):
    y=np.asarray(y,int); n,f=X.shape
    if offset is None:offset=np.zeros((n,k))
    def obj(w):
        B=w.reshape(k-1,f)
        z=offset.copy()
        z[:,:k-1]+=X@B.T
        z=z-z.max(axis=1,keepdims=True)
        logden=np.log(np.exp(z).sum(axis=1))
        ll=z[np.arange(n),y]-logden
        return float(-ll.sum()+.5*l2*np.sum(B[:,1:]**2))
    r=minimize(obj,np.zeros((k-1)*f),method="L-BFGS-B",options={"maxiter":350})
    return r.x.reshape(k-1,f)

def htft_direct(train,test,l2=100.0):
    good=train.dropna(subset=["actual_y","ht_y"]).copy()
    gtest=test.dropna(subset=["actual_y","ht_y"]).copy()
    if len(good)<50 or len(gtest)==0:return {"n":0}
    ptr=market_probs(good); pte=market_probs(gtest)
    Xtr,Xte,_=feature_matrix(good,gtest,"market_team_handicap",ptr,pte)
    y=(good.actual_y.to_numpy(int)*3+good.ht_y.to_numpy(int)).astype(int)
    B=fit_softmax(Xtr,y,9,l2)
    z=np.zeros((len(gtest),9));z[:,:8]+=Xte@B.T
    z=z-z.max(axis=1,keepdims=True); p=np.exp(z);p/=p.sum(axis=1,keepdims=True)
    actual=(gtest.actual_y.to_numpy(int)*3+gtest.ht_y.to_numpy(int)).astype(int)
    order=np.argsort(p,axis=1)[:,::-1]
    out={"n":len(gtest)}
    for k in [1,2,3]:
        out[f"top{k}"]=float(np.mean([actual[i] in order[i,:k] for i in range(len(actual))]))
    out["log_loss"]=float(-np.mean(np.log(np.clip(p[np.arange(len(actual)),actual],1e-12,1))))
    return out

def htft_tournament(df):
    folds=[]
    for name,ts,te,vs,ve in DEV_FOLDS:
        tr=df[(df.date>=ts)&(df.date<=te)].copy();ho=df[(df.date>=vs)&(df.date<=ve)].copy()
        base=htft_eval(tr,ho,market_probs(ho)); direct=htft_direct(tr,ho)
        folds.append({"fold":name,"conditional":base,"direct9":direct})
    tr=df[(df.date>="2026-05-01")&(df.date<="2026-08-31")].copy()
    sep=df[(df.date>="2026-09-01")&(df.date<="2026-09-20")].copy()
    return {"folds":folds,"september":{"conditional":htft_eval(tr,sep,market_probs(sep)),"direct9":htft_direct(tr,sep)}}

def add_causal_strength(df,alpha=.20):
    z=df.sort_values(["date","kickoff","match_id"]).copy()
    atk=defaultdict(lambda:1.30); deff=defaultdict(lambda:1.30)
    league_for=defaultdict(lambda:1.30); league_against=defaultdict(lambda:1.30)
    vals={c:[] for c in ["home_atk_state","home_def_state","away_atk_state","away_def_state","league_home_goal","league_away_goal"]}
    pending_date=None; pending=[]
    def flush(rows):
        for r in rows:
            h,a=str(r.home_team),str(r.away_team); lg=str(r.league)
            hg=float(r.home_goals) if pd.notna(r.home_goals) else None
            ag=float(r.away_goals) if pd.notna(r.away_goals) else None
            if hg is None or ag is None:continue
            atk[h]=(1-alpha)*atk[h]+alpha*hg; deff[h]=(1-alpha)*deff[h]+alpha*ag
            atk[a]=(1-alpha)*atk[a]+alpha*ag; deff[a]=(1-alpha)*deff[a]+alpha*hg
            league_for[lg]=(1-alpha)*league_for[lg]+alpha*hg
            league_against[lg]=(1-alpha)*league_against[lg]+alpha*ag
    records=[]
    for idx,r in z.iterrows():
        d=pd.Timestamp(r.date).normalize()
        if pending_date is not None and d!=pending_date:
            flush(pending); pending=[]
        pending_date=d
        h,a,lg=str(r.home_team),str(r.away_team),str(r.league)
        rec={
          "idx":idx,"home_atk_state":atk[h],"home_def_state":deff[h],
          "away_atk_state":atk[a],"away_def_state":deff[a],
          "league_home_goal":league_for[lg],"league_away_goal":league_against[lg],
        }
        records.append(rec); pending.append(r)
    flush(pending)
    st=pd.DataFrame(records).set_index("idx")
    for c in st.columns:z[c]=st[c]
    return z.sort_index()

def poisson_dynamic_design(train,test):
    cols=["p_home","p_draw","p_away","home_pos_diff","attack_diff","defense_diff","h2h_diff","form_diff",
          "team_modules_missing","home_atk_state","home_def_state","away_atk_state","away_def_state",
          "league_home_goal","league_away_goal"]
    tr=train[cols].astype(float).copy();te=test[cols].astype(float).copy()
    med=tr.median().fillna(0);tr=tr.fillna(med);te=te.fillna(med)
    mu=tr.mean();sd=tr.std().replace(0,1).fillna(1)
    A=((tr-mu)/sd).to_numpy();B=((te-mu)/sd).to_numpy()
    return np.column_stack([np.ones(len(A)),A]),np.column_stack([np.ones(len(B)),B])

def fit_pois(X,y,l2=10.0):
    def obj(w):
        eta=np.clip(X@w,-5,5);lam=np.exp(eta)
        return float(np.sum(lam-y*eta)+.5*l2*np.sum(w[1:]**2))
    return minimize(obj,np.zeros(X.shape[1]),method="L-BFGS-B",options={"maxiter":350}).x

def pois_pmf(k,lam):
    return math.exp(k*math.log(max(lam,1e-12))-lam-gammaln(k+1))

def score_dynamic(train,test,maxg=10):
    Xtr,Xte=poisson_dynamic_design(train,test)
    wh=fit_pois(Xtr,train.home_goals.fillna(train.home_goals.median()).to_numpy(float),10)
    wa=fit_pois(Xtr,train.away_goals.fillna(train.away_goals.median()).to_numpy(float),10)
    lh=np.exp(np.clip(Xte@wh,-5,5));la=np.exp(np.clip(Xte@wa,-5,5))
    hits={1:0,2:0,3:0,5:0};n=0;nll=[]
    for i,(_,r) in enumerate(test.iterrows()):
        if pd.isna(r.home_goals) or pd.isna(r.away_goals):continue
        h0,a0=int(r.home_goals),int(r.away_goals)
        if h0>maxg or a0>maxg:continue
        mat=np.zeros((maxg+1,maxg+1))
        for h in range(maxg+1):
            ph=pois_pmf(h,lh[i])
            for a in range(maxg+1):mat[h,a]=ph*pois_pmf(a,la[i])
        mat/=mat.sum();flat=mat.ravel();act=h0*(maxg+1)+a0;order=np.argsort(flat)[::-1]
        for k in hits:hits[k]+=int(act in order[:k])
        nll.append(-math.log(max(flat[act],1e-12)));n+=1
    return {"n":n,"top1":hits[1]/n if n else None,"top2":hits[2]/n if n else None,
            "top3":hits[3]/n if n else None,"top5":hits[5]/n if n else None,
            "score_nll":float(np.mean(nll)) if nll else None}

def score_tournament(df):
    z=add_causal_strength(df)
    folds=[]
    for name,ts,te,vs,ve in DEV_FOLDS:
        tr=z[(z.date>=ts)&(z.date<=te)].copy();ho=z[(z.date>=vs)&(z.date<=ve)].copy()
        base=score_eval(tr,ho,market_probs(ho),0.0)
        dyn=score_dynamic(tr,ho)
        folds.append({"fold":name,"pooled":base,"dynamic":dyn})
    tr=z[(z.date>="2026-05-01")&(z.date<="2026-08-31")].copy()
    sep=z[(z.date>="2026-09-01")&(z.date<="2026-09-20")].copy()
    return {"folds":folds,"september":{"pooled":score_eval(tr,sep,market_probs(sep),0.0),"dynamic":score_dynamic(tr,sep)}}

def choose_best_devig(df):
    rows=[]
    for name,ts,te,vs,ve in DEV_FOLDS:
        ho=df[(df.date>=vs)&(df.date<=ve)].copy()
        c=devig_compare(ho)
        rows.append({"fold":name,**c})
    def avg(method,key):
        return float(np.mean([r[method][key] for r in rows]))
    winner=min(["proportional","power"],key=lambda m:(avg(m,"log_loss"),avg(m,"rps")))
    return {"folds":rows,"selected":winner,
            "dev_avg":{m:{"accuracy":avg(m,"accuracy"),"log_loss":avg(m,"log_loss"),"rps":avg(m,"rps")} for m in ["proportional","power"]}}

def decision(result):
    rel=result["reliability"]["selected_dev"]
    sep=result["reliability"]["september"]
    draw=result["draw"]["september"]
    ht=result["htft"]["september"]
    sc=result["score"]["september"]
    return {
      "full_coverage_wdl":"MARKET",
      "devig":result["devig"]["selected"],
      "selective_reliability":rel["variant"],
      "selective_reliability_l2":rel["l2"],
      "selective_sep_accuracy":sep["accuracy"],
      "selective_sep_coverage":sep["coverage"],
      "selective_increment_vs_equal_coverage_pmax":sep["increment_vs_equal_coverage_pmax"],
      "draw_branch":"KEEP_MARKET" if draw["draw_adjusted"]["log_loss"]>=draw["market"]["log_loss"] or draw["draw_adjusted"]["rps"]>=draw["market"]["rps"] else "DRAW_ADJUSTED_CANDIDATE",
      "htft":"CONDITIONAL" if ht["conditional"]["log_loss"]<=ht["direct9"]["log_loss"] else "DIRECT9_CANDIDATE",
      "score":"DYNAMIC" if sc["dynamic"]["score_nll"]<sc["pooled"]["score_nll"] else "POOLED",
      "stable_status":"CANDIDATE_ONLY"
    }

def run():
    df,missing=prep("2026-05-01","2026-09-20")
    if missing:raise RuntimeError(f"missing cache dates={len(missing)} first={missing[:5]}")
    df=add_causal_strength(df)
    devig=choose_best_devig(df)
    best,table=reliability_tournament(df)
    sep=final_reliability_sep(df,best)
    result={
      "system":"HH520 Relationship Discovery + Multi-Formula Tournament V3.2",
      "rows":len(df),
      "month_counts":{str(k):int(v) for k,v in df.groupby(df.date.dt.strftime("%Y-%m")).size().items()},
      "devig":devig,
      "v31_increment_audit":v31_gate_increment(df),
      "reliability":{"selected_dev":best,"all_candidates":table,"september":sep},
      "draw":draw_tournament(df),
      "htft":htft_tournament(df),
      "score":score_tournament(df),
      "stable_access":"READ_ONLY",
      "status":"CANDIDATE_ONLY",
      "notes":["September is development stress only, not pristine final test.",
               "All predictors are pre-match fields; results are labels only.",
               "League effects use shrinkage by strong L2 and only leagues with >=30 training rows."]
    }
    result["best_architecture"]=decision(result)
    return result

def pct(x):
    return "N/A" if x is None else f"{100*x:.1f}%"

def render(r):
    b=r["best_architecture"];rel=r["reliability"];s=rel["september"]
    v=r["v31_increment_audit"];d=r["draw"]["september"];h=r["htft"]["september"];sc=r["score"]["september"]
    L=[
      "# HH520 V3.2 Relationship Discovery + Multi-Formula Tournament","",
      f"- Rows: **{r['rows']}**",
      "- Stable: **READ_ONLY / CANDIDATE_ONLY**",
      "- September: **development stress only**","",
      "## Final winner","",
      f"- Full coverage WDL: **{b['full_coverage_wdl']}**",
      f"- De-vig: **{b['devig']}**",
      f"- Selective reliability: **{b['selective_reliability']}**, L2={b['selective_reliability_l2']}",
      f"- September selective: **{pct(s['accuracy'])}**, coverage **{pct(s['coverage'])}**, equal-coverage pmax control **{pct(s['equal_coverage_pmax_accuracy'])}**, incremental **{pct(s['increment_vs_equal_coverage_pmax'])}**",
      f"- Draw branch: **{b['draw_branch']}**",
      f"- HTFT: **{b['htft']}**",
      f"- Score: **{b['score']}**","",
      "## V3.1 0.73 + 2/5 incremental audit","",
    ]
    for k,z in v.items():
        L.append(f"- {k}: pmax-only {pct(z['pmax_only']['accuracy'])} n={z['pmax_only']['n']} vs +2/5 {pct(z['pmax_plus_2of5']['accuracy'])} n={z['pmax_plus_2of5']['n']}")
    L += ["","## Reliability dev winner","",
          f"- Variant: {rel['selected_dev']['variant']}, L2={rel['selected_dev']['l2']}",
          f"- Dev OOF: {pct(rel['selected_dev']['accuracy'])}, n={rel['selected_dev']['n']}, Wilson lower {pct(rel['selected_dev']['wilson_low'])}, worst fold {pct(rel['selected_dev']['min_fold_accuracy'])}",
          f"- Equal-coverage pmax control: {pct(rel['selected_dev']['pmax_control_accuracy'])}",
          f"- Increment: {pct(rel['selected_dev']['increment_vs_equal_coverage_pmax'])}","",
          "### September top relationship coefficients"]
    for z in s["top_coefficients"]:
        L.append(f"- {z['feature']}: {z['coef']:+.3f}")
    L += ["","## Draw September","",
          f"- Market LL/RPS: {d['market']['log_loss']:.4f}/{d['market']['rps']:.4f}",
          f"- Draw-adjusted LL/RPS: {d['draw_adjusted']['log_loss']:.4f}/{d['draw_adjusted']['rps']:.4f}","",
          "## HTFT September","",
          f"- Conditional: Top1 {pct(h['conditional']['top1'])}, Top2 {pct(h['conditional']['top2'])}, Top3 {pct(h['conditional']['top3'])}, LL {h['conditional']['log_loss']:.4f}",
          f"- Direct9: Top1 {pct(h['direct9']['top1'])}, Top2 {pct(h['direct9']['top2'])}, Top3 {pct(h['direct9']['top3'])}, LL {h['direct9']['log_loss']:.4f}","",
          "## Score September","",
          f"- Pooled Poisson: Top1 {pct(sc['pooled']['top1'])}, Top2 {pct(sc['pooled']['top2'])}, Top3 {pct(sc['pooled']['top3'])}, Top5 {pct(sc['pooled']['top5'])}, NLL {sc['pooled']['score_nll']:.4f}",
          f"- Dynamic: Top1 {pct(sc['dynamic']['top1'])}, Top2 {pct(sc['dynamic']['top2'])}, Top3 {pct(sc['dynamic']['top3'])}, Top5 {pct(sc['dynamic']['top5'])}, NLL {sc['dynamic']['score_nll']:.4f}","",
          "## Decision","",
          "**CANDIDATE_ONLY.** Freeze the winning architecture and certify only on a fresh post-freeze shadow window."]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json",type=Path,required=True);ap.add_argument("--md",type=Path,required=True)
    a=ap.parse_args();r=run()
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    a.md.write_text(render(r),encoding="utf-8")
    print(render(r))
if __name__=="__main__":main()
