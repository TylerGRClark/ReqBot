# Clause labeling, second test on an independent labeled set: pre-registration (2026-10-22, before any run)

Why: the first test used the silver set (labels from two copies of one model family) and a prompt tuned on part of it. This test uses an older, independent set: 74 hand-checked obligations on 38 chunks of three documents (afman17-2101, DODI 8410.03, NIST SP 800-125), scored by the project's existing dev scorer (WP-45.7 / WP-45.11 code). Those pages were used to design the production prompt, so the baseline is, if anything, favorable to the current method.

## Frozen method (no changes allowed)
The frozen prompt, splitter, context rule and label rules from the first test (`scripts/prompt_FROZEN.txt`, sha256 b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4). Applied to each labeled chunk's raw text. A clause is flagged if its label is not NOT_REQUIREMENT. The flagged clause text is the quote.

## Baseline
The production extraction rows after normalizing (Step D) from the six stored 8B runs (ctl8b r1 to r6), scored with the same scorer; the mean over the six is the baseline. (Run r7 excluded, as in WP-45.11.)

## Arms
L8 (llama3.1 8B) and L35 (35B), temperature 0, each run twice with different seeded batch orders (noise floor).

## Metrics
Recall of the 74 (obligations whose scorer status is not 'none'), precision by the scorer's own precision function applied to the flagged clauses as records, number of the 24 never-found obligations (found by no baseline run) that an arm finds, flagged rows per 100 obligations.

## Decision rules (fixed now)
PASS: an arm's recall (mean of its two runs) is at least baseline mean plus 8 points AND its precision is at least baseline precision minus 5 points AND the gain is larger than the arm's noise floor. PROMISING: gain 4 to 7.9 points with the precision condition met. FAIL otherwise. The number of the 24 never-found obligations found is reported, not a pass condition.

## Limits stated now
74 obligations: one obligation is 1.4 points. Three documents. The scorer was built for the old pipeline; clause quotes are matched to labeled obligations by its rules. Pages were used to design the baseline prompt. No tuning of the frozen method on these pages is allowed; if it fails here, that is the result.
