import json,os,requests
teams=["利雅新月","斯旺西","大阪樱花","米亚尔比","弗拉门戈"]
key=os.environ["FIRECRAWL_API_KEY_BACKUP"]
H={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
out={}
for t in teams:
 r=requests.post("https://api.firecrawl.dev/v2/search",headers=H,json={"query":f'{t} football club FootyStats SoccerSTATS goal timing',"limit":5,"sources":["web"]},timeout=60)
 try:d=r.json()
 except:d={"raw":r.text}
 out[t]={"status":r.status_code,"data":d}
open("_fc_search_probe.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:{"status":v["status"],"data":v["data"]} for k,v in out.items()},ensure_ascii=False))
