# HH520 AI Decision Engine V1.0 — 2026-10-17 trial

## Goal
AI leads football analysis; Stable V3.5.1 supplies quantitative reference only. Review all 28 matches, prioritize draw risk and favorite-failure / outright-upset risk. Do not prefilter fixtures. Keep this trial isolated from production.

## Frozen starting point
- request_id: hh520-20261017-1402-d8f1
- branch: action-results
- file: results/hh520-20261017-1402-d8f1.json
- status READY, 28 matches, model HH520 Stable V3.5.1.
- Dongqiudi available for 22 fixtures, independent goal-timing availability 0; investigate different collection provenance rather than concluding all timing unavailable.

## Per-match research protocol
1. Match identity: league + local kickoff + home/away + alias resolution. Do not cross-match names alone.
2. Independent AI first: analyze recent strength, attacking/defensive performance, xG, shot quality, schedules, injuries, tactical matchup, goals-by-time, and odds movement where reliable. Actively search credible external sites when Stable lacks data.
3. Record each key claim, page URL, observation timestamp, definition/sample size, kickoff time and confidence. Historical trials must exclude post-kickoff information.
4. Propose one of: DRAW, FAVORITE_NOT_WIN, UPSET_WIN, NO_SIGNAL, PASS. Each requires counter-evidence and rationale; missing data are not negative evidence.
5. Only then compare Stable probabilities, score top 2, HTFT top 2, total-goal forecast. Document agreements and disagreements without modifying locked_prediction.
6. Research all 28 before drawing the ranked draw and upset watchlists. Rank based on support, contrary evidence and data quality; do not force exactly four draws or two upsets.
7. Report all 28, including exclusion/PASS reasons. Display Stable probability numbers only where they exist; AI estimates must not be invented.
8. After final results, test Stable alone, blinded AI judgement and combined decision on draw/upset hit rate, score/HTFT top-2 coverage, calibration and PASS. Use true as-of pre-match evidence to avoid hindsight leakage.

## Required research record per match
match_id, league, kickoff_timezone, home, away, stable_data_mode, evidence_sources[], evidence_time, missing_fields[], AI_independent_hypothesis, supporting_reasons[], opposing_reasons[], stable_comparison, AI_final_decision, confidence_qualitative, score_top2_with_origin, htft_top2_with_origin, postmatch_outcome, verification_status.

## Guardrails
Research is independent. No new prediction request; no modification of Stable V3.5.1, production files, result contract or GitHub Actions. No claim of having finished independent reviews until external match-by-match sources have been checked and documented. This file defines a trial; it does not claim that the 28-match independent AI study has already been completed.
