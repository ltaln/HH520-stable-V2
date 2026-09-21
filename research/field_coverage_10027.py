"""Audit 10027s reverse-engineering field coverage over historical cache."""
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path
from collector.service import collect_date

FIELDS = {
  "home_odds": lambda m: (m.get("market") or {}).get("home_odds"),
  "draw_odds": lambda m: (m.get("market") or {}).get("draw_odds"),
  "away_odds": lambda m: (m.get("market") or {}).get("away_odds"),
  "home_possession": lambda m: (m.get("possession") or {}).get("home"),
  "away_possession": lambda m: (m.get("possession") or {}).get("away"),
  "possession_diff": lambda m: (m.get("possession") or {}).get("diff"),
  "possession_interval": lambda m: (m.get("possession") or {}).get("interval"),
  "smooth_p": lambda m: (m.get("possession") or {}).get("smooth_p"),
  "handicap": lambda m: (m.get("research_factors") or {}).get("handicap"),
  "water_level": lambda m: (m.get("research_factors") or {}).get("water_level"),
  "home_water": lambda m: (m.get("research_factors") or {}).get("home_water"),
  "away_water": lambda m: (m.get("research_factors") or {}).get("away_water"),
  "home_attack": lambda m: (m.get("research_factors") or {}).get("home_attack"),
  "away_attack": lambda m: (m.get("research_factors") or {}).get("away_attack"),
  "home_defense": lambda m: (m.get("research_factors") or {}).get("home_defense"),
  "away_defense": lambda m: (m.get("research_factors") or {}).get("away_defense"),
  "home_h2h": lambda m: (m.get("research_factors") or {}).get("home_h2h"),
  "away_h2h": lambda m: (m.get("research_factors") or {}).get("away_h2h"),
  "home_form": lambda m: (m.get("research_factors") or {}).get("home_form"),
  "away_form": lambda m: (m.get("research_factors") or {}).get("away_form"),
  "result": lambda m: m.get("result"),
  "half_score": lambda m: m.get("half_score"),
}

def _present(v):
    return v not in (None, "", "-", "--", "—")

def run(start="2026-08-01", end="2026-09-20"):
    import datetime as dt
    a=dt.date.fromisoformat(start); b=dt.date.fromisoformat(end)
    counts=Counter(); total=0; dates=Counter(); headers=Counter(); examples=defaultdict(list)
    d=a
    while d<=b:
        day=d.isoformat()
        data=collect_date(day)
        matches=data.get("matches",[])
        for m in matches:
            total += 1
            for name,fn in FIELDS.items():
                v=fn(m)
                if _present(v):
                    counts[name]+=1; dates[name]+=1
                    if len(examples[name])<5: examples[name].append(v)
            for name,val in (m.get("raw_fusion_fields") or {}).items():
                if _present(val): headers[name]+=1
        d += dt.timedelta(days=1)
    return {
      "window":f"{start}..{end}",
      "matches":total,
      "coverage":{
        k:{"count":counts[k],"ratio":counts[k]/total if total else 0.0,"examples":examples[k]}
        for k in FIELDS
      },
      "fusion_headers":dict(headers.most_common()),
    }

def render(r):
    lines=["# HH520 10027s Field Coverage Audit","",f"- Window: {r['window']}",f"- Matches: {r['matches']}","","## Core fields",""]
    for k,v in r["coverage"].items():
        lines.append(f"- {k}: {v['count']}/{r['matches']} ({v['ratio']*100:.1f}%) examples={v['examples']}")
    lines += ["","## Fusion headers discovered",""]
    for k,n in r["fusion_headers"].items():
        lines.append(f"- {k}: {n}")
    return "\n".join(lines)

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--md",type=Path,required=True); a=p.parse_args(argv)
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8"); a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__": main()
