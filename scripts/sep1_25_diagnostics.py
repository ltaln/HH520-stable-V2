import json, os, sys
from pathlib import Path
from datetime import date, timedelta
import requests

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown

def count_matches():
    start=date(2026,9,1); end=date(2026,9,25)
    per_day={}
    missing=[]
    total=0
    d=start
    while d<=end:
        ds=d.isoformat()
        p=Path("cache")/f"10027s_{ds}.json"
        if not p.exists():
            per_day[ds]=None
            missing.append(ds)
        else:
            try:
                payload=json.loads(p.read_text(encoding="utf-8"))
                md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
                rows=parse_10027s_markdown(md) if isinstance(md,str) else []
                per_day[ds]=len(rows)
                total+=len(rows)
            except Exception:
                per_day[ds]="ERROR"
                missing.append(ds)
        d+=timedelta(days=1)
    return {"per_day":per_day,"total":total,"missing_dates":missing}

def backup_credits():
    key=os.getenv("FIRECRAWL_API_KEY_BACKUP","").strip()
    if not key:
        return {"ok":False,"error":"backup_secret_missing"}
    headers={"Authorization":f"Bearer {key}"}
    urls=[
      "https://api.firecrawl.dev/v2/team/credit-usage",
      "https://api.firecrawl.dev/v1/team/credit-usage",
    ]
    attempts=[]
    for url in urls:
        try:
            r=requests.get(url,headers=headers,timeout=20)
            attempts.append({"url":url,"status":r.status_code})
            if r.ok:
                try:data=r.json()
                except Exception:return {"ok":False,"error":"non_json_success","attempts":attempts}
                return {"ok":True,"data":data,"attempts":attempts}
        except Exception as e:
            attempts.append({"url":url,"error":type(e).__name__})
    return {"ok":False,"error":"credit_endpoint_failed","attempts":attempts}

out={"match_count":count_matches(),"backup_firecrawl":backup_credits()}
Path("_diagnostic_sep1_25.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
