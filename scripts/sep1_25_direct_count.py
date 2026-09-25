import json, sys, requests, time
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown
from bs4 import BeautifulSoup

out={}
total=0
d=date(2026,9,1)
while d<=date(2026,9,25):
    ds=d.isoformat()
    url=f"https://www.hh520.com/tx/10027s.php?riqi={ds}&threshold=1&bankroll=5000"
    try:
        r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
        html=r.text
        # Convert table page to text/markdown-like text that parser may understand.
        text=BeautifulSoup(html,"html.parser").get_text("\n")
        rows=parse_10027s_markdown(text)
        out[ds]={"status":r.status_code,"count":len(rows),"chars":len(html)}
        total+=len(rows)
    except Exception as e:
        out[ds]={"error":type(e).__name__}
    d+=timedelta(days=1)
Path("_sep1_25_direct.json").write_text(json.dumps({"per_day":out,"total":total},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"per_day":out,"total":total},ensure_ascii=False))
