# HH520 Hidden Formula V3 — Walk-Forward Result

- Rows: **1432**
- Missing cache dates: **0**
- Stable access: **READ_ONLY**

## Month counts

- 2026-05: 413
- 2026-06: 125
- 2026-07: 190
- 2026-08: 402
- 2026-09: 302

## MAY_to_JUN

- Train/Test: 413 / 125
- Market WDL: **58.4%**, LogLoss 0.8978, RPS 0.1624
- Residual WDL: **60.0%**, LogLoss 0.9179, RPS 0.1671
- Selected confidence gate: pmax>=0.60, votes>=2, n=24, accuracy=75.0%, coverage=19.2%
- HTFT: Top1 32.0%, Top2 55.2%, Top3 67.2%, LogLoss 1.8853
- Score blend15: Top1 16.8%, Top2 29.6%, Top3 36.8%, NLL 2.8868

## MAYJUN_to_JUL

- Train/Test: 538 / 190
- Market WDL: **54.7%**, LogLoss 0.9610, RPS 0.1950
- Residual WDL: **52.6%**, LogLoss 0.9672, RPS 0.1962
- Selected confidence gate: pmax>=0.68, votes>=5, n=10, accuracy=70.0%, coverage=5.3%
- HTFT: Top1 34.2%, Top2 52.1%, Top3 66.3%, LogLoss 1.8174
- Score blend15: Top1 13.2%, Top2 23.2%, Top3 31.1%, NLL 2.8721

## MAYJUL_to_AUG

- Train/Test: 728 / 402
- Market WDL: **55.7%**, LogLoss 0.9591, RPS 0.1948
- Residual WDL: **55.0%**, LogLoss 0.9600, RPS 0.1957
- Selected confidence gate: pmax>=0.68, votes>=3, n=40, accuracy=87.5%, coverage=10.0%
- HTFT: Top1 33.6%, Top2 50.7%, Top3 64.9%, LogLoss 1.8296
- Score blend15: Top1 12.9%, Top2 24.1%, Top3 33.3%, NLL 3.0179

## MAYAUG_to_SEP

- Train/Test: 1130 / 302
- Market WDL: **52.3%**, LogLoss 1.0041, RPS 0.2061
- Residual WDL: **50.7%**, LogLoss 1.0114, RPS 0.2087
- Selected confidence gate: pmax>=0.68, votes>=5, n=11, accuracy=81.8%, coverage=3.6%
- HTFT: Top1 31.5%, Top2 49.0%, Top3 62.6%, LogLoss 1.8877
- Score blend15: Top1 12.9%, Top2 24.5%, Top3 32.1%, NLL 3.0236

## Research interpretation

1. Full-coverage market WDL remains the strongest anchor. Residual WDL did not improve probability quality consistently.
2. Selective confidence filtering remains promising, but threshold/vote settings are unstable across folds and must be stabilized before promotion.
3. Factor orientation changes in the earliest fold, then stabilizes from May+June onward. This requires a dedicated semantic/non-stationarity audit before freezing a consensus rule.
4. HTFT is relatively stable around Top1 31–34%, Top2 49–55%, Top3 63–67%.
5. Score performance varies materially by month. A fixed 15% empirical score blend does not consistently beat raw Poisson and should not be frozen yet.

## Decision

**CANDIDATE_ONLY. No Stable promotion.**

Next research target:
- fixed cross-fold confidence rule selection;
- month/league non-stationarity analysis;
- factor-sign stability audit;
- adaptive score blending selected by walk-forward CV rather than fixed 15%;
- fresh untouched shadow validation after the V3 rule set is frozen.
