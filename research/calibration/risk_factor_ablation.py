"""Research-only Risk Factor Attribution / Ablation for production Risk Engine V3.0."""
import argparse, json
from pathlib import Path
from collector.service import collect_date
from research.result_label.collector import collect_result_labels
from research.result_joiner import join_results
from engine.probability_layer import probability_layer
from engine.value_layer import value_layer
from engine.data_quality import data_quality_gate
from engine.match_classifier import classify_match

FACTORS = (
    "top_probability",
    "probability_margin",
    "match_type",
    "value_conflict",
    "odds_zone",
    "page_risk",
    "pattern",
)

def _actual(label):
    raw=str(label.get("actual_outcome") or label.get("result") or "").upper()
    return {"HOME":"home","DRAW":"draw","AWAY":"away"}.get(raw)

def _selected_odds(match, direction):
    m=match.get("market") or {}
    return m.get({"home":"home_odds","draw":"draw_odds","away":"away_odds"}.get(direction,""))

def _components(match,p,v,q,c):
    out={k:0 for k in FACTORS}
    reasons={}
    if not q["valid"]:
        return out, {"data_quality":100}
    top=c["top_probability"]; margin=c["probability_margin"]
    if top < .40: out["top_probability"]=40
    elif top < .50: out["top_probability"]=18
    if margin < .05: out["probability_margin"]=30
    elif margin < .10: out["probability_margin"]=16
    if c["type"]=="balanced": out["match_type"]=15
    elif c["type"]=="cup": out["match_type"]=8
    edge=v.get("directional_edge")
    if edge is not None:
        if edge < -.03: out["value_conflict"]=25
        elif edge < 0: out["value_conflict"]=10
    try: odds=float(_selected_odds(match,p.get("direction")))
    except (TypeError,ValueError): odds=None
    if odds is not None and 1.80 <= odds < 3.00: out["odds_zone"]=10
    rf=match.get("research_factors") or {}
    page=str(rf.get("risk","")).strip()
    if page in {"高","很高"}: out["page_risk"]=25
    elif page in {"中高","中"}: out["page_risk"]=12
    pattern=str(rf.get("pattern","")).strip()
    if "极端" in pattern: out["pattern"]=25
    elif "边缘" in pattern: out["pattern"]=15
    return out, reasons

def _metric(rows,key):
    chosen=[r for r in rows if r[key] <= 20]
    hits=sum(int(r["hit"]) for r in chosen)
    return {
      "n":len(chosen),
      "accuracy": hits/len(chosen) if chosen else None,
      "coverage":len(chosen)/len(rows) if rows else 0.0,
      "filtered_wrong":sum(1 for r in rows if r[key]>20 and not r["hit"]),
      "filtered_correct":sum(1 for r in rows if r[key]>20 and r["hit"]),
    }

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
        comps,_=_components(match,p,v,q,c)
        if not q["valid"]: continue
        full=min(100,sum(comps.values()))
        row={"hit":p["direction"]==actual,"full":full,"match_type":c["type"],"components":comps}
        for f in FACTORS:
            row["without_"+f]=min(100,sum(vv for k,vv in comps.items() if k!=f))
            row["only_"+f]=min(100,comps[f])
        rows.append(row)

    baseline=_metric(rows,"full")
    ablation={}
    single={}
    for f in FACTORS:
        m=_metric(rows,"without_"+f)
        m["accuracy_delta_vs_full"]=(m["accuracy"]-baseline["accuracy"]) if m["accuracy"] is not None and baseline["accuracy"] is not None else None
        m["coverage_delta_vs_full"]=m["coverage"]-baseline["coverage"]
        ablation[f]=m
        s=_metric(rows,"only_"+f)
        single[f]=s

    contribution_rank=sorted(
      [{"factor":f,**ablation[f]} for f in FACTORS],
      key=lambda x: (x["accuracy_delta_vs_full"] if x["accuracy_delta_vs_full"] is not None else 999)
    )
    return {
      "system":"HH520 Risk Factor Attribution / Ablation",
      "window":"2026-08-01..2026-09-20",
      "sample_count":len(rows),
      "baseline_risk_v3":baseline,
      "leave_one_out":ablation,
      "single_factor":single,
      "rank_by_damage_when_removed":contribution_rank,
      "stable_access":"READ_ONLY",
      "note":"Negative accuracy_delta_vs_full means removing the factor hurts low-risk accuracy; such factors contribute positively."
    }

def render(r):
    def pct(x): return "-" if x is None else f"{x*100:.1f}%"
    b=r["baseline_risk_v3"]
    lines=["# HH520 Risk Factor Attribution / Ablation","",
      f"- Window: {r['window']}",
      f"- Samples: {r['sample_count']}",
      f"- Baseline Risk<=20: n={b['n']}, acc={pct(b['accuracy'])}, coverage={pct(b['coverage'])}","",
      "## Leave-One-Out",""]
    for f,x in r["leave_one_out"].items():
        lines.append(f"- {f}: n={x['n']}, acc={pct(x['accuracy'])}, delta={pct(x['accuracy_delta_vs_full'])}, coverage={pct(x['coverage'])}, filtered wrong/correct={x['filtered_wrong']}/{x['filtered_correct']}")
    lines += ["","## Single-Factor Risk<=20",""]
    for f,x in r["single_factor"].items():
        lines.append(f"- {f}: n={x['n']}, acc={pct(x['accuracy'])}, coverage={pct(x['coverage'])}")
    lines += ["","## Interpretation",
      "- A factor is useful when removing it reduces accuracy and/or worsens the wrong-vs-correct filtering tradeoff.",
      "- A factor is suspicious/noisy when removing it improves accuracy with acceptable coverage.",
      "- No production rule is changed automatically."]
    return "\n".join(lines)

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--md",type=Path,required=True); a=p.parse_args(argv)
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8"); a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__": main()
