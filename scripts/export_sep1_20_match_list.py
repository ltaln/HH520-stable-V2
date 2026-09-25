import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown
rows=[]
for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
    day=p.stem.replace("10027s_","")
    if not ("2026-09-01"<=day<="2026-09-20"): continue
    try:
        payload=json.loads(p.read_text(encoding="utf-8"))
        md=((payload.get("raw") or {}).get("data") or {}).get("markdown") or ""
        ms=parse_10027s_markdown(md)
    except Exception:
        continue
    for m in ms:
        rows.append({
          "date":day,
          "league":m.get("league"),
          "kickoff":m.get("kickoff"),
          "home_team":m.get("home_team"),
          "away_team":m.get("away_team"),
          "result":m.get("result") or m.get("full_score"),
          "half_score":m.get("half_score")
        })
Path("_sep1_20_match_list.json").write_text(json.dumps({"count":len(rows),"matches":rows},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"count":len(rows),"dates":sorted(set(r["date"] for r in rows))},ensure_ascii=False))
