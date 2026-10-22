# Clause labeling, third test (whole fresh document, dafman17-1304): result (2026-10-22)

Pre-registered in PREREG3.md (commit before any run). Frozen method, 35B only, every chunk of the document (148 chunks, 870 clauses, 218 calls, 0 unparsed batches, about 9.4 minutes of model time on a shared GPU). Blind review by a separate model session of all 59 NEW clauses, 40 of 109 PROD-ONLY rows, and 20 BOTH items (`scripts3/`).

## Verdict: FAIL on rule (a), by 0.7 point; the other three rules pass
| Group | n | REAL | PARTIAL | NOT_REAL | UNSURE |
|---|---|---|---|---|---|
| NEW (flagged by labeling, no production row) | 59 (all of them) | 35 (59.3%) | 1 | 18 | 5 |
| PROD-ONLY (production row, no flagged clause) | 40 of 109 | 4 (10%) | 1 | 32 | 3 |
| BOTH (calibration) | 20 | 18 (90%) | 0 | 1 | 1 |

- (a) NEW needs at least 60% REAL or 75% REAL+PARTIAL: 59.3% and 61%. NOT MET (a 59-item group has about +/- 12 points of uncertainty, so this is a coin flip, but the rule was fixed in advance and is reported as written).
- (b) flagged / production rows = 402 / 450 = 0.89, limit 1.6: met.
- (c) calibration BOTH at least 90% REAL or PARTIAL: 18 of 20 = 90%: met, exactly at the limit.
- (d) unparsed batches 0 of 218: met.
- PROD-ONLY warning (over 50% real) not triggered: only 10% of the sample is real.

## What it means (read as estimates, not measurements)
- The 109 production rows that labeling does not flag are mostly not requirements (about 10% real, so roughly 11 real requirements would be lost out of 450 rows). This is where the precision gain comes from.
- The 59 NEW clauses are about 60% real, so roughly 35 real requirements are added.
- Rough totals for this document: production about 320 real of 450 rows (71% real); labeling about 345 real of 402 flagged (86%). Fewer rows, more of them real, but the added rows are only 60% real.
- Cost: under 10 minutes for a 450-row document with the 35B.

## Limits
One document, no hand labels (recall is not measured), one model reviewer who listed many judgment calls (scope sentences, system descriptions, tier-tagged descriptions, pointers to forms), 9 UNSURE items, front-matter not analyzed separately. Production rows are after Step D, so some PROD-ONLY rows may be kept for reasons not visible here.

## Overall across the three tests
Test 1 (silver set, EXAM): pass. Test 2 (independent 74-obligation set): 35B pass, 8B fail on precision. Test 3 (whole fresh document, no labels): fail on one rule by 0.7 point, with the other three met. The consistent picture is: the 35B labeling every clause finds clearly more of the known requirements and returns fewer, cleaner rows. What is not shown: the quality of the added rows on a whole document is only about 60% real, which is a review-workload question for the owner, not proof of a better pipeline.
