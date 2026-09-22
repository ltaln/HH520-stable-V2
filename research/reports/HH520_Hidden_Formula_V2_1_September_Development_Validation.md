# HH520 Hidden Formula V2.1 — September Development Validation

Date window:
- Train / model selection: 2026-08-01 to 2026-08-31 (402 matches)
- Development validation: 2026-09-01 to 2026-09-20 (302 matches)

Important:
September is now a development validation set, not a pristine final test set. Production promotion must use a new untouched window after 2026-09-20.

## Data corrections applied

1. Corrected 8-factor mapping:
   - home_attack / away_attack
   - home_defense / away_defense
   - home_h2h / away_h2h
   - home_form / away_form

2. All-zero 8-factor blocks were treated as missing rather than real zero strength.

3. Possession was recomputed as:
   - home_pos_diff = home_possession - away_possession
   - favorite_pos_edge = favorite-side oriented possession difference

4. Forbidden fields remained excluded:
   - 建议下注
   - 是否下注

## WDL

### De-vig comparison

August:

| Method | Accuracy | Log Loss | Brier | RPS |
|---|---:|---:|---:|---:|
| Proportional | 55.72% | 0.9591 | 0.5685 | 0.1948 |
| Power | 55.72% | 0.9552 | 0.5667 | 0.1941 |
| Shin | 55.72% | 0.9562 | 0.5671 | 0.1942 |

Strict August-only model selection therefore chooses Power.

September:

| Method | Accuracy | Log Loss | Brier | RPS |
|---|---:|---:|---:|---:|
| Proportional | 52.32% | 1.0041 | 0.5988 | 0.2061 |
| Power | 52.32% | 1.0083 | 0.6012 | 0.2073 |
| Shin | 52.32% | 1.0067 | 0.6002 | 0.2068 |

Observation: Power won by a small margin in August but Proportional was better in September probability quality. This is evidence that the de-vig choice itself is unstable at the current sample size.

### Residual correction gate

A market-anchored residual softmax using possession, attack, defense, H2H, form, handicap availability and nonlinear gap features was evaluated with chronological August walk-forward folds.

Best residual candidate:
- L2 = 100
- residual weight = 0.25

August walk-forward:
- residual log loss: 0.9377
- market baseline log loss: 0.9368
- residual RPS: 0.1895
- market baseline RPS: 0.1893

Conclusion: the residual correction did not beat the market even in August OOF. Per V2.1 rules, residual weight should be set to zero for deployment.

### Draw residual gate

Best tested DRAW-vs-NONDRAW residual:
- binary log loss: 0.5300
- market draw baseline: 0.5298

Conclusion: no draw residual correction is deployed.

## Confidence consensus

Five favorite-oriented confirmation signals:

1. favorite possession edge > 0
2. favorite attack edge > 0
3. favorite defense edge > 0
4. favorite H2H edge > 0
5. favorite form edge < 0

Using August-selected Power de-vig:

| Tier | August | September | Sep Coverage |
|---|---:|---:|---:|
| A++: pmax >= .60 and 5/5 | 31/38 = 81.6% | 21/28 = 75.0% | 9.3% |
| A: pmax >= .60 and >=4/5 | 57/74 = 77.0% | 42/58 = 72.4% | 19.2% |

Wilson 95% CI:
- September A++: 56.6%–87.3%
- September A: 59.8%–82.2%

Development observation only:
with Proportional de-vig the corresponding September rates were:
- A++: 18/22 = 81.8%
- A: 35/47 = 74.5%

Conclusion:
the strongest stable use of the four team modules remains confidence filtering, not full-coverage result flipping.

## HTFT

Architecture:
P(HT=h, FT=f | X) = P_WDL(FT=f | X) × P(HT=h | FT=f, X)

Hierarchical challenger:
- condition on FT class
- market-strength bin
- confidence tier
- shrink sparse cells toward empirical P(HT|FT)

August walk-forward selected shrinkage alpha = 50 using Power market probabilities.

August OOF:
- challenger log loss: 1.8076
- empirical conditional baseline: 1.8108

September:

| Model | HT Acc | HTFT Top1 | Top2 | Top3 | Log Loss |
|---|---:|---:|---:|---:|---:|
| Hierarchical challenger | 42.72% | 31.13% | 50.99% | 64.24% | 1.8991 |
| Empirical P(HT|FT) baseline | 44.04% | 31.46% | 49.67% | 63.58% | 1.8985 |

Conclusion:
the challenger adds some Top2/Top3 coverage but does not improve Top1 or joint log loss. Do not promote it yet.

## Score

Score family:
- separate PoissonRegressor for home and away expected goals
- corrected 10027 factors
- market probabilities
- possession
- strong regularization
- Dixon-Coles low-score correction
- optional soft WDL consistency

August walk-forward selected:
- Poisson alpha = 1
- WDL soft-alignment strength = 0.50

Fit on all August:
- Dixon-Coles rho = +0.0050

September:

| Score model | Top1 | Top2 | Top3 | Top5 | Score NLL |
|---|---:|---:|---:|---:|---:|
| Poisson + DC, no alignment | 12.58% | 26.16% | 33.44% | 45.36% | 3.0143 |
| Poisson + DC, align .25 | 12.91% | 25.83% | 33.77% | 44.70% | 3.0105 |
| Poisson + DC, align .50 | 13.25% | 25.50% | 33.77% | 45.03% | 3.0079 |

Conclusion:
soft WDL consistency slightly improves score NLL and Top1/Top3, but the gains are small and not enough for production promotion.

## Final development result

Status: CANDIDATE_ONLY

The September development validation supports:

1. Keep market WDL as the full-coverage anchor.
2. Do not deploy the current residual WDL correction.
3. Use attack/defense/H2H/form primarily for confidence tiers.
4. Keep conditional HTFT architecture, but empirical P(HT|FT) remains the safer baseline.
5. Keep Poisson + Dixon-Coles as the score family; soft WDL alignment remains a challenger.
6. Freeze the next candidate and test on a new untouched period after 2026-09-20 before Stable promotion.

## Best current deployable candidate

WDL:
- market de-vig probabilities
- no residual direction override
- A++ / A confidence consensus

HTFT:
- empirical P(HT|FT) baseline conditioned on frozen WDL

Score:
- Poisson + Dixon-Coles
- retain soft WDL alignment as challenger until a fresh holdout confirms improvement
