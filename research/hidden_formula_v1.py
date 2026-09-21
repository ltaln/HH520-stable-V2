"""Stage-1 reverse engineering from 10027s pre-match fields + isolated outcomes."""
import argparse,json,datetime as dt
from collections import defaultdict
from pathlib import Path
from collector.service import collect_date
from research.result_label.collector import collect_result_labels
from research.result_joiner import join_results

def out(label):
    x=str(label.get("actual_outcome") or label.get("result") or "").upper()
    return x if x in {"HOME","DRAW","AWAY"} else None

def bucket(x,cuts,names):
    for i,c in enumerate(cuts):
        if x < c:return names[i]
    return names[-1]

def odds(m):
    mk=m.get("market") or {}
    try:h,d,a=float(mk["home_odds"]),float(mk["draw_odds"]),float(mk["away_odds"])
    except:return None
    vals={"HOME":h,"DRAW":d,"AWAY":a}; s=sorted(vals.items(),key=lambda z:z[1]); fav,fo=s[0]
    return {"fav":fav,"fav_bucket":bucket(fo,[1.4,1.6,1.8,2.0,2.3],["<1.40","1.40-1.59","1.60-1.79","1.80-1.99","2.00-2.29",">=2.30"]),
            "draw_bucket":bucket(d,[3.0,3.3,3.6,4.0,4.5],["<3.00","3.00-3.29","3.30-3.59","3.60-3.99","4.00-4.49",">=4.50"]),
            "gap_bucket":bucket(s[1][1]-fo,[.25,.5,.8,1.2,2],["<0.25","0.25-0.49","0.50-0.79","0.80-1.19","1.20-1.99",">=2.00"])}

def poss(m):
    p=m.get("possession") or {}
    try:h,a=float(p["home"]),float(p["away"])
    except:return None
    diff=h-a
    return {"diff_bucket":bucket(diff,[-10,-5,0,5,10,15,20],["<-10","-10--5","-5-0","0-5","5-10","10-15","15-20",">=20"]),
            "ratio_bucket":bucket(h/a,[.85,.95,1.05,1.15,1.30],["<0.85","0.85-0.94","0.95-1.04","1.05-1.14","1.15-1.29",">=1.30"]) if a else None}

def agg(rows,keyfn,min_n=8):
    b=defaultdict(lambda:{"n":0,"HOME":0,"DRAW":0,"AWAY":0,"HTH":0,"HTD":0,"HTA":0})
    for r in rows:
        k=keyfn(r)
        if k is None:continue
        z=b[str(k)];z["n"]+=1;z[r["out"]]+=1
        try:x,y=map(int,(r["half"] or "").split("-"));z["HTH" if x>y else "HTA" if x<y else "HTD"]+=1
        except:pass
    o={}
    for k,z in b.items():
        n=z["n"]
        if n<min_n:continue
        o[k]={"n":n,"home_rate":z["HOME"]/n,"draw_rate":z["DRAW"]/n,"away_rate":z["AWAY"]/n,
              "ht_home":z["HTH"]/n,"ht_draw":z["HTD"]/n,"ht_away":z["HTA"]/n}
    return o

def analyze(rows):
    return {
      "n":len(rows),
      "favorite_odds":agg(rows,lambda r:r["o"]["fav_bucket"] if r["o"] else None),
      "draw_odds":agg(rows,lambda r:r["o"]["draw_bucket"] if r["o"] else None),
      "favorite_gap":agg(rows,lambda r:r["o"]["gap_bucket"] if r["o"] else None),
      "possession_diff":agg(rows,lambda r:r["p"]["diff_bucket"] if r["p"] else None),
      "possession_ratio":agg(rows,lambda r:r["p"]["ratio_bucket"] if r["p"] else None),
      "handicap_side":agg(rows,lambda r:(r["h"] or {}).get("side")),
      "handicap_line":agg(rows,lambda r:(r["h"] or {}).get("primary_line")),
      "handicap_water":agg(rows,lambda r:(f'{r["h"].get("primary_water")}->{r["h"].get("secondary_water")}' if r["h"] else None)),
      "fav_handicap_align":agg(rows,lambda r:("aligned" if r["o"] and r["h"] and ((r["o"]["fav"]=="HOME" and r["h"].get("side")=="home") or (r["o"]["fav"]=="AWAY" and r["h"].get("side")=="away")) else "not_aligned") if r["o"] and r["h"] else None),
    }

def run():
    rec=[];d=dt.date(2026,8,1);end=dt.date(2026,9,20)
    while d<=end:
        day=d.isoformat();data=collect_date(day)
        for m in data.get("matches",[]):x=dict(m);x["date"]=day;rec.append(x)
        d+=dt.timedelta(days=1)
    joined=join_results(rec,collect_result_labels(rec));rows=[]
    for m in joined:
        if m.get("label_status")!="MATCHED":continue
        y=out(m.get("result_label") or {})
        if not y:continue
        rows.append({"date":m["date"],"out":y,"half":m.get("half_score"),"o":odds(m),"p":poss(m),"h":((m.get("research_factors") or {}).get("handicap_features"))})
    tr=[r for r in rows if r["date"]<"2026-09-01"];ho=[r for r in rows if r["date"]>="2026-09-01"]
    return {"system":"HH520 Hidden Formula Reverse V1 Stage1","all":analyze(rows),"train":analyze(tr),"holdout":analyze(ho),"stable_access":"READ_ONLY"}

def render(r):
    lines=["# HH520 Hidden Formula Reverse V1 — Stage 1","",f"- All n={r['all']['n']}","- Train=2026-08-01..08-31","- Holdout=2026-09-01..09-20",""]
    for sec in ("favorite_odds","draw_odds","favorite_gap","possession_diff","possession_ratio","handicap_side","handicap_line","handicap_water","fav_handicap_align"):
        lines += [f"## {sec}",""]
        for k,v in r["all"][sec].items():
            lines.append(f"- {k}: n={v['n']}, H/D/A={v['home_rate']:.1%}/{v['draw_rate']:.1%}/{v['away_rate']:.1%}, HT={v['ht_home']:.1%}/{v['ht_draw']:.1%}/{v['ht_away']:.1%}")
        lines.append("")
    lines += ["## Note","","进攻/防守/交锋/状态在当前10027s历史缓存中没有独立字段，本阶段不虚构。"]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser();p.add_argument("--json",type=Path,required=True);p.add_argument("--md",type=Path,required=True);a=p.parse_args()
    r=run();a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8");a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__":main()
