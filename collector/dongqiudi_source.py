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
import requests
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .firecrawl_client import search_web, scrape_markdown
from .dongqiudi_technical import collect_prematch_technical_history


DONGQIUDI_INDEX_URL="https://lottery-aggregator.dongqiudi.com/pcWeb/spreadMatch"
DONGQIUDI_PC_BASE="https://pc.dongqiudi.com"

def _parse_kickoff(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except Exception:
        return None

def _league_similarity(a,b):
    aa=_norm_team_name(a); bb=_norm_team_name(b)
    if not aa or not bb:
        return 0.0
    if aa in bb or bb in aa:
        return 1.0
    return SequenceMatcher(None,aa,bb).ratio()

def _pc_index_entries(timeout=20):
    try:
        r=requests.get(
            DONGQIUDI_INDEX_URL,
            headers={"Accept":"application/json","User-Agent":"HH520-Stable/3.5.1"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return []
        payload=r.json()
    except Exception:
        return []
    rows=payload.get("data") if isinstance(payload,dict) else None
    return rows if isinstance(rows,list) else []

def _entry_team(entry, side):
    if side=="home":
        return entry.get("home_name") or entry.get("team_A_name") or entry.get("home")
    return entry.get("guest_name") or entry.get("team_B_name") or entry.get("away")

def _entry_league(entry):
    return entry.get("match_name") or entry.get("competition_name") or entry.get("league")

def _entry_kickoff(entry):
    raw=entry.get("match_time") or entry.get("start_play")
    if not raw:
        return None
    s=str(raw).strip()
    # spreadMatch commonly uses MM/DD HH:MM for Beijing-local fixtures.
    if re.fullmatch(r"\d{2}/\d{2}\s+\d{2}:\d{2}",s):
        return s
    dt=_parse_kickoff(s)
    return dt

def _entry_match_id(entry):
    return str(entry.get("match_id") or entry.get("relate_id") or entry.get("id") or "").strip()

def _match_pc_entry(date, home, away, league=None, kickoff=None):
    rows=_pc_index_entries()
    if not rows:
        return None
    base_h=_alias_list(home); base_a=_alias_list(away)
    requested_dt=_parse_kickoff(kickoff)
    candidates=[]
    for entry in rows:
        mid=_entry_match_id(entry)
        if not mid:
            continue
        eh=_entry_team(entry,"home"); ea=_entry_team(entry,"away")
        hs=max((_name_similarity(x,eh) for x in base_h),default=0.0)
        aas=max((_name_similarity(x,ea) for x in base_a),default=0.0)
        if hs < 0.56 or aas < 0.56:
            continue
        score=hs+aas
        el=_entry_league(entry)
        if league and el:
            ls=_league_similarity(league,el)
            if ls < 0.45:
                continue
            score+=ls
        ek=_entry_kickoff(entry)
        if isinstance(ek,str) and re.fullmatch(r"\d{2}/\d{2}\s+\d{2}:\d{2}",ek):
            mmdd=str(date or "")[5:].replace("-","/")
            if mmdd and not ek.startswith(mmdd):
                continue
            if requested_dt:
                try:
                    hhmm=ek.split()[1]
                    req_hm=requested_dt.strftime("%H:%M")
                    h1,m1=map(int,hhmm.split(":")); h2,m2=map(int,req_hm.split(":"))
                    if abs((h1*60+m1)-(h2*60+m2)) > 20:
                        continue
                    score+=1.0
                except Exception:
                    pass
        elif requested_dt and isinstance(ek,datetime):
            try:
                delta=abs((ek.astimezone(timezone.utc)-requested_dt.astimezone(timezone.utc)).total_seconds())
                if delta > 20*60:
                    continue
                score+=1.0
            except Exception:
                pass
        candidates.append((score,entry))
    if not candidates:
        return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    if len(candidates)>1 and abs(candidates[0][0]-candidates[1][0])<0.05:
        return None
    return candidates[0][1]

def _parse_odds_markdown(markdown):
    """Parse public Dongqiudi European odds and representative live water."""
    text=str(markdown or "").replace("\r","")
    out={}

    m=re.search(
        r"平均值\s+初\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)",
        text,
    )
    if m:
        out["european_odds_average_initial"]=[float(x) for x in m.groups()]
        cm=re.search(
            r"平均值\s+初\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?.*?"
            r"即\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)",
            text,re.S,
        )
        if cm:
            out["european_odds_average_current"]=[float(x) for x in cm.groups()]

    m=re.search(
        r"竞\s+竞\s+初\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"
        r"\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"
        r".*?即\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"
        r"\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)",
        text,re.S,
    )
    if m:
        vals=[float(x) for x in m.groups()]
        out["representative_european_odds_initial"]=vals[:3]
        out["representative_asian_water_initial"]=vals[3:5]
        out["representative_european_odds_current"]=vals[5:8]
        out["representative_asian_water_current"]=vals[8:10]

    if out:
        out["home_draw_away_order"]=["home","draw","away"]
        out["source"]="DONGQIUDI_LOTTERY_ODDS_PUBLIC"
    return out


def _merge_odds(parsed, match_id):
    """Capture odds with direct HTTP first; use Firecrawl only as a parser fallback."""
    odds={}
    url=f"https://m.dongqiudi.com/matchDetail/{match_id}/lotteryOddsNew?cmp_type=soccer"
    try:
        response=requests.get(
            url,
            headers={"Accept":"text/html","User-Agent":"HH520-Stable/3.5.1"},
            timeout=10,
        )
        if response.status_code == 200:
            odds=_parse_odds_markdown(response.text)
    except Exception:
        pass
    if not odds:
        try:
            raw=scrape_markdown(url)
            markdown=((raw.get("data") or {}).get("markdown") if isinstance(raw,dict) else None) or ""
            odds=_parse_odds_markdown(markdown)
        except Exception:
            odds={}
    if odds:
        parsed["odds"]=odds
    return parsed


def _analysis_hit_from_pc_entry(entry):
    mid=_entry_match_id(entry)
    if not mid:
        return None
    return {
        "match_id":mid,
        "analysis_url":f"https://m.dongqiudi.com/matchDetail/{mid}/analysis",
        "pc_match_url":f"{DONGQIUDI_PC_BASE}/match/{mid}",
        "discovered_from":DONGQIUDI_INDEX_URL,
        "query":"DONGQIUDI_PC_SPREAD_MATCH",
        "league":_entry_league(entry),
        "kickoff":entry.get("match_time") or entry.get("start_play"),
    }

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
    "热刺":("热刺","托特纳姆热刺","托特纳姆"),
    "埃弗顿":("埃弗顿","爱华顿"),
    "摩纳哥":("摩纳哥","AS摩纳哥"),
    "埃尔切":("埃尔切","艾尔切"),
    "卡萨皮亚":("卡萨皮亚","卡萨皮亚AC","卡萨皮亚竞技"),
    "波尔图":("波尔图","波图"),
    "里昂":("里昂","里昂奥林匹克"),
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
    text=re.sub(r"[\s·・\-_/().（）]+","",text)
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
        if not value or len(value)>30 or re.search(r"\d{1,2}[-:/：]\d{1,2}",value):
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
    m=re.fullmatch(r"\d{4}-(\d{2})-(\d{2})",str(date or ""))
    if m:
        mmdd=f"{m.group(1)}-{m.group(2)}"
        if mmdd not in header:
            return False
    return True


def _candidate_queries(date,home,away):
    hq,aq=_search_name(home),_search_name(away)
    mmdd=str(date or "")[5:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}",str(date or "")) else date
    return [
        f'懂球帝 {hq} {aq} {date} 比赛详情',
        f'site:m.dongqiudi.com/matchDetail "{hq}" "{aq}" {mmdd}',
        f'懂球帝 {home} {away} {mmdd} 比赛详情',
    ]


def _discover_query(query):
    raw=search_web(query,limit=8)
    candidates=[]
    seen=set()
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
    return candidates


def discover_match_details(date,home,away):
    # Compatibility helper: keep the cheapest single-search behaviour.
    for query in _candidate_queries(date,home,away):
        try:
            candidates=_discover_query(query)
        except Exception:
            continue
        if candidates:
            return candidates
    return []


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



TIMING_BINS=("0-15","16-30","31-45","46-60","61-75","76-90")

def _pair_metric(text, labels):
    for label in labels:
        patterns=(
            rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[-:：/|]\s*(\d+(?:\.\d+)?)",
            rf"\|\s*{re.escape(label)}\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|",
        )
        for pattern in patterns:
            m=re.search(pattern,text,re.I|re.M)
            if m:
                return {"home":float(m.group(1)),"away":float(m.group(2))}
    return None

def _pair_percent_metric(text, labels):
    for label in labels:
        patterns=(
            rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]?\s*(\d+(?:\.\d+)?)\s*%\s*[-:：/|]\s*(\d+(?:\.\d+)?)\s*%",
            rf"\|\s*{re.escape(label)}\s*\|\s*(\d+(?:\.\d+)?)\s*%\s*\|\s*(\d+(?:\.\d+)?)\s*%\s*\|",
        )
        for pattern in patterns:
            m=re.search(pattern,text,re.I|re.M)
            if m:
                return {"home":float(m.group(1))/100.0,"away":float(m.group(2))/100.0}
    return None

def _six_numbers(line):
    vals=[float(x) for x in re.findall(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])",line)]
    return vals[-6:] if len(vals)>=6 else None

def _timing_values(text, team, kind):
    if not team:
        return None
    aliases=_alias_list(team)
    lines=text.splitlines()
    kind_tokens=("进球","得分") if kind=="for" else ("失球","丢球","被进球")
    for i,line in enumerate(lines):
        if not any(alias and alias in line for alias in aliases):
            continue

        # Prefer a complete same-line record. This prevents the six-bin parser
        # from drifting into the next team's row when compact markdown places
        # home/away timing rows next to each other.
        if any(token in line for token in kind_tokens):
            vals=_six_numbers(line)
            if vals:
                return vals

        # Multi-line table fallback: team label -> metric label -> six values.
        for j in range(i+1,min(len(lines),i+3)):
            probe=lines[j]
            if not any(token in probe for token in kind_tokens):
                continue
            vals=_six_numbers(probe)
            if vals:
                return vals
            if j+1 < len(lines):
                vals=_six_numbers(lines[j+1])
                if vals:
                    return vals
    return None

def _shares(values):
    if not values or len(values)!=6:
        return None
    vals=[max(0.0,float(x)) for x in values]
    total=sum(vals)
    if total<=0:
        return None
    return [x/total for x in vals]

def _timing_profile(text, team):
    gf=_shares(_timing_values(text,team,"for"))
    ga=_shares(_timing_values(text,team,"against"))
    if not gf or not ga:
        return {}
    raw_gf=_timing_values(text,team,"for")
    raw_ga=_timing_values(text,team,"against")
    return {
        "timing_bins":list(TIMING_BINS),
        "goals_for_bins":raw_gf,
        "goals_against_bins":raw_ga,
        "goals_for_share":gf,
        "goals_against_share":ga,
        "first_half_gf_signal":sum(gf[:3]),
        "first_half_ga_signal":sum(ga[:3]),
        "second_half_gf_signal":sum(gf[3:]),
        "second_half_ga_signal":sum(ga[3:]),
    }

def _merge_technical_history(parsed, match_id, home_team, away_team, kickoff=None):
    try:
        technical=collect_prematch_technical_history(match_id,home_team,away_team,kickoff)
    except Exception as exc:
        parsed["technical_history"]={"available":False,"reason":f"technical_history_error:{type(exc).__name__}"}
        return parsed

    min_samples=3
    for side in ("home","away"):
        block=(technical.get(side) or {})
        samples=int(block.get("sample_count") or 0)
        metrics=block.get("metrics") or {}
        target=parsed.get(side) or {}
        target["technical_history_samples"]=samples
        target["technical_history_match_ids"]=[
            str(x.get("match_id")) for x in (block.get("observations") or []) if x.get("match_id")
        ]
        if samples>=min_samples:
            for key,value in metrics.items():
                if key.endswith("_samples"):
                    target[key]=value
                elif target.get(key) is None:
                    target[key]=value
        parsed[side]=target

    h=parsed.get("home") or {}; a=parsed.get("away") or {}
    groups=parsed.setdefault("groups",{})
    groups["SHOTS"]=all(x.get("shots") is not None and x.get("shots_on_target") is not None for x in (h,a))
    groups["POSSESSION"]=all(x.get("possession") is not None for x in (h,a))
    groups["DANGEROUS_ATTACKS"]=all(x.get("dangerous_attacks") is not None for x in (h,a))
    groups["BIG_CHANCES"]=all(x.get("big_chances") is not None for x in (h,a))
    groups["GOAL_TIMING"]=all(
        isinstance(x.get(key),(list,tuple)) and len(x.get(key))==6
        for x in (h,a) for key in ("goals_for_share","goals_against_share")
    )
    parsed["technical_history"]={
        "available":bool((technical.get("home") or {}).get("sample_count") or (technical.get("away") or {}).get("sample_count")),
        "source":technical.get("source"),
        "min_samples_for_model":min_samples,
        "home_samples":(technical.get("home") or {}).get("sample_count",0),
        "away_samples":(technical.get("away") or {}).get("sample_count",0),
    }
    parsed["field_count"]=len(h)+len(a)
    return parsed


def parse_analysis_markdown(markdown, home_team=None, away_team=None):
    text=str(markdown or "").replace("\r","")
    last10=_pair_wdl(text,"近10场战绩")
    samevenue=_pair_wdl(text,"近10场同主客")
    h2h=_pair_wdl(text,"近6场交锋") or _pair_wdl(text,"近5场交锋")
    gf=_pair_ball(text,"场均进球")
    ga=_pair_ball(text,"场均失球")
    shots=_pair_metric(text,("射门","场均射门","射门次数"))
    sot=_pair_metric(text,("射正","场均射正","射正次数"))
    shots_off=_pair_metric(text,("射偏","场均射偏","射偏次数","未射正"))
    possession=_pair_percent_metric(text,("控球率","控球"))
    dangerous=_pair_metric(text,("危险进攻","场均危险进攻"))
    big_chances=_pair_metric(text,("绝佳机会","重大机会","得分机会"))
    home={}; away={}
    if last10:
        hr=_rates(last10["home"]); ar=_rates(last10["away"])
        home.update(hr); away.update(ar)
        home["recent10_record"]={"wins":last10["home"][0],"draws":last10["home"][1],"losses":last10["home"][2]}
        away["recent10_record"]={"wins":last10["away"][0],"draws":last10["away"][1],"losses":last10["away"][2]}
        home.update({f"recent10_{k}":v for k,v in hr.items()})
        away.update({f"recent10_{k}":v for k,v in ar.items()})
    if samevenue:
        hr=_rates(samevenue["home"]); ar=_rates(samevenue["away"])
        home["venue10_record"]={"wins":samevenue["home"][0],"draws":samevenue["home"][1],"losses":samevenue["home"][2]}
        away["venue10_record"]={"wins":samevenue["away"][0],"draws":samevenue["away"][1],"losses":samevenue["away"][2]}
        home.update({f"venue10_{k}":v for k,v in hr.items()})
        away.update({f"venue10_{k}":v for k,v in ar.items()})
    if h2h:
        hr=_rates(h2h["home"]); ar=_rates(h2h["away"])
        home["h2h_record"]={"wins":h2h["home"][0],"draws":h2h["home"][1],"losses":h2h["home"][2]}
        away["h2h_record"]={"wins":h2h["away"][0],"draws":h2h["away"][1],"losses":h2h["away"][2]}
        home.update({f"h2h_{k}":v for k,v in hr.items()})
        away.update({f"h2h_{k}":v for k,v in ar.items()})
    if gf:
        home["scored_per_match"]=gf["home"]; away["scored_per_match"]=gf["away"]
    if ga:
        home["conceded_per_match"]=ga["home"]; away["conceded_per_match"]=ga["away"]
    if shots:
        home["shots"]=shots["home"]; away["shots"]=shots["away"]
    if sot:
        home["shots_on_target"]=sot["home"]; away["shots_on_target"]=sot["away"]
    if shots_off:
        home["shots_off_target"]=shots_off["home"]; away["shots_off_target"]=shots_off["away"]
    if possession:
        home["possession"]=possession["home"]; away["possession"]=possession["away"]
    if dangerous:
        home["dangerous_attacks"]=dangerous["home"]; away["dangerous_attacks"]=dangerous["away"]
    if big_chances:
        home["big_chances"]=big_chances["home"]; away["big_chances"]=big_chances["away"]
    for side,profile in ((home,_timing_profile(text,home_team)),(away,_timing_profile(text,away_team))):
        side.update(profile)
        if side.get("shots") not in (None,0) and side.get("shots_on_target") is not None:
            side["shot_on_target_rate"]=side["shots_on_target"]/side["shots"]
            if side.get("shots_off_target") is None and side["shots"] >= side["shots_on_target"]:
                side["shots_off_target"]=side["shots"]-side["shots_on_target"]
        if side.get("shots") not in (None,0) and side.get("scored_per_match") is not None:
            side["shot_conversion"]=side["scored_per_match"]/side["shots"]
    return {
        "home":home,"away":away,
        "groups":{
            "RECENT_FORM":bool(last10),
            "VENUE_FORM":bool(samevenue),
            "H2H":bool(h2h),
            "GF_GA":bool(gf and ga),
            "SHOTS":bool(shots and sot),
            "POSSESSION":bool(possession),
            "DANGEROUS_ATTACKS":bool(dangerous),
            "BIG_CHANCES":bool(big_chances),
            "GOAL_TIMING":bool(
                home.get("goals_for_share") and home.get("goals_against_share")
                and away.get("goals_for_share") and away.get("goals_against_share")
            ),
        },
        "field_count":len(home)+len(away),
    }


def collect_match_analysis(date,home,away,league=None,kickoff=None):
    # Prefer Dongqiudi's own public PC fixture list. Search is only a fallback.
    pc_entry=_match_pc_entry(date,home,away,league=league,kickoff=kickoff)
    if pc_entry:
        hit=_analysis_hit_from_pc_entry(pc_entry)
        if hit:
            try:
                raw=scrape_markdown(hit["analysis_url"])
                markdown=((raw.get("data") or {}).get("markdown") if isinstance(raw,dict) else None) or ""
            except Exception:
                markdown=""
            if markdown and _header_matches(markdown,date,home,away):
                parsed=parse_analysis_markdown(markdown,home,away)
                parsed=_merge_technical_history(parsed,hit["match_id"],home,away,kickoff)
                parsed=_merge_odds(parsed,hit["match_id"])
                available=any(parsed["groups"].values())
                return {
                    "available":available,
                    "reason":None if available else "dongqiudi_analysis_no_features",
                    "source":"DONGQIUDI_PC_FIXTURE_PLUS_PUBLIC_ANALYSIS",
                    "source_domain":urlparse(hit["analysis_url"]).netloc.lower(),
                    "match_detail_id":hit["match_id"],
                    "analysis_url":hit["analysis_url"],
                    "pc_match_url":hit.get("pc_match_url"),
                    "discovered_from":hit["discovered_from"],
                    "query":hit["query"],
                    "validated_header":True,
                    "fixture_match":{
                        "league":hit.get("league"),"kickoff":hit.get("kickoff"),
                        "home":_entry_team(pc_entry,"home"),"away":_entry_team(pc_entry,"away"),
                    },
                    "search_attempts":0,
                    "rejected_candidates":[],
                    **parsed,
                }

    # Search progressively. We only pay for fallback searches when every
    # candidate from the cheaper first query fails validation.
    rejected=[]
    seen=set()
    candidate_count=0
    search_attempts=0
    for query in _candidate_queries(date,home,away):
        try:
            candidates=_discover_query(query)
            search_attempts+=1
        except Exception:
            continue
        candidate_count+=len(candidates)
        for hit in candidates[:8]:
            if hit["match_id"] in seen:
                continue
            seen.add(hit["match_id"])
            try:
                raw=scrape_markdown(hit["analysis_url"])
                markdown=((raw.get("data") or {}).get("markdown") if isinstance(raw,dict) else None) or ""
            except Exception as exc:
                rejected.append({"match_id":hit["match_id"],"reason":type(exc).__name__})
                continue
            if not _header_matches(markdown,date,home,away):
                rejected.append({"match_id":hit["match_id"],"reason":"team_or_home_away_mismatch"})
                continue
            parsed=parse_analysis_markdown(markdown,home,away)
            parsed=_merge_technical_history(parsed,hit["match_id"],home,away,kickoff)
            parsed=_merge_odds(parsed,hit["match_id"])
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
                "search_attempts":search_attempts,
                "rejected_candidates":rejected,
                **parsed,
            }
    return {
        "available":False,
        "reason":"dongqiudi_match_not_found_or_unvalidated",
        "rejected_candidates":rejected,
        "candidate_count":candidate_count,
        "search_attempts":search_attempts,
    }
