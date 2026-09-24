# HH520 V3.5 Shadow Candidate

This is an isolated candidate and does not modify Stable V3.4 production.

FT candidate thresholds from May-Aug development with September holdout:
- p >= 0.55: STANDARD single-direction candidate
- p >= 0.60: STRONG
- p >= 0.65: HIGH
- below 0.55: BALANCED / no forced single direction
- Draw remains SHADOW_ONLY until a stable rule survives forward validation.

Score:
- fit independent home/away Poisson intensities to formal Stable H/D/A probabilities
- choose score Top2 globally; do not filter by FT selected direction

HT/FT:
- prediction only
- goal-timing data is required
- no historical goal-timing collection
- no timing => HT/FT PASS/unavailable
- Top2 selected globally from first-half/second-half joint model, not locked to FT direction
