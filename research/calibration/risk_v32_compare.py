"""Research-only V3.0 vs simplified V3.2 candidate comparison."""
import argparse, json
from pathlib import Path
from collector.service import collect_date
from research.result_label.collector import collect_result_labels
from research.result_joiner import join_results
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match
from engine.risk_engine import assess_risk_v3, assess_risk_v32


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
    joined=join_results(records,collect_result_labels(records))
    rows=[]
    for item in joined:
        if item.get("label_status")!="MATCHED": continue
        actual=_actual(item.get("result_label") or {})
        if not actual: continue
        match=dict(item); match.pop("result",None); match.pop("result_label",None); match.pop("label_status",None)
        p=probability_layer(match)
        if not p.get("valid") or not p.get("direction"): continue
        v=value_layer(match,p); q=data_quality_gate(match,p); c=classify_match(match,p)
        r3=assess_risk_v3(match,p,v,q,c)
        r32=assess_risk_v32(match,p,v,q,c)
        rows.append({
          "date":item["date"],"match_id":item["match_id"],"hit":p["direction"]==actual,
          "match_type":c["type"],"risk_v3":r3["score"],"risk_v32":r32["score"]
        })

    def summary(key):
        low=[r for r in rows if r[key] <=20]
        filtered=[r for r in rows if r[key] >20]
        return {
          "all":_metric(rows),
          "risk_le_20":_metric(low),
          "coverage":len(low)/len(rows) if rows else 0.0,
          "filtered":{"n":len(filtered),"wrong":sum(1 for r in filtered if not r["hit"]),"correct":sum(1 for r in filtered if r["hit"])},
          "match_type":{
            t:{
              "all":_metric([r for r in rows if r["match_type"]==t]),
              "risk_le_20":_metric([r for r in rows if r["match_type"]==t and r[key] <=20]),
              "coverage":(len([r for r in rows if r["match_type"]==t and r[key] <=20])/len([r for r in rows if r["match_type"]==t])) if [r for r in rows if r["match_type"]==t] else 0.0
            } for t in sorted(set(r["match_type"] for r in rows))
          }
        }

    v3=summary("risk_v3"); v32=summary("risk_v32")
    return {
      "system":"HH520 Risk Engine V3.0 vs V3.2 Candidate",
      "window":"2026-08-01..2026-09-20",
      "v3":v3,"v32":v32,
      "delta_low_risk_accuracy":(v32["risk_le_20"]["accuracy"]-v3["risk_le_20"]["accuracy"]) if v32["risk_le_20"]["accuracy"] is not None and v3["risk_le_20"]["accuracy"] is not None else None,
      "delta_low_risk_coverage":v32["coverage"]-v3["coverage"],
      "promotion_gate":{
        "min_accuracy_delta":0.01,
        "min_coverage_ratio_vs_v3":0.80,
        "candidate_pass":False
      },
      "stable_access":"READ_ONLY"
    }


def render(r):
    def pct(x): return "-" if x is None else f"{x*100:.1f}%"
    v3=r["v3"]; v32=r["v32"]
    acc_delta=r["delta_low_risk_accuracy"]
    coverage_ratio=(v32["coverage"]/v3["coverage"]) if v3["coverage"] else 0
    passed=bool(acc_delta is not None and acc_delta >= .01 and coverage_ratio >= .80)
    r["promotion_gate"]["candidate_pass"]=passed
    lines=["# HH520 Risk Engine V3.0 vs V3.2 Candidate","",
      f"- Window: {r['window']}",
      f"- V3 Risk<=20: n={v3['risk_le_20']['n']}, acc={pct(v3['risk_le_20']['accuracy'])}, coverage={pct(v3['coverage'])}",
      f"- V3.2 Risk<=20: n={v32['risk_le_20']['n']}, acc={pct(v32['risk_le_20']['accuracy'])}, coverage={pct(v32['coverage'])}",
      f"- Accuracy delta: {pct(acc_delta)}",
      f"- Coverage delta: {pct(r['delta_low_risk_coverage'])}",
      f"- Promotion gate passed: {passed}","",
      "## Match Types",""]
    for t,x in v32["match_type"].items():
        old=v3["match_type"][t]
        lines.append(f"- {t}: V3 {pct(old['risk_le_20']['accuracy'])} (n={old['risk_le_20']['n']}) -> V3.2 {pct(x['risk_le_20']['accuracy'])} (n={x['risk_le_20']['n']})")
    lines += ["","## Filtered",
      f"- V3: wrong/correct={v3['filtered']['wrong']}/{v3['filtered']['correct']}",
      f"- V3.2: wrong/correct={v32['filtered']['wrong']}/{v32['filtered']['correct']}",
      "","No automatic promotion."]
    return "\n".join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--md",type=Path,required=True); a=p.parse_args(argv)
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8"); a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__": main()
