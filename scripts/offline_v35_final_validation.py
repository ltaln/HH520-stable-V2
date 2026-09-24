import json, math, subprocess
from pathlib import Path

ARCHIVES={
 "dev1":"archive/hh520-research-20260501-0630-v35d.json",
 "dev2":"archive/hh520-research-20260701-0831-v35e.json",
 "stress":"archive/hh520-research-20260901-0920-v35d.json",
}

def load_from_branch(path):
    raw=subprocess.check_output(["git","show",f"origin/research-results:{path}"],text=True)
    return json.loads(raw)

def pois(lam,n=8):
    out=[math.exp(-lam)]
    for k in range(1,n+1): out.append(out[-1]*lam/k)
    return out

GRID=[]
for ih in range(44):
    lh=.2+.1*ih; hp=pois(lh)
    for ia in range(44):
        la=.2+.1*ia; ap=pois(la)
        w={"home":0.0,"draw":0.0,"away":0.0}; best=(-1,None)
        for h,ph in enumerate(hp):
            for a,pa in enumerate(ap):
                p=ph*pa
                o="home" if h>a else "away" if h<a else "draw"
                w[o]+=p
                if p>best[0]: best=(p,o)
        s=sum(w.values()) or 1.0
        GRID.append((w["home"]/s,w["draw"]/s,w["away"]/s,best[1]))

def score_direction(probs):
    ph,pd,pa=probs["home"],probs["draw"],probs["away"]
    best=min(GRID,key=lambda g:(g[0]-ph)**2+(g[1]-pd)**2+(g[2]-pa)**2)
    return best[3]

def metric(rows, pred_fn):
    n=h=0
    for r in rows:
        pred=pred_fn(r)
        if pred is None: continue
        n+=1; h+=int(pred.upper()==r["actual_outcome"])
    return {"n":n,"hits":h,"accuracy":h/n if n else None}

data={k:load_from_branch(v) for k,v in ARCHIVES.items()}
rows={k:(v.get("v35_ft_dataset") or {}).get("rows") or [] for k,v in data.items()}

# FT threshold table
thresholds=[]
for t in [x/100 for x in range(50,71)]:
    rec={"threshold":t}
    for split in rows:
        rec[split]=metric(rows[split],lambda r,t=t: (
            r["current_direction"] if r["current_direction"] in ("home","away")
            and float((r["probabilities"] or {}).get(r["current_direction"],0))>=t else None))
    thresholds.append(rec)

# Draw grid selection uses dev only; stress never participates in selection.
draw_candidates=[]
for pd_min in [x/100 for x in range(20,36,2)]:
  for side_gap in [x/100 for x in range(4,17,2)]:
    for top_gap in [x/100 for x in range(4,17,2)]:
      def rule(r,pd_min=pd_min,side_gap=side_gap,top_gap=top_gap):
        p=r["probabilities"]; ph,pd,pa=float(p["home"]),float(p["draw"]),float(p["away"])
        if pd>=pd_min and abs(ph-pa)<=side_gap and max(ph,pa)-pd<=top_gap: return "draw"
      a=metric(rows["dev1"],rule); b=metric(rows["dev2"],rule); s=metric(rows["stress"],rule)
      if a["n"]>=15 and b["n"]>=15 and a["n"]+b["n"]>=40:
        devn=a["n"]+b["n"]; devh=a["hits"]+b["hits"]; devacc=devh/devn
        stability=min(a["accuracy"],b["accuracy"])
        draw_candidates.append({"pd_min":pd_min,"side_gap":side_gap,"top_gap":top_gap,
          "dev1":a,"dev2":b,"dev":{"n":devn,"hits":devh,"accuracy":devacc},
          "stress":s,"stability":stability})
draw_candidates.sort(key=lambda x:(x["stability"],x["dev"]["accuracy"],x["dev"]["n"]),reverse=True)
best_draw=draw_candidates[0] if draw_candidates else None

# Cross-layer gate: FT >=55% and independent score top1 directional agreement.
def ft55(r):
    d=r["current_direction"]; p=r["probabilities"]
    if d in ("home","away") and float(p[d])>=.55: return d
    return None

cross={}
for split,rr in rows.items():
    buckets={"agree":[],"conflict":[]}
    for r in rr:
        ft=ft55(r)
        if not ft: continue
        sd=score_direction(r["probabilities"])
        buckets["agree" if sd==ft else "conflict"].append((ft,r["actual_outcome"]))
    cross[split]={}
    for k,vals in buckets.items():
        n=len(vals); h=sum(1 for p,a in vals if p.upper()==a)
        cross[split][k]={"n":n,"hits":h,"accuracy":h/n if n else None}

# Existing HTFT and score metrics from archive only; no new timing collection.
existing={}
for split,d in data.items():
    bt=d.get("backtest") or {}
    stable=d.get("stable_v34_backtest") or {}
    existing[split]={
      "htft":((bt.get("metrics") or {}).get("half_time")),
      "score":((bt.get("metrics") or {}).get("score")),
      "stable_score_top2":((stable.get("summary") or {}).get("score_top2")),
      "stable_wdl":((stable.get("summary") or {}).get("wdl")),
    }

out={
 "mode":"OFFLINE_EXISTING_ARCHIVES_ONLY",
 "recollection":False,
 "goal_timing_collected":False,
 "sample_counts":{k:len(v) for k,v in rows.items()},
 "ft_thresholds":thresholds,
 "best_draw_rule":best_draw,
 "top_draw_rules":draw_candidates[:10],
 "cross_gate":cross,
 "existing_metrics":existing,
}
Path("_offline_v35_final.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
