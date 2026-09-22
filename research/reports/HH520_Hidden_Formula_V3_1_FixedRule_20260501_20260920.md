# HH520 Hidden Formula V3.1 — Fixed Rule Result

- Rows: **1432**
- Selection data: **June-July-August walk-forward OOF only**
- September: **development validation only**
- Stable: **READ_ONLY**

## Fixed confidence gate

- Rule: **market pmax >= 0.73 + at least 2/5 confirmations**
- Dev OOF: **90.2%**, n=41, worst fold=87.5%
- Dev Wilson lower 95%: **77.5%**
- September: **85.7%**, n=21, coverage=7.0%

### Forward folds
- MAY_to_JUN: 87.5% (7/8), coverage 6.4%
- MAYJUN_to_JUL: 100.0% (8/8), coverage 4.2%
- MAYJUL_to_AUG: 88.0% (22/25), coverage 6.2%

## Factor sign stability

- attack_diff: dev=[-1, 1, 1], stable=False, final=1
- defense_diff: dev=[-1, 1, 1], stable=False, final=1
- form_diff: dev=[1, -1, -1], stable=False, final=-1
- h2h_diff: dev=[1, 1, 1], stable=True, final=1
- home_pos_diff: dev=[1, 1, 1], stable=True, final=1

## Full-coverage WDL

- September Market: **52.3%**, LogLoss 1.0041, RPS 0.2061
- September Residual: **50.7%**, LogLoss 1.0114, RPS 0.2087

## HTFT

- September Top1 31.5%, Top2 49.0%, Top3 62.6%, LogLoss 1.8877

## Adaptive score blend

- Selected blend: **0% empirical + 100% Poisson**
- Dev OOF: Top1 13.7%, Top2 26.1%, Top3 34.4%, NLL 2.9534
- September selected: Top1 15.2%, Top2 24.8%, Top3 31.5%, NLL 3.0264
- September no-blend: Top1 15.2%, Top2 24.8%, Top3 31.5%, NLL 3.0264

## Decision

**CANDIDATE_ONLY.** Freeze only after reviewing fixed-gate support and factor-sign stability; final promotion requires a fresh untouched shadow window.
