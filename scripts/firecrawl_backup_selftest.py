import json, os, requests, sys
from pathlib import Path

def check(name):
    key=(os.getenv(name) or "").strip()
    out={"name":name,"configured":bool(key),"status_code":None,"ok":False}
    if not key:
        return out
    try:
        r=requests.post(
            "https://api.firecrawl.dev/v2/search",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"query":"OpenAI","limit":1},
            timeout=20,
        )
        out["status_code"]=r.status_code
        out["ok"]=r.status_code==200
        try:
            body=r.json()
            if isinstance(body,dict):
                out["success"]=body.get("success")
        except Exception:
            pass
    except Exception as e:
        out["error"]=type(e).__name__
    return out

primary=check("FIRECRAWL_API_KEY")
backup=check("FIRECRAWL_API_KEY_BACKUP")
result={
    "primary":primary,
    "backup":backup,
    "configured_key_count":int(primary["configured"])+int(backup["configured"]),
    "failover_ready":bool(backup["configured"] and backup["ok"]),
}
Path("_firecrawl_selftest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
