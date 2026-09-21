# HH520 Decision Filter V2.0 — 2026-08 + 2026-09 Joint Error Analysis

Status: **RESEARCH_ONLY / CANDIDATE_ONLY**  
Stable access: **FORBIDDEN**  
Source windows:
- Discovery: 2026-08-01..2026-08-31
- Historical Shadow / independent validation: 2026-09-01..2026-09-20

## Dataset

- August evaluable matches: 402
- September evaluable matches: 302
- Total evaluable labels: **704**
- August WDL baseline: **53.98%**
- September WDL baseline: **47.02%**
- Frozen August candidate rules: 29
- September Shadow result: **22 PASS / 7 HOLD**

## Strongest cross-window WDL positive evidence

| Factor | Aug | Sep | Pooled | Worst-window uplift |
|---|---:|---:|---:|---:|
| away_odds_bucket <1.50 | 84.21% (38) | 72.41% (29) | **79.10% (67)** | +25.39pp |
| probability_concentration >=60% | 79.17% (48) | 70.59% (34) | **75.61% (82)** | +23.57pp |
| structure = 强优 | 85.29% (34) | 70.00% (20) | **79.63% (54)** | +22.98pp |
| pattern = 🔶风控赔率 | 71.67% (60) | 68.29% (41) | **70.30% (101)** | +17.69pp |
| home_odds_bucket <1.50 | 71.05% (76) | 66.67% (51) | **69.29% (127)** | +17.07pp |
| handicap = 客让半一低水/一球高水 | 75.00% (36) | 58.33% (24) | **68.33% (60)** | +11.31pp |
| rating = B+ | 66.30% (92) | 58.11% (74) | **62.65% (166)** | +11.09pp |
| risk = 低 | 63.83% (94) | 61.19% (67) | **62.73% (161)** | +9.85pp |

## Persistent WDL negative evidence

| Factor | Aug | Sep | Pooled |
|---|---:|---:|---:|
| probability_concentration <40% | 38.00% (50) | 28.57% (35) | **34.12% (85)** |
| pattern = ⚡ 极端 | 42.86% (35) | 25.00% (32) | **34.33% (67)** |
| pattern = ⚠️ 边缘 | 36.67% (30) | 37.50% (16) | **36.96% (46)** |
| away_odds_bucket 2.20-2.99 | 37.93% (87) | 35.48% (62) | **36.91% (149)** |
| home_odds_bucket 2.20-2.99 | 38.82% (85) | 35.19% (54) | **37.41% (139)** |
| away_odds_bucket 1.80-2.19 | 46.67% (45) | 32.50% (40) | **40.00% (85)** |
| home_odds_bucket 1.80-2.19 | 48.19% (83) | 33.90% (59) | **42.25% (142)** |
| risk = 中高 | 41.30% (92) | 34.38% (64) | **38.46% (156)** |

## Decision Filter V2 candidate policy

1. **Hard PASS**
   - probability_concentration <40%
   - pattern = ⚡ 极端

2. **Positive evidence**
   - away odds <1.50
   - probability concentration >=60%
   - structure = 强优
   - pattern = 🔶风控赔率
   - home odds <1.50
   - strong away handicap bucket
   - rating B+
   - risk = 低

3. **Negative evidence**
   - ⚠️ 边缘
   - home/away mid-odds 1.80–2.99
   - risk = 中高
   - weak home handicap bucket

4. **Decision**
   - at least one positive signal is required
   - weighted score >= 0.12
   - any hard-PASS condition forces PASS
   - no automatic Stable promotion

## Important interpretation

The pooled percentages above are **factor-level conditional accuracies**, not the accuracy of the final combined filter. Factor overlap means they cannot be added together or treated as independent probabilities. The candidate filter therefore remains Research-only until match-level forward validation measures its actual coverage and accuracy.

## Shadow evidence retained

Strongest frozen rules that also passed historical Shadow include CR-009, CR-002, CR-004, CR-001, CR-010, CR-015, CR-012, CR-023, CR-026 and related HT/FT rules.

HOLD evidence:
- Norway / Portugal league-specific rules: insufficient Shadow sample.
- risk=中低 WDL: 40.00%, below Sep baseline.
- Netherlands league WDL/HTFT Top2: 37.5%, below Sep baseline and insufficient sample.

## Result

Decision Filter V2 candidate is now based on **cross-window stability**, not one-period peak accuracy. Stable remains unchanged. The next measurement target is the actual combined filter performance on forward data from 2026-09-21 onward.
