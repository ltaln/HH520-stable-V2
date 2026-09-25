import json, math, sys
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.htft_transition_research import load_rows, STATES, fit_multinomial, predict_conditional
from engine.htft_layer import htft_layer
from engine.score_layer import _fit_lambdas, _poisson

CLASSES=tuple(f"{h}_{f}" for h in STATES for f in STATES)

def normalize(m):
    s=sum(max(0.0,float(v)) for v in m.values()) or 1.0
    return {k:max(0.0,float(v))/s for k,v in m.items()}

def formal_mass(row):
    p={"valid":True,"probabilities":{"home":row["features"]["ph"],"draw":row["features"]["pd"],"away":row["features"]["pa"]}}
    o=htft_layer(p)
    return {f'{x["ht"]}_{x["ft"]}':float(x["probability"]) for x in o["distribution"]}

def ht_probs(lh,la,hs,as_):
    h=_poisson(lh*hs,7); a=_poisson(la*as_,7)
    out={"HOME":0.0,"DRAW":0.0,"AWAY":0.0}
    for i,pi in enumerate(h):
        for j,pj in enumerate(a):
            k="HOME" if i>j else "AWAY" if i<j else "DRAW"
            out[k]+=pi*pj
    return normalize(out)

def profile_share(profile,kind,first=True):
    try:
        p=profile[kind]["percent"]
        if len(p)!=6:return None
        return float(sum(p[:3] if first else p[3:]))
    except Exception:
        return None

def profile_late(profile,kind):
    try:
        p=profile[kind]["percent"]
        return float(p[5]) if len(p)==6 else None
    except Exception:
        return None

def avg_valid(*xs):
    vals=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return sum(vals)/len(vals) if vals else None

def timing_signals(home,away,shrink):
    if not (home and away and home.get("available") and away.get("available")):
        return None
    hfh=avg_valid(profile_share(home,"goals_for",True),profile_share(away,"goals_against",True))
    afh=avg_valid(profile_share(away,"goals_for",True),profile_share(home,"goals_against",True))
    hsh=avg_valid(profile_share(home,"goals_for",False),profile_share(away,"goals_against",False))
    ash=avg_valid(profile_share(away,"goals_for",False),profile_share(home,"goals_against",False))
    hlate=avg_valid(profile_late(home,"goals_for"),profile_late(away,"goals_against"))
    alate=avg_valid(profile_late(away,"goals_for"),profile_late(home,"goals_against"))
    if None in (hfh,afh,hsh,ash,hlate,alate):
        return None
    # shrink is the fraction of timing signal used; baseline half shares stay authoritative at 0.
    hs=.36+shrink*(hfh-.36)
    as_=.44+shrink*(afh-.44)
    return {
      "home_half_share":min(.72,max(.12,hs)),
      "away_half_share":min(.72,max(.12,as_)),
      "second_diff":hsh-ash,
      "late_diff":hlate-alate,
      "second_balance":1.0-min(1.0,abs(hsh-ash)),
      "late_balance":1.0-min(1.0,abs(hlate-alate)),
    }

def transition_mass(row,conditional,sig,beta_second,beta_late,beta_draw):
    probs={"home":row["features"]["ph"],"draw":row["features"]["pd"],"away":row["features"]["pa"]}
    fit=_fit_lambdas(probs)
    if not fit:return formal_mass(row)
    _,lh,la=fit
    hp=ht_probs(lh,la,sig["home_half_share"],sig["away_half_share"])
    mass={}
    directional=beta_second*sig["second_diff"]+beta_late*sig["late_diff"]
    drawboost=beta_draw*((sig["second_balance"]+sig["late_balance"])/2-.5)
    for ht in STATES:
        base=np.asarray(conditional[ht],dtype=float)
        log=np.log(np.maximum(base,1e-12))
        log[0]+=directional
        log[2]-=directional
        log[1]+=drawboost
        log-=log.max(); q=np.exp(log);q/=q.sum()
        for i,ft in enumerate(STATES):
            mass[f"{ht}_{ft}"]=hp[ht]*float(q[i])
    return normalize(mass)

def blend_mass(formal,timing,alpha):
    return normalize({k:(1-alpha)*formal[k]+alpha*timing[k] for k in CLASSES})

def rank(m):return sorted(m,key=m.get,reverse=True)

def metrics(rows,masses):
    n=len(rows);t1=t2=t3=0
    by=defaultdict(lambda:{"n":0,"top1":0,"top2":0,"top3":0})
    for r,m in zip(rows,masses):
        rr=rank(m);a=r["actual_htft"];z=by[a];z["n"]+=1
        t1+=int(a==rr[0]);t2+=int(a in rr[:2]);t3+=int(a in rr[:3])
        z["top1"]+=int(a==rr[0]);z["top2"]+=int(a in rr[:2]);z["top3"]+=int(a in rr[:3])
    for z in by.values():
        for k in ("top1","top2","top3"):z[k+"_rate"]=z[k]/z["n"] if z["n"] else None
    return {"n":n,"top1_hits":t1,"top1_accuracy":t1/n if n else None,
            "top2_hits":t2,"top2_accuracy":t2/n if n else None,
            "top3_hits":t3,"top3_accuracy":t3/n if n else None,"by_actual":dict(by)}

def locked_third_metrics(rows,formal,timing):
    hits=base=0;by=defaultdict(lambda:{"n":0,"formal":0,"candidate":0});dist=defaultdict(int)
    for r,f,t in zip(rows,formal,timing):
        fr=rank(f);tr=rank(t);a=r["actual_htft"]
        third=next((x for x in tr if x not in fr[:2]),fr[2])
        rr=fr[:2]+[third];dist[third]+=1
        base+=int(a in fr[:3]);hits+=int(a in rr)
        z=by[a];z["n"]+=1;z["formal"]+=int(a in fr[:3]);z["candidate"]+=int(a in rr)
    for z in by.values():
        z["formal_rate"]=z["formal"]/z["n"];z["candidate_rate"]=z["candidate"]/z["n"]
    n=len(rows)
    return {"n":n,"formal_top3_hits":base,"formal_top3_accuracy":base/n if n else None,
            "candidate_top3_hits":hits,"candidate_top3_accuracy":hits/n if n else None,
            "net_hits":hits-base,"third_distribution":dict(dist),"by_actual":dict(by)}

def main():
    timing=json.loads(Path("_timing_profiles.json").read_text(encoding="utf-8"))
    rows=load_rows()["stress"]
    tmatches=timing.get("matches") or []
    mappings=timing.get("team_mappings") or {}
    def trusted(team):
        mp=mappings.get(team) or {}
        try: score=float(mp.get("score") or 0)
        except Exception: score=0.0
        return score>=0.85
    tmap={}
    rejected_low_confidence=0
    rejected_same_url=0
    for x in tmatches:
        h=x["home_team"]; a=x["away_team"]
        if not (trusted(h) and trusted(a)):
            rejected_low_confidence+=1
            continue
        hu=((mappings.get(h) or {}).get("url"))
        au=((mappings.get(a) or {}).get("url"))
        if hu and au and hu==au:
            rejected_same_url+=1
            continue
        tmap[(x["date"],h,a)]=x

    # Freeze the already-researched HT->FT conditional model on May-Aug only.
    old=load_rows()
    dev=old["dev1"]+old["dev2"]
    models={ht:fit_multinomial(dev,ht,1.0) for ht in STATES}
    cond={ht:predict_conditional(models[ht],rows) for ht in STATES}
    formal=[formal_mass(r) for r in rows]

    train_idx=[i for i,r in enumerate(rows) if r["date"]<="2026-09-14"]
    hold_idx=[i for i,r in enumerate(rows) if r["date"]>="2026-09-15"]
    coverage=sum(1 for r in rows if (tmap.get((r["date"],r["home_team"],r["away_team"])) or {}).get("timing_sides_available")==2)

    grid=[]
    # alpha=0 is exact formal baseline, so the search can explicitly choose no timing effect.
    for shrink in (0.0,.25,.5,.75,1.0):
      for b2 in (0.0,.5,1.0,1.5,2.0):
       for bl in (0.0,.5,1.0,1.5,2.0):
        for bd in (0.0,.25,.5,1.0):
         raw=[]
         for i,r in enumerate(rows):
            x=tmap.get((r["date"],r["home_team"],r["away_team"]))
            sig=timing_signals((x or {}).get("home_timing"),(x or {}).get("away_timing"),shrink) if x else None
            if sig is None:
                raw.append(formal[i]);continue
            cb={ht:cond[ht][i] for ht in STATES}
            raw.append(transition_mass(r,cb,sig,b2,bl,bd))
         for alpha in (0.0,.2,.4,.6,.8,1.0):
            masses=[blend_mass(formal[i],raw[i],alpha) for i in range(len(rows))]
            tr=metrics([rows[i] for i in train_idx],[masses[i] for i in train_idx])
            base=metrics([rows[i] for i in train_idx],[formal[i] for i in train_idx])
            # Do not accept training candidates that sacrifice more than one Top1 hit.
            if tr["top1_hits"]<base["top1_hits"]-1:continue
            grid.append({"shrink":shrink,"beta_second":b2,"beta_late":bl,"beta_draw":bd,"alpha":alpha,
                         "train_top1":tr["top1_hits"],"train_top2":tr["top2_hits"],"train_top3":tr["top3_hits"],
                         "_masses":masses,"_raw":raw})
    grid.sort(key=lambda x:(x["train_top2"],x["train_top3"],x["train_top1"],-x["alpha"]),reverse=True)
    best=grid[0]
    masses=best.pop("_masses");raw=best.pop("_raw")

    train_rows=[rows[i] for i in train_idx]; hold_rows=[rows[i] for i in hold_idx]
    train_formal=[formal[i] for i in train_idx];hold_formal=[formal[i] for i in hold_idx]
    train_m=[masses[i] for i in train_idx];hold_m=[masses[i] for i in hold_idx]
    train_raw=[raw[i] for i in train_idx];hold_raw=[raw[i] for i in hold_idx]

    # Separate optimization for a third candidate while freezing formal Top1+Top2.
    third_grid=[]
    for shrink in (0.0,.25,.5,.75,1.0):
      for b2 in (0.0,.5,1.0,1.5,2.0,3.0):
       for bl in (0.0,.5,1.0,1.5,2.0,3.0):
        for bd in (0.0,.25,.5,1.0):
         raw2=[]
         for i,r in enumerate(rows):
            x=tmap.get((r["date"],r["home_team"],r["away_team"]))
            sig=timing_signals((x or {}).get("home_timing"),(x or {}).get("away_timing"),shrink) if x else None
            if sig is None:raw2.append(formal[i]);continue
            cb={ht:cond[ht][i] for ht in STATES}
            raw2.append(transition_mass(r,cb,sig,b2,bl,bd))
         tr=locked_third_metrics(train_rows,train_formal,[raw2[i] for i in train_idx])
         third_grid.append({"shrink":shrink,"beta_second":b2,"beta_late":bl,"beta_draw":bd,
                            "train_hits":tr["candidate_top3_hits"],"train_net":tr["net_hits"],"_raw":raw2})
    third_grid.sort(key=lambda x:(x["train_hits"],x["train_net"]),reverse=True)
    third=third_grid[0]; third_raw=third.pop("_raw")

    out={
      "mode":"RETROSPECTIVE_GOAL_TIMING_PROFILE_AUGMENTED_HTFT_TRANSITION",
      "timing_collection_summary":timing.get("summary"),
      "timing_coverage_rows":coverage,
      "timing_quality_gate":{"mapping_score_min":0.85,"rejected_low_confidence_matches":rejected_low_confidence,"rejected_same_profile_url_matches":rejected_same_url},
      "base_transition_model":"P_HT_BASE_X_P_FT_GIVEN_HT_MULTINOMIAL_l2_1_MAY_AUG",
      "selection_window":"2026-09-01..2026-09-14",
      "holdout_window":"2026-09-15..2026-09-20",
      "selection_used_holdout_labels":False,
      "historical_point_in_time":False,
      "leakage_warning":"FootyStats profiles are Sep25 current-season snapshots, so this is retrospective exploratory validation, not leakage-clean historical OOS.",
      "best_full_ranking_params":best,
      "full_ranking_train":{"formal":metrics(train_rows,train_formal),"candidate":metrics(train_rows,train_m)},
      "full_ranking_holdout":{"formal":metrics(hold_rows,hold_formal),"candidate":metrics(hold_rows,hold_m)},
      "full_ranking_all":{"formal":metrics(rows,formal),"candidate":metrics(rows,masses)},
      "best_locked_third_params":third,
      "locked_third_train":locked_third_metrics(train_rows,train_formal,[third_raw[i] for i in train_idx]),
      "locked_third_holdout":locked_third_metrics(hold_rows,hold_formal,[third_raw[i] for i in hold_idx]),
      "locked_third_all":locked_third_metrics(rows,formal,third_raw),
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"
    }
    Path("_timing_profile_optimizer.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "timing_collection_summary":out["timing_collection_summary"],
      "coverage":coverage,
      "best_full_ranking_params":best,
      "full_ranking_holdout":out["full_ranking_holdout"],
      "best_locked_third_params":third,
      "locked_third_holdout":out["locked_third_holdout"]
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
