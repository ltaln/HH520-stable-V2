# HH520 V3.2 — Relationship Tournament Final Interpretation

## Data
- 2026-05-01 to 2026-09-20
- 1,432 valid matches
- September is development stress only, not final untouched validation
- Stable remains read-only

## Best current architecture

### 1. Full-coverage WDL
Keep the bookmaker market as the direction anchor.

Current residual / draw-adjusted / team+handicap+league models do not show stable incremental value over market.

### 2. De-vig
Power de-vig was slightly better on June-August development proper scores:
- Proportional dev avg LogLoss 0.9393, RPS 0.18410
- Power dev avg LogLoss 0.9362, RPS 0.18350

But September reversed:
- Proportional LogLoss 1.00413, RPS 0.20613
- Power LogLoss 1.00835, RPS 0.20731

Therefore there is no stable de-vig winner yet. Keep Proportional as production benchmark; Power remains a research challenger.

### 3. Selective high-confidence WDL
The strongest reproducible result remains market strength itself.

For pmax >= 0.73:
- June-August development: 46/52 = 88.5%
- September stress: 19/22 = 86.4%

Adding the V3.1 2/5 factor confirmation:
- June-August: 38/42 = 90.5%
- September: 18/21 = 85.7%

Interpretation:
- factor confirmation added +2.0pp in development but -0.7pp in September
- it reduced coverage
- therefore the 2/5 vote has not demonstrated stable incremental value beyond pmax alone

The broader reliability models also failed the equal-coverage control:
- best market+team+handicap reliability dev: 76.9%, n=173
- equal-coverage pmax control: 77.5%
- incremental: -0.6pp
- September: 74.1% vs equal-coverage pmax 72.2%, +1.9pp, but this does not offset the negative development result

Conclusion: current best selective rule is market pmax, not the multi-factor vote.

### 4. Relationships found
Stable conditional relationships in the regularized reliability model:
- pmax: positive
- market margin: positive
- market entropy: negative
- handicap depth: positive
- handicap depth × market-side alignment: positive
- H2H favourite-oriented edge: weak positive

Unstable / non-incremental:
- possession
- attack
- defense
- form
- league one-hot effects

Water:
- primary water signal was effectively non-discriminative in the current historical structure
- this is consistent with the source having very limited primary-water variation
- do not assign predictive weight to water until richer movement/timestamp data exist

Important: coefficient signs are conditional associations after controlling for market strength, not causal football interpretations.

### 5. Draw
Dedicated draw adjustment failed:
- September Market: LogLoss 1.0041, RPS 0.2061
- Draw-adjusted: LogLoss 1.0090, RPS 0.2069

Keep market draw probability.

### 6. HTFT
Keep the conditional structure P(FT) × P(HT|FT).

September:
- Conditional: Top1 31.5%, Top2 49.0%, Top3 62.6%, LL 1.8877
- Direct 9-class: Top1 30.1%, Top2 48.7%, Top3 64.6%, LL 1.8944

Direct 9-class only improved Top3; it lost Top1/Top2 and probability quality.

### 7. Score
Keep pooled Poisson.

September:
- Pooled: Top1 15.2%, Top2 24.8%, Top3 31.5%, Top5 45.0%, NLL 3.0264
- Dynamic EWMA team/league model: Top1 14.9%, Top2 24.2%, Top3 30.8%, Top5 47.0%, NLL 3.0267

Dynamic model improved only Top5 and failed NLL/Top1-3, so it is not promoted.

## Final current candidate

```text
10027s prematch
    ↓
Market implied probabilities
    ↓
Full-coverage WDL = Market
    ↓
High-confidence filter = pmax strength
    ↓
Conditional HTFT
    ↓
Pooled Poisson score distribution
```

Do not promote:
- 2/5 factor vote as a mandatory gate
- market+team+handicap reliability model
- draw residual model
- direct HTFT 9-class model
- dynamic EWMA score model
- water-based weighting
- league-specific hard rules

## Status
CANDIDATE_ONLY.

The next Stable promotion decision must be based on a fresh post-freeze shadow window.
