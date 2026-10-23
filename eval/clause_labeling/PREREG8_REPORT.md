# PREREG8 report: labeler lead-in context (Q1) and speed settings (Q2)

Run 2026-10-23 on main c4b8136, `ornith:35b`, frozen prompt v3 (sha b9b20379... in every arm), 7 whole documents, 2,289 clauses, one model job at a time. Rules and pass lines: `PREREG8.md` (committed before any run; no amendment). Numbers: `PREREG8_metrics.json`, every requirement flip with both contexts: `PREREG8_flips.json`. Driver `label_ctx_run.py`, scorer `label_ctx_metrics.py` (scoring functions copied unchanged from PREREG6/7).

## Answers
- **Q1 (lead-in from `find_lead_in`): PASS.** Recall 95.0 -> 95.7 (+0.6), precision 87.3 -> 88.5 (+1.2). Of 388 clauses whose context changed, 26 flipped between "row" and "not a requirement"; 23 lie in gold units: 16 judged correct, 7 wrong. No time cost (877 s vs 875 s).
- **Q2 (speed settings): FAIL on speed, every setting.** Quality is fine for batch 8, batch 16, num_ctx 4096 and num_predict 100 on their own, but the best single speedup is batch 16 at 1.18x (needs 1.5x). The pre-registered combination (b16 + c4096 + p100) is unusable: num_predict 100 is too small for 16 answers, 143 of 147 batches went unparsed.

## Q1 numbers (pooled, 624 gold requirements, 709 rows in gold units for control)
| arm | recall | precision | rows | seconds |
|---|---|---|---|---|
| control | 95.03 | 87.31 | 1188 | 875 |
| control2 (repeat) | 94.87 | 87.29 | 1187 | 866 |
| rule | 95.67 | 88.51 | 1178 | 877 |
Noise floor: control2 differs from control on 1 clause of 2,289 (99.96% identical), recall -0.16, precision -0.02. So the labeler is essentially deterministic here and N = 1.0 (the minimum in the rule). Q1-a (recall >= -1.0) holds, Q1-b (precision >= -1.0) holds. Q1-c: 23 flips in gold units, correct 16 > wrong 7 (at least 6 required: met). Label agreement control vs rule: 96.9% over all clauses; on the 388 changed clauses 360 keep the same label (92.8%); 28 change label, 26 of them row/not-row (14 to row, 12 to not-requirement). List-item rows only: precision 83.9 -> 85.5 (224 -> 221 list-item rows in gold units; the "recall" of that subset is not meaningful and not used).
Exposure per document of the 388 changes: afi17-203 15, afi13-550 66, DODI 5200.01 39, afi17-101 83, afman17-204 49, DODI 5200.48 92, DODI 8551.01 44.

## What the flips look like (all 26 are in `PREREG8_flips.json`)
- Good: lists whose lead-in sat in an earlier chunk or after another colon line now get their real parent. afman17-204: five duty items under "Support the development, revision ... by 81 TRSS/TSQ" went from not-a-requirement to DUTY, all matching gold. DODI 8551.01 / DODI 5200.48: items "(1)..(4) Access to such information ..." under "CUI ... may be released ..." and purpose statements "3. (a) Enhance baseline ..." went from DUTY to not-a-requirement, both right against gold.
- Bad: DODI 5200.48 "(3)/(4) Is not restricted ... / Is not otherwise prohibited ..." under "CUI access should be encouraged and permitted to the extent..." became DUTY (gold says no); DODI 5200.01 "(1)/(2) ... review requests" under "Directs and administers a DoD Mandatory Declassification Review Program" became DUTY (gold no); afi17-203 "24 AF is designated as the AF CNDSP ..." got the lead-in "24 AF/CC, when acting as ...:" because a clause that starts with a number is treated as a list item by the rule (gold no); DODI 8551.01 "13. (b) The RT&E ... provides ..." likewise.
- Flips are clustered in a few lists (afman17-204 5, DODI 5200.48 9, DODI 8551.01 5), so 16 vs 7 is closer to about 8 independent groups than 23 independent items; the direction is clear, the size is soft. 3 of the 26 flips lie outside gold units and are not scored. (The author, not a blind reviewer, read the lists.)
- A third thing the rule changes besides the lead-in rule: control shows the lead-in as the full clause text with marker and double spaces; the rule shows the last sentence without marker.

## Q2 numbers (sum over 7 documents; control seconds = mean of control and control2 = 870)
| arm | recall | precision | label agreement with control (row/not-row) | unparsed | seconds | speedup | verdict |
|---|---|---|---|---|---|---|---|
| b8 | 94.87 | 87.18 | 96.2% | 0 | 825 | 1.05x | quality ok, speed FAIL |
| b16 | 94.55 | 88.51 | 94.9% | 0 | 739 | 1.18x | quality ok, speed FAIL |
| c4096 | 95.19 | 87.68 | 99.4% | 0 | 833 | 1.04x | quality ok, speed FAIL |
| p100 | 95.19 | 87.68 | 99.4% | 0 | 832 | 1.05x | quality ok, speed FAIL |
| combo (b16+c4096+p100) | 99.7 | 51.4 | 52% | 143 of 147 batches | 700 | 1.24x | FAIL (unparsed) |
The prompt sha was the same in every arm. Why so little speed-up: time follows the number of clauses (reading each clause and writing its label), not the number of calls; cutting calls from 575 to 147 saves only 16% (the server's per-call overhead is small). The 1.5x line is not reachable by these settings. Agreement for batch 8/16 with control (95 to 96%) is below the repeat-control floor (99.96%), i.e. these change individual labels while keeping totals; c4096 and p100 change 0.6% of labels (an effect of numerical differences with a smaller context window, not a systematic one).
The combination was run exactly as pre-registered (all four settings passed quality). Its failure is mechanical: a 16-item answer needs more than 100 tokens, so it is cut, cannot be parsed, and every clause becomes UNSURE (recall 99.7, precision 51.4 are an artifact). I did not run a rescue combination (b16 with c4096 only): by the arithmetic above its speed would be about 1.2x and cannot reach 1.5x.

## Resume ledger (checked in `pipeline/clause_labeling.py`)
`input_hash = sha256(model + "\n" + filled prompt)`; a ledger record is reused only when both its clause keys and its input hash match. Changing the lead-in rule changes the filled prompt for the changed clauses (and so their batches' hashes): those batches are relabeled, the rest reused. Changing the batch size changes every batch's clause keys: nothing reused. num_ctx and num_predict are NOT in the hash, so an old ledger would be silently reused after changing them (here that would have changed 0.6% of labels at most). Old ledgers need no migration: unmatched records are simply replaced when the run rewrites the ledger.

## Recommendation
1. Adopt the rule lead-in for the labeler (Q1 passed). Needs Tyler's decision: it changes what the labeler sees and a library re-run relabels about 17% of clauses' batches (a full re-run is planned anyway). Frozen prompt text and sha unchanged. A separate, proposed code commit is on this branch.
2. Do not change batch size, num_ctx or num_predict: no meaningful speed gain; never combine a small num_predict with a large batch.
3. Optional follow-up (not tested): the wrong flips come from the rule treating a number-leading plain sentence as a list item and from stale colon lines; tightening `find_lead_in` there is a separate experiment.

## Limits
Seven documents, one run per arm (plus one repeat of control, which was nearly bit-identical); 624 gold requirements from two model families, so precision is a lower bound; only sampled paragraphs carry gold (23 of 26 flips judged; clustered); gold units for the exam documents were exposed to this frozen prompt in REPORT4 (not tuned), and afi17-203/afi13-550 were also the PREREG6/7 sealed pair. Nothing was tuned here. Reserve exam documents never run with any arm: dafman17-1301, dafman17-1203, NIST.SP.800-125, CNSSI_No1253 (skipped: 2,692 clauses, mostly tables; the effect of the rule on table lines is therefore untested). No untouched exam set remains for a final confirmation except that reserve. Timing is wall-clock on a server whose other users are unknown.
