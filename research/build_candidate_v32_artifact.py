"""Build frozen Candidate V3.2 runtime artifact from cached 10027s history.

Cache-only. Labels are used only here to estimate frozen HTFT and score-model
parameters. Runtime prediction consumes only the resulting artifact.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

from research.hidden_formula_v3 import prep, market_probs, FEATURES, fit_poisson

START="2026-05-01"
END="2026-09-20"
CLASSES=["HOME","DRAW","AWAY"]
FEATURE_COLUMNS=["p_home","p_draw","p_away"]+FEATURES+["team_modules_missing"]

def build_htft(df):
    counts=np.ones((3,3),float)  # FT x HT Laplace
    good=df.dropna(subset=["actual_y","ht_y"])
    for _,r in good.iterrows():
        counts[int(r.actual_y),int(r.ht_y)]+=1
    cond=counts/counts.sum(axis=1,keepdims=True)
    return {
        CLASSES[f]:{CLASSES[h]:float(cond[f,h]) for h in range(3)}
        for f in range(3)
    }

def build_score(df):
    z=df.dropna(subset=["home_goals","away_goals"]).copy()
    raw=z[FEATURE_COLUMNS].astype(float).copy()
    med=raw.median(numeric_only=True).fillna(0.0)
    raw=raw.fillna(med)
    mu=raw.mean()
    sd=raw.std().replace(0,1).fillna(1)
    X=((raw-mu)/sd).to_numpy()
    X=np.column_stack([np.ones(len(X)),X])
    wh=fit_poisson(X,z.home_goals.to_numpy(float),1.0)
    wa=fit_poisson(X,z.away_goals.to_numpy(float),1.0)
    return {
      "model":"POOLED_POISSON",
      "feature_columns":FEATURE_COLUMNS,
      "median":{c:float(med[c]) for c in FEATURE_COLUMNS},
      "mean":{c:float(mu[c]) for c in FEATURE_COLUMNS},
      "std":{c:float(sd[c]) for c in FEATURE_COLUMNS},
      "home_coef":[float(x) for x in wh],
      "away_coef":[float(x) for x in wa],
      "max_goals":10,
      "l2":1.0,
    }

def run():
    df,missing=prep(START,END)
    if missing:
        raise RuntimeError(f"missing cache dates: {len(missing)} first={missing[:5]}")
    p=market_probs(df)
    df[["p_home","p_draw","p_away"]]=p
    return {
      "version":"HH520 Stable V3.2",
      "artifact_version":"HH520-Candidate-V3.2-Frozen-20260920",
      "training_period":{"start":START,"end":END,"rows":int(len(df))},
      "wdl":{
        "model":"MARKET_PROPORTIONAL_DEVIG",
        "direction_override":False,
        "page_probability_for_direction":False
      },
      "confidence":{
        "model":"MARKET_PMAX",
        "s_threshold":0.73,
        "factor_vote_required":False
      },
      "htft":{
        "model":"CONDITIONAL_HT_GIVEN_FT",
        "matrix":build_htft(df),
        "laplace_prior":1.0
      },
      "score":build_score(df),
      "disabled":{
        "draw_residual":True,
        "factor_direction_override":True,
        "league_hard_rules":True,
        "water_weight":True,
        "empirical_score_blend":True
      }
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    r=run()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
