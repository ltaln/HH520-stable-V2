import json,requests
from bs4 import BeautifulSoup
urls=[
"https://footystats.org/japan/j1-league",
"https://footystats.org/cn/japan/j1-league",
"https://footystats.org/england/championship",
"https://footystats.org/cn/england/championship",
"https://footystats.org/clubs/cerezo-osaka-866",
"https://footystats.org/cn/clubs/cerezo-osaka-866",
]
S=requests.Session();S.headers.update({"User-Agent":"Mozilla/5.0"})
out={}
for u in urls:
 try:
  r=S.get(u,timeout=30)
  soup=BeautifulSoup(r.text,"html.parser")
  clubs=[{"text":a.get_text(" ",strip=True),"href":a.get("href")} for a in soup.find_all("a",href=True) if "/clubs/" in (a.get("href") or "")]
  text=soup.get_text("\n",strip=True)
  out[u]={"status":r.status_code,"final":r.url,"chars":len(r.text),"title":soup.title.get_text(" ",strip=True) if soup.title else None,
          "club_links":clubs[:30],"club_count":len(clubs),
          "has_goals_scored_15":"Goals Scored By 15" in text,
          "has_cn_goal":"进球" in text,
          "sample":text[:1000]}
 except Exception as e:out[u]={"error":repr(e)}
open("_footystats_direct_diag.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:{kk:v.get(kk) for kk in ("status","final","chars","title","club_count","has_goals_scored_15","has_cn_goal")} for k,v in out.items()},ensure_ascii=False,indent=2))
