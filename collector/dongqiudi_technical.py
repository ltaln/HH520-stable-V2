"""Prematch Dongqiudi technical-history collector.

Uses only completed matches that precede the target fixture. It never reads the
target match's own overview statistics, so historical replay cannot leak
post-match information.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

PC_BASE="https://pc.dongqiudi.com"
BINS=("0-15","16-30","31-45","46-60","61-75","76-90")


def _norm(value):
    s=str(value or "").lower()
    for token in ("足球俱乐部","俱乐部","football club","fc","afc","cf","sc","队"):
        s=s.replace(token,"")
    return re.sub(r"[\s·・._/()（）-]+","",s)


def _similar(a,b):
    aa=_norm(a); bb=_norm(b)
    if not aa or not bb:
        return 0.0
    if aa in bb or bb in aa:
        return min(len(aa),len(bb))/max(len(aa),len(bb))
    return SequenceMatcher(None,aa,bb).ratio()


def _number(value):
    if isinstance(value,(int,float)):
        return float(value)
    m=re.search(r"-?\d+(?:\.\d+)?",str(value or ""))
    return float(m.group()) if m else None


def _get_json(url, timeout=15):
    r=requests.get(
        url,
        headers={"Accept":"application/json","User-Agent":"HH520-Stable/3.5.1"},
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _lineup_id(match_id):
    mid=str(match_id or "").lstrip("0")
    return mid[1:] if mid.startswith("5") else mid


def _lineup(match_id):
    lid=_lineup_id(match_id)
    if not lid:
        return None
    return _get_json(f"{PC_BASE}/sport-data/soccer/biz/dqd/v1/match/lineup/{lid}?app=dqd&lang=zh-cn")


def _overview(match_id):
    return _get_json(f"{PC_BASE}/api/data/overview/match/{match_id}")


def _recent_row(lineup, side):
    return ((((lineup or {}).get("recent_match_persons") or {}).get("recent_match") or {}).get(side))


def _team_side(row, team_name):
    if _similar(team_name,(row or {}).get("team_A_name")) >= 0.56:
        return "team_A"
    if _similar(team_name,(row or {}).get("team_B_name")) >= 0.56:
        return "team_B"
    return None


def _stat_map(overview):
    output={}
    statistics=(overview or {}).get("statistics") or {}
    for row in statistics.get("list") or []:
        key=str(row.get("type") or "").strip()
        if not key:
            continue
        hv=_number((row.get("team_A") or {}).get("value"))
        av=_number((row.get("team_B") or {}).get("value"))
        if hv is not None or av is not None:
            output[key]={"team_A":hv,"team_B":av}
    return output


def _goal_bins(overview):
    out={"team_A":[0.0]*6,"team_B":[0.0]*6}
    for bucket in ((overview or {}).get("events") or {}).values():
        minute=int(_number((bucket or {}).get("minute")) or 0)
        if minute <= 0:
            continue
        idx=0 if minute<=15 else 1 if minute<=30 else 2 if minute<=45 else 3 if minute<=60 else 4 if minute<=75 else 5
        for source,side in (("teamAEvents","team_A"),("teamBEvents","team_B")):
            for event in (bucket or {}).get(source) or []:
                if str(event.get("code") or "").upper()=="G":
                    out[side][idx]+=1.0
    return out


def _parse_time(value):
    if not value:
        return None
    s=str(value).strip().replace(" ","T")
    try:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _share(values):
    total=sum(values)
    return [x/total for x in values] if total>0 else None


def collect_team_history(target_match_id, team_name, target_side, target_kickoff=None, max_matches=None):
    try:
        max_matches=max_matches or max(1,min(8,int(os.getenv("HH520_DONGQIUDI_HISTORY_MATCHES","5"))))
    except ValueError:
        max_matches=5
    lineup=_lineup(target_match_id)
    row=_recent_row(lineup,target_side)
    target_dt=_parse_time(target_kickoff)
    observations=[]
    seen=set()

    while isinstance(row,dict) and len(observations)<max_matches:
        mid=str(row.get("match_id") or "").strip()
        if not mid or mid in seen:
            break
        seen.add(mid)
        side=_team_side(row,team_name)
        if not side:
            break
        row_dt=_parse_time(row.get("start_play"))
        if target_dt and row_dt and row_dt>=target_dt:
            break

        overview=_overview(mid)
        stats=_stat_map(overview)
        goals=_goal_bins(overview)
        opp="team_B" if side=="team_A" else "team_A"
        obs={
            "match_id":mid,
            "kickoff":row.get("start_play"),
            "side":side,
            "shots":(stats.get("射门") or {}).get(side),
            "shots_on_target":(stats.get("射正") or {}).get(side),
            "possession":(stats.get("控球率") or stats.get("控球") or {}).get(side),
            "dangerous_attacks":(stats.get("危险进攻") or {}).get(side),
            "big_chances":(stats.get("绝佳机会") or stats.get("重大机会") or stats.get("得分机会") or {}).get(side),
            "goals_for_bins":goals[side],
            "goals_against_bins":goals[opp],
        }
        if obs["possession"] is not None and obs["possession"]>1:
            obs["possession"]/=100.0
        if any(v is not None for k,v in obs.items() if k not in {"match_id","kickoff","side","goals_for_bins","goals_against_bins"}) or sum(goals[side])+sum(goals[opp])>0:
            observations.append(obs)

        previous_lineup=_lineup(mid)
        row=_recent_row(previous_lineup,side)

    metrics={}
    for key in ("shots","shots_on_target","possession","dangerous_attacks","big_chances"):
        vals=[float(o[key]) for o in observations if o.get(key) is not None]
        if vals:
            metrics[key]=sum(vals)/len(vals)
            metrics[f"{key}_samples"]=len(vals)

    gf=[0.0]*6; ga=[0.0]*6
    for o in observations:
        gf=[a+b for a,b in zip(gf,o["goals_for_bins"])]
        ga=[a+b for a,b in zip(ga,o["goals_against_bins"])]
    gfs=_share(gf); gas=_share(ga)
    if gfs and gas:
        metrics.update({
            "timing_bins":list(BINS),
            "goals_for_bins":gf,
            "goals_against_bins":ga,
            "goals_for_share":gfs,
            "goals_against_share":gas,
            "first_half_gf_signal":sum(gfs[:3]),
            "first_half_ga_signal":sum(gas[:3]),
            "second_half_gf_signal":sum(gfs[3:]),
            "second_half_ga_signal":sum(gas[3:]),
        })
    if metrics.get("shots") not in (None,0) and metrics.get("shots_on_target") is not None:
        metrics["shots_off_target"]=max(0.0,metrics["shots"]-metrics["shots_on_target"])
        metrics["shot_on_target_rate"]=metrics["shots_on_target"]/metrics["shots"]
        goals_for=sum(gf)
        if goals_for>0:
            metrics["shot_conversion"]=goals_for/(metrics["shots"]*max(1,len(observations)))

    return {
        "team":team_name,
        "sample_count":len(observations),
        "metrics":metrics,
        "observations":observations,
    }


def collect_prematch_technical_history(target_match_id, home_team, away_team, target_kickoff=None):
    home=collect_team_history(target_match_id,home_team,"team_A",target_kickoff)
    away=collect_team_history(target_match_id,away_team,"team_B",target_kickoff)
    return {
        "source":"DONGQIUDI_PREMATCH_HISTORY",
        "target_match_id":str(target_match_id),
        "home":home,
        "away":away,
    }
