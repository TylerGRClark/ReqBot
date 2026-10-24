# PREREG9: confirmation of the "checklist lead-in" labeler context (no tuning)

Written 2026-10-23, before any run on these documents. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything.

## Question
PREREG8 (PR #372) found that showing the labeler the checklist's lead-in finder (`pipeline/lead_in.find_lead_in`, arm `rule`) instead of the nearest-colon-clause lead-in passed on seven documents. Does it hold on four documents no arm has ever run?

## Setup (frozen)
- Base: origin/main 3c0990a plus the PROPOSED commit 5b5c511 (same code as the driver's `rule` arm). Worktree `~/wt-confirm`.
- Documents (whole documents, never run in any PREREG8 arm): dafman17-1301, dafman17-1203, NIST.SP.800-125, CNSSI_No1253 (table-heavy; reported separately).
- Model `ornith:35b` (config `extraction_model`), frozen prompt v3 (sha b9b20379...), batch 4, num_ctx 8192, num_predict 300. Driver `label_ctx_run.py` unchanged apart from a `--docs` switch. Arms: `control` then `rule`, one model job at a time, never two. No repeat arm: the PREREG8 noise floor stands (repeat control differed on 1 of 2,289 clauses; recall -0.16, precision -0.02).
- No tuning of any kind between arms or after seeing results.

## Gold (internal files under ~/reqbot-work/scratch, not committed)
- dafman17-1301, NIST.SP.800-125: gold2 exam units, requirements both labeler families listed (`gold2/gold_both.json`, REPORT4).
- CNSSI_No1253: gold2 extension (`gold2_cnssi/gold_both_cnssi.json`): 80 units, only 10 agreed requirements, so coarse.
- dafman17-1203: no gold2 units; the silver exam units (`silver/units*.jsonl`, requirements both blind copies list, 0.8 match rule, as in PREREG8).
- Scoring is the PREREG8 scorer unchanged (`label_ctx_metrics.py`: recall = gold requirements covered by a row; precision = rows inside the sampled gold paragraphs matching a gold requirement; match = containment or 0.6 token overlap). Only the document list and the CNSSI gold file are added. Gold covers sampled paragraphs only; rows outside them are unscored.

## Pass rule (all must hold, pooled over the four documents)
1. Recall(rule) >= Recall(control) - 1.0 point.
2. Precision(rule) >= Precision(control) - 1.0 point. (1.0 = the noise floor, rounded up.)
3. Net flips against gold: among requirement flips (row <-> not a requirement) whose clause lies inside a gold unit, "correct" > "wrong" (verdict as in PREREG8: a new row that matches gold, or a dropped row that does not, is correct).
Otherwise FAIL. A tie or fewer than 4 judged flips is "not confirmed", reported as such.
CNSSI_No1253 is also reported alone (same three numbers) because tables were untested; it is part of the pooled pass rule, and a pooled pass driven by a CNSSI loss/gain is called out in the report. Pooled-without-CNSSI is also printed.

## Also reported (not part of pass)
- Every requirement flip printed with old context, new context, label change and gold status (inside a gold unit or not); un-judged flips are listed for hand reading.
- Number-start failure: over the four documents, clauses whose text begins with a bare number followed by a word and no list marker (regex `^\s*\d+\s+[A-Za-z]`, e.g. "24 AF is designated as ...") and that receive a non-empty lead-in under `rule`: how many, and of those, how many I judge (by reading) to be plain sentences wrongly given a lead-in. Same count for the "13. (b) The ... provides ..." form (digit-dot marker then letter-paren, sentence-like). Counted separately, all hand-read, author-judged.
- Label agreement control vs rule (all clauses and changed clauses), rows, seconds, unparsed/failed batches (any unparsed or failed batch invalidates that arm and it is rerun).

## Limits stated in advance
Four documents, one run per arm; gold is two model families (precision a lower bound); CNSSI gold has 10 requirements; dafman17-1203 gold is silver (older, weaker); the author reads the flips and the number-start cases, not a blind reviewer; REPORT4 exposed the gold2 exam units to this frozen prompt earlier (not tuned).
