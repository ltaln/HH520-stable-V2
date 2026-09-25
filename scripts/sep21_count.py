import json, os, sys, requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown
key=os.environ["FIRECRAWL_API_KEY_BACKUP"]
url="https://www.hh520.com/tx/10027s.php?riqi=2026-09-21&threshold=1&bankroll=5000"
r=requests.post("https://api.firecrawl.dev/v2/scrape",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json={"url":url,"formats":["markdown"],"onlyMainContent":False},timeout=60)
r.raise_for_status()
data=r.json()
md=((data.get("data") or {}).get("markdown")) or data.get("markdown")
rows=parse_10027s_markdown(md or "")
out={"date":"2026-09-21","count":len(rows),"success":True}
Path("_sep21_count.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
