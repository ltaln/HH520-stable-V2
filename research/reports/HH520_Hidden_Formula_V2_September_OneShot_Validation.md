# HH520 Hidden Formula V2 — September 2026 One-Shot Validation

## Protocol

- Train / model selection: 2026-08-01 to 2026-08-31 (402 matches)
- Locked holdout: 2026-09-01 to 2026-09-20 (302 matches)
- No September data used for threshold or hyperparameter selection
- Primary key: date + match_id
- Forbidden inputs remain excluded: 建议下注 / 是否下注
- Corrected factors used: attack / defense / H2H / form H/A, possession, 1X2 odds; handicap only in score challenger

## WDL

August CV selected residual-market model:
- Market prior: normalized de-vig 1X2
- Residual features: possession diff, attack diff, defense diff, H2H diff, form diff, absolute gaps, draw odds, favorite gap/sign, overround, limited interactions
- L2 = 10

September holdout:

| Model | Accuracy | Balanced Acc | Macro F1 | Log Loss | Brier | RPS |
|---|---:|---:|---:|---:|---:|---:|
| Market de-vig baseline | 52.32% | 46.18% | 39.49% | 1.0041 | 0.5988 | 0.2061 |
| Residual WDL Candidate | 50.00% | 44.43% | 39.94% | 1.0255 | 0.6147 | 0.2119 |

Paired comparison:
- Candidate-only correct: 3
- Market-only correct: 10
- McNemar exact p = 0.0923
- Accuracy difference = -2.32 pp
- Bootstrap 95% CI for accuracy difference: [-4.64 pp, 0.00 pp]
- Log-loss difference (candidate - market): +0.0214, bootstrap 95% CI [ +0.0050, +0.0377 ]
- RPS difference (candidate - market): +0.0057, bootstrap 95% CI [ +0.0014, +0.0100 ]

Conclusion: WDL residual model FAILS upgrade gate. Keep market prior as current WDL benchmark.

## HTFT

Conditional model:
P(HT,FT|X) = P(FT|X) * P(HT|FT,X)

August CV selected logistic C=0.1.

September with residual WDL candidate:
- HT accuracy: 47.02%
- HTFT Top1: 31.13%
- HTFT Top2: 48.01%
- HTFT Top3: 60.60%
- HTFT log loss: 2.0537

September benchmark using market WDL + empirical Aug P(HT|FT):
- HT accuracy: 44.04%
- HTFT Top1: 31.46%
- HTFT Top2: 50.00%
- HTFT Top3: 64.24%
- HTFT log loss: 1.8943

Conclusion: current learned HT conditional layer does not pass upgrade gate.

## Score

August CV:
- Poisson alpha = 1
- Dixon-Coles rho = -0.03936
- Soft WDL consistency strength tuned on August only

September, Poisson + Dixon-Coles + residual-WDL soft alignment:
- Top1: 11.59%
- Top2: 25.17%
- Top3: 32.12%
- Top5: 46.69%
- Score log loss: 3.0195

September, same score model aligned to market WDL:
- Top1: 13.25%
- Top2: 25.17%
- Top3: 32.78%
- Top5: 48.01%
- Score log loss: 3.0040

September, unaligned Poisson + Dixon-Coles:
- Top1: 12.91%
- Top2: 25.83%
- Top3: 33.77%
- Top5: 47.68%
- Score log loss: 3.0161

Conclusion: Dixon-Coles is useful enough to retain as a challenger, but WDL soft alignment needs redesign. Current score candidate does not pass a production-upgrade gate.

## Decision

Status: CANDIDATE_ONLY / NO STABLE PROMOTION

The September holdout rejects the current V2 residual WDL correction. The market prior remains stronger out of sample. Next research should focus on:

1. Learn only residual signals that improve market probabilities under walk-forward CV.
2. Treat draw as a separate subproblem and test DRAW-vs-NONDRAW before H-vs-A.
3. Re-estimate factor semantics/nonlinearity using GAM/splines and monotonic/threshold diagnostics.
4. Expand historical sample before fitting higher-order interactions.
5. For score, retain Poisson/Dixon-Coles but improve team-goal intensity features and compare market-consistent blending without hurting Top-N.
