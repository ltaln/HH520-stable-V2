"""HH520 V3.5 shadow candidate.

Goals:
- Quantified FT direction standards instead of raw argmax labels.
- Score model independent of selected FT direction.
- HT/FT requires live goal-timing data and is never backfilled from FT.
- Stable V3.4 remains untouched.
"""
import math

from engine.probability_layer import probability_layer
from engine.data_quality import data_quality_gate

MAX_GOALS = 8
ZH = {"home": "主胜", "draw": "平", "away": "客胜"}
HTZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}

def _poisson(lmbda, n=MAX_GOALS):
    out=[math.exp(-lmbda)]
    for k in range(1,n+1):
        out.append(out[-1]*lmbda/k)
    return out

def _wdl_score_dist(lh, la):
    hp, ap = _poisson(lh), _poisson(la)
    rows=[]; w={"home":0.0,"draw":0.0,"away":0.0}
    for h,ph in enumerate(hp):
        for a,pa in enumerate(ap):
            p=ph*pa
            o="home" if h>a else "away" if h<a else "draw"
            w[o]+=p; rows.append((p,h,a,o))
    total=sum(w.values()) or 1.0
    rows.sort(reverse=True)
    return {k:v/total for k,v in w.items()}, rows

def _fit_lambdas(target):
    best=None
    for ih in range(44):
        lh=0.2+ih*0.1
        for ia in range(44):
            la=0.2+ia*0.1
            w,rows=_wdl_score_dist(lh,la)
            err=sum((w[k]-float(target[k]))**2 for k in ("home","draw","away"))
            if best is None or err<best[0]:
                best=(err,lh,la,rows)
    return best

def ft_policy(probability, quality):
    probs=probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs)!=3 or not quality.get("valid"):
        return {"status":"PASS","direction":None,"raw_direction":probability.get("direction"),"reason":"invalid_probability_or_quality"}
    ordered=sorted(probs.items(),key=lambda kv:float(kv[1]),reverse=True)
    primary,p1=ordered[0]
    margin=float(p1)-float(ordered[1][1])
    warnings=set(quality.get("warnings") or [])
    if "team_modules_missing_or_zero" in warnings and "possession_missing" in warnings:
        return {"status":"PASS","direction":None,"raw_direction":primary,"pmax":p1,"margin":margin,"reason":"critical_structural_data_missing"}
    if primary=="draw":
        return {"status":"DRAW_SHADOW","direction":None,"raw_direction":"draw","pmax":p1,"margin":margin,"reason":"draw_requires_forward_validation"}
    if p1>=0.65:
        tier="HIGH"
    elif p1>=0.60:
        tier="STRONG"
    elif p1>=0.55:
        tier="STANDARD"
    else:
        tier="BALANCED"
    direction=ZH[primary] if tier!="BALANCED" else None
    return {"status":tier,"direction":direction,"raw_direction":primary,"pmax":p1,"margin":margin,
            "thresholds":{"standard":0.55,"strong":0.60,"high":0.65},
            "reason":"historically_calibrated_ft_thresholds"}

def independent_score(probability):
    probs=probability.get("probabilities") or {}
    if len(probs)!=3:
        return {"available":False,"reason":"invalid_probability"}
    fit=_fit_lambdas(probs)
    if fit is None:
        return {"available":False,"reason":"fit_failed"}
    err,lh,la,rows=fit
    total_mass=sum(p for p,_,_,_ in rows) or 1.0
    scored=[]
    for p,h,a,o in rows:
        scored.append({"score":f"{h}:{a}","probability":p/total_mass,"outcome":ZH[o]})
    totals={}
    for row in scored:
        h,a=(int(x) for x in row["score"].split(":"))
        totals[h+a]=totals.get(h+a,0.0)+row["probability"]
    total_top=max(totals.items(),key=lambda kv:kv[1])
    return {"available":True,"model":"FORMAL_HDA_POISSON_V35","home_lambda":lh,"away_lambda":la,
            "fit_error":err,"top2":scored[:2],
            "total_goals":f"{total_top[0]}球","total_goals_probability":total_top[1]}

def _timing_share(side, opponent, mode):
    if side.get("first_half_gf_share") is not None or opponent.get("first_half_ga_share") is not None:
        vals=[side.get("first_half_gf_share"),opponent.get("first_half_ga_share")]
    else:
        vals=[]
        fg1,fg2=side.get("first_half_gf_signal"),side.get("second_half_gf_signal")
        ga1,ga2=opponent.get("first_half_ga_signal"),opponent.get("second_half_ga_signal")
        try:
            if fg1 is not None and fg2 is not None and float(fg1)+float(fg2)>0:
                vals.append(float(fg1)/(float(fg1)+float(fg2)))
            if ga1 is not None and ga2 is not None and float(ga1)+float(ga2)>0:
                vals.append(float(ga1)/(float(ga1)+float(ga2)))
        except (TypeError,ValueError,ZeroDivisionError):
            return None
    nums=[]
    for x in vals:
        try:
            x=float(x)
            if 0<=x<=1: nums.append(x)
        except (TypeError,ValueError):
            pass
    if not nums:
        return None
    return min(0.75,max(0.25,sum(nums)/len(nums)))

def timing_htft(match, score):
    timing=match.get("goal_timing") or {}
    if not timing.get("available"):
        return {"available":False,"status":"PASS","reason":timing.get("reason") or "goal_timing_missing"}
    if not score.get("available"):
        return {"available":False,"status":"PASS","reason":"score_intensity_missing"}
    mode=timing.get("timing_mode")
    home,away=timing.get("home") or {},timing.get("away") or {}
    hs=_timing_share(home,away,mode)
    as_=_timing_share(away,home,mode)
    if hs is None or as_ is None:
        return {"available":False,"status":"PASS","reason":"timing_share_invalid","timing_mode":mode}
    lh,la=float(score["home_lambda"]),float(score["away_lambda"])
    h1,a1=lh*hs,la*as_
    h2,a2=max(0.01,lh-h1),max(0.01,la-a1)
    hp1,ap1=_poisson(h1,6),_poisson(a1,6)
    hp2,ap2=_poisson(h2,7),_poisson(a2,7)
    joint={f"{x}_{y}":0.0 for x in ("HOME","DRAW","AWAY") for y in ("HOME","DRAW","AWAY")}
    def outcome(h,a): return "HOME" if h>a else "AWAY" if h<a else "DRAW"
    for hh,ph in enumerate(hp1):
        for ah,pa in enumerate(ap1):
            ht=outcome(hh,ah)
            for hsecond,psh in enumerate(hp2):
                for asecond,psa in enumerate(ap2):
                    ft=outcome(hh+hsecond,ah+asecond)
                    joint[f"{ht}_{ft}"] += ph*pa*psh*psa
    total=sum(joint.values()) or 1.0
    ranked=sorted(((p/total,k) for k,p in joint.items()),reverse=True)
    top=[]
    for p,key in ranked[:2]:
        ht,ft=key.split("_")
        top.append({"selection":f"{HTZH[ht]}/{HTZH[ft]}","probability":p})
    return {"available":True,"status":"READY","model":"GOAL_TIMING_SPLIT_POISSON_V35",
            "timing_mode":mode,"source":timing.get("source_domain"),
            "home_first_half_share":hs,"away_first_half_share":as_,"top2":top}

def evaluate_match(match):
    probability=probability_layer(match)
    quality=data_quality_gate(match,probability)
    ft=ft_policy(probability,quality)
    score=independent_score(probability)
    htft=timing_htft(match,score)
    return {"match_id":match.get("match_id"),"home_team":match.get("home_team"),"away_team":match.get("away_team"),
            "probabilities":probability.get("probabilities"),"ft":ft,"score":score,"htft":htft,
            "quality_warnings":quality.get("warnings") or []}
