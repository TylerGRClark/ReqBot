# Clause labeling, round 2 (gold2): result (2026-10-22)

Pre-registered in PREREG4.md and PREREG4_AMEND1.md (committed before any label or run). Two labeler families (Claude and Codex) labeled 720 paragraphs from 9 documents never used in earlier tuning or tests; a requirement is real if both list it (488 requirements on the eight original documents, 92% overlap; plus CNSSI_No1253). The owner ruled 31 items: agreed items 16 real / 1 partial / 1 not; one-family-only items about half real (permissions count, per the owner).

## Tuning (TUNE documents only; 35B; noise floor about 1.5 points)
Two tuning stages (gold2 TUNE, then gold2 TUNE plus silver TUNE under Amendment 1): nine candidate changes (batch size 1; duty-vs-description wording; document name and tier tag in context; permission wording; description wording; lead-in rule; one-line reason; worked examples from the other pool; a full prompt written by Codex). None beat the original prompt by more than the noise without costing the other metric: each fixed one error type and created another (recall +2.2 / precision -1.1 for the permission wording; precision +1 / silver recall -1 for the lead-in rule; the reason line cost 4 points of silver recall and was 1.5x slower). Stop rule fired after two reverted rounds; the original prompt (sha256 b9b20379...) was frozen and goes to EXAM unchanged. Rounds c to f were run as post-freeze diagnostics only. Logs in `scripts4/TUNE_LOG3.md`.

## EXAM (sealed; run once; 3 seeded batch orders per arm; CNSSI_No1253 included)
Documents: dafman17-1301, afi13-550, DODI 5200.01, NIST.SP.800-125, CNSSI_No1253 (80 paragraphs each; CNSSI is mostly control-baseline tables, only 10 agreed requirements).

| arm (pooled, 5 documents, 250 labeled requirements) | recall | precision | paragraphs with nothing flagged | flagged per 100 labeled |
|---|---|---|---|---|
| B0 stored production rows | 78.0% | 67.8% | 17.1% | 113 |
| 35B labeling every clause | 96.4% (+18.4) | 91.0% (+23.2) | 2.0% | 104 |
| 8B labeling every clause | 94.8% (+16.8) | 73.4% (+5.6) | 3.9% | 128 |

Without CNSSI (4 documents, 240 requirements): B0 78.8 / 75.9; 35B 96.2 / 93.4; 8B 95.4 / 78.2.
Noise floor between the three seeds: 35B 1.2 points recall, 1.9 precision; 8B 0.8 and 2.5.
Per document recall, B0 to 35B: dafman17-1301 85.2 to 92.8; afi13-550 69.6 to 100.0; DODI 5200.01 77.4 to 97.8; NIST 800-125 85.7 to 93.7; CNSSI 60.0 to 100.0. Precision, B0 to 35B: 83.9 to 94.0; 88.9 to 95.0; 78.7 to 94.8; 39.5 to 82.5; 15.8 to 57.7.
Table-grid paragraphs (27 of them, none with an agreed requirement): the stored extractor made 11 rows from them, the 35B 1, the 8B about 11.

## Verdict against the pre-registered rules (35B): PASS
Recall at least B0 + 8: +18.4. Precision at least B0 + 10: +23.2. Gain above the noise floor: yes (1.2 and 1.9). No single EXAM document worse than B0 by more than 5 points on recall: every document improved (smallest +7.6). The 8B arm also meets the written rules (recall +16.8, precision +5.6 with recall at least +12) but its precision gain is small (+2.3 without CNSSI, equal to the noise floor), so the 35B is the choice. The shipped 35B YES/NO check on top of the 35B adds nothing (recall -0.4, precision +0.5).
Regression checks: the prompt did not change from the first frozen version, so the silver EXAM result (recall 95.6/92.7, precision 77.5/92.6) and the 74-obligation set (35B 94.6 / 93.7) stand as run.

## Limits
Truth comes from two model families and 31 owner rulings, not a full human audit. Precision is relative to the agreed lists, so it is a lower bound (a blind audit in the first round put real precision a few points higher for every arm). Paragraph-sized units; whole-document behavior was tested once (dafman17-1304, 59% of the added rows real, below the 60% bar). CNSSI has only 10 agreed requirements, so its per-document numbers are coarse. Cost on a full library was estimated, not run.
