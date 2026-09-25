import json, os, re, sys, time
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown

FC="https://api.firecrawl.dev/v2"
KEY=os.environ["FIRECRAWL_API_KEY_BACKUP"]
H={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
S=requests.Session()

LEAGUE_URLS={
"西甲":"spain/la-liga",
"意甲":"italy/serie-a",
"英超":"england/premier-league",
"德甲":"germany/bundesliga",
"英冠":"england/championship",
"法甲":"france/ligue-1",
"日职":"japan/j1-league",
"欧冠":"europe/uefa-champions-league",
"欧罗巴":"europe/uefa-europa-league",
"沙职":"saudi-arabia/professional-league",
"巴甲":"brazil/serie-a",
"韩职":"south-korea/k-league-1",
"挪超":"norway/eliteserien",
"荷甲":"netherlands/eredivisie",
"葡超":"portugal/liga-nos",
"解放者杯":"south-america/copa-libertadores",
"瑞超":"sweden/allsvenskan",
"亚冠精英":"asia/afc-champions-league",
"英联赛杯":"england/league-cup",
"亚运男足":"asia/asian-games",
"美职":"usa/mls",
"德乙":"germany/2-bundesliga",
"意大利杯":"italy/coppa-italia",
"日乙":"japan/j2-league",
"法乙":"france/ligue-2",
"芬超":"finland/veikkausliiga",
"荷乙":"netherlands/eerste-divisie",
"巴西杯":"brazil/copa-do-brasil",
"亚冠乙":"asia/afc-cup",
"日联赛杯":"japan/j-league-cup",
}

ALIASES={
"伍尔弗":["狼队","伍尔弗汉普顿流浪"],
"布城":["布里斯托尔城","布里斯托城"],
"米堡":["米德尔斯堡"],
"雷克斯":["雷克瑟姆"],
"女王巡游":["女王公园巡游者","QPR"],
"西布罗姆":["西布罗姆维奇"],
"伊普斯":["伊普斯维奇"],
"巴黎圣曼":["巴黎圣日耳曼"],
"弗鲁米嫩":["弗鲁米嫩塞"],
"巴竞技":["巴拉纳竞技"],
"布拉干RB":["布拉甘蒂诺红牛","RB Bragantino"],
"安德莱":["安德莱赫特"],
"柏太阳神":["柏雷索尔","Kashiwa Reysol"],
"名古屋鲸":["名古屋鲸八","Nagoya Grampus"],
"町田泽维":["町田泽维亚","FC Machida Zelvia"],
"京都":["京都不死鸟","Kyoto Sanga"],
"东京绿茵":["东京绿茵","Tokyo Verdy"],
"利雅新月":["利雅得新月","Al Hilal"],
"利雅胜利":["利雅得胜利","Al Nassr"],
"吉达国民":["吉达阿赫利","Al Ahli"],
"吉达联合":["吉达伊蒂哈德","Al Ittihad"],
"巴黎FC":["巴黎FC","Paris FC"],
"雷恩":["雷恩","Rennes"],
"布伦特":["布伦特福德"],
"米尔沃尔":["米尔沃尔","Millwall"],
"诺维奇":["诺维奇城","Norwich City"],
"谢菲联":["谢菲尔德联"],
"南安普敦":["南安普顿"],
"沃特福德":["沃特福德","Watford"],
"斯旺西":["斯旺西城","Swansea City"],
"伯恩利":["伯恩利","Burnley"],
"布莱克本":["布莱克本流浪"],
"普雷斯顿":["普雷斯顿北区"],
"博尔顿":["博尔顿流浪"],
"德比郡":["德比郡","Derby County"],
}

def load_matches():
    out=[]
    for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
        ds=p.stem.replace("10027s_","")
        if not ("2026-09-01"<=ds<="2026-09-20"):
            continue
        payload=json.loads(p.read_text(encoding="utf-8"))
        md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
        for m in parse_10027s_markdown(md or ""):
            out.append({
                "date":ds,"match_id":m.get("match_id"),"league":str(m.get("league") or ""),
                "home_team":str(m.get("home_team") or ""),"away_team":str(m.get("away_team") or ""),
                "half_score":m.get("half_score"),"full_score":m.get("result"),
            })
    return out

def credit_balance():
    try:
        r=requests.get(FC+"/team/credit-usage",headers={"Authorization":f"Bearer {KEY}"},timeout=20)
        d=r.json()
        return (d.get("data") or {}).get("remainingCredits")
    except Exception:
        return None

def scrape(url):
    payload={"url":url,"formats":["markdown","links"],"onlyMainContent":False,"maxAge":604800000}
    for i in range(4):
        r=requests.post(FC+"/scrape",headers=H,json=payload,timeout=150)
        if r.status_code==429:
            time.sleep(2+2*i);continue
        if r.ok:
            d=r.json()
            return (d.get("data") or {}),d.get("creditsUsed")
        time.sleep(1+i)
    return {},None

def clean_name(s):
    s=re.sub(r"!\[[^\]]*\]\([^)]*\)","",str(s or ""))
    s=re.sub(r"\[[^\]]*\]","",s)
    s=s.replace("\\","")
    return re.sub(r"\s+"," ",s).strip(" -|")

def norm(s):
    s=str(s or "").lower()
    repl=["足球俱乐部","俱乐部","football club","f.c.","fc","afc","sc","club"," ","-","_","·",".","'","’","（","）","(",")","市","竞技体育"]
    for x in repl:s=s.replace(x,"")
    return s

def score_name(team,source):
    ns=norm(source)
    choices=[team]+ALIASES.get(team,[])
    best=0.0
    for c in choices:
        nc=norm(c)
        if not nc or not ns:continue
        if nc==ns:best=max(best,1.0)
        elif nc in ns or ns in nc:best=max(best,.91)
        else:best=max(best,SequenceMatcher(None,nc,ns).ratio())
    return best

LINK_RE=re.compile(r"\[([^\]]+)\]\((https?://footystats\.org/cn/clubs/[^)#?]+)[^)]*\)",re.I)

def clubs_from_markdown(md):
    out={}
    for label,url in LINK_RE.findall(md or ""):
        name=clean_name(label)
        if not name:continue
        path=urlparse(url).path
        key=re.sub(r"^/cn","",path)
        if key not in out or len(name)<len(out[key]["name"]):
            out[key]={"name":name,"url":"https://footystats.org/cn"+key}
    return list(out.values())

def to_english(url):
    p=urlparse(url)
    path=re.sub(r"^/cn","",p.path)
    return "https://footystats.org"+path

def six_bin(section):
    if not section:return None
    pairs=re.findall(r"(\d+(?:\.\d+)?)%\s*\n+\s*(\d+)\s*/\s*(\d+)\s*Goals",section,re.I)
    if len(pairs)>=6:
        p=pairs[:6]
        return {
            "percent":[float(x[0])/100 for x in p],
            "counts":[int(x[1]) for x in p],
            "total":int(p[0][2]),
        }
    return None

def parse_profile(md,url):
    def sec(a,b):
        i=(md or "").find(a)
        if i<0:return None
        j=(md or "").find(b,i+len(a))
        if j<0:j=min(len(md),i+5000)
        return md[i:j]
    gf=six_bin(sec("Goals Scored By 15 min'","Goals Conceded By 15 min'"))
    ga=six_bin(sec("Goals Conceded By 15 min'","Total Goals By 10 min'"))
    if not gf or not ga:
        return {"available":False,"reason":"timing_section_missing","url":url}
    return {
        "available":True,
        "bins":["0-15","16-30","31-45","46-60","61-75","76-90"],
        "goals_for":gf,"goals_against":ga,
        "url":url,"snapshot_date":"2026-09-25",
    }

def main():
    matches=load_matches()
    initial=credit_balance()
    teams=sorted({x for m in matches for x in (m["home_team"],m["away_team"])})
    teams_by_league=defaultdict(set)
    for m in matches:
        teams_by_league[m["league"]].update([m["home_team"],m["away_team"]])

    league_pages={}
    league_clubs={}
    global_pool={}
    # One scrape per competition page; this is the main discovery path.
    for lg in sorted(teams_by_league,key=lambda x:-len(teams_by_league[x])):
        path=LEAGUE_URLS.get(lg)
        if not path:
            league_pages[lg]={"ok":False,"reason":"no_url_mapping"};continue
        if (credit_balance() or 9999)<40:break
        url="https://footystats.org/cn/"+path
        data,cost=scrape(url)
        md=data.get("markdown") or ""
        clubs=clubs_from_markdown(md)
        league_clubs[lg]=clubs
        league_pages[lg]={"url":url,"clubs":len(clubs),"markdown_chars":len(md),"cost":cost}
        for c in clubs:
            global_pool[urlparse(c["url"]).path]=c

    # Map teams first inside their league; global fallback second.
    mappings={}
    for team in teams:
        relevant=[]
        for lg,ts in teams_by_league.items():
            if team in ts:relevant.extend(league_clubs.get(lg,[]))
        def best(cands):
            vals=sorted(((score_name(team,c["name"]),c) for c in cands),key=lambda x:x[0],reverse=True)
            return vals[0] if vals else (0,None)
        sc,c=best(relevant)
        method="league"
        if sc<.64:
            sc2,c2=best(list(global_pool.values()))
            if sc2>sc:sc,c,method=sc2,c2,"global"
        if c and sc>=.60:
            mappings[team]={"score":sc,"source_name":c["name"],"url":c["url"],"method":method}

    # Scrape unique mapped team profiles, budget bounded.
    url_to_teams=defaultdict(list)
    for team,mp in mappings.items():url_to_teams[to_english(mp["url"])].append(team)
    profiles_by_url={}
    ordered_urls=sorted(url_to_teams, key=lambda u:-sum(1 for m in matches if m["home_team"] in url_to_teams[u] or m["away_team"] in url_to_teams[u]))
    for u in ordered_urls:
        rem=credit_balance()
        if rem is not None and rem<20:break
        data,cost=scrape(u)
        profiles_by_url[u]=parse_profile(data.get("markdown") or "",u)
        profiles_by_url[u]["cost"]=cost

    profiles={}
    for team,mp in mappings.items():
        profiles[team]=profiles_by_url.get(to_english(mp["url"]),{"available":False,"reason":"budget_or_scrape_missing","url":to_english(mp["url"])})

    rows=[];both=one=none=0
    for m in matches:
        hp=profiles.get(m["home_team"],{"available":False,"reason":"unmapped"})
        ap=profiles.get(m["away_team"],{"available":False,"reason":"unmapped"})
        n=int(bool(hp.get("available")))+int(bool(ap.get("available")))
        both+=n==2;one+=n==1;none+=n==0
        rows.append({**m,"home_timing":hp,"away_timing":ap,"timing_sides_available":n})

    final=credit_balance()
    out={
      "summary":{
        "requested_matches":len(matches),"unique_teams":len(teams),
        "league_pages_attempted":len(league_pages),"club_pool":len(global_pool),
        "mapped_teams":len(mappings),"unique_profile_urls":len(url_to_teams),
        "profiles_scraped":len(profiles_by_url),
        "timing_profiles_available":sum(1 for p in profiles.values() if p.get("available")),
        "matches_both_sides_timing":both,"matches_one_side_timing":one,"matches_no_timing":none,
        "initial_backup_credits":initial,"final_backup_credits":final,
        "credits_consumed":initial-final if isinstance(initial,(int,float)) and isinstance(final,(int,float)) else None,
        "source":"FootyStats current-season team six-bin goal timing",
        "snapshot_date":"2026-09-25","historical_point_in_time":False,
        "warning":"Current-season snapshot captured after target dates; retrospective research only, not a leakage-clean historical validation."
      },
      "league_pages":league_pages,
      "team_mappings":mappings,
      "profiles":profiles,
      "matches":rows
    }
    Path("_footystats_sep1_20_timing_v2.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
