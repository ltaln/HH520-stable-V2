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
    base=dict((((timing.get(side) or {}).get("profile_stats")) or {}))
    dq=(match.get("dongqiudi_enrichment") or {})
    if dq.get("available"):
        for key,value in ((dq.get(side) or {}).items()):
            if key not in base and _f(value) is not None:
                base[key]=value
    return base


def _timing_side(match, side):
    base=dict(((match.get("goal_timing") or {}).get(side) or {}))
    dq=(match.get("dongqiudi_enrichment") or {})
    if dq.get("available"):
        dside=(dq.get(side) or {})
        for key in (
            "goals_for_share","goals_against_share",
            "first_half_gf_signal","first_half_ga_signal",
            "second_half_gf_signal","second_half_ga_signal",
        ):
            if key not in base and dside.get(key) is not None:
                base[key]=dside.get(key)
    return base


def _count_present(d, keys):
    return sum(1 for k in keys if _f(d.get(k)) is not None)


def data_mode(match: dict) -> dict:
    timing=match.get("goal_timing") or {}
    hp=_profile(match,"home"); ap=_profile(match,"away")
    shots=("shots","shots_on_target")
    stability=("wins_rate","draws_rate","losses_rate")
    gfga=("scored_per_match","conceded_per_match")
    ht=_timing_side(match,"home"); at=_timing_side(match,"away")
    timing_ok=all(_f(x) is not None for x in (
        ht.get("first_half_gf_signal"), ht.get("first_half_ga_signal"),
        at.get("first_half_gf_signal"), at.get("first_half_ga_signal"),
    ))
    timing_available=bool(timing.get("available")) or timing_ok
    dq=(match.get("dongqiudi_enrichment") or {})
    dq_timing_complete=True
    dq_gfga_complete=True
    if dq.get("available"):
        dh=(dq.get("home") or {}); da=(dq.get("away") or {})
        if not bool(timing.get("available")):
            dq_timing_complete=all(
                isinstance(v,(list,tuple)) and len(v)==6
                for v in (
                    dh.get("goals_for_share"),dh.get("goals_against_share"),
                    da.get("goals_for_share"),da.get("goals_against_share"),
                )
            )
        dq_gfga_complete=(
            _count_present(dh,gfga)==2 and _count_present(da,gfga)==2
        )
    shots_ok=_count_present(hp,shots)==2 and _count_present(ap,shots)==2
    stability_ok=_count_present(hp,stability)==3 and _count_present(ap,stability)==3
    timing_group_ok=timing_available and timing_ok and dq_timing_complete
    gfga_ok=dq_gfga_complete and _count_present(hp,gfga)==2 and _count_present(ap,gfga)==2
    groups=[]
    if shots_ok: groups.append("SHOTS")
    if stability_ok: groups.append("RESULT_STABILITY")
    if timing_group_ok: groups.append("HALF_TIMING")
    if gfga_ok: groups.append("GF_GA")
    full=(set(("SHOTS","RESULT_STABILITY","HALF_TIMING")).issubset(groups))
    partial=bool(groups)
    return {
        "mode":"FULL_DATA" if full else ("PARTIAL_DATA" if partial else "10027_ONLY"),
        "full_data":full,
        "partial_data":partial,
        "timing_available":timing_available,
        "dongqiudi_available":bool((match.get("dongqiudi_enrichment") or {}).get("available")),
        "dongqiudi_timing_complete":dq_timing_complete,
        "dongqiudi_gfga_complete":dq_gfga_complete,
        "home_profile_fields":sum(1 for v in hp.values() if _f(v) is not None),
        "away_profile_fields":sum(1 for v in ap.values() if _f(v) is not None),
        "groups_used":groups,
        "model":MODEL_NAME if full else ("BASE_10027S+AVAILABLE_ENRICHMENT" if partial else "BASE_10027S"),
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
    if not probability.get("valid"):
        out["full_data_probability_used"]=False
        return out

    base=probability.get("probabilities") or {}
    hp=_profile(match,"home"); ap=_profile(match,"away")
    stab=_stability_distribution(hp,ap)
    has_stab=stab is not None and "RESULT_STABILITY" in ctx["groups_used"]
    has_shots="SHOTS" in ctx["groups_used"]
    challengers=[]
    weights=[]
    shot=None
    if has_stab:
        challengers.append(stab); weights.append(0.17)
    if has_shots:
        ha=_side_attack(hp); aa=_side_attack(ap)
        diff=_clip(ha-aa,-1.5,1.5)
        side_home=1.0/(1.0+math.exp(-diff))
        challengers.append(_norm3([0.72*side_home,0.28,0.72*(1.0-side_home)])); weights.append(0.05)

    b=[float(base[k]) for k in OUTCOMES]
    # Keep 10027S dominant. When only some external groups are available,
    # renormalize their bounded weights instead of discarding the usable data.
    used_weight=sum(weights)
    base_weight=0.78 + (0.22-used_weight)
    if not challengers:
        out["full_data_probability_used"]=False
        return out
    mix=[base_weight*b[i] for i in range(3)]
    for ch,w in zip(challengers,weights):
        for i in range(3): mix[i]+=w*ch[i]
    mix=_norm3(mix)
    final=dict(zip(OUTCOMES,mix))
    ordered=sorted(final.items(),key=lambda kv:kv[1],reverse=True)
    out["probabilities"]=final
    out["direction"]=ordered[0][0]
    out["pmax"]=ordered[0][1]
    out["concentration"]=ordered[0][1]-ordered[1][1]
    out["source"]=probability.get("source","")+"+collection1_1_enrichment"
    out["full_data_probability_used"]=ctx["full_data"]
    out["partial_enrichment_used"]=ctx["partial_data"]
    components={"base_weight":base_weight}
    if has_stab:
        components["result_stability_weight"]=0.17
        components["result_stability_distribution"]=dict(zip(OUTCOMES,stab))
    if has_shots:
        components["shots_weight"]=0.05
        components["shots_distribution"]=dict(zip(OUTCOMES,shot))
    out["full_data_components"]=components
    return out


def score_lambda_multipliers(match: dict) -> tuple[float,float]:
    ctx=data_mode(match)
    if not ctx["partial_data"]:
        return 1.0,1.0
    hp=_profile(match,"home"); ap=_profile(match,"away")
    ha=_side_attack(hp) if "SHOTS" in ctx["groups_used"] else 0.0
    aa=_side_attack(ap) if "SHOTS" in ctx["groups_used"] else 0.0
    stab=_stability_distribution(hp,ap) if "RESULT_STABILITY" in ctx["groups_used"] else None
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
