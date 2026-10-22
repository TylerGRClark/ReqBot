# Clause labeling vs list extraction: pre-registration (written 2026-10-22, before any clause-labeling result exists)

Status: experiment only. Nothing in production changes. Scratch outputs live outside the repository; only this file and the final report are committed.

## Question
The extractor asks one model call per 256-token chunk to LIST the requirements. A diagnosis of 100 misses (private notes) found: about 62% are wording the model does not treat as a requirement (no "shall"; should/may), about 17% plain duties it skipped, about 15 to 21% lost context, and in 70 of 100 cases the extractor produced no row at all for the paragraph. Hypothesis: forcing a label on EVERY clause (instead of asking for a list) with a parent line shown raises recall without an unacceptable loss of precision.

## Data (internal silver set; not in this repository)
1,711 paragraph-sized units from 12 documents, two blind labelers who list every requirement per unit; a requirement counts as real only if BOTH list it. Split by document: TUNE = afi10-2402, afi90-802, dafman17-1305, dafpam90-803, CJCSI 6510.02G, DODI 5200.44. EXAM = afi17-101, dafman17-1203, DODI 5200.48, afi17-203, afman17-204, DODI 8551.01. Prompt wording may be changed on TUNE documents only. EXAM is run ONCE per arm after the wording is frozen; nothing is changed after seeing an exam number. If a bug is found, it is fixed, stated, and ALL arms rerun.

## Matching rule (same as the diagnosis)
A labeled requirement is covered by a text if, after whitespace and case normalisation, one contains the other or at least 60% of the shorter one's words are shared. Strict containment is reported beside it.

## Arms
- B0 baseline: the production rows already stored for each unit (no model call).
- L8: Llama 3.1 8B (the production model), temperature 0.
- L35: the 35B model, temperature 0.
Method for L8 and L35 (identical wording): rules split each unit's text into clauses (sentences; list items on their own; a line ending in a colon is a lead-in). The model gets up to 4 clauses per call plus a context block built by rule only (document heading, paragraph number, and the nearest preceding lead-in line inside the unit), and answers with one label per clause: DUTY, PROHIBITION, PERMISSION, NOT_REQUIREMENT or UNSURE. A clause is "flagged" if its label is anything but NOT_REQUIREMENT (UNSURE is kept, as the standing rule says). The prompt states that third-person duties ("The office coordinates with X"), imperatives, "should" and "may" count, and that headings, definitions, dates, purposes and background do not. The model never writes text; the quote is the clause itself.
- Stage 2 (reported separately, arm L+C): the already-shipped cleanup YES/NO check (35B, strict wording) applied to the flagged clauses of the better L arm.

Limitation stated in advance: units are paragraphs, so a parent lead-in that sits in an earlier paragraph is not available; the context benefit is underestimated.

## Metrics (all computed by one script, exam documents separate from tune)
- Recall = labeled requirements covered by at least one flagged clause (or, for B0, by at least one row) / all labeled requirements.
- Precision = flagged clauses (or rows) that match at least one labeled requirement / all flagged clauses (rows). A lower bound, since labelers can miss; computed identically for B0.
- Unit skip rate = units with at least one labeled requirement and nothing flagged / units with at least one labeled requirement.
- Workload = flagged clauses per 100 labeled requirements; calls; seconds per unit.
- Unreachable share = labeled requirements that no single clause can cover (the requirement spans a lead-in plus an item), counted before any model call.

## Noise floor
Each L arm is run twice on TUNE with a different seeded order of clauses into batches; the difference between the two runs is the noise floor. Any difference smaller than it counts as no difference.

## Decision rules (fixed now)
1. Choose the primary L arm on TUNE: the one with the higher recall among arms whose precision is at least B0 precision minus 5 points. If neither qualifies, the experiment FAILS on TUNE and EXAM is not run.
2. PASS on EXAM: primary arm recall at least B0 recall plus 8 points AND precision at least B0 precision minus 5 points AND the gain is larger than the noise floor.
3. PROMISING (follow-up allowed, not adoption): recall gain of 4 to 7.9 points with the precision condition met.
4. FAIL otherwise. A fail is reported as plainly as a pass.
5. L+C: reported as additive information; success there = recall loss of at most 1 point versus the L arm and precision up at least 5 points.
Per-document results are reported alongside the pooled numbers; a pooled pass driven by one document is called out as such.

## Evidence limits (stated now)
One labeler family (two copies of one model; owner spot check still owed). 12 documents. Prompt written by the same author who reads the results; mitigated by freezing before EXAM and by the fixed rules above. "Precision" is relative to the labelers' lists. Units are paragraph-sized pieces, not whole documents. Not tested: tables and templates, cross-references, cost on a full 300-page document.

## What this does NOT decide
Nothing is adopted from this file. A pass leads to a separate proposal that touches the extractor (a new model call design, which needs the owner's approval before any build).
