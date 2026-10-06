import json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.htft_transition_research import load_rows, fit_multinomial, predict_conditional
from scripts.htft_transition_hybrid_research import formal_mass, eval_rankings

DRAW_STATES=("DRAW_HOME","DRAW_DRAW","DRAW_AWAY")

def redistribute_draw(formal, cond):
    out=dict(formal)
    draw_total=sum(float(formal.get(k,0.0)) for k in DRAW_STATES)
    s=float(sum(cond)) or 1.0
    probs=[float(x)/s for x in cond]
    for k,p in zip(DRAW_STATES,probs):
        out[k]=draw_total*p
    z=sum(out.values()) or 1.0
    return {k:v/z for k,v in out.items()}

def main():
    if os.getenv("HH520_HTFT_DRAW_GATE_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")

    rows=load_rows()
    dev=rows["dev1"]+rows["dev2"]
    stress=rows["stress"]

    model=fit_multinomial(dev,"DRAW",1.0)
    cond=predict_conditional(model,stress)

    baseline_rank=[]
    draw_gate_rank=[]
    changed=[]
    rescued=harmed=0

    for r,c in zip(stress,cond):
        fm=formal_mass(r)
        fr=sorted(fm,key=fm.get,reverse=True)
        gm=redistribute_draw(fm,c)
        gr=sorted(gm,key=gm.get,reverse=True)
        baseline_rank.append(fr)
        draw_gate_rank.append(gr)
        a=r["actual_htft"]
        b_hit=(a==fr[0])
        g_hit=(a==gr[0])
        if (fr[:2] != gr[:2]) or (fr[0] != gr[0]):
            changed.append({
              "date":r["date"],
              "home_team":r["home_team"],
              "away_team":r["away_team"],
              "actual_htft":a,
              "baseline_top1":fr[0],
              "baseline_top2":fr[1],
              "new_top1":gr[0],
              "new_top2":gr[1],
              "baseline_top1_hit":b_hit,
              "new_top1_hit":g_hit
            })
        rescued += int((not b_hit) and g_hit)
        harmed += int(b_hit and (not g_hit))

    base=eval_rankings(stress,baseline_rank)
    new=eval_rankings(stress,draw_gate_rank)

    out={
      "mode":"OFFLINE_EXISTING_CACHE_ONLY",
      "new_collection":False,
      "stress_window":"2026-09-01..2026-09-20",
      "selection_used_stress":False,
      "rule":"KEEP_FORMAL_HT_DRAW_TOTAL; REDISTRIBUTE_ONLY DRAW_HOME/DRAW_DRAW/DRAW_AWAY USING P(FT|HT=DRAW,x); OTHER SIX STATES UNCHANGED",
      "training_window":"2026-05-01..2026-08-31",
      "draw_model_l2":1.0,
      "baseline":base,
      "draw_gate":new,
      "delta":{
        "top1_hits":new["top1_hits"]-base["top1_hits"],
        "top1_accuracy":new["top1_accuracy"]-base["top1_accuracy"],
        "top2_hits":new["top2_hits"]-base["top2_hits"],
        "top2_accuracy":new["top2_accuracy"]-base["top2_accuracy"],
        "rescued_top1":rescued,
        "harmed_top1":harmed,
        "changed_match_count":len(changed)
      },
      "changed_matches":changed,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED"
    }
    Path("_htft_draw_gate_backtest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
