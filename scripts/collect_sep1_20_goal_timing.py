import json, re, sys, time, math
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import requests

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from collector.hh520_10027_parser import parse_10027s_markdown

S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (HH520 research; contact none)","Accept":"application/json"})
TZ=ZoneInfo("Asia/Shanghai")
BINS=((0,15),(16,30),(31,45),(46,60),(61,75),(76,130))

def parse_score(v):
 m=re.search(r"(\d+)\s*[-:：]\s*(\d+)",str(v or ""))
 return (int(m.group(1)),int(m.group(2))) if m else None

def load_hh():
 out=[]
 for p in sorted(Path("cache").glob("10027s_2026-09-*.json")):
  ds=p.stem.replace("10027s_","")
  if not ("2026-09-01"<=ds<="2026-09-20"):continue
  payload=json.loads(p.read_text(encoding="utf-8"))
  md=((payload.get("raw") or {}).get("data") or {}).get("markdown")
  for m in parse_10027s_markdown(md or ""):
   out.append({"date":ds,"match_id":m.get("match_id"),"home_team":m.get("home_team"),"away_team":m.get("away_team"),
               "league":m.get("league"),"kickoff":m.get("kickoff"),"half":m.get("half_score"),"full":m.get("result")})
 return out

def get_json(url,tries=3):
 last=None
 for i in range(tries):
  try:
   r=S.get(url,timeout=25)
   if r.status_code==429:
    time.sleep(2+i*2);continue
   r.raise_for_status();return r.json()
  except Exception as e:
   last=e;time.sleep(.6+i*.8)
 raise last

def schedule_for(ds):
 data=get_json(f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{ds}")
 return data.get("events") or []

def sh_time(ts):
 return datetime.fromtimestamp(int(ts),tz=timezone.utc).astimezone(TZ)

def score_of(ev,key):
 hs=ev.get("homeScore") or {};as_=ev.get("awayScore") or {}
 hv=hs.get(key);av=as_.get(key)
 try:return int(hv),int(av)
 except:return None

def minutes_diff(a,b):
 return abs((a.hour*60+a.minute)-(b.hour*60+b.minute))

def match_event(m, events_by_date):
 fs=parse_score(m["full"]);hs=parse_score(m["half"])
 if not fs:return None,{"reason":"missing_full"}
 ko=None
 mm=re.search(r"(\d{1,2}):(\d{2})",str(m.get("kickoff") or ""))
 if mm:ko=(int(mm.group(1)),int(mm.group(2)))
 candidates=[]
 for offset in (-1,0,1):
  ds=(date.fromisoformat(m["date"])+timedelta(days=offset)).isoformat()
  for ev in events_by_date.get(ds,[]):
   if score_of(ev,"current")!=fs:continue
   eh=score_of(ev,"period1")
   half_ok=(hs is None or eh==hs)
   st=sh_time(ev.get("startTimestamp",0))
   dt=999
   if ko:dt=minutes_diff(st,datetime(2000,1,1,ko[0],ko[1],tzinfo=TZ))
   score=0
   score+=100 if half_ok else 0
   score+=max(0,60-dt) if dt<=60 else 0
   if st.date().isoformat()==m["date"]:score+=30
   candidates.append((score,dt,half_ok,ev))
 if not candidates:return None,{"reason":"no_candidate"}
 candidates.sort(key=lambda x:(x[0],-x[1]),reverse=True)
 best=candidates[0]
 # strict: prefer exact HT + kickoff within 45m; otherwise require unique exact HT+FT+date
 strict=[x for x in candidates if x[2] and x[1]<=45]
 if len(strict)==1:
  return strict[0][3],{"method":"score_ht_kickoff","dt":strict[0][1],"candidate_count":len(candidates)}
 same=[x for x in candidates if x[2] and sh_time(x[3].get("startTimestamp",0)).date().isoformat()==m["date"]]
 if len(same)==1:
  return same[0][3],{"method":"score_ht_date_unique","dt":same[0][1],"candidate_count":len(candidates)}
 # exact kickoff alone if unique
 kt=[x for x in candidates if x[1]<=10 and sh_time(x[3].get("startTimestamp",0)).date().isoformat()==m["date"]]
 if len(kt)==1:
  return kt[0][3],{"method":"score_kickoff_unique","dt":kt[0][1],"candidate_count":len(candidates)}
 return None,{"reason":"ambiguous","candidate_count":len(candidates),"top":[{"id":x[3].get("id"),"home":(x[3].get("homeTeam") or {}).get("name"),"away":(x[3].get("awayTeam") or {}).get("name"),"dt":x[1],"half_ok":x[2]} for x in candidates[:5]]}

def incident_goals(event_id):
 data=get_json(f"https://www.sofascore.com/api/v1/event/{event_id}/incidents")
 goals=[]
 for inc in data.get("incidents") or []:
  if inc.get("incidentType")!="goal":continue
  if inc.get("incidentClass") in {"missed","varDecision"}:continue
  t=inc.get("time")
  if t is None:continue
  minute=int(t);added=int(inc.get("addedTime") or 0)
  side="HOME" if inc.get("isHome") else "AWAY"
  goals.append({"minute":minute,"added":added,"effective_minute":minute+min(added,9),"side":side,
                "incidentClass":inc.get("incidentClass"),"player":((inc.get("player") or {}).get("name"))})
 goals.sort(key=lambda x:(x["minute"],x["added"]))
 return goals

def bins(goals):
 out={"HOME":[0]*6,"AWAY":[0]*6,"ALL":[0]*6}
 for g in goals:
  minute=g["minute"]
  idx=5
  for i,(lo,hi) in enumerate(BINS):
   if lo<=minute<=hi:idx=i;break
  out[g["side"]][idx]+=1;out["ALL"][idx]+=1
 return out

def main():
 hh=load_hh()
 dates=set()
 for m in hh:
  d=date.fromisoformat(m["date"])
  for o in (-1,0,1):dates.add((d+timedelta(days=o)).isoformat())
 events={}
 for ds in sorted(dates):
  try:events[ds]=schedule_for(ds)
  except Exception as e:events[ds]=[]
  time.sleep(.08)
 results=[];matched=0;inc_ok=0
 for i,m in enumerate(hh):
  ev,diag=match_event(m,events)
  row={**m,"match":diag,"source":"sofascore"}
  if ev:
   matched+=1
   row["event_id"]=ev.get("id")
   row["source_home"]=(ev.get("homeTeam") or {}).get("name")
   row["source_away"]=(ev.get("awayTeam") or {}).get("name")
   row["source_tournament"]=((ev.get("tournament") or {}).get("name"))
   try:
    gs=incident_goals(ev.get("id"));inc_ok+=1
    row["goals"]=gs;row["bins"]=bins(gs);row["goal_count"]=len(gs)
   except Exception as e:
    row["goals_error"]=type(e).__name__
  results.append(row)
  time.sleep(.05)
 summary={"requested_matches":len(hh),"matched_events":matched,"incidents_fetched":inc_ok,
          "coverage":matched/len(hh) if hh else 0,
          "goal_timing_available":sum(1 for r in results if "bins" in r),
          "source":"SofaScore public scheduled-events + incidents API",
          "leakage_note":"actual goal minutes are labels/history only; do not feed target-match minutes into its own prediction"}
 out={"summary":summary,"matches":results}
 Path("_sep1_20_goal_timing.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":main()
