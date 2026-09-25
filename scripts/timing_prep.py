import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from collector.hh520_10027_parser import parse_10027s_markdown

samples=[]
teams=set()
leagues={}
counts={}

for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
    d=p.stem.replace("10027s_","")
    if not ("2026-09-01"<=d<="2026-09-20"):
        continue
    payload=json.loads(p.read_text(encoding="utf-8"))
    md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
    rows=parse_10027s_markdown(md or "")
    counts[d]=len(rows)
    for m in rows:
        teams.add(str(m.get("home_team")))
        teams.add(str(m.get("away_team")))
        lg=str(m.get("league") or "")
        leagues[lg]=leagues.get(lg,0)+1
        if len(samples)<40:
            samples.append({
                "date":d,
                "home":m.get("home_team"),
                "away":m.get("away_team"),
                "half":m.get("half_score"),
                "full":m.get("result") or m.get("full_score"),
                "league":m.get("league")
            })

out={
    "counts":counts,
    "sample_matches":samples,
    "unique_teams":len(teams),
    "teams":sorted(teams),
    "leagues":dict(sorted(leagues.items(), key=lambda kv:(-kv[1],kv[0])))
}
Path("_timing_prep.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"unique_teams":len(teams),"leagues":out["leagues"]},ensure_ascii=False))
