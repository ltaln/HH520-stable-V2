import json, math, sys
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from scripts.htft_transition_research import load_rows, STATES, fit_multinomial, predict_conditional
from engine.score_layer import _fit_lambdas, _poisson
from engine.htft_layer import htft_layer

BINS=6
TARGET_PROTECTED={"HOME_HOME","AWAY_AWAY","DRAW_HOME"}

def formal_mass(row):
    p={"valid":True,"probabilities":{"home":row["features"]["ph"],"draw":row["features"]["pd"],"away":row["features"]["pa"]}}
    out=htft_layer(p)
    return {f'{x["ht"]}_{x["ft"]}':float(x["probability"]) for x in out["distribution"]}

def ht_probs(lh,la,hs,as_):
    h=_poisson(lh*hs,7); a=_poisson(la*as_,7)
    o={"HOME":0.0,"DRAW":0.0,"AWAY":0.0}
    for i,pi in enumerate(h):
      for j,pj in enumerate(a):
        k="HOME" if i>j else "AWAY" if i<j else "DRAW"
        o[k]+=pi*pj
    s=sum(o.values()) or 1
    return {k:v/s for k,v in o.items()}

def empty_team():
    return {"gf":[0]*BINS,"ga":[0]*BINS,"gf_total":0,"ga_total":0}

def prior_share(num,den,base,k):
    return (num+k*base)/(den+k) if den+k>0 else base

def build_timing_features(timing_matches):
    # Strictly walk-forward: current match timing is added only AFTER its feature snapshot.
    stats=defaultdict(empty_team)
    feats={}
    valid_updates=0
    invalid_rows=0
    for m in sorted(timing_matches,key=lambda x:(x.get("date",""),str(x.get("kickoff") or ""),str(x.get("match_id") or ""))):
        key=(m.get("date"),m.get("home_team"),m.get("away_team"))
        h=stats[m.get("home_team")]; a=stats[m.get("away_team")]
        feats[key]={
          "home":{k:list(v) if isinstance(v,list) else v for k,v in h.items()},
          "away":{k:list(v) if isinstance(v,list) else v for k,v in a.items()},
        }
        b=m.get("bins"); fs=m.get("full")
        if not isinstance(b,dict):
            continue
        try:
            hg=list(map(int,b["HOME"])); ag=list(map(int,b["AWAY"]))
            score=[int(x) for x in str(fs).replace(":","-").split("-")[:2]]
            if len(hg)!=6 or len(ag)!=6 or sum(hg)!=score[0] or sum(ag)!=score[1]:
                invalid_rows+=1; continue
        except Exception:
            invalid_rows+=1; continue
        for i in range(6):
            h["gf"][i]+=hg[i]; h["ga"][i]+=ag[i]
            a["gf"][i]+=ag[i]; a["ga"][i]+=hg[i]
        h["gf_total"]+=sum(hg);h["ga_total"]+=sum(ag)
        a["gf_total"]+=sum(ag);a["ga_total"]+=sum(hg)
        valid_updates+=1
    return feats,valid_updates,invalid_rows

def timing_signals(row, snapshot, k, gamma):
    hb,ab=.36,.44
    h=snapshot["home"];a=snapshot["away"]
    h_fh_num=sum(h["gf"][:3])+sum(a["ga"][:3]); h_fh_den=h["gf_total"]+a["ga_total"]
    a_fh_num=sum(a["gf"][:3])+sum(h["ga"][:3]); a_fh_den=a["gf_total"]+h["ga_total"]
    h_est=prior_share(h_fh_num,h_fh_den,hb,k);a_est=prior_share(a_fh_num,a_fh_den,ab,k)
    hs=hb+gamma*(h_est-hb);as_=ab+gamma*(a_est-ab)
    hs=min(.70,max(.15,hs));as_=min(.70,max(.15,as_))
    # second-half and 76-90 attack-vs-opponent-concede shares, shrunk around complements / 1/6.
    h_sh=prior_share(sum(h["gf"][3:])+sum(a["ga"][3:]),h["gf_total"]+a["ga_total"],1-hb,k)
    a_sh=prior_share(sum(a["gf"][3:])+sum(h["ga"][3:]),a["gf_total"]+h["ga_total"],1-ab,k)
    h_late=prior_share(h["gf"][5]+a["ga"][5],h["gf_total"]+a["ga_total"],1/6,k)
    a_late=prior_share(a["gf"][5]+h["ga"][5],a["gf_total"]+h["ga_total"],1/6,k)
    return {"home_half_share":hs,"away_half_share":as_,"second_diff":h_sh-a_sh,"late_diff":h_late-a_late,
            "history_goals":h["gf_total"]+h["ga_total"]+a["gf_total"]+a["ga_total"]}

def conditional_adjust(cond,second_diff,late_diff,beta2,betaL):
    sig=beta2*second_diff+betaL*late_diff
    vals=np.array(cond,dtype=float)
    vals=np.maximum(vals,1e-9)
    log=np.log(vals)
    log[0]+=sig
    log[2]-=sig
    log[1]-=.35*abs(sig)
    log-=log.max()
    p=np.exp(log);p/=p.sum()
    return p

def timing_transition_mass(row,cond_by_ht,signal,beta2,betaL):
    probs={"home":row["features"]["ph"],"draw":row["features"]["pd"],"away":row["features"]["pa"]}
    fit=_fit_lambdas(probs)
    if not fit:return formal_mass(row)
    _,lh,la=fit
    hp=ht_probs(lh,la,signal["home_half_share"],signal["away_half_share"])
    mass={}
    for hi,ht in enumerate(STATES):
        cond=conditional_adjust(cond_by_ht[ht],signal["second_diff"],signal["late_diff"],beta2,betaL)
        for fi,ft in enumerate(STATES):
            mass[f"{ht}_{ft}"]=hp[ht]*float(cond[fi])
    s=sum(mass.values()) or 1
    return {k:v/s for k,v in mass.items()}

def rank(m): return sorted(m,key=m.get,reverse=True)

def evaluate(rows,masses,formal_masses):
    n=len(rows); stats={"n":n}
    for name,ms in [("candidate",masses),("formal",formal_masses)]:
        t1=t2=t3=0;by=defaultdict(lambda:{"n":0,"top1":0,"top2":0,"top3":0})
        for r,m in zip(rows,ms):
            rr=rank(m);a=r["actual_htft"];z=by[a];z["n"]+=1
            t1+=a==rr[0];t2+=a in rr[:2];t3+=a in rr[:3]
            z["top1"]+=a==rr[0];z["top2"]+=a in rr[:2];z["top3"]+=a in rr[:3]
        for z in by.values():
            for q in ("top1","top2","top3"):z[q+"_rate"]=z[q]/z["n"] if z["n"] else None
        stats[name]={"top1_hits":t1,"top1_accuracy":t1/n if n else None,"top2_hits":t2,"top2_accuracy":t2/n if n else None,
                     "top3_hits":t3,"top3_accuracy":t3/n if n else None,"by_actual":dict(by)}
    return stats

def evaluate_locked_third(rows,timing_masses,formal_masses):
    hits=0; formal_hits=0; by=defaultdict(lambda:{"n":0,"formal_top3":0,"timing_third_top3":0})
    choices=defaultdict(int)
    for r,tm,fm in zip(rows,timing_masses,formal_masses):
        fr=rank(fm);tr=rank(tm);a=r["actual_htft"]
        third=next((x for x in tr if x not in fr[:2]),fr[2])
        hybrid=fr[:2]+[third]
        hits+=a in hybrid;formal_hits+=a in fr[:3];choices[third]+=1
        z=by[a];z["n"]+=1;z["formal_top3"]+=a in fr[:3];z["timing_third_top3"]+=a in hybrid
    n=len(rows)
    for z in by.values():
        z["formal_rate"]=z["formal_top3"]/z["n"];z["timing_rate"]=z["timing_third_top3"]/z["n"]
    return {"n":n,"formal_top3_hits":formal_hits,"formal_top3_accuracy":formal_hits/n,
            "timing_third_hits":hits,"timing_third_accuracy":hits/n,"net_hits":hits-formal_hits,
            "third_distribution":dict(choices),"by_actual":dict(by)}

def main():
    timing=json.loads(Path("_timing_input.json").read_text(encoding="utf-8"))
    timing_matches=timing.get("matches") or []
    snapshots,valid_updates,invalid_rows=build_timing_features(timing_matches)
    allrows=load_rows()
    dev=allrows["dev1"]+allrows["dev2"]
    stress=allrows["stress"]
    models={ht:fit_multinomial(dev,ht,1.0) for ht in STATES}
    cond={ht:predict_conditional(models[ht],stress) for ht in STATES}
    formal=[formal_mass(r) for r in stress]
    aligned=[]
    for i,r in enumerate(stress):
        snap=snapshots.get((r["date"],r["home_team"],r["away_team"]))
        aligned.append(snap)
    coverage=sum(x is not None for x in aligned)

    train_idx=[i for i,r in enumerate(stress) if r["date"]<="2026-09-14"]
    hold_idx=[i for i,r in enumerate(stress) if r["date"]>="2026-09-15"]
    grid=[]
    for k in (2,4,8,12,20,40):
      for gamma in (0,.5,1.0):
       for b2 in (0,.5,1.0,1.5,2.0):
        for bl in (0,.5,1.0,1.5,2.0):
         masses=[]
         for i,r in enumerate(stress):
            snap=aligned[i]
            if snap is None:
                masses.append(formal[i]);continue
            sig=timing_signals(r,snap,k,gamma)
            cb={ht:cond[ht][i] for ht in STATES}
            masses.append(timing_transition_mass(r,cb,sig,b2,bl))
         train_rows=[stress[i] for i in train_idx];train_mass=[masses[i] for i in train_idx];train_formal=[formal[i] for i in train_idx]
         ev=evaluate(train_rows,train_mass,train_formal)
         lock=evaluate_locked_third(train_rows,train_mass,train_formal)
         c=ev["candidate"];f=ev["formal"]
         # Primary objective: Top2, with no Top1 degradation beyond one hit; Top3 and locked-third net are tie-breakers.
         if c["top1_hits"] < f["top1_hits"]-1:continue
         grid.append({"k":k,"gamma":gamma,"beta_second":b2,"beta_late":bl,
                      "train_top1":c["top1_hits"],"train_top2":c["top2_hits"],"train_top3":c["top3_hits"],
                      "train_locked_third_net":lock["net_hits"],"masses":masses})
    grid.sort(key=lambda x:(x["train_top2"],x["train_locked_third_net"],x["train_top3"],x["train_top1"]),reverse=True)
    best=grid[0] if grid else None
    if not best: raise RuntimeError("no timing candidate")
    masses=best.pop("masses")
    train_eval=evaluate([stress[i] for i in train_idx],[masses[i] for i in train_idx],[formal[i] for i in train_idx])
    hold_eval=evaluate([stress[i] for i in hold_idx],[masses[i] for i in hold_idx],[formal[i] for i in hold_idx])
    full_eval=evaluate(stress,masses,formal)
    train_third=evaluate_locked_third([stress[i] for i in train_idx],[masses[i] for i in train_idx],[formal[i] for i in train_idx])
    hold_third=evaluate_locked_third([stress[i] for i in hold_idx],[masses[i] for i in hold_idx],[formal[i] for i in hold_idx])
    full_third=evaluate_locked_third(stress,masses,formal)

    # Also select a third-candidate-specific candidate using training only, while Top1/Top2 remain frozen formal by design.
    third_grid=[]
    for k in (2,4,8,12,20,40):
      for gamma in (0,.5,1.0):
       for b2 in (0,.5,1.0,1.5,2.0,3.0):
        for bl in (0,.5,1.0,1.5,2.0,3.0):
         masses=[]
         for i,r in enumerate(stress):
            snap=aligned[i]
            if snap is None:masses.append(formal[i]);continue
            sig=timing_signals(r,snap,k,gamma);cb={ht:cond[ht][i] for ht in STATES}
            masses.append(timing_transition_mass(r,cb,sig,b2,bl))
         tr=evaluate_locked_third([stress[i] for i in train_idx],[masses[i] for i in train_idx],[formal[i] for i in train_idx])
         third_grid.append({"k":k,"gamma":gamma,"beta_second":b2,"beta_late":bl,"train":tr,"masses":masses})
    third_grid.sort(key=lambda x:(x["train"]["timing_third_hits"],-sum(x["train"]["third_distribution"].values())),reverse=True)
    tb=third_grid[0];tm=tb.pop("masses")
    third_hold=evaluate_locked_third([stress[i] for i in hold_idx],[tm[i] for i in hold_idx],[formal[i] for i in hold_idx])
    third_full=evaluate_locked_third(stress,tm,formal)

    out={
      "mode":"NEW_SEP1_20_GOAL_TIMING_PLUS_EXISTING_MODEL",
      "timing_source_summary":timing.get("summary"),
      "timing_integrity":{"valid_updates":valid_updates,"invalid_timing_rows":invalid_rows,"aligned_rows":coverage,
                          "no_target_leakage":True,"rule":"each match uses only timing from earlier collected matches"},
      "selection_window":"2026-09-01..2026-09-14",
      "holdout_window":"2026-09-15..2026-09-20",
      "selection_used_holdout":False,
      "best_full_ranking_params":best,
      "full_ranking_train":train_eval,
      "full_ranking_holdout":hold_eval,
      "full_ranking_all":full_eval,
      "full_ranking_locked_third_train":train_third,
      "full_ranking_locked_third_holdout":hold_third,
      "full_ranking_locked_third_all":full_third,
      "best_locked_third_params":{k:v for k,v in tb.items() if k!="train"},
      "best_locked_third_train":tb["train"],
      "best_locked_third_holdout":third_hold,
      "best_locked_third_all":third_full,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"
    }
    Path("_timing_transition_optimizer.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "timing_source_summary":out["timing_source_summary"],"timing_integrity":out["timing_integrity"],
      "best_full_ranking_params":best,"holdout":hold_eval,
      "best_locked_third_params":out["best_locked_third_params"],"locked_third_holdout":third_hold
    },ensure_ascii=False,indent=2))

if __name__=="__main__":main()
