# Dual-source collector integration contract (candidate; not enabled)
# HH520 Stable V3.5.1 — 2026-10-11

## Sources
- HH520 10027S: mandatory base, refreshed per formal prediction.
- Dongqiudi: optional pre-match enrichment, collected by a separate adapter.
- On source failure, preserve 10027_ONLY for that match; never block the full slate.

## Identity matching (mandatory)
1. Normalize league identifiers with an explicit league alias registry.
2. Convert kickoff timestamps to UTC; require a compatible kickoff within a configurable tolerance (default 15 minutes). Flag reschedules for review.
3. Normalize home and away club names using a versioned bilingual alias registry; do not rely on string similarity alone.
4. Require consistent home/away roles, unless an explicit verified venue reversal is recorded.
5. If more than one candidate matches, or club identity is unverified, return AMBIGUOUS and do not merge.
6. Store verified mappings with provenance and audit timestamps; do not auto-learn ambiguous aliases.

## Required enrichment
Recent form, home/away splits, shots, shots on target, goals for/against, goal timing distribution, half-time tendencies; injuries only when timestamped and sourced. Each field carries source URL, capture time, effective as-of time, and missingness indicator. Never backfill pre-match features with post-match data.

## Gate and model protection
- FULL_DATA only if existing Collection1-1 SHOTS, RESULT_STABILITY, HALF_TIMING gates pass.
- Otherwise 10027_ONLY, with reason codes SOURCE_UNAVAILABLE, NO_FIXTURE_MATCH, AMBIGUOUS_MATCH, MISSING_FIELDS, POST_KICKOFF_DATA.
- Keep frozen 10027 H/D/A anchor, existing bounded challenger and 6-column output contract.
- No new prediction request_id on retries; source retry budget is separate from prediction polling.

## Acceptance tests before enabling
- Same club with different Chinese/English aliases resolves to same fixture.
- Same league and kickoff but different clubs never cross-match.
- Time zone conversions and daylight saving boundaries.
- Postponed fixtures and swapped home/away roles.
- Missing, blocked, and stale Dongqiudi pages trigger per-match fallback.
- Cached goal-timing data remains valid only when source version/as-of semantics match.
- CI end-to-end and shadow comparisons must pass before any production switch.

Status: specification only. No Dongqiudi scraper, workflow wiring, or CI validation is claimed here.
