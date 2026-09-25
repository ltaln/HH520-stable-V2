import json,requests,time,re,sys
from pathlib import Path
S=requests.Session();S.headers.update({"User-Agent":"HH520Research/1.0"})
prep=json.loads(Path("_timing_prep_input.json").read_text(encoding="utf-8"))
teams=prep["teams"]
out={}
def get(params):
 r=S.get("https://zh.wikipedia.org/w/api.php",params=params,timeout=15);r.raise_for_status();return r.json()
for i,t in enumerate(teams):
 rec={"zh":t}
 try:
  q=get({"action":"query","list":"search","srsearch":t+" 足球","format":"json","utf8":1,"srlimit":3})
  hits=q.get("query",{}).get("search",[])
  if not hits:
   q=get({"action":"query","list":"search","srsearch":t,"format":"json","utf8":1,"srlimit":3});hits=q.get("query",{}).get("search",[])
  rec["search_titles"]=[x.get("title") for x in hits]
  if hits:
   title=hits[0]["title"]
   ll=get({"action":"query","prop":"langlinks","titles":title,"lllang":"en","lllimit":10,"format":"json"})
   pages=(ll.get("query") or {}).get("pages") or {}
   page=next(iter(pages.values()),{})
   links=page.get("langlinks") or []
   if links: rec["en"]=links[0].get("*")
 except Exception as e:rec["error"]=type(e).__name__
 out[t]=rec
 time.sleep(.03)
Path("_wiki_aliases.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"total":len(out),"resolved":sum(1 for x in out.values() if x.get("en")),"examples":[v for v in out.values() if v.get("en")][:25]},ensure_ascii=False))
