import os,json,requests
teams=["利雅新月","吉达国民","斯旺西","沃特福德","都灵","蒙扎","大阪樱花","柏太阳神","米亚尔比","佐加顿斯"]
q='site:footystats.org/clubs ('+' OR '.join(f'"{t}"' for t in teams)+')'
H={"Authorization":f"Bearer {os.environ['FIRECRAWL_API_KEY_BACKUP']}","Content-Type":"application/json"}
r=requests.post("https://api.firecrawl.dev/v2/search",headers=H,json={"query":q,"limit":50,"sources":["web"]},timeout=60)
out={"query":q,"status":r.status_code,"data":r.json()}
open("_fc_batch_probe.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False))
