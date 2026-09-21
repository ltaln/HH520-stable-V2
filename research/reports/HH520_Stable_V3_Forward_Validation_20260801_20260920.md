# HH520 Stable V3 Forward Validation

- Train: 2026-08-01..2026-08-31 | n=402 | acc=55.0%
- Holdout: 2026-09-01..2026-09-20 | n=302 | acc=51.0%

## Global Rules

- risk_score: train <= 20 → holdout n=132, acc=60.6%, delta=+9.6%, validated=True
- probability_margin: train >= 0.20 → holdout n=167, acc=56.9%, delta=+5.9%, validated=True
- value_edge: train >= 0.00 → holdout n=215, acc=52.6%, delta=+1.6%, validated=True

## Match Types

### balanced
- holdout n=54, baseline=31.5%
- probability_margin >= 0.03 → n=32, acc=28.1%, delta=-3.4%, validated=False
- value_edge >= 0.00 → n=40, acc=37.5%, delta=+6.0%, validated=True

### cup
- holdout n=38, baseline=68.4%
- risk_score <= 20 → n=21, acc=76.2%, delta=+7.8%, validated=True
- probability_margin >= 0.20 → n=24, acc=70.8%, delta=+2.4%, validated=True
- value_edge >= 0.00 → n=31, acc=67.7%, delta=-0.7%, validated=False

### standard
- holdout n=144, baseline=46.5%
- risk_score <= 40 → n=113, acc=50.4%, delta=+3.9%, validated=True
- probability_margin >= 0.20 → n=77, acc=44.2%, delta=-2.4%, validated=False
- value_edge >= 0.00 → n=94, acc=47.9%, delta=+1.3%, validated=True

### strong_favorite
- holdout n=66, baseline=66.7%
- risk_score <= 20 → n=62, acc=67.7%, delta=+1.1%, validated=True
- probability_margin >= 0.03 → n=66, acc=66.7%, delta=0.0%, validated=False
- value_edge >= 0.00 → n=50, acc=64.0%, delta=-2.7%, validated=False

## Decision

Only rules with positive holdout delta and sufficient holdout sample are eligible for Stable V3.1 review. No automatic promotion.

## Data Integrity Fix

Result labels are joined with the canonical composite key: (date, match_id). HH520 match_id restarts every date, so match_id alone is not a valid historical join key.
