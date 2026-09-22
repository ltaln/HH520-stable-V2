# HH520 Hidden Formula V3 — Expanded Sample Walk-Forward Result

## Scope

- Master window: 2026-05-01 to 2026-09-20
- Raw exported rows: 1436
- Valid full-time labels: 1432
- Duplicate (date, match_id): 0
- Factor semantic guardrail failures: 0
- Stable access: READ_ONLY
- Status: CANDIDATE_ONLY

Valid rows by month:

| Month | Matches |
|---|---:|
| 2026-05 | 413 |
| 2026-06 | 125 |
| 2026-07 | 190 |
| 2026-08 | 402 |
| 2026-09 | 302 |

106 rows contained an all-zero 8-factor block and were treated as missing team-module data rather than genuine zero strength.

## Walk-forward protocol

- F1: May -> June
- F2: May-June -> July
- F3: May-July -> August
- F4_DEV: May-August -> September 1-20

September remains development data, not a pristine production-promotion holdout.

## WDL result

Market remains the strongest full-coverage anchor.

| Fold | Market Acc | Selected Model Acc | Market LogLoss | Model LogLoss |
|---|---:|---:|---:|---:|
| F1 | 58.40% | 58.40% | 0.8978 | 0.8978 |
| F2 | 54.74% | 53.16% | 0.9610 | 0.9654 |
| F3 | 55.72% | 55.72% | 0.9591 | 0.9591 |
| F4_DEV | 52.32% | 52.32% | 1.0067 | 1.0067 |

Mean:
- Market accuracy: 55.29%
- Selected model accuracy: 54.90%
- Market LogLoss: 0.9561
- Selected model LogLoss: 0.9572
- Market RPS: 0.1898
- Selected model RPS: 0.1900

Additional challengers using odds + possession + attack/defense/H2H/form + handicap + league all failed to beat market full coverage:
- Logistic: ~51.4% mean accuracy
- Random Forest: ~51.1%
- ExtraTrees: ~50.5%
- Gradient Boosting: ~50.4%
- Market: ~55.3%

Decision:
- Full-coverage WDL = market direction.
- No residual direction override is promoted.

## Reliability / confidence ablation

A strict same-coverage comparison was performed between:
1. pmax-only ranking
2. pmax plus train-only factor/handicap reliability adjustments

Pooled forward-validation result:

| Coverage | pmax only | factor-adjusted | Delta |
|---|---:|---:|---:|
| 10% | 82.18% | 83.17% | +0.99 pp |
| 20% | 75.86% | 75.86% | 0.00 pp |
| 30% | 71.99% | 70.68% | -1.30 pp |
| 40% | 68.14% | 68.14% | 0.00 pp |

Conclusion:
- 10027 factors do not yet show a stable incremental advantage over market pmax for reliability ranking.
- Market pmax itself is the strongest current confidence variable.
- Factors may remain secondary tie-breakers / diagnostics, but must not be credited for confidence uplift until a fresh holdout proves incremental value.

A fixed proportional-de-vig pmax view also shows strong but regime-dependent high-confidence performance:
- pmax >= .70: May 70.3%, Jun 81.8%, Jul 81.0%, Aug 89.2%, Sep 82.1%.
This variation reinforces the need for fresh shadow validation and league/regime monitoring.

## HTFT

Baseline:
P(HT,FT|X) = P_market(FT|X) * P(HT|FT)

Forward results:
- Top1 mean: 32.68%
- Top2 mean: 51.25%
- Top3 mean: 65.62%
- Joint LogLoss mean: 1.8567

A hierarchical challenger using train-only league / market-strength / favorite-side groupings with shrinkage was also tested.

Weighted across validation folds:
- Baseline Top1: 32.88%
- Baseline Top2: 51.03%
- Baseline Top3: 64.77%
- Baseline LogLoss: 1.8529
- Hierarchical Top1: 32.88%
- Hierarchical Top2: 51.72%
- Hierarchical Top3: 65.16%
- Hierarchical LogLoss: 1.8552

Conclusion:
- Hierarchical shrinkage gives a small Top2/Top3 ranking lift, but worsens probability LogLoss slightly.
- Keep empirical P(HT|FT) as the probability baseline.
- Keep hierarchical HTFT as a Top2/Top3 challenger only.

## Exact score

The earlier September-only score numbers were optimistic and do not remain stable across the expanded walk-forward sample.

Original V3 Poisson/DC family:
- Base Top1 mean: 11.36%
- Base Top2 mean: 22.28%
- Base Top3 mean: 31.29%
- 15% empirical prior Top1 mean: 11.72%
- 15% empirical prior Top2 mean: 22.44%
- 15% empirical prior Top3 mean: 32.37%
- NLL improves from 3.0293 to 3.0030

A reworked separate home/away numeric Poisson model, selected strictly inside each training window, improved the cross-fold aggregate to approximately:
- Top1: 13.35%
- Top2: 24.73%
- Top3: 34.94%
- Top5: 48.97%
- NLL: 2.9746

Adding train-selected Dixon-Coles + empirical score-prior correction produced:
- Top1: 12.76%
- Top2: 25.02%
- Top3: 35.23%
- Top5: 47.60%
- NLL: 2.9720

For the user's two-score output, the corrected variant is the better current score challenger because Top2 and Top3 improve, although Top1 slightly decreases.

Adding league/team identity to Poisson did not consistently outperform the numeric pre-match model.

## Current V3 architecture

10027s
-> data quality + missing-value repair
-> market de-vig
-> WDL market anchor
-> pmax confidence
-> optional factor diagnostics only
-> empirical P(HT|FT)
-> hierarchical HTFT challenger for Top2/Top3
-> separate home/away Poisson goal intensity
-> train-selected Dixon-Coles / empirical score-prior correction
-> score Top1/Top2/Top3

## Decision

The expanded May-September sample materially changes the interpretation of V2.2:

1. Market WDL remains very difficult to beat at full coverage.
2. Much of the previous high-confidence uplift was explained by pmax itself, not clearly by the five team factors.
3. HTFT is comparatively stable: Top2 ~51%, Top3 ~65%.
4. Exact score is still the weakest layer; robust Top2 is around 25%, not the earlier September-only ~29%.
5. The next meaningful gain must come from new information / better goal-intensity structure, not simply more classifier complexity.

No Stable promotion is authorized from this report.
