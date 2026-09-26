"""Collection1-1 runtime enrichment for HH520 Stable V3.5.1.

This module keeps the original 10027s probability model as the base and only
activates a bounded full-data challenger when both teams have sufficiently
complete external enrichment. Missing/partial enrichment falls back to the
10027s-only path.

Runtime groups mirror the validated Collection1-1 research families:
- SHOTS
- RESULT_STABILITY
- HALF_TIMING
"""
from __future__ import annotations

import math
from copy import deepcopy

OUTCOMES=("home","draw","away")
MODEL_NAME="COLLECTION1_1_FULL_DATA_RUNTIME_V1"


def _f(v):
    try:
        x=float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def _profile(match, side):
    timing=(match.get("goal_timing") or {})
    return (((timing.get(side) or {}).get("profile_stats")) or {})


def _timing_side(match, side):
    return ((match.get("goal_timing") or {}).get(side) or {})


def _count_present(d, keys):
    return sum(1 for k in keys if _f(d.get(k)) is not None)


def data_mode(match: dict) -> dict:
    timing=match.get("goal_timing") or {}
    hp=_profile(match,"home"); ap=_profile(match,"away")
    shots=("shots","shots_on_target","shot_conversion","shots_off_target")
    stability=("wins_rate","draws_rate","losses_rate")
    ht=_timing_side(match,"home"); at=_timing_side(match,"away")
    timing_ok=all(_f(x) is not None for x in (
        ht.get("first_half_gf_signal"), ht.get("first_half_ga_signal"),
        at.get("first_half_gf_signal"), at.get("first_half_ga_signal"),
    ))
    full=(
        bool(timing.get("available"))
        and _count_present(hp,shots)>=1 and _count_present(ap,shots)>=1
        and _count_present(hp,stability)>=2 and _count_present(ap,stability)>=2
        and timing_ok
    )
    return {
        "mode":"FULL_DATA" if full else "10027_ONLY",
        "full_data":full,
        "timing_available":bool(timing.get("available")),
        "home_profile_fields":sum(1 for v in hp.values() if _f(v) is not None),
        "away_profile_fields":sum(1 for v in ap.values() if _f(v) is not None),
        "groups_used":["SHOTS","RESULT_STABILITY","HALF_TIMING"] if full else [],
        "model":MODEL_NAME if full else "BASE_10027S",
    }


def _norm3(vals):
    vals=[max(1e-9,float(x)) for x in vals]
    s=sum(vals)
    return [x/s for x in vals]


def _side_attack(profile):
    sot=_f(profile.get("shots_on_target"))
    shots=_f(profile.get("shots"))
    conv=_f(profile.get("shot_conversion"))
    parts=[]
    if sot is not None: parts.append(math.log1p(max(0.0,sot)))
    if shots is not None: parts.append(0.35*math.log1p(max(0.0,shots)))
    if conv is not None:
        if conv>1: conv/=100.0
        parts.append(1.5*_clip(conv,0.0,1.0))
    return sum(parts)/len(parts) if parts else 0.0


def _stability_distribution(home, away):
    hw=_f(home.get("wins_rate")); hd=_f(home.get("draws_rate")); hl=_f(home.get("losses_rate"))
    aw=_f(away.get("wins_rate")); ad=_f(away.get("draws_rate")); al=_f(away.get("losses_rate"))
    if None in (hw,hd,hl,aw,ad,al):
        return None
    return _norm3(((hw+al)/2.0,(hd+ad)/2.0,(aw+hl)/2.0))


def enhance_probability(match: dict, probability: dict) -> dict:
    ctx=data_mode(match)
    out=deepcopy(probability)
    out["data_mode"]=ctx["mode"]
    out["full_data_context"]=ctx
    out["base_probabilities"]=deepcopy(probability.get("probabilities") or {})
    if not ctx["full_data"] or not probability.get("valid"):
        out["full_data_probability_used"]=False
        return out

    base=probability.get("probabilities") or {}
    hp=_profile(match,"home"); ap=_profile(match,"away")
    stab=_stability_distribution(hp,ap)
    if not stab:
        out["full_data_probability_used"]=False
        out["data_mode"]="10027_ONLY"
        out["full_data_context"]["mode"]="10027_ONLY"
        out["full_data_context"]["full_data"]=False
        return out

    ha=_side_attack(hp); aa=_side_attack(ap)
    diff=_clip(ha-aa,-1.5,1.5)
    side_home=1.0/(1.0+math.exp(-diff))
    shot=[0.72*side_home,0.28,0.72*(1.0-side_home)]
    shot=_norm3(shot)

    b=[float(base[k]) for k in OUTCOMES]
    # Bounded challenger: market model remains the dominant anchor.
    mix=_norm3([
        0.78*b[0]+0.17*stab[0]+0.05*shot[0],
        0.78*b[1]+0.17*stab[1]+0.05*shot[1],
        0.78*b[2]+0.17*stab[2]+0.05*shot[2],
    ])
    final=dict(zip(OUTCOMES,mix))
    ordered=sorted(final.items(),key=lambda kv:kv[1],reverse=True)
    out["probabilities"]=final
    out["direction"]=ordered[0][0]
    out["pmax"]=ordered[0][1]
    out["concentration"]=ordered[0][1]-ordered[1][1]
    out["source"]=probability.get("source","")+"+collection1_1_full_data"
    out["full_data_probability_used"]=True
    out["full_data_components"]={
        "base_weight":0.78,
        "result_stability_weight":0.17,
        "shots_weight":0.05,
        "result_stability_distribution":dict(zip(OUTCOMES,stab)),
        "shots_distribution":dict(zip(OUTCOMES,shot)),
    }
    return out


def score_lambda_multipliers(match: dict) -> tuple[float,float]:
    ctx=data_mode(match)
    if not ctx["full_data"]:
        return 1.0,1.0
    hp=_profile(match,"home"); ap=_profile(match,"away")
    ha=_side_attack(hp); aa=_side_attack(ap)
    stab=_stability_distribution(hp,ap)
    edge=_clip((ha-aa)/2.0,-0.35,0.35)
    if stab:
        edge+=_clip((stab[0]-stab[2])*0.35,-0.15,0.15)
    h=_clip(math.exp(edge*0.35),0.86,1.16)
    a=_clip(math.exp(-edge*0.35),0.86,1.16)
    return h,a


def half_share_adjustments(match: dict, base_home: float, base_away: float) -> tuple[float,float,bool]:
    ctx=data_mode(match)
    if not ctx["full_data"]:
        return base_home,base_away,False
    h=_timing_side(match,"home"); a=_timing_side(match,"away")
    hv=[_f(h.get("first_half_gf_signal")),_f(a.get("first_half_ga_signal"))]
    av=[_f(a.get("first_half_gf_signal")),_f(h.get("first_half_ga_signal"))]
    if None in hv or None in av:
        return base_home,base_away,False
    ht=_clip(sum(hv)/2.0,0.20,0.70)
    at=_clip(sum(av)/2.0,0.20,0.70)
    # Historical frozen split remains the anchor; timing is a bounded challenger.
    return (
        _clip(0.75*base_home+0.25*ht,0.25,0.60),
        _clip(0.75*base_away+0.25*at,0.25,0.60),
        True,
    )
