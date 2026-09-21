"""Export corrected 10027s row-level research dataset."""
import argparse,csv,datetime as dt,json
from pathlib import Path
from collector.service import collect_date

COLUMNS=[
"date","match_id","league","kickoff","home_team","away_team",
"home_odds","draw_odds","away_odds",
"home_possession","away_possession","possession_diff","possession_ratio","possession_interval","smooth_p",
"handicap_raw","handicap_side","handicap_primary_line","handicap_secondary_line","handicap_primary_water","handicap_secondary_water",
"home_attack","away_attack","attack_diff","attack_ratio",
"home_defense","away_defense","defense_diff","defense_ratio",
"home_h2h","away_h2h","h2h_diff","h2h_ratio",
"home_form","away_form","form_diff","form_ratio",
"half_score","full_score","ft_outcome","ht_outcome","total_goals"
]

def ratio(a,b):
    return (a/b) if a is not None and b not in (None,0) else None
def diff(a,b):
    return (a-b) if a is not None and b is not None else None
def outcome(score):
    if not score:return None
    try:
        h,a=map(int,score.split("-"))
        return "HOME" if h>a else "AWAY" if h<a else "DRAW"
    except:return None
def goals(score):
    if not score:return None
    try:
        h,a=map(int,score.split("-")); return h+a
    except:return None

def build_row(m):
    mk=m.get("market") or {}; p=m.get("possession") or {}; f=m.get("research_factors") or {}
    hcap=f.get("handicap_features") or {}
    ha,aa=f.get("home_attack"),f.get("away_attack")
    hd,ad=f.get("home_defense"),f.get("away_defense")
    hh,ah=f.get("home_h2h"),f.get("away_h2h")
    hf,af=f.get("home_form"),f.get("away_form")
    hs,fs=m.get("half_score"),m.get("result")
    return {
      "date":m.get("date"),"match_id":m.get("match_id"),"league":m.get("league"),"kickoff":m.get("kickoff"),
      "home_team":m.get("home_team"),"away_team":m.get("away_team"),
      "home_odds":mk.get("home_odds"),"draw_odds":mk.get("draw_odds"),"away_odds":mk.get("away_odds"),
      "home_possession":p.get("home"),"away_possession":p.get("away"),"possession_diff":p.get("diff"),
      "possession_ratio":ratio(p.get("home"),p.get("away")),"possession_interval":p.get("interval"),"smooth_p":p.get("smooth_p"),
      "handicap_raw":f.get("handicap"),"handicap_side":hcap.get("side"),"handicap_primary_line":hcap.get("primary_line"),
      "handicap_secondary_line":hcap.get("secondary_line"),"handicap_primary_water":hcap.get("primary_water"),
      "handicap_secondary_water":hcap.get("secondary_water"),
      "home_attack":ha,"away_attack":aa,"attack_diff":diff(ha,aa),"attack_ratio":ratio(ha,aa),
      "home_defense":hd,"away_defense":ad,"defense_diff":diff(hd,ad),"defense_ratio":ratio(hd,ad),
      "home_h2h":hh,"away_h2h":ah,"h2h_diff":diff(hh,ah),"h2h_ratio":ratio(hh,ah),
      "home_form":hf,"away_form":af,"form_diff":diff(hf,af),"form_ratio":ratio(hf,af),
      "half_score":hs,"full_score":fs,"ft_outcome":outcome(fs),"ht_outcome":outcome(hs),"total_goals":goals(fs),
    }

def run(start,end):
    rows=[]; d=dt.date.fromisoformat(start); z=dt.date.fromisoformat(end)
    while d<=z:
        payload=collect_date(d.isoformat())
        for m in payload.get("matches",[]): rows.append(build_row(m))
        d+=dt.timedelta(days=1)
    return rows

def audit(rows):
    keys=[("date","match_id")]
    dup=len(rows)-len({(r["date"],r["match_id"]) for r in rows})
    cov={}
    for k in COLUMNS:
        n=sum(r.get(k) not in (None,"") for r in rows)
        cov[k]={"count":n,"ratio":n/len(rows) if rows else 0}
    # Semantic guardrails based on the actual source scales observed in raw pages.
    # Attack/H2H are count-like; Defense/Form are decimal rate-like.
    suspect=[]
    for r in rows:
        if r["home_defense"] is not None and r["home_defense"]>6: suspect.append((r["date"],r["match_id"],"home_defense",r["home_defense"]))
        if r["away_defense"] is not None and r["away_defense"]>6: suspect.append((r["date"],r["match_id"],"away_defense",r["away_defense"]))
        if r["home_form"] is not None and r["home_form"]>6: suspect.append((r["date"],r["match_id"],"home_form",r["home_form"]))
        if r["away_form"] is not None and r["away_form"]>6: suspect.append((r["date"],r["match_id"],"away_form",r["away_form"]))
    return {"rows":len(rows),"duplicate_date_match_id":dup,"coverage":cov,"semantic_suspects":suspect[:50],"semantic_suspect_count":len(suspect)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--start",default="2026-08-01"); ap.add_argument("--end",default="2026-09-20")
    ap.add_argument("--csv",type=Path,required=True); ap.add_argument("--audit",type=Path,required=True); a=ap.parse_args()
    rows=run(a.start,a.end); report=audit(rows)
    if report["duplicate_date_match_id"]!=0: raise SystemExit("duplicate (date,match_id) detected")
    if report["semantic_suspect_count"]!=0: raise SystemExit("factor semantic guardrail failed; inspect mapping before research")
    a.csv.parent.mkdir(parents=True,exist_ok=True)
    with a.csv.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
    a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
