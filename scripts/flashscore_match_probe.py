import json, os, re, requests
from pathlib import Path
from collector.hh520_10027_parser import parse_10027s_markdown

HEADERS={
 "User-Agent":"Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
 "Accept":"*/*","Accept-Language":"en","Referer":"https://www.flashscore.com/",
 "x-fsign":"SW9D1eZo","Origin":"https://www.flashscore.com",
}
day="2026-09-01"
cache=Path("cache")/f"10027s_{day}.json"
payload=json.loads(cache.read_text(encoding="utf-8"))
md=((payload.get("raw") or {}).get("data") or {}).get("markdown") or ""
matches=parse_10027s_markdown(md)
source=[]
for m in matches[:20]:
    source.append({k:m.get(k) for k in ("match_id","league","kickoff","home_team","away_team","result","full_score","half_score")})

url="https://local-global.flashscore.ninja/2/x/feed/f_1_-24_3_en_1"
r=requests.get(url,headers=HEADERS,timeout=30)
out={"status":r.status_code,"source_count":len(matches),"source_sample":source,"flashscore_prefix":r.text[:12000]}
Path("_flashscore_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"status":r.status_code,"source_count":len(matches),"source_sample":source[:8],"flashscore_prefix":r.text[:4000]},ensure_ascii=False,indent=2))
