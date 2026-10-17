# Kind-aware draft audit questions (spike)

Experiment only. No change to `services/`, any sidecar, the live index or the checklist. Stacked on PR #339 (kind-rules-6, front-matter duties fix), so the experiment sees that fix.
Pre-registration: `PREREGISTRATION.md` (committed before any model call). Plain-words report for Tyler: `report.md`.

## Files

| File | What |
|---|---|
| `PREREGISTRATION.md` | criteria and checks, fixed before the run |
| `kind_questions.py` | pure functions: rules-7 wrapper, pointer decision, recommendation flag, automatic checks, permission prompts v1 to v3 |
| `build_rows.py`, `list_rows.py` | checklist rows (no model) for the six documents |
| `run_experiment.py` | `det` (no model) and `perm` (model calls, serial) |
| `finalize.py`, `make_report.py` | combine rounds, hand grades, write `report.md` |
| `outputs/` | per-round answers, final table, summary, pointers, recommendations, kind changes |
| `tests/unit/test_kind_questions_spike.py` | tests for the pure functions |

Re-run: `python3 build_rows.py <scratch>` then `run_experiment.py <scratch> det`, `perm 1 v1`, `perm 2 v2`, `perm 3 v3 outputs/round3_ids.json`, `finalize.py`, `make_report.py`.
Model: `services.audit_questions.MODEL` (qwen2.5:14b), temperature 0.1, local Ollama from config, 155 calls in total (70 + 67 + 18).

## Prompt rounds

| Round | Change | Rows | Questions | Fail C1-C4 | Fail C5 |
|---|---|---|---|---|---|
| 1 (v1) | first prompt: ask whether the stated limit was met; JSON with grant, limit, question, why_null | 67 (70 incl. 3 later reclassified) | 36 | 3 (C4 x2, one a false alarm from "required" in the source; C1 x1) | 0 |
| 2 (v2) | defined a real limit; null for descriptive may; two worked examples; ban "is it required", "is the limit that" | 67 | 36 | 0 | 1 |
| 3 (v3) | purposes / bare adverbs / always-yes questions are not limits | 18 (8 weak + 10 sentinels) | 18 | 0 | 1 |

Final per row: v3 answer for the 18 rows of round 3, otherwise v2.

## Pre-registered criteria: results

| Criterion | Result |
|---|---|
| (a) rows dropped: 0 | 0. All 1,418 rows keep a before and after; the 31 permission rows without a new question stay as rows |
| (b) new permission questions failing an automatic check, target <= 10% | 0 of 36 on C1-C4 (round 1: 3 of 36 = 8.3%); 1 of 36 on the added C5 (limit not verbatim). Hand reading (not pre-registered as a target): 28 good, 6 weak, 2 wrong, so 22% weak or wrong |
| (c) pointer suppressions that remove a real duty, target 0 | 0 after one fix (first version wrongly suppressed afi10-2402 2.17.29 because "Lead" was not in the verb list). All 11 pointer rows read by hand: 8 suppressed, 3 kept |
| (d) rows whose kind changes under the rules-7 wrapper | 3 of 1,418, all permission to duty_imperative: dafman17-1305 2.15.18, 2.20.6, 2.21; all judged correct |

## Findings worth keeping

- The leading-imperative defect was not the word "authorize": the verb list lacked it, so a "can" in a later sentence made the row a permission. Same cause for "Deny ...".
- Permission rows hold many descriptive "may" statements; the model sorts them well but treats purposes as limits.
- 13 existing permission-row questions would be erased; about 4 of them look useful (see report.md, unsure rows). Proposal: keep the old question when it is a plain "Can ...?" and the new rule says null.
- 2 of 24 recommendation rows are mislabelled by the kind rules ("should" inside an "if" clause or after "determine if").

## Limits

Single run per prompt, no noise floor. Hand grades are by the agent that wrote the prompt. C1-C4 measure form only. The 3 rules-7 rows were still run through the model in round 1 (their answers are not used).

## Round 2 (after #339 merged; rebased on origin/main)

Pre-registration: `ROUND2_PREREGISTRATION.md`. Changes: (1) fallback keeps the existing question when the permission rule gives none and it is grounded, has no duty words and does not open with Do/Does/Did; (2) deterministic purpose / bare-adverb guard on the reported limit (plus prompt v4 on 16 rows); (3) if-clause "should" fix in the wrapper. Run: `pick_round4.py`, `run_experiment.py <scratch> perm 4 v4 outputs/round4_ids.json`, `round2_final.py <scratch>`, `make_report2.py`. Round-1 report kept as `report_round1.md`.

Results: 9 of the 13 vanished questions return (8 fallback, 1 new model question), 4 stay gone; 6 of 8 weak/wrong round-1 questions caught or fixed (5 guard, 1 prompt), 0 of 28 good rejected (first draft rejected 1: "only"); only afi10-2402 3.3.2 and afi17-203 3.4.4.3 move under the if-clause fix; 16 model calls, 1 prompt round. 59 rows differ from the live question or flag, 0 dropped (see report.md).

## Round 3 (after the independent reviewer graded round 2 as 18 good / 10 weak / 3 wrong)

Pre-registration: `ROUND3_PREREGISTRATION.md`. Checks in `round3_checks.py` (qualifiers kept, subject kept, no dangling pronoun, no future or other-party question, no generic limit, no circular scope); prompt v5 and v6 on the 13 flagged rows (14 calls, 2 rounds). Run: `pick_round3.py`, `run_experiment.py <scratch> perm 5 v5 outputs/round5_ids.json`, `pick_round6.py`, `perm 6 v6 outputs/round6_ids.json`, `round3_final.py <scratch>`, `make_report3.py`. Results in `report.md`: 3 wrong rows now none / today / rewritten; 8 of 10 weak end as no question or today; 2 weak rewritten (unproven); 0 good rows turned null; afi10-2402 3.3.3.3.4 restored. Self-grades are not given: round 2 showed they run too generous. Checks are fitted to these outputs.

## Round 4 (part A fixes on the six AFIs; part B held-out test on seven documents)

Pre-registration and freeze commit: `ROUND4_PREREGISTRATION.md`. Code: `round4_checks.py` (antecedent-aware prompt v7, bare-pronoun scope, for-any scope, head subject, numeric bound, waiver template, `decide()`), `run_round4.py`, `held_out.py`, `part_a.py`, `make_report4.py`. Outputs: `outputs/round4_partA.json`, `round4_partB_rows.json`, `round4_partB_summary.json`. Part B: 1,181 rows, 0 dropped, 102 model calls, 13 of 94 model questions rejected by the checks (14%), 0 qualifier violations. No self-grades; blind reviewer to grade. Earlier reports: `report_round1.md`, `report_round3.md`.

## Round 5 (additive-only policy; main-verb gate; document gate; fresh document dafi36-2903)

Pre-registration and freeze commit: `ROUND5_PREREGISTRATION.md`. Code: `round5_checks.py`, `run_round5.py`, `make_report5.py`. Outputs: `outputs/round5_regress_*.json` (the seven earlier documents, no longer a clean test), `outputs/round5_fresh_*.json` (dafi36-2903, run once with frozen rules; 92 of 311 gate-passing permission rows asked). Calls: 35 regression + 97 fresh = 132 (cap 150). Findings, honestly: additive-only works as designed; pointer rule suppresses real duties on the fresh document (target not met); check rejection rate rose to 42% on the fresh document; the fresh document had no live questions, so replace/keep paths were untested there. Earlier report: `report_round4.md`.
