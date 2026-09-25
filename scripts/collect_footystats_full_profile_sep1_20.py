import json, os, re, sys, time
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

FC="https://api.firecrawl.dev/v2"
KEY=os.environ["FIRECRAWL_API_KEY_BACKUP"]
H={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
S=requests.Session()

def credit_balance():
    try:
        r=requests.get(FC+"/team/credit-usage",headers={"Authorization":f"Bearer {KEY}"},timeout=20)
        d=r.json()
        return (d.get("data") or {}).get("remainingCredits")
    except Exception:
        return None

def scrape(url):
    payload={"url":url,"formats":["markdown"],"onlyMainContent":False,"maxAge":0}
    for i in range(4):
        try:
            r=requests.post(FC+"/scrape",headers=H,json=payload,timeout=180)
            if r.status_code==429:
                time.sleep(3+3*i);continue
            if r.ok:
                d=r.json()
                return (d.get("data") or {}),d.get("creditsUsed"),None
            err=f"http_{r.status_code}:{r.text[:200]}"
        except Exception as e:
            err=repr(e)
        time.sleep(2+i)
    return {},None,err

def clean_label(s):
    s=re.sub(r"[*_]+","",str(s or ""))
    s=re.sub(r"\s+"," ",s).strip()
    return s

def scalar(v):
    s=clean_label(v).replace(",","")
    if not s or s in {"-","—","N/A","n/a"}:return None
    m=re.match(r"^(-?\d+(?:\.\d+)?)\s*%$",s)
    if m:return float(m.group(1))/100.0
    m=re.match(r"^(-?\d+(?:\.\d+)?)\s*(?:min|mins|min')?$",s,re.I)
    if m:return float(m.group(1))
    m=re.match(r"^(-?\d+(?:\.\d+)?)\s+in\s+\d+$",s,re.I)
    if m:return float(m.group(1))
    m=re.match(r"^(-?\d+(?:\.\d+)?)\s*(?:Conc\.|Goals?|Pts)?$",s,re.I)
    if m:return float(m.group(1))
    return None

def parse_tables(md):
    rows=[]
    section=""
    for raw in (md or "").splitlines():
        line=raw.strip()
        if line.startswith("#"):
            section=clean_label(re.sub(r"^#+\s*","",line))
            continue
        if not line.startswith("|"):continue
        cells=[clean_label(x) for x in line.strip("|").split("|")]
        if len(cells)<4:continue
        if all(re.fullmatch(r"[:\- ]*",x or "") for x in cells):continue
        label=cells[0]
        if not label or label.lower() in {"stats","overall","team shots","expected goals","over / btts","conceded per game","conceded 1st/2nd half"}:continue
        vals=[scalar(cells[i]) if i<len(cells) else None for i in range(1,4)]
        if all(v is None for v in vals):continue
        rows.append({"section":section,"label":label,"overall":vals[0],"home":vals[1],"away":vals[2],"raw":cells[1:4]})
    return rows

def first_row(rows,*labels):
    wanted={x.lower() for x in labels}
    for r in rows:
        if r["label"].lower() in wanted:return r
    return None

def val3(row):
    if not row:return {"overall":None,"home":None,"away":None}
    return {k:row.get(k) for k in ("overall","home","away")}

def six_bin(section):
    if not section:return None
    pairs=re.findall(r"(\d+(?:\.\d+)?)%\s*\n+\s*(\d+)\s*/\s*(\d+)\s*Goals",section,re.I)
    if len(pairs)>=6:
        p=pairs[:6]
        return {"percent":[float(x[0])/100 for x in p],"counts":[int(x[1]) for x in p],"total":int(p[0][2])}
    return None

def parse_timing(md):
    def sec(a,b):
        i=(md or "").find(a)
        if i<0:return None
        j=(md or "").find(b,i+len(a))
        if j<0:j=min(len(md),i+7000)
        return md[i:j]
    gf=six_bin(sec("Goals Scored By 15 min'","Goals Conceded By 15 min'"))
    ga=six_bin(sec("Goals Conceded By 15 min'","Total Goals By 10 min'"))
    return {"bins":["0-15","16-30","31-45","46-60","61-75","76-90"],"goals_for":gf,"goals_against":ga}

def parse_profile(md,url):
    rows=parse_tables(md)
    p={
      "xg_for":val3(first_row(rows,"xG For / Match","xG For")),
      "xg_against":val3(first_row(rows,"xG Against / Match","xG Against")),
      "scored_per_match":val3(first_row(rows,"Scored / Match")),
      "conceded_per_match":val3(first_row(rows,"Conceded / Match")),
      "clean_sheet":val3(first_row(rows,"Clean Sheets %")),
      "failed_to_score":val3(first_row(rows,"Failed to Score %")),
      "possession":val3(first_row(rows,"Possession AVG")),
      "shots":val3(first_row(rows,"Shots Taken / Match","Shots / Match")),
      "shots_on_target":val3(first_row(rows,"Shots On Target / Match")),
      "shots_off_target":val3(first_row(rows,"Shots Off Target / Match")),
      "shot_conversion":val3(first_row(rows,"Shots Conversion Rate")),
      "shots_per_goal":val3(first_row(rows,"Shots Per Goal Scored")),
      "sot_per_goal":val3(first_row(rows,"Shots On Target Per Goal Scored")),
      "wins":val3(first_row(rows,"Wins")),
      "draws":val3(first_row(rows,"Draws")),
      "losses":val3(first_row(rows,"Losses")),
      "btts":val3(first_row(rows,"BTTS %")),
      "btts_win":val3(first_row(rows,"BTTS & Win %")),
      "btts_draw":val3(first_row(rows,"BTTS & Draw %")),
      "over_05":val3(first_row(rows,"Over 0.5 %")),
      "over_15":val3(first_row(rows,"Over 1.5 %")),
      "over_25":val3(first_row(rows,"Over 2.5 %")),
      "over_35":val3(first_row(rows,"Over 3.5 %")),
      "scored_1h":val3(first_row(rows,"Scored in 1H")),
      "scored_2h":val3(first_row(rows,"Scored in 2H")),
      "failed_score_1h":val3(first_row(rows,"Failed To Score 1H")),
      "failed_score_2h":val3(first_row(rows,"Failed To Score 2H")),
      "scored_both_halves":val3(first_row(rows,"Scored in Both Halves")),
      "conceded_avg_1h":val3(first_row(rows,"Conceded Average 1H")),
      "conceded_avg_2h":val3(first_row(rows,"Conceded Average 2H")),
      "clean_sheet_1h":val3(first_row(rows,"Clean Sheets 1H")),
      "clean_sheet_2h":val3(first_row(rows,"Clean Sheets 2H")),
    }
    timing=parse_timing(md)
    present=sum(1 for x in p.values() if any(v is not None for v in x.values()))
    return {
      "available":present>=8,
      "url":url,
      "snapshot_date":"2026-09-25",
      "historical_point_in_time":False,
      "core_stats":p,
      "timing":timing,
      "parsed_numeric_rows":rows,
      "core_fields_present":present,
      "markdown_chars":len(md or ""),
    }

def main():
    src=json.loads(Path("_timing_source.json").read_text(encoding="utf-8"))
    mappings=src.get("team_mappings") or {}
    # Use the already-discovered 159 team mappings; no league/search recollection.
    url_to_teams=defaultdict(list)
    for team,mp in mappings.items():
        u=(mp or {}).get("url")
        if not u:continue
        p=urlparse(u)
        path=re.sub(r"^/cn","",p.path)
        eu="https://footystats.org"+path
        url_to_teams[eu].append(team)

    initial=credit_balance()
    ordered=list(sorted(url_to_teams))
    profiles_by_url={}
    errors={}
    # One fresh scrape per unique profile URL. Keep a hard safety floor.
    for idx,u in enumerate(ordered,1):
        rem=credit_balance()
        if rem is not None and rem<=20:
            errors[u]="credit_safety_floor";break
        data,cost,err=scrape(u)
        if err:
            errors[u]=err
            profiles_by_url[u]={"available":False,"url":u,"reason":err,"cost":cost}
        else:
            p=parse_profile(data.get("markdown") or "",u);p["cost"]=cost
            profiles_by_url[u]=p
        print(f"[{idx}/{len(ordered)}] {u} ok={profiles_by_url.get(u,{}).get('available')} rem={credit_balance()}")

    profiles={}
    for team,mp in mappings.items():
        u=(mp or {}).get("url")
        if not u:continue
        p=urlparse(u);eu="https://footystats.org"+re.sub(r"^/cn","",p.path)
        profiles[team]=profiles_by_url.get(eu,{"available":False,"url":eu,"reason":"not_scraped"})

    final=credit_balance()
    out={
      "summary":{
        "mapped_teams":len(mappings),
        "unique_profile_urls":len(url_to_teams),
        "profiles_scraped":len(profiles_by_url),
        "profiles_available":sum(1 for x in profiles.values() if x.get("available")),
        "unique_profiles_available":sum(1 for x in profiles_by_url.values() if x.get("available")),
        "initial_backup_credits":initial,"final_backup_credits":final,
        "credits_consumed":initial-final if isinstance(initial,(int,float)) and isinstance(final,(int,float)) else None,
        "source":"FootyStats full team profile",
        "snapshot_date":"2026-09-25",
        "historical_point_in_time":False,
        "warning":"Current-season snapshot captured after Sep1-20 target matches; retrospective feature-value research only."
      },
      "team_mappings":mappings,
      "profile_url_owners":dict(url_to_teams),
      "profiles":profiles,
      "profiles_by_url":profiles_by_url,
      "errors":errors,
    }
    Path("_footystats_full_profile_sep1_20.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
