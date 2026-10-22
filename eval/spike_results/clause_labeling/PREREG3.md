# Clause labeling, third test: a whole fresh document, end to end (pre-registration, 2026-10-22, before any run)

Why: tests 1 and 2 used sampled paragraphs and a small page set. This test runs the frozen method over every chunk of one complete document that no earlier test or tuning used (dafman17-1304, stored run 20261015_043719), and compares with the production rows of the same document. No hand labels exist for it, so recall cannot be computed; the question is whether the extra rows are real and whether the workload stays reasonable.

## Method (frozen)
Frozen prompt (sha256 b9b20379...), splitter and context rule from the first test. Model: the 35B only (the 8B failed the precision rule in test 2). Input: the stored chunk file of the run (raw chunk text); every chunk is split into clauses and labeled; flagged = anything but NOT_REQUIREMENT. Report time, calls, clauses.

## Comparison
Production rows = the stored normalized requirement rows of the same run. A clause "matches" a production row by the same rule as the first test (containment or 60% word overlap). Three groups: BOTH (a flagged clause matches a row), NEW (flagged clause matching no row), PROD-ONLY (a production row matched by no flagged clause).

## Blind review
A separate reviewer, shown no group names, judges a seeded shuffled sample: 60 NEW clauses, 40 PROD-ONLY rows, 20 BOTH items (calibration), each with its paragraph, as REAL / PARTIAL / NOT_REAL / UNSURE under the labeling rules.

## Decision rules (fixed now)
PASS needs all of: (a) of the NEW sample, at least 60% REAL, or at least 75% REAL plus PARTIAL; (b) total flagged clauses at most 1.6 times the number of production rows; (c) at least 90% of the BOTH calibration items judged REAL or PARTIAL; (d) full-document run completes without unparsed batches exceeding 2% of batches. The PROD-ONLY result is reported either way (it measures what labeling would lose): if more than 50% of the sample is REAL, say so as a warning that the union of both methods is needed.
FAIL otherwise. Report plainly.

## Limits stated now
One document, no hand labels, one reviewer, reviewer is a model; recall is not measured here; the stored production rows are after Step D so some PROD-ONLY rows may be ones Step D keeps for reasons not visible here.
