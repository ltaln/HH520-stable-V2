# Codex Task — HH520 V3.5 Goal-Timing Completion

## Scope
Finish only the V3.5 Shadow goal-timing acquisition path. Do not modify Stable V3.4/V3.4.1 production probability, Decision Filter, 6-column output, or historical Research behavior.

## Hard constraints
- Historical Research MUST NOT collect goal-timing data.
- Formal/shadow prediction HT/FT MUST require goal-timing data.
- Missing/invalid timing => HT/FT PASS/unavailable. Never fall back to FT-conditioned template.
- Score remains independent of selected FT direction.
- GPT remains EXPLANATION_ONLY.

## Current state
- V3.5 Shadow workflow: .github/workflows/hh520-v35-shadow.yml
- Candidate core: candidate/v35/core.py
- Timing collector: collector/goal_timing_service.py
- First 2026-09-24 shadow run attempted 7 matches, timing available 0.
- Discovery retry patch adds English aliases for current national teams, independent team-page fallback, failed-cache retry, and diagnostics.
- Retry request: hh520-v35-shadow-20260924-a2

## Required work
1. Wait for/read a2 result from branch v35-shadow-results:
   results/hh520-v35-shadow-20260924-a2.json
2. Inspect goal_timing_diagnostic per match.
3. If candidate URLs exist but extraction fails, implement source-specific adapters before generic LLM extraction:
   - FootyStats team page
   - SoccerSTATS team page
   - SofaScore/365Scores only when timing fields are actually exposed
4. Build a reusable team alias resolver; do not hard-code only one match day.
   Prefer source-provided English name/slug if available from collected HH520 payload; otherwise maintain a cached alias map.
5. Keep Firecrawl usage bounded:
   - no historical timing collection
   - prediction only
   - cache successful team timing by team/date/source
   - maximum bounded searches/scrapes per team
6. Validate on at least 3 matches from 2026-09-24.
   Acceptance:
   - >=1 match with timing available
   - HT/FT top2 generated from timing split model
   - HT/FT top2 may differ from FT primary direction
   - no FT-template fallback
7. Add tests for:
   - failed-cache retry flag
   - independent team-page join
   - missing timing => HTFT PASS
   - six-bin timing => READY
   - historical research path never invokes goal-timing collector
8. Keep all changes shadow-only until forward validation sample is sufficient.

## Do not promote
Do not replace Stable with V3.5 automatically. Return a test report and PR only.
