"""Research-only V3 vs V3.1 Risk Engine comparison."""
import argparse, json
from pathlib import Path
from collector.service import collect_date
from research.result_label.collector import collect_result_labels
from research.result_joiner import join_results
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk, assess_risk_v3


def _metric(rows):
    if not rows:
        return {"n":0,"hits":0,"accuracy":None}
    hits=sum(int(r["hit"]) for r in rows)
    return {"n":len(rows),"hits":hits,"accuracy":hits/len(rows)}


def _actual(label):
    raw=str(label.get("actual_outcome") or label.get("result") or "").upper()
    return {"HOME":"home","DRAW":"draw","AWAY":"away"}.get(raw)


def run():
    records=[]
    for day in [f"2026-08-{d:02d}" for d in range(1,32)] + [f"2026-09-{d:02d}" for d in range(1,21)]:
        data=collect_date(day)
        for m in data.get("matches",[]):
            x=dict(m); x["date"]=day; records.append(x)
    labels=collect_result_labels(records)
    joined=join_results(records,labels)
    rows=[]
    for item in joined:
        if item.get("label_status")!="MATCHED":
            continue
        actual=_actual(item.get("result_label") or {})
        if not actual:
            continue
        match=dict(item)
        match.pop("result",None); match.pop("result_label",None); match.pop("label_status",None)
        p=probability_layer(match)
        if not p.get("valid") or not p.get("direction"):
            continue
        v=value_layer(match,p); q=data_quality_gate(match,p); c=classify_match(match,p)
        r3=assess_risk_v3(match,p,v,q,c); r31=assess_risk(match,p,v,q,c)
        rows.append({
            "date":item["date"],"match_id":item["match_id"],"hit":p["direction"]==actual,
            "match_type":c["type"],"risk_v3":r3["score"],"risk_v31":r31["score"]
        })

    def summary(key):
        low=[r for r in rows if r[key] <= 20]
        out={"all":_metric(rows),"risk_le_20":_metric(low),"coverage":len(low)/len(rows) if rows else 0.0}
        mt={}
        for t in sorted(set(r["match_type"] for r in rows)):
            sub=[r for r in rows if r["match_type"]==t]
            lowt=[r for r in sub if r[key] <=20]
            mt[t]={"all":_metric(sub),"risk_le_20":_metric(lowt),"coverage":len(lowt)/len(sub) if sub else 0.0}
        out["match_type"]=mt
        filtered=[r for r in rows if r[key] >20]
        out["filtered"]={"n":len(filtered),"wrong":sum(1 for r in filtered if not r["hit"]),"correct":sum(1 for r in filtered if r["hit"])}
        return out

    v3=summary("risk_v3"); v31=summary("risk_v31")
    return {
      "system":"HH520 Risk Engine V3 vs V3.1",
      "window":"2026-08-01..2026-09-20",
      "v3":v3,"v31":v31,
      "delta_low_risk_accuracy": (v31["risk_le_20"]["accuracy"]-v3["risk_le_20"]["accuracy"]) if v31["risk_le_20"]["accuracy"] is not None and v3["risk_le_20"]["accuracy"] is not None else None,
      "delta_low_risk_coverage":v31["coverage"]-v3["coverage"],
      "stable_access":"READ_ONLY"
    }


def render(r):
    def pct(x): return "-" if x is None else f"{x*100:.1f}%"
    lines=["# HH520 Risk Engine V3 vs V3.1","",
      f"- Window: {r['window']}",
      f"- V3 Risk<=20: n={r['v3']['risk_le_20']['n']}, acc={pct(r['v3']['risk_le_20']['accuracy'])}, coverage={pct(r['v3']['coverage'])}",
      f"- V3.1 Risk<=20: n={r['v31']['risk_le_20']['n']}, acc={pct(r['v31']['risk_le_20']['accuracy'])}, coverage={pct(r['v31']['coverage'])}",
      f"- Accuracy delta: {pct(r['delta_low_risk_accuracy'])}",
      f"- Coverage delta: {pct(r['delta_low_risk_coverage'])}","",
      "## Match Types",""]
    for t,x in r["v31"]["match_type"].items():
        old=r["v3"]["match_type"][t]
        lines.append(f"- {t}: V3 {pct(old['risk_le_20']['accuracy'])} (n={old['risk_le_20']['n']}) → V3.1 {pct(x['risk_le_20']['accuracy'])} (n={x['risk_le_20']['n']})")
    lines += ["","## Filtered Matches",
      f"- V3: filtered={r['v3']['filtered']['n']}, wrong={r['v3']['filtered']['wrong']}, correct={r['v3']['filtered']['correct']}",
      f"- V3.1: filtered={r['v31']['filtered']['n']}, wrong={r['v31']['filtered']['wrong']}, correct={r['v31']['filtered']['correct']}",
      "","No automatic promotion. Research result only."]
    return "\n".join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--md",type=Path,required=True); a=p.parse_args(argv)
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8"); a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__": main()
