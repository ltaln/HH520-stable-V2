"""Public Dongqiudi match-analysis collector.

Research-safe design:
- discover public matchDetail candidates with targeted search;
- validate home/away order from the match header before accepting a page;
- scrape only the public /analysis page;
- parse pre-match comparison blocks locally;
- never use /situation post-match technical statistics in historical replay.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .firecrawl_client import search_web, scrape_markdown

MATCH_RE=re.compile(r"https?://m\.dongqiudi\.com/matchDetail/(\d+)(?:/[^\s\"'<>?]*)?(?:\?[^\s\"'<>]*)?",re.I)

ALIASES={
    "京都":("京都","京都不死鸟"),
    "哈马费萨":("哈马费萨","费萨里哈曼","费萨里"),
    "马斯特里":("马斯特里","马斯特里赫特"),
    "雷克斯":("雷克斯","雷克瑟姆","雷克斯汉姆"),
    "巴伦西亚":("巴伦西亚","瓦伦西亚"),
    "科里蒂巴":("科里蒂巴","库里蒂巴"),
    "巴竞技":("巴竞技","巴拉纳竞技","巴拉纳"),
    "蔚山现代":("蔚山现代","蔚山HD","蔚山"),
    "维拉":("维拉","阿斯顿维拉"),
    "诺丁汉":("诺丁汉","诺丁汉森林"),
    "斯特拉斯":("斯特拉斯","斯特拉斯堡"),
    "科隆":("科隆","科隆足球俱乐部"),
    "不来梅":("不来梅","云达不莱梅","不莱梅"),
    "毕尔巴鄂":("毕尔巴鄂","毕尔巴鄂竞技"),
    "福图纳":("福图纳","福图纳锡塔德","锡塔德幸运"),
    "巴黎FC":("巴黎FC","巴黎足球会","巴黎FC足球俱乐部"),
}


def _alias_list(team):
    team=str(team or "").strip()
    return ALIASES.get(team,(team,))


def _search_name(team):
    vals=_alias_list(team)
    return vals[-1] if len(vals)>1 else vals[0]


def _urls(value):
    found=[]
    def walk(node):
        if isinstance(node,dict):
            for v in node.values(): walk(v)
        elif isinstance(node,list):
            for v in node: walk(v)
        elif isinstance(node,str) and node.startswith(("http://","https://")):
            found.append(node)
    walk(value)
    return found


def _match_id_from_url(url):
    m=MATCH_RE.search(str(url or ""))
    return m.group(1) if m else None


def _norm_team_name(value):
    text=str(value or "").strip().lower()
    for token in ("足球俱乐部","俱乐部","football club","fc","afc","cf","sc","fk","club","队"):
        text=text.replace(token,"")
    text=re.sub(r"[\\s·・\-_/().（）]+","",text)
    return text


def _name_similarity(a,b):
    aa=_norm_team_name(a); bb=_norm_team_name(b)
    if not aa or not bb:
        return 0.0
    if aa in bb or bb in aa:
        return min(len(aa),len(bb))/max(len(aa),len(bb))
    return SequenceMatcher(None,aa,bb).ratio()


def _header_team_position(header,team):
    positions=[]
    for alias in _alias_list(team):
        if not alias:
            continue
        idx=header.find(alias)
        if idx>=0:
            positions.append((idx,1.0,alias))
    if positions:
        return min(positions,key=lambda x:x[0])

    # Fuzzy fallback for names that differ between HH520 and Dongqiudi.
    # Only consider short non-empty lines near the match header and require a
    # reasonably strong similarity so an unrelated search hit is rejected.
    for line_no,line in enumerate(header.splitlines()[:30]):
        value=line.strip(" -*#\t")
        if not value or len(value)>30 or re.search(r"\\d{1,2}[-:/：]\\d{1,2}",value):
            continue
        best=max((_name_similarity(alias,value) for alias in _alias_list(team)),default=0.0)
        if best>=0.56:
            positions.append((line_no*50,best,value))
    return min(positions,key=lambda x:x[0]) if positions else None


def _header_matches(markdown,date,home,away):
    header=str(markdown or "")[:800]
    hp=_header_team_position(header,home)
    ap=_header_team_position(header,away)
    if not hp or not ap or hp[0]>=ap[0]:
        return False

    # Historical replay must bind to the requested day. Dongqiudi headers use
    # MM-DD, so verify that token when a valid ISO date is supplied.
    m=re.fullmatch(r"\\d{4}-(\\d{2})-(\\d{2})",str(date or ""))
    if m:
        mmdd=f"{m.group(1)}-{m.group(2)}"
        if mmdd not in header:
            return False
    return True


def discover_match_details(date,home,away):
    hq,aq=_search_name(home),_search_name(away)
    queries=[
        f'懂球帝 {hq} {aq} {date} 比赛详情',
        f'site:m.dongqiudi.com/matchDetail {hq} {aq} 比赛详情',
        f'懂球帝 {home} {away} 比赛详情',
    ]
    candidates=[]
    seen=set()
    for query in queries:
        try:
            raw=search_web(query,limit=8)
        except Exception:
            continue
        for url in _urls(raw):
            mid=_match_id_from_url(url)
            if not mid or mid in seen:
                continue
            seen.add(mid)
            candidates.append({
                "match_id":mid,
                "analysis_url":f"https://m.dongqiudi.com/matchDetail/{mid}/analysis",
                "discovered_from":url,
                "query":query,
            })
        if candidates:
            # Validation below is authoritative; one query is normally enough.
            break
    return candidates


def _pair_wdl(text,label):
    p=re.compile(
        rf"(\d+)胜\s*(\d+)平\s*(\d+)负\s*\n+\s*{re.escape(label)}\s*\n+\s*(\d+)胜\s*(\d+)平\s*(\d+)负",
        re.M,
    )
    m=p.search(text)
    if not m: return None
    nums=[int(x) for x in m.groups()]
    return {"home":nums[:3],"away":nums[3:]}


def _pair_ball(text,label):
    p=re.compile(
        rf"(\d+(?:\.\d+)?)球\s*\n+\s*{re.escape(label)}\s*\n+\s*(\d+(?:\.\d+)?)球",
        re.M,
    )
    m=p.search(text)
    if not m: return None
    return {"home":float(m.group(1)),"away":float(m.group(2))}


def _rates(wdl):
    if not wdl: return {}
    s=sum(wdl)
    if s<=0: return {}
    return {"wins_rate":wdl[0]/s,"draws_rate":wdl[1]/s,"losses_rate":wdl[2]/s}


def parse_analysis_markdown(markdown):
    text=str(markdown or "").replace("\r","")
    last10=_pair_wdl(text,"近10场战绩")
    samevenue=_pair_wdl(text,"近10场同主客")
    h2h=_pair_wdl(text,"近6场交锋") or _pair_wdl(text,"近5场交锋")
    gf=_pair_ball(text,"场均进球")
    ga=_pair_ball(text,"场均失球")
    home={}; away={}
    if last10:
        hr=_rates(last10["home"]); ar=_rates(last10["away"])
        home.update(hr); away.update(ar)
        home.update({f"recent10_{k}":v for k,v in hr.items()})
        away.update({f"recent10_{k}":v for k,v in ar.items()})
    if samevenue:
        hr=_rates(samevenue["home"]); ar=_rates(samevenue["away"])
        home.update({f"venue10_{k}":v for k,v in hr.items()})
        away.update({f"venue10_{k}":v for k,v in ar.items()})
    if h2h:
        hr=_rates(h2h["home"]); ar=_rates(h2h["away"])
        home.update({f"h2h_{k}":v for k,v in hr.items()})
        away.update({f"h2h_{k}":v for k,v in ar.items()})
    if gf:
        home["scored_per_match"]=gf["home"]; away["scored_per_match"]=gf["away"]
    if ga:
        home["conceded_per_match"]=ga["home"]; away["conceded_per_match"]=ga["away"]
    return {
        "home":home,"away":away,
        "groups":{
            "RECENT_FORM":bool(last10),
            "VENUE_FORM":bool(samevenue),
            "H2H":bool(h2h),
            "GF_GA":bool(gf and ga),
        },
        "field_count":len(home)+len(away),
    }


def collect_match_analysis(date,home,away):
    candidates=discover_match_details(date,home,away)
    rejected=[]
    for hit in candidates[:8]:
        try:
            raw=scrape_markdown(hit["analysis_url"])
            markdown=((raw.get("data") or {}).get("markdown") if isinstance(raw,dict) else None) or ""
        except Exception as exc:
            rejected.append({"match_id":hit["match_id"],"reason":type(exc).__name__})
            continue
        if not _header_matches(markdown,date,home,away):
            rejected.append({"match_id":hit["match_id"],"reason":"team_or_home_away_mismatch"})
            continue
        parsed=parse_analysis_markdown(markdown)
        available=any(parsed["groups"].values())
        return {
            "available":available,
            "reason":None if available else "dongqiudi_analysis_no_features",
            "source":"DONGQIUDI_PUBLIC_ANALYSIS",
            "source_domain":urlparse(hit["analysis_url"]).netloc.lower(),
            "match_detail_id":hit["match_id"],
            "analysis_url":hit["analysis_url"],
            "discovered_from":hit["discovered_from"],
            "query":hit["query"],
            "validated_header":True,
            "rejected_candidates":rejected,
            **parsed,
        }
    return {
        "available":False,
        "reason":"dongqiudi_match_not_found_or_unvalidated",
        "rejected_candidates":rejected,
        "candidate_count":len(candidates),
    }
