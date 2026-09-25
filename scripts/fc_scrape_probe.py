import json,os,requests
H={"Authorization":f"Bearer {os.environ['FIRECRAWL_API_KEY_BACKUP']}","Content-Type":"application/json"}
urls=["https://footystats.org/cn/japan/j1-league","https://footystats.org/clubs/cerezo-osaka-866"]
out={}
for u in urls:
 r=requests.post("https://api.firecrawl.dev/v2/scrape",headers=H,json={"url":u,"formats":["markdown","links"],"onlyMainContent":False,"maxAge":86400000},timeout=120)
 try:d=r.json()
 except:d={"raw":r.text}
 out[u]={"status":r.status_code,"body":d}
open("_fc_scrape_probe.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))
for u,v in out.items():
 d=(v["body"].get("data") or {}) if isinstance(v["body"],dict) else {}
 md=d.get("markdown") or ""
 print(json.dumps({"url":u,"status":v["status"],"success":v["body"].get("success") if isinstance(v["body"],dict) else None,
                   "md_chars":len(md),"links":len(d.get("links") or []),
                   "has_scored15":"Goals Scored By 15" in md,"has_cn":"大阪樱花" in md,
                   "credits":v["body"].get("creditsUsed") if isinstance(v["body"],dict) else None},ensure_ascii=False))
