# Round 2 pre-registration (approved by Tyler; written before any round-2 model call)

Base: origin/main at 77909db (PR #339 merged). Same guardrails as round 1: experiment folder only; `services/`, sidecars, index and checklist untouched.

## Changes under test

1. **Fallback.** When the permission rule says null (or the guard below rejects a question) and the row has an existing question, keep the existing question unchanged if it (a) is grounded (`unverified_terms` empty against the row's material), (b) has no duty words ("does the unit", must, shall, required, has/needs to), and (c) is not duty-shaped for a may: it must not open with Do/Does/Did. Permission-shaped openings (Can/May/Could) and neutral ones (Is/Are) pass.
2. **Purpose-not-limit guard** (deterministic, on the model's reported `limit`): reject when the limit is only a purpose (starts with "to <verb>", "in order to", "so as to", or "for" + additional/further/guidance/information/reference/use) or a bare adverb (one word ending -ly, or "as required / as necessary / as appropriate / as needed / when necessary / when required / if required / when applicable / if necessary"). Possibly one prompt tightening (v4) if the guard alone does not reach the target. The guard was written after reading round-1 outputs, so it is partly fitted to them: the number below is an upper bound on how it will do on new rows.
3. **If-clause "should".** In the experiment's wrapper, a "should" that follows if / whether / determine / assess / decide earlier in the sentence, or is followed by those/these/this/that/such, is not a recommendation. The row gets no "recommended" flag; its kind is recomputed with that "should" masked.

## Criteria (fixed now)

- (T1) Report how many of the 13 vanished permission-row questions come back; 0 old "Does ... " questions kept for a genuine grant (hand check of each kept question).
- (T2) Of the 8 rows hand-graded weak or wrong in round 1 (outputs/permission_final.json, hand_grade weak/wrong): at least 6 caught (guard rejects) or fixed (re-run answer graded good, or a justified null). Of the 28 graded good: at most 2 wrongly rejected by the guard. Both counts reported exactly, with every false alarm listed.
- (T3) Rows whose recommendation flag or kind moves under the wrapper: exactly afi10-2402 3.3.2 and afi17-203 3.4.4.3; any other row that moves is listed and counts as a failure.
- (T4) At most 2 prompt rounds, only rows whose output can change are re-run, at most 40 calls.

## Grading

Every new question (every row whose final question differs from today's live question) is hand graded again good / weak / wrong, from a shuffled list that omits the earlier grades. The grader is the same agent that wrote the prompt and remembers some earlier grades, so "blind" is partial; stated in the report.

## Comparison baseline

"Before" in the final list is the row's live question today (the checklist `audit_question`), not round 1.
