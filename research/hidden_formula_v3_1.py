"""HH520 Hidden Formula V3.1 fixed-rule optimization.

Select one confidence gate and one score blend only from June-July-August
walk-forward out-of-fold results. Freeze them, then evaluate September.
Stable remains read-only.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

from research.hidden_formula_v3 import (
    prep, market_probs, orientation, confirmations, wdl_metrics,
    fit_residual, htft_eval, score_eval, wilson
)

DEV_FOLDS = [
    ("MAY_to_JUN","2026-05-01","2026-05-31","2026-06-01","2026-06-30"),
    ("MAYJUN_to_JUL","2026-05-01","2026-06-30","2026-07-01","2026-07-31"),
    ("MAYJUL_to_AUG","2026-05-01","2026-07-31","2026-08-01","2026-08-31"),
]
GATE_THRESHOLDS=[.55,.58,.60,.62,.64,.66,.68,.70,.73,.76]
GATE_VOTES=[2,3,4,5]
BLENDS=[0.0,.05,.10,.15,.20,.25,.30]

def split(df,ts,te,vs,ve):
    tr=df[(df.date>=ts)&(df.date<=te)].copy()
    ho=df[(df.date>=vs)&(df.date<=ve)].copy()
    return tr,ho

def gate_result(test,signs,pmax,votes):
    v,a=confirmations(test,signs)
    mask=(test.market_pmax.to_numpy()>=pmax)&(a>=votes)&(v>=votes)
    ok=test.market_pred.eq(test.ft_outcome).to_numpy()
    n=int(mask.sum()); k=int(ok[mask].sum())
    return {"n":n,"correct":k,"accuracy":(k/n if n else None),
            "coverage":(n/len(test) if len(test) else 0.0)}

def select_fixed_gate(df):
    fold_data=[]
    sign_history={}
    for name,ts,te,vs,ve in DEV_FOLDS:
        tr,ho=split(df,ts,te,vs,ve)
        signs=orientation(tr)
        sign_history[name]=signs
        fold_data.append((name,tr,ho,signs))
    candidates=[]
    for pmax in GATE_THRESHOLDS:
        for votes in GATE_VOTES:
            per=[]; total_n=total_k=0; valid=True
            for name,tr,ho,signs in fold_data:
                r=gate_result(ho,signs,pmax,votes)
                per.append({"fold":name,**r})
                total_n+=r["n"]; total_k+=r["correct"]
                if r["n"]<8: valid=False
            if not valid or total_n<40: continue
            min_acc=min(x["accuracy"] for x in per if x["accuracy"] is not None)
            overall=total_k/total_n
            candidates.append({
                "pmax":pmax,"min_votes":votes,"n":total_n,"correct":total_k,
                "accuracy":overall,"wilson_low":wilson(total_k,total_n),
                "min_fold_accuracy":min_acc,"folds":per
            })
    if not candidates:
        raise RuntimeError("no confidence gate met stability/support constraints")
    candidates.sort(key=lambda x:(x["min_fold_accuracy"],x["wilson_low"],x["accuracy"],x["n"]),reverse=True)
    return candidates[0],candidates[:20],sign_history

def select_score_blend(df):
    scores={b:{"n":0,"nll_sum":0.0,"top1_num":0.0,"top2_num":0.0,"top3_num":0.0,"folds":[]} for b in BLENDS}
    for name,ts,te,vs,ve in DEV_FOLDS:
        tr,ho=split(df,ts,te,vs,ve)
        p=market_probs(ho)
        for b in BLENDS:
            r=score_eval(tr,ho,p,b)
            n=int(r.get("n") or 0)
            scores[b]["folds"].append({"fold":name,**r})
            if n:
                scores[b]["n"]+=n
                scores[b]["nll_sum"]+=r["score_nll"]*n
                scores[b]["top1_num"]+=r["top1"]*n
                scores[b]["top2_num"]+=r["top2"]*n
                scores[b]["top3_num"]+=r["top3"]*n
    table=[]
    for b,z in scores.items():
        n=z["n"]
        table.append({
            "blend":b,"n":n,
            "score_nll":z["nll_sum"]/n if n else None,
            "top1":z["top1_num"]/n if n else None,
            "top2":z["top2_num"]/n if n else None,
            "top3":z["top3_num"]/n if n else None,
            "folds":z["folds"]
        })
    # Primary objective is proper score NLL; top2 breaks near-ties.
    table.sort(key=lambda x:(x["score_nll"],-(x["top2"] or 0)))
    return table[0],table

def factor_stability(sign_history,final_signs):
    keys=sorted(final_signs)
    out={}
    for k in keys:
        hist=[z[k] for z in sign_history.values()]
        out[k]={
            "dev_fold_signs":hist,
            "stable_across_dev_folds":len(set(hist))==1,
            "final_may_aug_sign":final_signs[k]
        }
    return out

def league_audit(df,pmax,votes,signs,start,end,min_n=8):
    z=df[(df.date>=start)&(df.date<=end)].copy()
    v,a=confirmations(z,signs)
    mask=(z.market_pmax.to_numpy()>=pmax)&(a>=votes)&(v>=votes)
    z=z.loc[mask].copy()
    rows=[]
    for league,g in z.groupby("league"):
        n=len(g)
        if n<min_n: continue
        k=int(g.market_pred.eq(g.ft_outcome).sum())
        rows.append({"league":str(league),"n":n,"accuracy":k/n,"wilson_low":wilson(k,n)})
    rows.sort(key=lambda x:(x["n"],x["accuracy"]),reverse=True)
    return rows

def run():
    df,missing=prep("2026-05-01","2026-09-20")
    if missing:
        raise RuntimeError(f"missing cache dates: {missing[:10]} total={len(missing)}")
    gate,gate_candidates,sign_history=select_fixed_gate(df)
    blend,blend_table=select_score_blend(df)

    train=df[(df.date>="2026-05-01")&(df.date<="2026-08-31")].copy()
    sep=df[(df.date>="2026-09-01")&(df.date<="2026-09-20")].copy()
    final_signs=orientation(train)

    p_sep=market_probs(sep)
    residual_sep=fit_residual(train,sep,100.0)
    sep_gate=gate_result(sep,final_signs,gate["pmax"],gate["min_votes"])
    sep_score=score_eval(train,sep,p_sep,blend["blend"])
    sep_score_zero=score_eval(train,sep,p_sep,0.0)
    sep_htft=htft_eval(train,sep,p_sep)

    return {
      "system":"HH520 Hidden Formula V3.1 Fixed Rule",
      "stable_access":"READ_ONLY",
      "status":"CANDIDATE_ONLY",
      "rows":len(df),
      "month_counts":{str(k):int(v) for k,v in df.groupby(df.date.dt.strftime("%Y-%m")).size().items()},
      "fixed_confidence_gate":{
          "selected_from":"June-July-August walk-forward OOF only",
          "pmax":gate["pmax"],"min_votes":gate["min_votes"],
          "dev_oof_n":gate["n"],"dev_oof_accuracy":gate["accuracy"],
          "dev_min_fold_accuracy":gate["min_fold_accuracy"],
          "dev_wilson_low":gate["wilson_low"],
          "folds":gate["folds"],
          "september":sep_gate,
      },
      "factor_sign_stability":factor_stability(sign_history,final_signs),
      "final_factor_signs":final_signs,
      "score_blend":{
          "selected_from":"June-July-August walk-forward OOF only",
          "selected_blend":blend["blend"],
          "dev_oof_score_nll":blend["score_nll"],
          "dev_oof_top1":blend["top1"],"dev_oof_top2":blend["top2"],"dev_oof_top3":blend["top3"],
          "september_selected":sep_score,
          "september_no_blend":sep_score_zero,
          "candidates":blend_table,
      },
      "september":{
          "market_wdl":wdl_metrics(p_sep,sep),
          "residual_wdl":wdl_metrics(residual_sep,sep),
          "htft":sep_htft,
      },
      "league_gate_audit":{
          "development_jun_aug":league_audit(df,gate["pmax"],gate["min_votes"],orientation(df[(df.date>="2026-05-01")&(df.date<="2026-05-31")]),"2026-06-01","2026-08-31"),
          "september":league_audit(df,gate["pmax"],gate["min_votes"],final_signs,"2026-09-01","2026-09-20"),
      },
      "gate_candidates_top20":gate_candidates,
      "promotion_policy":"MANUAL_REVIEW_REQUIRED; September is development validation, not pristine final test."
    }

def render(r):
    g=r["fixed_confidence_gate"]; sg=g["september"]
    sb=r["score_blend"]; s=r["september"]
    L=[
      "# HH520 Hidden Formula V3.1 — Fixed Rule Result","",
      f"- Rows: **{r['rows']}**",
      "- Selection data: **June-July-August walk-forward OOF only**",
      "- September: **development validation only**",
      "- Stable: **READ_ONLY**","",
      "## Fixed confidence gate","",
      f"- Rule: **market pmax >= {g['pmax']:.2f} + at least {g['min_votes']}/5 confirmations**",
      f"- Dev OOF: **{g['dev_oof_accuracy']:.1%}**, n={g['dev_oof_n']}, worst fold={g['dev_min_fold_accuracy']:.1%}",
      f"- Dev Wilson lower 95%: **{g['dev_wilson_low']:.1%}**",
      f"- September: **{sg['accuracy']:.1%}**, n={sg['n']}, coverage={sg['coverage']:.1%}","",
      "### Forward folds"
    ]
    for f in g["folds"]:
        L.append(f"- {f['fold']}: {f['accuracy']:.1%} ({f['correct']}/{f['n']}), coverage {f['coverage']:.1%}")
    L+=["","## Factor sign stability",""]
    for k,v in r["factor_sign_stability"].items():
        L.append(f"- {k}: dev={v['dev_fold_signs']}, stable={v['stable_across_dev_folds']}, final={v['final_may_aug_sign']}")
    L+=["","## Full-coverage WDL","",
         f"- September Market: **{s['market_wdl']['accuracy']:.1%}**, LogLoss {s['market_wdl']['log_loss']:.4f}, RPS {s['market_wdl']['rps']:.4f}",
         f"- September Residual: **{s['residual_wdl']['accuracy']:.1%}**, LogLoss {s['residual_wdl']['log_loss']:.4f}, RPS {s['residual_wdl']['rps']:.4f}",
         "","## HTFT","",
         f"- September Top1 {s['htft']['top1']:.1%}, Top2 {s['htft']['top2']:.1%}, Top3 {s['htft']['top3']:.1%}, LogLoss {s['htft']['log_loss']:.4f}",
         "","## Adaptive score blend","",
         f"- Selected blend: **{sb['selected_blend']:.0%} empirical + {1-sb['selected_blend']:.0%} Poisson**",
         f"- Dev OOF: Top1 {sb['dev_oof_top1']:.1%}, Top2 {sb['dev_oof_top2']:.1%}, Top3 {sb['dev_oof_top3']:.1%}, NLL {sb['dev_oof_score_nll']:.4f}",
         f"- September selected: Top1 {sb['september_selected']['top1']:.1%}, Top2 {sb['september_selected']['top2']:.1%}, Top3 {sb['september_selected']['top3']:.1%}, NLL {sb['september_selected']['score_nll']:.4f}",
         f"- September no-blend: Top1 {sb['september_no_blend']['top1']:.1%}, Top2 {sb['september_no_blend']['top2']:.1%}, Top3 {sb['september_no_blend']['top3']:.1%}, NLL {sb['september_no_blend']['score_nll']:.4f}",
         "","## Decision","",
         "**CANDIDATE_ONLY.** Freeze only after reviewing fixed-gate support and factor-sign stability; final promotion requires a fresh untouched shadow window."
    ]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json",type=Path,required=True); ap.add_argument("--md",type=Path,required=True)
    a=ap.parse_args(); r=run()
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    a.md.write_text(render(r),encoding="utf-8")
    print(render(r))

if __name__=="__main__":
    main()
