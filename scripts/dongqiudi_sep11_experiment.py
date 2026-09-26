"""Direct Dongqiudi public-analysis experiment for 2026-09-11.

Research-only. Stable V3.5.1 production files and weights are not changed.
The experiment deliberately excludes Dongqiudi /situation post-match stats.
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
from collections import Counter
from pathlib import Path

from collector.service import collect_date
from collector.dongqiudi_source import collect_match_analysis
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk
from engine.decision_filter import decision_filter
from engine.htft_layer import htft_layer
from engine.score_layer import score_layer
from engine.state_engine import build_state
from engine.consistency_layer import consistency_layer
from engine.calibration_layer import calibration_layer
from analysis.confidence import confidence_from_probability
from prediction.builder import prepare_match
from research.result_label.collector import collect_result_labels

POSTMATCH_KEYS={
    "result","half_score","full_score","actual_score","actual_half_score",
    "actual_outcome","actual_total_goals","result_label","label_status","label_match_method",
}
OUTCOMES=("home","draw","away")
DIRECTIONS={"home":"主胜","draw":"平","away":"客胜"}
GROUP_WEIGHTS={"RECENT_FORM":0.10,"VENUE_FORM":0.07,"GF_GA":0.08,"H2H":0.05}


def _strip(row):
    out=copy.deepcopy(row)
    for k in POSTMATCH_KEYS: out.pop(k,None)
    return out


def _norm3(vals):
    vals=[max(1e-9,float(x)) for x in vals]
    s=sum(vals)
    return [x/s for x in vals]


def _wdl_dist(home,away,prefix=""):
    hw=home.get(prefix+"wins_rate"); hd=home.get(prefix+"draws_rate"); hl=home.get(prefix+"losses_rate")
    aw=away.get(prefix+"wins_rate"); ad=away.get(prefix+"draws_rate"); al=away.get(prefix+"losses_rate")
    if None in (hw,hd,hl,aw,ad,al): return None
    return _norm3(((hw+al)/2,(hd+ad)/2,(aw+hl)/2))


def _gfga_dist(home,away):
    hs=home.get("scored_per_match"); hc=home.get("conceded_per_match")
    a_s=away.get("scored_per_match"); ac=away.get("conceded_per_match")
    if None in (hs,hc,a_s,ac): return None
    h=max(.05,(float(hs)+float(ac))/2)
    a=max(.05,(float(a_s)+float(hc))/2)
    # Goal-strength signal: preserve a substantial draw prior.
    return _norm3((h,0.70*(h*a)**0.5,a))


def _candidate_probability(match,groups):
    base=probability_layer(match)
    out=copy.deepcopy(base)
    if not base.get("valid"):
        out["dongqiudi_groups_used"]=[]
        return out
    dq=match.get("dongqiudi") or {}
    home=dq.get("home") or {}; away=dq.get("away") or {}
    signals={}
    signals["RECENT_FORM"]=_wdl_dist(home,away,"recent10_")
    signals["VENUE_FORM"]=_wdl_dist(home,away,"venue10_")
    signals["H2H"]=_wdl_dist(home,away,"h2h_")
    signals["GF_GA"]=_gfga_dist(home,away)
    used=[g for g in groups if signals.get(g)]
    ext=sum(GROUP_WEIGHTS[g] for g in used)
    b=[float(base["probabilities"][k]) for k in OUTCOMES]
    mix=[(1-ext)*b[i] for i in range(3)]
    for g in used:
        w=GROUP_WEIGHTS[g]; sig=signals[g]
        for i in range(3): mix[i]+=w*sig[i]
    mix=_norm3(mix)
    final=dict(zip(OUTCOMES,mix))
    ordered=sorted(final.items(),key=lambda kv:kv[1],reverse=True)
    out["probabilities"]=final
    out["direction"]=ordered[0][0]
    out["pmax"]=ordered[0][1]
    out["concentration"]=ordered[0][1]-ordered[1][1]
    out["source"]=base.get("source","")+"+dongqiudi_public_candidate"
    out["dongqiudi_groups_used"]=used
    out["dongqiudi_signals"]={g:dict(zip(OUTCOMES,signals[g])) for g in used}
    out["dongqiudi_external_weight"]=ext
    return out


def _candidate_full_prediction(match,groups):
    probability=_candidate_probability(match,groups)
    value=value_layer(match,probability)
    quality=data_quality_gate(match,probability)
    classification=classify_match(match,probability)
    risk=assess_risk(match,probability,value,quality,classification)
    state=build_state(match,probability)
    decision=decision_filter(match,probability,value,quality,classification,risk,state)
    confidence=confidence_from_probability(probability,decision)
    htft=htft_layer(probability,match,decision)
    score=score_layer(match,probability,htft)
    consistency=consistency_layer(probability,state,htft,score,decision)
    calibration=calibration_layer(probability,state)

    primary=decision.get("resolved_direction") or probability.get("direction")
    authorized=bool(decision.get("ft_direction_authorized",True))
    direction=DIRECTIONS.get(primary)
    if primary in {"home","away"} and not authorized:
        direction="均衡"
    ht=consistency.get("htft_top",[])
    sc=consistency.get("score_top",[])
    totals=score.get("top_totals",[])
    return {
        "status":"PREDICTED" if len(sc)>=2 else "PASS",
        "direction":direction,
        "raw_direction":DIRECTIONS.get(probability.get("direction")),
        "resolved_direction":DIRECTIONS.get(primary),
        "state":consistency.get("effective_decision",decision.get("decision","PASS")),
        "confidence":confidence,
        "score1":sc[0]["score"] if len(sc)>0 else None,
        "score2":sc[1]["score"] if len(sc)>1 else None,
        "htft1":ht[0]["selection"] if len(ht)>0 else None,
        "htft2":ht[1]["selection"] if len(ht)>1 else None,
        "total_goals":score.get("total_goals_pick"),
        "groups_used":probability.get("dongqiudi_groups_used",[]),
        "external_weight":probability.get("dongqiudi_external_weight",0),
        "probabilities":probability.get("probabilities"),
        "decision":decision,
        "calibration":calibration,
    }


def _score_pair(v):
    import re
    m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None


def _actual_htft(label):
    h=_score_pair(label.get("actual_half_score")); f=_score_pair(label.get("actual_score"))
    if not h or not f: return None
    side=lambda p: "主" if p[0]>p[1] else "客" if p[0]<p[1] else "平"
    return f"{side(h)}/{side(f)}"


def _metrics(preds,label_map):
    out={k:{"evaluable":0,"hits":0} for k in ("formal_wdl","raw_wdl","score_top2","htft_top2","total_goals")}
    for mid,row in preds.items():
        lab=label_map.get(mid)
        if not lab or row.get("status")!="PREDICTED": continue
        actual=lab.get("actual_outcome")
        zh={"主胜":"HOME","平":"DRAW","客胜":"AWAY"}
        formal=zh.get(row.get("direction"))
        raw=zh.get(row.get("raw_direction") or row.get("direction"))
        if actual in {"HOME","DRAW","AWAY"}:
            if formal:
                out["formal_wdl"]["evaluable"]+=1; out["formal_wdl"]["hits"]+=int(formal==actual)
            if raw:
                out["raw_wdl"]["evaluable"]+=1; out["raw_wdl"]["hits"]+=int(raw==actual)
        actual_score=_score_pair(lab.get("actual_score"))
        picks=[_score_pair(row.get("score1")),_score_pair(row.get("score2"))]
        picks=[x for x in picks if x]
        if actual_score and picks:
            out["score_top2"]["evaluable"]+=1; out["score_top2"]["hits"]+=int(actual_score in picks[:2])
        ah=_actual_htft(lab); hp=[row.get("htft1"),row.get("htft2")]; hp=[x for x in hp if x]
        if ah and hp:
            out["htft_top2"]["evaluable"]+=1; out["htft_top2"]["hits"]+=int(ah in hp[:2])
        try: pg=int(str(row.get("total_goals") or "").replace("球",""))
        except Exception: pg=None
        ag=lab.get("actual_total_goals")
        if isinstance(ag,int) and pg is not None:
            out["total_goals"]["evaluable"]+=1; out["total_goals"]["hits"]+=int(ag==pg)
    for b in out.values():
        b["accuracy"]=b["hits"]/b["evaluable"] if b["evaluable"] else None
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()

    raw=collect_date(args.date)
    records=[]
    for m in raw.get("matches",[]):
        x=copy.deepcopy(m); x["date"]=args.date; records.append(x)
    labels=collect_result_labels(records)
    label_map={str(x["match_id"]):x for x in labels}
    matches=[_strip(x) for x in records]

    direct={}
    coverage=Counter(); field_coverage=Counter(); ids={}
    for m in matches:
        mid=str(m.get("match_id") or "")
        try:
            dq=collect_match_analysis(args.date,m.get("home_team",""),m.get("away_team",""))
        except Exception as exc:
            dq={"available":False,"reason":f"collector_error:{type(exc).__name__}"}
        m["dongqiudi"]=dq
        direct[mid]=dq
        if dq.get("match_detail_id"): ids[mid]=dq.get("match_detail_id")
        for g,v in (dq.get("groups") or {}).items(): coverage[g]+=int(bool(v))
        for side in ("home","away"):
            for k,v in (dq.get(side) or {}).items():
                if isinstance(v,(int,float)) and math.isfinite(float(v)): field_coverage[k]+=1

    baseline={str(m.get("match_id")):prepare_match(m) for m in matches}
    group_names=list(GROUP_WEIGHTS)
    combos=[()]
    for n in range(1,len(group_names)+1):
        combos.extend(itertools.combinations(group_names,n))

    tournament={}
    candidate_predictions={}
    for combo in combos:
        name="BASE" if not combo else "+".join(combo)
        preds={str(m.get("match_id")):_candidate_full_prediction(m,combo) for m in matches}
        candidate_predictions[name]=preds
        tournament[name]=_metrics(preds,label_map)
        tournament[name]["matches_with_any_group_used"]=sum(bool(x.get("groups_used")) for x in preds.values())
        tournament[name]["mean_external_weight"]=(
            sum(float(x.get("external_weight") or 0) for x in preds.values())/len(preds) if preds else 0
        )

    baseline_metrics=_metrics({
        mid:{
            **p,
            "raw_direction":p.get("raw_direction"),
        } for mid,p in baseline.items()
    },label_map)

    # Rank descriptively on this one-day sample only; never auto-promote.
    def rank_key(item):
        m=item[1]
        return (
            (m["formal_wdl"]["accuracy"] or -1),
            (m["htft_top2"]["accuracy"] or -1),
            (m["score_top2"]["accuracy"] or -1),
            (m["total_goals"]["accuracy"] or -1),
        )
    ranking=[name for name,_ in sorted(tournament.items(),key=rank_key,reverse=True)]

    result={
        "status":"READY",
        "experiment":"DONGQIUDI_SEP11_DIRECT_FULL_MODEL_V2",
        "date":args.date,
        "stable_mutated":False,
        "stable_version":"HH520 Stable V3.5.1",
        "historical_safety":{
            "used_public_analysis_tab":True,
            "excluded_situation_postmatch_stats":True,
            "excluded_current_match_score_from_features":True,
            "promotion_allowed":False,
        },
        "match_count":len(matches),
        "result_labels":len(labels),
        "dongqiudi_available":sum(int(x.get("available",False)) for x in direct.values()),
        "dongqiudi_match_ids":ids,
        "group_coverage_matches":dict(coverage),
        "profile_field_side_coverage":dict(field_coverage),
        "baseline_metrics":baseline_metrics,
        "combination_tournament":tournament,
        "descriptive_ranking":ranking,
        "best_one_day_combo":ranking[0] if ranking else None,
        "warning":"Best combo is descriptive for 2026-09-11 only; sample is too small for promotion.",
        "per_match":[
            {
                "match_id":str(m.get("match_id")),
                "league":m.get("league"),
                "home_team":m.get("home_team"),
                "away_team":m.get("away_team"),
                "dongqiudi":m.get("dongqiudi"),
                "actual":label_map.get(str(m.get("match_id"))),
                "baseline":baseline.get(str(m.get("match_id"))),
                "best_candidate":candidate_predictions.get(ranking[0],{}).get(str(m.get("match_id"))) if ranking else None,
            }
            for m in matches
        ],
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
