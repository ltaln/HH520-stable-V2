"""Public Dongqiudi match-analysis collector.

Research-safe design:
- discover a public matchDetail URL with one web search;
- scrape only the public /analysis page;
- parse pre-match comparison blocks locally (no JSON extraction);
- never use /situation or post-match technical statistics for historical replay.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .firecrawl_client import search_web, scrape_markdown

MATCH_RE = re.compile(r"https?://m\.dongqiudi\.com/matchDetail/(\d+)(?:/[^\s\"'<>?]*)?(?:\?[^\s\"'<>]*)?", re.I)
WDL_RE = re.compile(r"(\d+)胜\s*(\d+)平\s*(\d+)负")
FLOAT_BALL_RE = re.compile(r"(\d+(?:\.\d+)?)球")


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


def discover_match_detail(home, away):
    queries=[
        f'懂球帝 {home} {away} 比赛详情',
        f'site:m.dongqiudi.com/matchDetail {home} {away} 比赛详情',
    ]
    for query in queries:
        try:
            raw=search_web(query,limit=5)
        except Exception:
            continue
        for url in _urls(raw):
            mid=_match_id_from_url(url)
            if mid:
                return {
                    "match_id":mid,
                    "analysis_url":f"https://m.dongqiudi.com/matchDetail/{mid}/analysis",
                    "discovered_from":url,
                    "query":query,
                }
    return None


def _pair_wdl(text,label):
    # Dongqiudi renders: home WDL -> label -> away WDL
    p=re.compile(
        rf"(\d+)胜\s*(\d+)平\s*(\d+)负\s*\n+\s*{re.escape(label)}\s*\n+\s*(\d+)胜\s*(\d+)平\s*(\d+)负",
        re.M,
    )
    m=p.search(text)
    if not m:
        return None
    nums=[int(x) for x in m.groups()]
    return {"home":nums[:3],"away":nums[3:]}


def _pair_ball(text,label):
    p=re.compile(
        rf"(\d+(?:\.\d+)?)球\s*\n+\s*{re.escape(label)}\s*\n+\s*(\d+(?:\.\d+)?)球",
        re.M,
    )
    m=p.search(text)
    if not m:
        return None
    return {"home":float(m.group(1)),"away":float(m.group(2))}


def _rates(wdl):
    if not wdl:
        return {}
    s=sum(wdl)
    if s<=0:
        return {}
    return {
        "wins_rate":wdl[0]/s,
        "draws_rate":wdl[1]/s,
        "losses_rate":wdl[2]/s,
    }


def parse_analysis_markdown(markdown):
    text=str(markdown or "").replace("\r","")
    last10=_pair_wdl(text,"近10场战绩")
    samevenue=_pair_wdl(text,"近10场同主客")
    h2h=_pair_wdl(text,"近6场交锋") or _pair_wdl(text,"近5场交锋")
    gf=_pair_ball(text,"场均进球")
    ga=_pair_ball(text,"场均失球")

    home={}
    away={}
    if last10:
        home.update(_rates(last10["home"]))
        away.update(_rates(last10["away"]))
        home["recent10_wins_rate"]=home["wins_rate"]
        home["recent10_draws_rate"]=home["draws_rate"]
        home["recent10_losses_rate"]=home["losses_rate"]
        away["recent10_wins_rate"]=away["wins_rate"]
        away["recent10_draws_rate"]=away["draws_rate"]
        away["recent10_losses_rate"]=away["losses_rate"]
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
        "home":home,
        "away":away,
        "groups":{
            "RECENT_FORM":bool(last10),
            "VENUE_FORM":bool(samevenue),
            "H2H":bool(h2h),
            "GF_GA":bool(gf and ga),
        },
        "field_count":len(home)+len(away),
    }


def collect_match_analysis(home, away):
    hit=discover_match_detail(home,away)
    if not hit:
        return {"available":False,"reason":"dongqiudi_match_not_found"}
    raw=scrape_markdown(hit["analysis_url"])
    markdown=((raw.get("data") or {}).get("markdown") if isinstance(raw,dict) else None) or ""
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
        **parsed,
    }
