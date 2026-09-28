"""HH520 multi-skill fusion holdout experiment.

Research-only, existing cached 10027s pages only. Stable is never modified.
Selection: May-Jun development -> Jul-Aug validation. Sep1-20 is untouched holdout.
"""
from __future__ import annotations
import json, math, os, re
from copy import deepcopy
from pathlib import Path
from collections import defaultdict
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from collector.hh520_10027_parser import parse_10027s_markdown
from analysis.match_analysis import analyze_match

MAX_GOALS=8
SCORE_KEYS=[(h,a) for h in range(9) for a in range(9)]
SCORE_INDEX={x:i for i,x in enumerate(SCORE_KEYS)}
OUTCOMES=("HOME","DRAW","AWAY")
OUT_INDEX={x:i for i,x in enumerate(OUTCOMES)}
HTFT_KEYS=tuple(f"{h}_{f}" for h in OUTCOMES for f in OUTCOMES)
HTFT_INDEX={x:i for i,x in enumerate(HTFT_KEYS)}
SPLITS={"dev1":("2026-05-01","2026-06-30"),"dev2":("2026-07-01","2026-08-31"),"stress":("2026-09-01","2026-09-20")}
POSTMATCH={"result","half_score","full_score","actual_score","actual_half_score","actual_outcome","actual_total_goals","result_label","label_status","label_match_method"}

def split_for(day):
    for k,(a,b) in SPLITS.items():
        if a<=day<=b:return k
    return None

def pair(v):
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

def outcome(x):
    return "HOME" if x[0]>x[1] else "AWAY" if x[0]<x[1] else "DRAW"

def norm(v):
    a=np.maximum(np.asarray(v,dtype=float),0)
    s=float(a.sum())
    return a/s if math.isfinite(s) and s>0 else np.ones_like(a)/len(a)

def pois(lam,n=8):
    lam=max(1e-6,float(lam)); out=[math.exp(-lam)]
    for k in range(1,n+1):out.append(out[-1]*lam/k)
    return np.asarray(out,dtype=float)

def ind_matrix(lh,la):
    return norm(np.outer(pois(lh),pois(la)).reshape(-1))

def dc_matrix(lh,la,rho):
    m=np.outer(pois(lh),pois(la))
    factors={(0,0):1-lh*la*rho,(0,1):1+lh*rho,(1,0):1+la*rho,(1,1):1-rho}
    for (h,a),t in factors.items():m[h,a]*=max(1e-8,t)
    return norm(m.reshape(-1))

def biv_matrix(lh,la,alpha):
    shared=max(0,min(float(alpha)*min(lh,la),.85*min(lh,la)))
    p1,p2,p3=pois(max(1e-6,lh-shared)),pois(max(1e-6,la-shared)),pois(shared)
    m=np.zeros((9,9))
    for h in range(9):
        for a in range(9):
            m[h,a]=sum(p1[h-k]*p2[a-k]*p3[k] for k in range(min(h,a)+1))
    return norm(m.reshape(-1))

def score_wdl(p):
    out=np.zeros(3)
    for i,(h,a) in enumerate(SCORE_KEYS):out[0 if h>a else 2 if h<a else 1]+=p[i]
    return norm(out)

def htft_ft(p):
    out=np.zeros(3)
    for i,key in enumerate(HTFT_KEYS):out[OUT_INDEX[key.split("_",1)[1]]]+=p[i]
    return norm(out)

def finite(v,default=np.nan):
    try:x=float(v)
    except (TypeError,ValueError):return default
    return x if math.isfinite(x) else default

def nested(d,*keys):
    cur=d
    for k in keys:
        if not isinstance(cur,dict):return np.nan
        cur=cur.get(k)
    return finite(cur)

def stable_row(match):
    full=pair(match.get("result") or match.get("full_score")); half=pair(match.get("half_score"))
    if full is None or half is None:return None
    prematch=deepcopy(match)
    for k in POSTMATCH:prematch.pop(k,None)
    a=analyze_match(prematch); prob=a.get("probability") or {}; sc=a.get("score") or {}; ht=a.get("htft") or {}; dec=a.get("decision") or {}
    if not prob.get("valid") or not sc.get("valid") or not ht.get("valid"):return None
    pp=prob.get("probabilities") or {}
    wdl=norm([pp.get("home",0),pp.get("draw",0),pp.get("away",0)])
    sd=np.zeros(81)
    for x in sc.get("all_scores") or []:
        q=(int(x["home"]),int(x["away"]))
        if q in SCORE_INDEX:sd[SCORE_INDEX[q]]=float(x["probability"])
    hd=np.zeros(9)
    for x in ht.get("distribution") or []:
        key=f"{x['ht']}_{x['ft']}"
        if key in HTFT_INDEX:hd[HTFT_INDEX[key]]=float(x["probability"])
    raw=dec.get("resolved_direction") or prob.get("direction")
    page=match.get("page_probability") or {}; market=match.get("market") or {}; pos=match.get("possession") or {}; f=match.get("research_factors") or {}
    return {
      "date":str(match.get("date") or ""),"league":str(match.get("league") or ""),"home_team":str(match.get("home_team") or ""),"away_team":str(match.get("away_team") or ""),
      "actual_score":full,"actual_half":half,"actual_ft":outcome(full),"actual_ht":outcome(half),"actual_htft":f"{outcome(half)}_{outcome(full)}",
      "b0_wdl":wdl.tolist(),"b0_score":norm(sd).tolist(),"b0_htft":norm(hd).tolist(),
      "b0_current_ft":{"home":"HOME","draw":"DRAW","away":"AWAY"}.get(raw),
      "b0_lambda_home":float(sc["lambda_home"]),"b0_lambda_away":float(sc["lambda_away"]),
      "page_home":finite(page.get("home")),"page_draw":finite(page.get("draw")),"page_away":finite(page.get("away")),
      "market_home_odds":finite(market.get("home_odds")),"market_draw_odds":finite(market.get("draw_odds")),"market_away_odds":finite(market.get("away_odds")),
      "pos_home":finite(pos.get("home")),"pos_away":finite(pos.get("away")),"pos_diff":finite(pos.get("diff")),"smooth_p":finite(pos.get("smooth_p")),
      "home_attack":finite(f.get("home_attack")),"away_attack":finite(f.get("away_attack")),"home_defense":finite(f.get("home_defense")),"away_defense":finite(f.get("away_defense")),
      "home_h2h":finite(f.get("home_h2h")),"away_h2h":finite(f.get("away_h2h")),"home_form":finite(f.get("home_form")),"away_form":finite(f.get("away_form")),
    }

def load_rows():
    if os.getenv("HH520_MULTISKILL_OFFLINE_ONLY")!="1":raise SystemExit("offline-only guard missing")
    rows={k:[] for k in SPLITS}; files=sorted(Path("cache").glob("10027s_2026-*.json")); parsed=0; bad=[]
    for pth in files:
        day=pth.stem.replace("10027s_",""); sp=split_for(day)
        if not sp:continue
        try:
            payload=json.loads(pth.read_text(encoding="utf-8")); md=(((payload.get("raw") or {}).get("data") or {}).get("markdown"))
            if not isinstance(md,str):bad.append(pth.name);continue
            matches=parse_10027s_markdown(md); parsed+=1
        except Exception:
            bad.append(pth.name);continue
        for m in matches:
            r=stable_row(m)
            if r is not None:rows[sp].append(r)
    for sp in rows:rows[sp].sort(key=lambda r:(r["date"],r["league"],r["home_team"],r["away_team"]))
    return rows,{"cache_files_total":len(files),"parsed_files_in_window":parsed,"invalid_files":bad,"rows":{k:len(v) for k,v in rows.items()}}

class TeamStrength:
    def __init__(self,halftime=False,prior=5):
        self.halftime=halftime;self.prior=float(prior);self.league={};self.hs=defaultdict(lambda:[0.,0.,0]);self.as_=defaultdict(lambda:[0.,0.,0]);self.gh=1.45;self.ga=1.15
    def fit(self,rows):
        acc=defaultdict(lambda:[0.,0.,0]);gh=ga=n=0
        for r in rows:
            h,a=r["actual_half"] if self.halftime else r["actual_score"];lg=r["league"]
            acc[lg][0]+=h;acc[lg][1]+=a;acc[lg][2]+=1
            self.hs[(lg,r["home_team"])][0]+=h;self.hs[(lg,r["home_team"])][1]+=a;self.hs[(lg,r["home_team"])][2]+=1
            self.as_[(lg,r["away_team"])][0]+=a;self.as_[(lg,r["away_team"])][1]+=h;self.as_[(lg,r["away_team"])][2]+=1
            gh+=h;ga+=a;n+=1
        if n:self.gh=gh/n;self.ga=ga/n
        for lg,(h,a,c) in acc.items():
            s=12.;self.league[lg]=((h+s*self.gh)/(c+s),(a+s*self.ga)/(c+s),c)
        return self
    def predict(self,r):
        lh0,la0,_=self.league.get(r["league"],(self.gh,self.ga,0));lh0=max(lh0,.05);la0=max(la0,.05)
        hs=self.hs.get((r["league"],r["home_team"]),[0.,0.,0]);as_=self.as_.get((r["league"],r["away_team"]),[0.,0.,0]);p=self.prior
        ha=((hs[0]+p*lh0)/(hs[2]+p))/lh0;hd=((hs[1]+p*la0)/(hs[2]+p))/la0;aa=((as_[0]+p*la0)/(as_[2]+p))/la0;ad=((as_[1]+p*lh0)/(as_[2]+p))/lh0
        ha,hd,aa,ad=[float(np.clip(x,.45,2.25)) for x in (ha,hd,aa,ad)]
        lh=float(np.clip(lh0*ha*ad,.12,5.5));la=float(np.clip(la0*aa*hd,.12,5.5))
        return lh,la,{"league_home_mean":lh0,"league_away_mean":la0,"home_samples":hs[2],"away_samples":as_[2]}

def fit_rho(train,s):
    best=None
    for rho in np.linspace(-.25,.25,51):
        ll=0.
        for r in train:
            lh,la,_=s.predict(r);p=dc_matrix(lh,la,float(rho));idx=SCORE_INDEX.get(tuple(r["actual_score"]));ll+=math.log(max(float(p[idx]) if idx is not None else 1e-12,1e-12))
        if best is None or ll>best[0]:best=(ll,float(rho))
    return best[1]

def fit_alpha(train,s):
    best=None
    for alpha in np.linspace(0,.45,24):
        ll=0.
        for r in train:
            lh,la,_=s.predict(r);p=biv_matrix(lh,la,float(alpha));idx=SCORE_INDEX.get(tuple(r["actual_score"]));ll+=math.log(max(float(p[idx]) if idx is not None else 1e-12,1e-12))
        if best is None or ll>best[0]:best=(ll,float(alpha))
    return best[1]

FEATURES=("b0_lambda_home","b0_lambda_away","page_home","page_draw","page_away","market_home_odds","market_draw_odds","market_away_odds","pos_home","pos_away","pos_diff","smooth_p","home_attack","away_attack","home_defense","away_defense","home_h2h","away_h2h","home_form","away_form")
def mlX(rows,s):
    data=[]
    for r in rows:
        lh,la,m=s.predict(r);data.append(list(r["b0_wdl"])+[r.get(k,np.nan) for k in FEATURES]+[lh,la,m["league_home_mean"],m["league_away_mean"],float(m["home_samples"]),float(m["away_samples"])])
    return np.asarray(data,dtype=float)
def fit_ml(train,s):
    X=mlX(train,s);yh=np.asarray([r["actual_score"][0] for r in train],float);ya=np.asarray([r["actual_score"][1] for r in train],float)
    kw=dict(loss="poisson",learning_rate=.045,max_iter=180,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=3.,random_state=520)
    return HistGradientBoostingRegressor(**kw).fit(X,yh),HistGradientBoostingRegressor(**kw).fit(X,ya)

def score_models(train,target):
    s=TeamStrength(False,5).fit(train);rho=fit_rho(train,s);alpha=fit_alpha(train,s);mh,ma=fit_ml(train,s);X=mlX(target,s)
    ph=np.clip(mh.predict(X),.12,5.5);pa=np.clip(ma.predict(X),.12,5.5)
    out={"B0":np.asarray([r["b0_score"] for r in target],float),"S1":[],"S2":[],"S3":[],"S4":[]}
    for i,r in enumerate(target):
        lh,la,_=s.predict(r);out["S1"].append(ind_matrix(lh,la));out["S2"].append(dc_matrix(lh,la,rho));out["S3"].append(biv_matrix(lh,la,alpha));out["S4"].append(ind_matrix(ph[i],pa[i]))
    for k in ("S1","S2","S3","S4"):out[k]=np.asarray(out[k],float)
    return out,{"dixon_coles_rho":rho,"bivariate_shared_alpha":alpha,"ml_model":"HistGradientBoostingRegressor(loss=poisson)","ml_feature_count":int(X.shape[1])}

def ht_models(train,target):
    s=TeamStrength(True,6).fit(train);counts=np.ones((3,3))*2
    for r in train:counts[OUT_INDEX[r["actual_ht"]],OUT_INDEX[r["actual_ft"]]]+=1
    trans=counts/counts.sum(axis=1,keepdims=True);h1=[];h2=[]
    for r in target:
        lh,la,_=s.predict(r);mat=ind_matrix(lh,la).reshape(9,9);pht=np.zeros(3)
        for h in range(9):
            for a in range(9):pht[0 if h>a else 2 if h<a else 1]+=mat[h,a]
        pht=norm(pht);pft=norm(r["b0_wdl"]);j1=np.zeros(9);j2=np.zeros(9)
        for hi,ht in enumerate(OUTCOMES):
            for fi,ft in enumerate(OUTCOMES):
                idx=HTFT_INDEX[f"{ht}_{ft}"];j1[idx]=pht[hi]*pft[fi];j2[idx]=pht[hi]*trans[hi,fi]
        h1.append(norm(j1));h2.append(norm(j2))
    return {"B0":np.asarray([r["b0_htft"] for r in target],float),"H1":np.asarray(h1),"H2":np.asarray(h2)},{"transition_matrix":trans.tolist(),"laplace_prior":2.}

def score_metrics(P,rows):
    P=np.asarray(P,float);y=np.asarray([SCORE_INDEX.get(tuple(r["actual_score"]),-1) for r in rows]);order=np.argsort(-P,axis=1);out={"n":len(rows)}
    for k in (1,2,3):
        hits=sum(int(y[i]>=0 and y[i] in order[i,:k]) for i in range(len(rows)));out[f"top{k}_hits"]=int(hits);out[f"top{k}_accuracy"]=hits/len(rows)
    out["log_loss"]=float(np.mean([-math.log(max(float(P[i,y[i]]) if y[i]>=0 else 1e-12,1e-12)) for i in range(len(rows))]))
    totals=np.asarray([h+a for h,a in SCORE_KEYS],float);errs=[];mh=0
    for i,r in enumerate(rows):
        actual=sum(r["actual_score"]);errs.append(abs(float(np.dot(P[i],totals))-actual);mass=defaultdict(float)
        for j,t in enumerate(totals):mass[int(t)]+=float(P[i,j])
        mh+=int(max(mass.items(),key=lambda kv:kv[1])[0]==actual)
    out["total_goals_mae"]=float(np.mean(errs));out["total_goals_mode_hits"]=int(mh);out["total_goals_mode_accuracy"]=mh/len(rows)
    return out

def ht_metrics(P,rows):
    P=np.asarray(P,float);y=np.asarray([HTFT_INDEX[r["actual_htft"]] for r in rows]);o=np.argsort(-P,axis=1);out={"n":len(rows)}
    for k in (1,2,3):
        h=sum(int(y[i] in o[i,:k]) for i in range(len(rows)));out[f"top{k}_hits"]=int(h);out[f"top{k}_accuracy"]=h/len(rows)
    out["log_loss"]=float(np.mean([-math.log(max(float(P[i,y[i]]),1e-12)) for i in range(len(rows))]));return out

def wdl_metrics(P,rows,current=None):
    P=np.asarray(P,float);y=np.asarray([OUT_INDEX[r["actual_ft"]] for r in rows]);pred=np.argmax(P,axis=1);h=int(np.sum(pred==y));oh=np.zeros_like(P);oh[np.arange(len(rows)),y]=1
    out={"n":len(rows),"top1_hits":h,"top1_accuracy":h/len(rows),"brier":float(np.mean(np.sum((P-oh)**2,axis=1))),"log_loss":float(np.mean([-math.log(max(float(P[i,y[i]]),1e-12)) for i in range(len(rows))]))}
    if current is not None:
        ch=sum(int(current[i]==rows[i]["actual_ft"]) for i in range(len(rows)));out["stable_decision_hits"]=int(ch);out["stable_decision_accuracy"]=ch/len(rows)
    return out

def comps(k,total=10,minu=1):
    if k==1:yield (total,);return
    def rec(left,parts):
        if len(parts)==k-1:
            if left>=minu:yield tuple(parts+[left])
            return
        rem=k-len(parts)-1
        for x in range(minu,left-minu*rem+1):yield from rec(left-x,parts+[x])
    yield from rec(total,[])

def blend(arr,names,w):
    out=np.zeros_like(arr[names[0]],float)
    for n,x in zip(names,w):out+=float(x)*arr[n]
    s=out.sum(axis=1,keepdims=True);s[s<=0]=1;return out/s

def select_score(models,rows,combo):
    best=None
    for u in comps(len(combo)):
        w=np.asarray(u,float)/10;P=blend(models,combo,w);m=score_metrics(P,rows);rank=(m["top2_hits"],m["top1_hits"],m["top3_hits"],-m["log_loss"],-m["total_goals_mae"])
        if best is None or rank>best[0]:best=(rank,w,m)
    return {"models":list(combo),"weights":{n:float(best[1][i]) for i,n in enumerate(combo)},"validation":best[2]}

def select_ht(models,rows,combo):
    best=None
    for u in comps(len(combo)):
        w=np.asarray(u,float)/10;P=blend(models,combo,w);m=ht_metrics(P,rows);rank=(m["top2_hits"],m["top1_hits"],m["top3_hits"],-m["log_loss"])
        if best is None or rank>best[0]:best=(rank,w,m)
    return {"models":list(combo),"weights":{n:float(best[1][i]) for i,n in enumerate(combo)},"validation":best[2]}

def apply(models,spec):return blend(models,spec["models"],[spec["weights"][n] for n in spec["models"]])

def select_wdl(rows,sf):
    b=np.asarray([r["b0_wdl"] for r in rows]);s=np.asarray([score_wdl(p) for p in sf]);best=None
    for w in np.linspace(0,1,11):
        P=w*b+(1-w)*s;m=wdl_metrics(P,rows);rank=(m["top1_hits"],-m["brier"],-m["log_loss"])
        if best is None or rank>best[0]:best=(rank,float(w),m)
    return {"stable_weight":best[1],"validation":best[2]}
def apply_wdl(rows,sf,spec):
    b=np.asarray([r["b0_wdl"] for r in rows]);s=np.asarray([score_wdl(p) for p in sf]);w=spec["stable_weight"];return np.asarray([norm(w*b[i]+(1-w)*s[i]) for i in range(len(rows))])

def select_gate(rows,sf,hf,wf):
    cand=[]
    for pmax in (0,.42,.46,.50,.54,.58):
      for agree_req in (1,2,3):
       for mass_min in (0,.16,.20,.24):
        keep=[]
        for i in range(len(rows)):
            wd=int(np.argmax(wf[i]));sd=int(np.argmax(score_wdl(sf[i])));hd=int(np.argmax(htft_ft(hf[i])));agree=1+int(wd==sd)+int(wd==hd);mass=float(np.sort(sf[i])[-2:].sum())
            keep.append(float(np.max(wf[i]))>=pmax and agree>=agree_req and mass>=mass_min)
        idx=np.flatnonzero(np.asarray(keep,bool))
        if len(idx)<int(.55*len(rows)):continue
        sub=[rows[i] for i in idx];sm=score_metrics(sf[idx],sub);hm=ht_metrics(hf[idx],sub);wm=wdl_metrics(wf[idx],sub);cov=len(idx)/len(rows);q=.55*sm["top2_accuracy"]+.35*hm["top2_accuracy"]+.10*wm["top1_accuracy"]+.025*cov
        cand.append({"pmax_min":pmax,"agree_required":agree_req,"score_top2_mass_min":mass_min,"coverage":cov,"objective":q,"score":sm,"htft":hm,"wdl":wm})
    return max(cand,key=lambda x:(x["objective"],x["coverage"])) if cand else {"pmax_min":0,"agree_required":1,"score_top2_mass_min":0,"coverage":1}

def apply_gate(rows,sf,hf,wf,spec):
    keep=[]
    for i in range(len(rows)):
        wd=int(np.argmax(wf[i]));sd=int(np.argmax(score_wdl(sf[i])));hd=int(np.argmax(htft_ft(hf[i])));agree=1+int(wd==sd)+int(wd==hd);mass=float(np.sort(sf[i])[-2:].sum())
        keep.append(float(np.max(wf[i]))>=spec["pmax_min"] and agree>=spec["agree_required"] and mass>=spec["score_top2_mass_min"])
    idx=np.flatnonzero(np.asarray(keep,bool));sub=[rows[i] for i in idx];cov=len(idx)/len(rows)
    return {"kept":int(len(idx)),"passed":int(len(rows)-len(idx)),"coverage":cov,"pass_ratio":1-cov,"score":score_metrics(sf[idx],sub) if len(idx) else None,"htft":ht_metrics(hf[idx],sub) if len(idx) else None,"wdl":wdl_metrics(wf[idx],sub) if len(idx) else None}

def bootstrap(rows,b,c,kind,k,reps=5000):
    rng=np.random.default_rng(520);n=len(rows)
    if kind=="score":
        y=np.asarray([SCORE_INDEX.get(tuple(r["actual_score"]),-1) for r in rows]);bo=np.argsort(-b,axis=1)[:,:k];co=np.argsort(-c,axis=1)[:,:k];bh=np.asarray([int(y[i]>=0 and y[i] in bo[i]) for i in range(n)]);ch=np.asarray([int(y[i]>=0 and y[i] in co[i]) for i in range(n)])
    else:
        y=np.asarray([HTFT_INDEX[r["actual_htft"]] for r in rows]);bo=np.argsort(-b,axis=1)[:,:k];co=np.argsort(-c,axis=1)[:,:k];bh=np.asarray([int(y[i] in bo[i]) for i in range(n)]);ch=np.asarray([int(y[i] in co[i]) for i in range(n)])
    d=ch-bh;draw=np.empty(reps)
    for j in range(reps):idx=rng.integers(0,n,size=n);draw[j]=d[idx].mean()
    return {"delta":float(d.mean()),"ci95_low":float(np.quantile(draw,.025)),"ci95_high":float(np.quantile(draw,.975))}

def clean(o):
    if isinstance(o,float):return round(o,8) if math.isfinite(o) else None
    if isinstance(o,dict):return {k:clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)):return [clean(v) for v in o]
    return o

def main():
    rows,load=load_rows()
    if len(rows["dev1"])<400 or len(rows["dev2"])<500 or len(rows["stress"])!=302:raise SystemExit(f"insufficient offline cache: {load}")
    d1,d2,st=rows["dev1"],rows["dev2"],rows["stress"];train=d1+d2
    sv,sdv=score_models(d1,d2);stmod,sdt=score_models(train,st);hv,hdv=ht_models(d1,d2);ht, hdt=ht_models(train,st)
    score_single_v={k:score_metrics(v,d2) for k,v in sv.items()};score_single_t={k:score_metrics(v,st) for k,v in stmod.items()}
    ht_single_v={k:ht_metrics(v,d2) for k,v in hv.items()};ht_single_t={k:ht_metrics(v,st) for k,v in ht.items()}
    combos=[("B0","S1"),("B0","S2"),("B0","S3"),("B0","S4"),("B0","S1","S2"),("B0","S2","S3"),("B0","S2","S4"),("B0","S3","S4"),("B0","S2","S3","S4"),("B0","S1","S2","S3","S4")]
    score_specs=[]
    for c in combos:
        q=select_score(sv,d2,c);q["holdout"]=score_metrics(apply(stmod,q),st);score_specs.append(q)
    bests=max(score_specs,key=lambda x:(x["validation"]["top2_hits"],x["validation"]["top1_hits"],x["validation"]["top3_hits"],-x["validation"]["log_loss"]))
    sfv=apply(sv,bests);sft=apply(stmod,bests)
    ht_specs=[]
    for c in [("B0","H1"),("B0","H2"),("B0","H1","H2")]:
        q=select_ht(hv,d2,c);q["holdout"]=ht_metrics(apply(ht,q),st);ht_specs.append(q)
    besth=max(ht_specs,key=lambda x:(x["validation"]["top2_hits"],x["validation"]["top1_hits"],x["validation"]["top3_hits"],-x["validation"]["log_loss"]))
    hfv=apply(hv,besth);hft=apply(ht,besth)
    ws=select_wdl(d2,sfv);wfv=apply_wdl(d2,sfv,ws);wft=apply_wdl(st,sft,ws)
    gs=select_gate(d2,sfv,hfv,wfv);gt=apply_gate(st,sft,hft,wft,gs)
    b0w=np.asarray([r["b0_wdl"] for r in st]);current=[r["b0_current_ft"] for r in st]
    out={
      "status":"READY","kind":"HH520_MULTISKILL_FUSION_HOLDOUT_V1","stable_version":"HH520 Stable V3.5.1","research_only":True,"stable_modified":False,"new_collection":False,"firecrawl_calls":0,"data_source":"EXISTING_10027S_CACHE_ONLY",
      "periods":{"development":SPLITS["dev1"],"validation":SPLITS["dev2"],"holdout":SPLITS["stress"]},"selection_policy":"All choices selected before Sep holdout; Sep1-20 never used for tuning.","load_summary":load,
      "baseline":{"score":score_metrics(stmod["B0"],st),"htft":ht_metrics(ht["B0"],st),"wdl":wdl_metrics(b0w,st,current)},
      "single_models":{"validation_score":score_single_v,"holdout_score":score_single_t,"validation_htft":ht_single_v,"holdout_htft":ht_single_t},
      "score_fusions":score_specs,"htft_fusions":ht_specs,"selected_score_fusion":bests,"selected_htft_fusion":besth,
      "selected_wdl_blend":{**ws,"holdout":wdl_metrics(wft,st)},"selected_gate":{"validation":gs,"holdout":gt},
      "final_raw_fusion_holdout":{"score":score_metrics(sft,st),"htft":ht_metrics(hft,st),"wdl":wdl_metrics(wft,st)},
      "paired_uncertainty":{"score_top1":bootstrap(st,stmod["B0"],sft,"score",1),"score_top2":bootstrap(st,stmod["B0"],sft,"score",2),"score_top3":bootstrap(st,stmod["B0"],sft,"score",3),"htft_top1":bootstrap(st,ht["B0"],hft,"htft",1),"htft_top2":bootstrap(st,ht["B0"],hft,"htft",2)},
      "diagnostics":{"validation_score":sdv,"holdout_score":sdt,"validation_ht":hdv,"holdout_ht":hdt},
      "model_definitions":{"B0":"Current Stable 3.5.1","S1":"Historical team-strength Poisson","S2":"Dixon-Coles","S3":"Bivariate Poisson","S4":"Poisson-loss gradient boosting goal intensity","H1":"Independent first-half Poisson x Stable FT marginal","H2":"Independent first-half Poisson x learned HT->FT transition","F1":"Validation-selected fusion + consistency/PASS gate"},
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"}
    out=clean(out);Path("_multiskill_fusion_holdout.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"load":out["load_summary"],"baseline":out["baseline"],"selected_score_fusion":out["selected_score_fusion"],"selected_htft_fusion":out["selected_htft_fusion"],"final":out["final_raw_fusion_holdout"],"gate":out["selected_gate"],"uncertainty":out["paired_uncertainty"]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
