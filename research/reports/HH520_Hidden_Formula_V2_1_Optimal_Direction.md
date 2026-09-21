# HH520 Hidden Formula V2.1 — Optimal Research Direction

## Executive conclusion

Do not replace the bookmaker market prior with a large weighted formula. The strongest architecture for the current 10027s dataset is:

1. Market-anchored WDL probabilities.
2. 10027s factors used primarily as residual/confidence gates, not as equal-weight predictors.
3. HTFT generated conditionally from frozen WDL probabilities.
4. Exact score generated from Poisson/Dixon-Coles goal intensities and kept probabilistically consistent with WDL/HTFT.
5. Promotion only after a new untouched validation window.

## New data-quality findings

### possession_diff semantics

The exported page field `possession_diff` is not simply `home_possession-away_possession`.

Across rows with possession data it is essentially the possession edge of the 1X2 favorite:

- home favorite: `home_possession-away_possession`
- away favorite: `away_possession-home_possession`

Therefore keep two distinct fields:

- `home_pos_diff = home_possession-away_possession`
- `favorite_pos_edge = favorite_side * home_pos_diff`

Do not use the source `possession_diff` as if it were home-minus-away.

### zero-coded missing team modules

31 of 705 rows have all eight team-module values equal to zero while possession is also absent. These are missing modules, not genuine zero team strength.

Research features must convert the all-zero 8-field block to NA and add a missingness flag. Effective complete team-module coverage is therefore approximately 674/705, matching possession coverage, not 705/705.

## WDL

The September full-coverage baseline remains the de-vigged 1X2 market. Earlier residual models failed to improve it.

The strongest stable use of the four team modules is confidence filtering.

Define favorite-oriented evidence using August only:

- possession confirmation: favorite possession edge > 0
- attack confirmation: favorite attack edge > 0
- defense confirmation: favorite defense edge > 0
- H2H confirmation: favorite H2H edge > 0
- form confirmation: favorite form edge <= 0

Define:

`Consensus = confirmations / available confirmations`

For rows with all five signals available:

| Gate | Aug | Sep research validation |
|---|---:|---:|
| market pmax >= .60 and Consensus >= .80 | 50/65 = 76.9% | 35/47 = 74.5% |
| market pmax >= .60 and Consensus = 1.00 | 28/33 = 84.8% | 18/22 = 81.8% |

These are high-confidence subsets, not full-coverage accuracy claims.

Simple attempts to flip low-consensus market favorites to draw or underdog were not stable out of sample. Therefore the team factors should not currently override the market winner at full coverage.

Recommended WDL V2.1:

`P_market = DEVIG(odds)`

Compare proportional, Shin and power de-vig inside training only.

Then fit a heavily regularized residual correction, but deploy it only when its walk-forward out-of-fold incremental log loss/RPS improvement is positive. Otherwise set residual correction weight to zero.

Output confidence tiers:

- A++: pmax >= .60 and 5/5 confirmation
- A: pmax >= .60 and >=4/5 confirmation
- B: pmax >= .55 and >=4/5 confirmation
- C: all others

Confidence tier changes confidence, not the predicted side unless a separately validated correction gate exists.

## HTFT

Use the sequential architecture:

`P(HT=h, FT=f | X) = P_WDL(FT=f | X) * P(HT=h | FT=f, X)`

This guarantees the FT marginal of the nine HTFT outcomes equals the WDL layer.

Start with a shrinkage model:

- base: empirical August `P(HT|FT)`
- challenger: `P(HT|FT, market-strength-bin, consensus-tier)`
- shrink sparse cells back to `P(HT|FT)`

Do not deploy a direct nine-class classifier unless it beats the shrinkage baseline in August walk-forward CV and then in an untouched period.

## Score

Keep Poisson/Dixon-Coles as the score family.

Estimate:

`log(lambda_home) = alpha_h + beta_h * X`
`log(lambda_away) = alpha_a + beta_a * X`

where X includes market WDL probabilities, home/away possession difference, attack, defense, H2H, form and missingness indicators.

Use strong regularization. Add Dixon-Coles only for low-score residual correction.

Do not hard-rescale the score matrix to WDL if it reduces score Top-N. Prefer soft consistency:

`Loss = ScoreNLL + lambda_wdl * KL(WDL_score || WDL_layer) + lambda_htft * KL(HTFT_score || HTFT_layer)`

Tune consistency penalties only inside the training period.

## Promotion gate

September has now been inspected repeatedly and is no longer a pristine final test set.

For production promotion freeze V2.1 and validate on a new untouched window.

Required:
- WDL: no worse than market on accuracy and significantly better or non-inferior on Log Loss/RPS.
- A tier: stable >= 70% hit rate with adequate support.
- HTFT: Top1/Top2 and joint log loss beat the frozen empirical conditional baseline.
- Score: Top1/Top3 plus score NLL beat frozen Poisson/DC baseline.
- No threshold changes after the final validation window opens.

Status: CANDIDATE_ONLY.
