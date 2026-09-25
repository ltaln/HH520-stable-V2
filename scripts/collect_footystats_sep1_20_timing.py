import json, os, re, sys, time, math
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse, urljoin
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown

FC="https://api.firecrawl.dev/v2"
KEY=os.environ["FIRECRAWL_API_KEY_BACKUP"]
FH={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (HH520 research collector)"})

LEAGUE_ALIAS={
"英超":"England Premier League","英冠":"England Championship","英联杯":"England EFL Cup","英足总杯":"England FA Cup",
"西甲":"Spain La Liga","西乙":"Spain Segunda Division","德甲":"Germany Bundesliga","德乙":"Germany 2 Bundesliga",
"意甲":"Italy Serie A","意乙":"Italy Serie B","意大利杯":"Italy Coppa Italia","法甲":"France Ligue 1","法乙":"France Ligue 2",
"荷甲":"Netherlands Eredivisie","葡超":"Portugal Liga NOS","俄超":"Russia Premier League","苏超":"Scotland Premiership",
"比甲":"Belgium Pro League","瑞超":"Sweden Allsvenskan","挪超":"Norway Eliteserien","芬超":"Finland Veikkausliiga",
"日职":"Japan J1 League","日乙":"Japan J2 League","日联赛杯":"Japan J League Cup","天皇杯":"Japan Emperor Cup",
"韩K":"South Korea K League 1","韩K2":"South Korea K League 2","沙职":"Saudi Arabia Professional League",
"澳超":"Australia A League","巴甲":"Brazil Serie A","巴西杯":"Brazil Copa do Brasil","阿甲":"Argentina Primera Division",
"美职":"USA MLS","MLS":"USA MLS","墨超":"Mexico Liga MX","智甲":"Chile Primera Division",
"欧冠":"UEFA Champions League","欧联":"UEFA Europa League","欧协联":"UEFA Europa Conference League",
"亚冠":"AFC Champions League","世欧预":"World Cup Qualification Europe","世亚预":"World Cup Qualification Asia",
"世界杯":"FIFA World Cup","欧洲杯":"UEFA Euro","美洲杯":"Copa America","亚洲杯":"AFC Asian Cup",
"中超":"China Chinese Super League"
}
TEAM_ALIAS={
"柏太阳神":"柏雷索尔","名古屋鲸":"名古屋鲸八","町田泽维":"FC Machida Zelvia","京都":"京都不死鸟",
"东京绿茵":"京都绿茵","伍尔弗":"狼队","布城":"布里斯托城","米堡":"米德尔斯堡","雷克斯":"雷克瑟姆",
"女王巡游":"女王公园巡游者","西布罗姆":"西布罗姆维奇","伊普斯":"伊普斯维奇","巴黎圣曼":"巴黎圣日耳曼",
"弗鲁米嫩":"弗鲁米嫩塞","巴竞技":"巴拉纳竞技","布拉干RB":"布拉甘蒂诺红牛","安德莱":"安德莱赫特",
"皇家社会":"皇家社会","利雅新月":"阿尔希拉尔","利雅胜利":"阿尔纳斯尔","吉达国民":"阿尔阿赫利"
}

def load_matches():
    out=[]
    for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
        ds=p.stem.replace("10027s_","")
        if not ("2026-09-01"<=ds<="2026-09-20"): continue
        payload=json.loads(p.read_text(encoding="utf-8"))
        md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
        for m in parse_10027s_markdown(md or ""):
            out.append({"date":ds,"match_id":m.get("match_id"),"league":str(m.get("league") or ""),
                        "home_team":str(m.get("home_team") or ""),"away_team":str(m.get("away_team") or ""),
                        "half_score":m.get("half_score"),"full_score":m.get("result")})
    return out

def credits():
    try:
        r=requests.get(FC+"/team/credit-usage",headers={"Authorization":f"Bearer {KEY}"},timeout=20)
        d=r.json()
        return ((d.get("data") or {}).get("remainingCredits")) if isinstance(d,dict) else None
    except Exception:return None

def search(q,limit=8):
    if (credits() is not None) and credits()<25:
        return []
    r=requests.post(FC+"/search",headers=FH,json={"query":q,"limit":limit,"sources":["web"]},timeout=60)
    if not r.ok:return []
    d=r.json()
    return (((d.get("data") or {}).get("web")) or [])

def norm(s):
    s=str(s or "").lower()
    for x in ["足球俱乐部","俱乐部","football club","f.c.","fc","sc","afc","club","队"," ","-","_","·",".","'","’","（","）","(",")"]:
        s=s.replace(x,"")
    return s

def sim(a,b):
    a=norm(a);b=norm(b)
    if not a or not b:return 0
    if a==b:return 1.0
    if a in b or b in a:return .9
    return SequenceMatcher(None,a,b).ratio()

def to_cn(url):
    p=urlparse(url)
    path=p.path
    if path.startswith("/cn/"):return url
    if path.startswith("/"):
        return f"{p.scheme or 'https'}://{p.netloc or 'footystats.org'}/cn{path}"
    return url

def to_en(url):
    p=urlparse(url)
    path=re.sub(r"^/cn","",p.path)
    return f"https://footystats.org{path}"

def choose_league_url(results):
    scored=[]
    for x in results:
        u=x.get("url") or ""
        if "footystats.org" not in u:continue
        path=urlparse(u).path.lower()
        if any(bad in path for bad in ["/clubs/","h2h-stats","/help","/app","/predictions"]):continue
        if path in {"","/"}:continue
        score=0
        if "/cn/" in path:score+=3
        if len([z for z in path.split("/") if z]) in (2,3):score+=3
        title=(x.get("title") or "").lower()
        if "2026" in title:score+=2
        if "stats" in title or "积分" in title:score+=1
        scored.append((score,u))
    return max(scored)[1] if scored else None

def get_html(url):
    r=S.get(url,timeout=30)
    r.raise_for_status()
    return r.text

def league_clubs(url):
    try:html=get_html(to_cn(url))
    except Exception:return []
    soup=BeautifulSoup(html,"html.parser")
    found={}
    for a in soup.find_all("a",href=True):
        href=a.get("href") or ""
        if "/clubs/" not in href:continue
        u=urljoin("https://footystats.org",href)
        text=a.get_text(" ",strip=True)
        if not text:
            img=a.find("img")
            if img:text=img.get("alt") or ""
        key=urlparse(u).path
        if text and key not in found:found[key]={"name":text,"url":u}
    return list(found.values())

def parse_timing_page(url):
    try:html=get_html(to_en(url))
    except Exception as e:return {"available":False,"reason":type(e).__name__}
    soup=BeautifulSoup(html,"html.parser")
    text=soup.get_text("\n",strip=True)
    def section(start,end):
        i=text.find(start)
        if i<0:return None
        j=text.find(end,i+len(start))
        if j<0:j=min(len(text),i+5000)
        return text[i:j]
    def six(sec):
        if not sec:return None
        pairs=re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(\d+)\s*/\s*(\d+)\s*Goals",sec,re.I)
        if len(pairs)>=6:
            vals=[int(x[1]) for x in pairs[:6]]
            total=int(pairs[0][2])
            if sum(vals)==total or total==0:return {"counts":vals,"total":total,"percent":[float(x[0])/100 for x in pairs[:6]]}
            return {"counts":vals,"total":total,"percent":[float(x[0])/100 for x in pairs[:6]],"count_sum_mismatch":True}
        # percentage-only fallback
        ps=re.findall(r"(\d+(?:\.\d+)?)\s*%",sec)
        if len(ps)>=6:return {"counts":None,"total":None,"percent":[float(x)/100 for x in ps[:6]]}
        return None
    gf=six(section("Goals Scored By 15 min'","Goals Conceded By 15 min'"))
    ga=six(section("Goals Conceded By 15 min'","Total Goals By 10 min'"))
    if not gf or not ga:
        return {"available":False,"reason":"timing_section_missing","url":to_en(url)}
    h1=soup.find("h1")
    return {"available":True,"team_title":h1.get_text(" ",strip=True) if h1 else None,
            "bins":["0-15","16-30","31-45","46-60","61-75","76-90"],"goals_for":gf,"goals_against":ga,
            "url":to_en(url),"captured_at":"2026-09-25"}

def candidate_valid(team,url):
    try:
        html=get_html(to_cn(url));soup=BeautifulSoup(html,"html.parser");h=soup.find("h1")
        title=h.get_text(" ",strip=True) if h else ""
        target=TEAM_ALIAS.get(team,team)
        return sim(target,title),title
    except Exception:return 0,""

def main():
    matches=load_matches()
    by_league=defaultdict(set)
    team_leagues=defaultdict(set)
    for m in matches:
        by_league[m["league"]].update([m["home_team"],m["away_team"]])
        team_leagues[m["home_team"]].add(m["league"]);team_leagues[m["away_team"]].add(m["league"])
    initial_credit=credits()
    league_urls={};league_search={}
    mappings={}

    # Stage 1: search one FootyStats competition page per HH520 league, then map localized club links.
    for lg,teams in sorted(by_league.items(),key=lambda kv:-len(kv[1])):
        q=LEAGUE_ALIAS.get(lg,lg)+" FootyStats 2026 stats"
        res=search(q,8)
        u=choose_league_url(res)
        league_urls[lg]=u
        league_search[lg]={"query":q,"url":u,"result_count":len(res)}
        if not u:continue
        clubs=league_clubs(u)
        for team in teams:
            target=TEAM_ALIAS.get(team,team)
            ranked=sorted(((sim(target,c["name"]),c) for c in clubs),key=lambda x:x[0],reverse=True)
            if ranked and ranked[0][0]>=.56:
                old=mappings.get(team)
                if old is None or ranked[0][0]>old["score"]:
                    mappings[team]={"score":ranked[0][0],"source_name":ranked[0][1]["name"],"url":ranked[0][1]["url"],"method":"league_page","league":lg}

    # Stage 2: one exact localized search for unresolved teams, bounded by credits.
    allteams=sorted(team_leagues)
    unresolved=[t for t in allteams if t not in mappings]
    fallback_attempted=0
    for team in unresolved:
        rem=credits()
        if rem is not None and rem<30:break
        lg=next(iter(team_leagues[team]),"")
        q=f'site:footystats.org/cn/clubs "{TEAM_ALIAS.get(team,team)}" {LEAGUE_ALIAS.get(lg,lg)}'
        res=search(q,8);fallback_attempted+=1
        candidates=[]
        for x in res:
            u=x.get("url") or ""
            if "footystats.org" in u and "/clubs/" in urlparse(u).path:
                sc,title=candidate_valid(team,u)
                candidates.append((sc,title,u))
        if candidates:
            candidates.sort(reverse=True)
            sc,title,u=candidates[0]
            if sc>=.42:
                mappings[team]={"score":sc,"source_name":title,"url":u,"method":"team_search","league":lg}

    # Fetch timing profiles concurrently.
    profiles={}
    def worker(item):
        team,mp=item
        return team,parse_timing_page(mp["url"])
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut=[ex.submit(worker,x) for x in mappings.items()]
        for f in as_completed(fut):
            team,p=f.result();profiles[team]=p

    rows=[]
    both=partial=none=0
    for m in matches:
        hp=profiles.get(m["home_team"],{"available":False,"reason":"team_unresolved"})
        ap=profiles.get(m["away_team"],{"available":False,"reason":"team_unresolved"})
        n=int(bool(hp.get("available")))+int(bool(ap.get("available")))
        if n==2:both+=1
        elif n==1:partial+=1
        else:none+=1
        rows.append({**m,"home_timing":hp,"away_timing":ap,"timing_sides_available":n})

    final_credit=credits()
    out={
      "summary":{
        "requested_matches":len(matches),"unique_teams":len(allteams),"mapped_teams":len(mappings),
        "timing_profiles_available":sum(1 for p in profiles.values() if p.get("available")),
        "matches_both_sides_timing":both,"matches_one_side_timing":partial,"matches_no_timing":none,
        "initial_backup_credits":initial_credit,"final_backup_credits":final_credit,
        "credits_consumed":(initial_credit-final_credit) if isinstance(initial_credit,(int,float)) and isinstance(final_credit,(int,float)) else None,
        "league_searches":len(by_league),"fallback_team_searches":fallback_attempted,
        "source":"FootyStats team goal timing, 15-minute six-bin distributions",
        "snapshot_date":"2026-09-25",
        "historical_point_in_time":False,
        "warning":"Retrospective current-season snapshot; contains information accumulated after some target dates. Research only, not leakage-clean validation."
      },
      "league_search":league_search,
      "team_mappings":mappings,
      "profiles":profiles,
      "matches":rows
    }
    Path("_footystats_sep1_20_timing.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
