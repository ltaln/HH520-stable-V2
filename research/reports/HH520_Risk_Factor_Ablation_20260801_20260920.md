# HH520 Risk Factor Attribution / Ablation

- Window: 2026-08-01..2026-09-20
- Samples: 704
- Baseline Risk<=20: n=297, acc=61.6%, coverage=42.2%

## Leave-One-Out

- top_probability: n=413, acc=59.6%, delta=-2.1%, coverage=58.7%
- probability_margin: n=297, acc=61.6%, delta=0.0%, coverage=42.2%
- match_type: n=297, acc=61.6%, delta=0.0%, coverage=42.2%
- value_conflict: n=362, acc=61.0%, delta=-0.6%, coverage=51.4%
- odds_zone: n=385, acc=60.5%, delta=-1.1%, coverage=54.7%
- page_risk: n=297, acc=61.6%, delta=0.0%, coverage=42.2%
- pattern: n=297, acc=61.6%, delta=0.0%, coverage=42.2%

## Interpretation

- Strongest contributor: top_probability.
- Secondary contributors: odds_zone, then value_conflict.
- Current threshold behavior shows no measurable incremental effect from probability_margin, match_type, page_risk, or pattern at Risk<=20.
- Production Risk Engine remains V3.0.
- No automatic rule promotion.
