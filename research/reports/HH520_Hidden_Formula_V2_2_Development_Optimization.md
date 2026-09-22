# HH520 Hidden Formula V2.2 — Development Optimization Result

## Data

- Train/discovery: 2026-08-01 to 2026-08-31, 402 matches
- Development validation: 2026-09-01 to 2026-09-20, 302 matches
- Total valid outcomes: 704
- September is development data now, not a final untouched test set.

## Main conclusion

The strongest current architecture is NOT a full-coverage factor override.

Use:
1. Market WDL as the full-coverage direction anchor.
2. 10027s possession/attack/defense/H2H/form as a stability/confidence filter.
3. No direction flip unless a future rule proves positive incremental value on an untouched period.
4. HTFT remains conditional on WDL.
5. Score uses Poisson-family intensities plus a small empirical score prior; Dixon-Coles remains optional because fitted rho is near zero in this sample.

## WDL full coverage

September market WDL:
- Accuracy: 52.32%
- No tested residual correction beat this reliably.
- No stable simple rule was found that flipped market favorites to DRAW or underdog with positive gain in BOTH August and September at reasonable support.

Therefore:
- full-coverage WDL prediction = market argmax
- residual direction correction = 0

## Selective confidence optimization

Five favorite-oriented confirmations:
- favorite possession edge > 0
- favorite attack edge > 0
- favorite defense edge > 0
- favorite H2H edge > 0
- favorite form edge < 0

Best stable development regions:

| Rule | Aug | Sep |
|---|---:|---:|
| pmax >= .73 and >=3/5 confirmations | 21/24 = 87.5% | 18/20 = 90.0% |
| pmax >= .66 and >=3/5 confirmations | 39/47 = 83.0% | 29/35 = 82.9% |
| pmax >= .64 and >=3/5 confirmations | 49/64 = 76.6% | 34/44 = 77.3% |
| pmax >= .60 and >=4/5 confirmations | 50/65 = 76.9% | 35/47 = 74.5% |

Recommended confidence gates for V2.2 candidate:
- S: pmax >= .73 and >=3/5 confirmations
- A++: pmax >= .66 and >=3/5 confirmations
- A: pmax >= .64 and >=3/5 confirmations
- B/C: lower confidence; do not override market direction

Interpretation:
the 10027 team factors improve cross-period stability of high-confidence selection more reliably than they improve full-coverage direction.

## Draw model

A dedicated DRAW-vs-NONDRAW residual model was tested with:
- market draw probability
- market gap / entropy
- absolute possession gap
- absolute attack/defense/H2H/form gaps
- handicap availability

Result:
- August walk-forward draw residual did not beat the raw market draw probability on log loss.
- Therefore no draw correction is promoted.

## HTFT

Architecture remains:

P(HT=h, FT=f | X) = P_WDL(FT=f | X) × P(HT=h | FT=f, X)

Empirical conditional baseline on September:
- HT accuracy: 44.70%
- HTFT Top1: 31.46%
- Top2: 50.00%
- Top3: 63.91%
- Joint log loss: 1.8951

A strongly regularized conditional logistic challenger:
- HT accuracy: 46.36%
- HTFT Top1: 30.79%
- Top2: 49.67%
- Top3: 63.25%
- Joint log loss: 1.8926

Conclusion:
- logistic challenger improves probability log loss slightly and HT classification
- empirical baseline remains better for Top1/Top2/Top3 ranking
- keep empirical baseline as production candidate; retain logistic conditional as probability challenger

## Score optimization

A pooled team-perspective Poisson model was tested using:
- market probabilities
- home advantage
- possession
- attack/defense/H2H/form
- handicap structure
- missingness indicators

September base pooled Poisson:
- Top1: 13.91%
- Top2: 27.15%
- Top3: 35.10%
- Top5: 44.70%
- Score NLL: 3.0276

Adding a small empirical score prior conditioned on FT improves ranking.

Best practical blend for two-score output:
- 85% Poisson + 15% empirical FT-conditioned score prior
- Top1: 13.58%
- Top2: 29.14%
- Top3: 36.42%
- Top5: 45.03%
- Score NLL: 3.0235

Balanced Top1 alternative:
- 95% Poisson + 5% empirical prior
- Top1: 14.90%
- Top2: 28.15%
- Top3: 35.43%
- NLL: 3.0246

Compared with V2.1 score candidate:
- V2.1 Top1: 13.25%
- V2.1 Top2: 25.50%
- V2.1 Top3: 33.77%

V2.2 ranking-oriented improvement:
- Top1: +1.65 pp at the Top1-oriented blend
- Top2: +3.64 pp at the two-score-oriented blend
- Top3: +2.65 pp at the two-score-oriented blend

Dixon-Coles:
- fitted rho on August pooled model ≈ +0.0047
- effect is negligible in this current sample
- keep implementation available, but do not force the correction when rho is near zero

## V2.2 candidate architecture

10027s
  -> data quality / missing-value repair
  -> market de-vig probabilities
  -> full-coverage WDL = market direction
  -> 5-factor consensus confidence gate
  -> S / A++ / A / B / C
  -> empirical P(HT|FT) for HTFT ranking
  -> Poisson goal intensity model
  -> 15% empirical FT-conditioned score prior for Top2 score output
  -> optional Dixon-Coles only if fitted rho materially departs from zero

## Promotion state

CANDIDATE_ONLY

Because September has been used repeatedly for development, V2.2 must be frozen and tested on a new untouched date range before Stable promotion.
