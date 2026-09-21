"""Forward validation: discover on August, validate on September holdout."""
import argparse, json
from pathlib import Path
from research.calibration.window_runner import run_window
from research.result_joiner import join_results
from research.calibration.core import _row, _metric, _threshold_scan, _candidate, RISK_THRESHOLDS, MARGIN_THRESHOLDS, EDGE_THRESHOLDS


def _apply(rows,key,op,thr):
    if thr is None: return []
    return [r for r in rows if r.get(key) is not None and ((r[key] <= thr) if op=="<=" else (r[key] >= thr))]


def _select(train,key,thresholds,mode):
    scan=_threshold_scan(train,key,thresholds,mode)
    return _candidate(scan,_metric(train).get("accuracy"))


def _validate(train,holdout,key,thresholds,mode):
    cand=_select(train,key,thresholds,mode)
    base=_metric(holdout)
    if not cand:
        return {"candidate":None,"holdout":base,"validated":False}
    chosen=_apply(holdout,key,cand["operator"],cand["threshold"])
    metric=_metric(chosen)
    metric["coverage"]=len(chosen)/len(holdout) if holdout else 0.0
    delta=(metric["accuracy"]-base["accuracy"]) if metric["accuracy"] is not None and base["accuracy"] is not None else None
    return {"candidate":cand,"holdout_baseline":base,"holdout_filtered":metric,"delta":delta,"validated": bool(delta is not None and delta > 0 and metric["sample_count"]>=20)}


def run():
    full=run_window("2026-08-01","2026-09-20")
    # Reconstruct joined rows from report internals is intentionally avoided;
    # collect once from preserved cache through the same window runner inputs.
    from collector.service import collect_date
    from research.result_label.collector import collect_result_labels
    from research.score_inference import attach_research_score_predictions
    from research.htft_inference import attach_research_htft_predictions
    records=[]
    for day in [f"2026-08-{d:02d}" for d in range(1,32)] + [f"2026-09-{d:02d}" for d in range(1,21)]:
        data=collect_date(day)
        for m in data.get("matches",[]):
            x=dict(m); x["date"]=day; records.append(x)
    labels=collect_result_labels(records)
    enriched=attach_research_score_predictions(records)
    enriched=attach_research_htft_predictions(enriched)
    joined=join_results(enriched,labels)
    rows=[r for item in joined if item.get("label_status")=="MATCHED" for r in [_row(item)] if r]
    train=[r for r in rows if r["date"]<"2026-09-01"]
    hold=[r for r in rows if r["date"]>="2026-09-01"]
    out={
      "system":"HH520 Stable V3 Forward Validation",
      "train_window":"2026-08-01..2026-08-31",
      "holdout_window":"2026-09-01..2026-09-20",
      "train":_metric(train),"holdout":_metric(hold),
      "risk_score":_validate(train,hold,"risk_score",RISK_THRESHOLDS,"max"),
      "probability_margin":_validate(train,hold,"margin",MARGIN_THRESHOLDS,"min"),
      "value_edge":_validate(train,hold,"edge",EDGE_THRESHOLDS,"min"),
      "match_type":{},
      "stable_access":"READ_ONLY","promotion_policy":"MANUAL_REVIEW_REQUIRED"
    }
    for mt in sorted(set(r["match_type"] for r in rows)):
        tr=[r for r in train if r["match_type"]==mt]; ho=[r for r in hold if r["match_type"]==mt]
        out["match_type"][mt]={
          "train":_metric(tr),"holdout":_metric(ho),
          "risk_score":_validate(tr,ho,"risk_score",RISK_THRESHOLDS,"max"),
          "probability_margin":_validate(tr,ho,"margin",MARGIN_THRESHOLDS,"min"),
          "value_edge":_validate(tr,ho,"edge",EDGE_THRESHOLDS,"min"),
        }
    return out


def render(r):
    def pct(x): return "-" if x is None else f"{x*100:.1f}%"
    lines=["# HH520 Stable V3 Forward Validation","",
      f"- Train: {r['train_window']} | n={r['train']['sample_count']} | acc={pct(r['train']['accuracy'])}",
      f"- Holdout: {r['holdout_window']} | n={r['holdout']['sample_count']} | acc={pct(r['holdout']['accuracy'])}","",
      "## Global Rules",""]
    for name in ("risk_score","probability_margin","value_edge"):
        x=r[name]; c=x["candidate"]
        if not c: lines.append(f"- {name}: no candidate"); continue
        hf=x["holdout_filtered"]
        lines.append(f"- {name}: train {c['operator']} {c['threshold']} → holdout n={hf['sample_count']}, acc={pct(hf['accuracy'])}, delta={pct(x['delta'])}, validated={x['validated']}")
    lines += ["","## Match Types",""]
    for mt,x in r["match_type"].items():
        lines.append(f"### {mt} — holdout n={x['holdout']['sample_count']}, baseline={pct(x['holdout']['accuracy'])}")
        for name in ("risk_score","probability_margin","value_edge"):
            y=x[name]; c=y["candidate"]
            if c:
                hf=y["holdout_filtered"]; lines.append(f"- {name}: {c['operator']} {c['threshold']} → n={hf['sample_count']}, acc={pct(hf['accuracy'])}, delta={pct(y['delta'])}, validated={y['validated']}")
        lines.append("")
    lines += ["## Decision","","Only rules with positive holdout delta and sufficient holdout sample are eligible for Stable V3.1 review. No automatic promotion."]
    return "\n".join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--md",type=Path,required=True); a=p.parse_args(argv)
    r=run(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8"); a.md.write_text(render(r),encoding="utf-8")
if __name__=="__main__": main()
