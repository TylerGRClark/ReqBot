# Pre-registration: kind-aware draft audit questions (spike)

Written and committed before any model call. Nothing here changes `services/`, a sidecar, the live index or the checklist; outputs are files in this folder only.

Base: branch `fix/kind-front-matter-duties` (PR #339, kind-rules-6), so the front-matter fix is in effect.

## Data

Six documents: afi10-2402, afi13-550, afi17-203, afman17-2101, afpd_17-1, dafman17-1305. Rows from `python3 cli/reqbot.py checklist --doc DOC --format json` (no model, live index and run folders). Kinds from `services/requirement_kind.classify`. "Before" question = the row's `audit_question`.

## What is tested

1. **permission**: a genuine grant or limit is a boundary. When the row states a limit or condition, ask whether it was met when the permission is used. If the row states none, or the "may" is descriptive ("may include", "may vary", a possibility), keep null and record why. One model call per permission row (~70 rows, serial).
2. **recommendation**: keep the existing question unchanged; add a separate field `strength = "recommended"` plus a plain note. No model call.
3. **pointer**: deterministic. No question plus a reason when the row only points elsewhere. If the row also states a duty (a duty word, or a leading command, in a sentence that is not the pointer sentence), keep the existing duty question. No model call.
4. **rules-7 wrapper** (experiment folder only): a leading imperative verb the shared verb list lacks ("Authorize ...", "Deny ...") makes the row a duty_imperative instead of a permission picked up from a later sentence. Implemented by classifying with an extended verb set; every row of the six documents whose kind changes is listed with before/after.

## Automatic checks per new permission question

- C1 grounded: `services.audit_questions.unverified_terms(question, row_material)` is empty.
- C2 no placeholder: no standalone `X`, no "the document allows" / "what the document allows" filler, no bracket or angle-bracket slots, no "..." slot.
- C3 yes/no: ends with "?" and opens with an auxiliary (does/do/is/are/was/were/has/have/did/can/could/will/would/should) or with a conditional lead ("When/If/Where/Once/Upon/After ..., " then an auxiliary).
- C4 not a duty: no "does the unit" / "do the unit", "must", "shall", "required", "has to", "needs to".
- C5 (added, reported separately and combined): the `limit` span the model reports must appear verbatim in the row's `source_quote`.

## Criteria (fixed now)

- (a) Rows dropped: 0. Every row of the six documents appears in the output with its before and after.
- (b) New permission questions failing at least one automatic check: report the count; target <= 10% of new permission questions (C1 to C4; C5 reported alongside).
- (c) Pointer suppressions that remove a real duty: target 0; every suppressed row is read by hand.
- (d) Rows whose kind changes under the rules-7 wrapper: list all, with a hand judgement on each.

## Procedure limits

At most 3 prompt rounds. Each round records its prompt changes and failure counts in `README.md`. A later round re-runs only rows that failed or whose behaviour the change targets, unless the change is structural (then all rows). Model: `services.audit_questions.MODEL` at temperature 0.1, local Ollama URL from config, calls serial. Roughly 150 calls in total.

## Honest limits stated in advance

Automatic checks measure form, not truth: a question can pass all five and still be a poor audit question. Whether a "may" is a real grant is a judgement; the hand reading of every after-question is done by the agent that wrote the prompt, not independently. Tyler's review is the real test.
