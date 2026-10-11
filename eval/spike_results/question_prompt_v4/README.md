# Draft audit question prompt v4 (an experiment; nothing is wired into the checklist)

Why: the owner's review of 21 flagged rows of AFI 10-2402 (2026-10-10) found one draft question not in the spirit of its requirement.
Row 2.17.26 holds two sentences. The marked one is "Required courses will be designated by the HAF CARM Program office."; the question asked
"Do MAJCOM/DRUs ensure that Center/Wing level CARM POCs complete the required courses designated by the HAF CARM Program office?",
which folds in the sentence before it and takes the actor from the "Applies to" heading instead of from the sentence.
Two causes in prompt v3: no rule says to ask only about the marked sentence, and rule 2 sends the actor to the "Applies to" line.

## The change (v4), and only this

Prompt only. Same model (`qwen2.5:14b`, temperature 0.1, same server), same inputs, same code gate (rows carrying a skip flag get no question), same schema.

1. New rule after rule 1: ask only about the requirement marked `>> <<`; the sentences around it are background; do not put their duties in the question.
2. Rule 2 replaced: if the requirement itself says who acts, use that; the "Applies to" line is the actor only when the requirement names none; if neither does, ask about "the unit".

Deliberately not in v4 (a later, separate experiment): spelling out abbreviations (row 21 turned "MA" into "Major Army Commands"; the document says Mission Assurance).
The examples inside the new rules are generic ("by the program office", "the commander will"); no name from the test rows appears in the prompt.

## Rules, fixed before any v4 output was generated

**Rows.**
- Set A: the 21 rows the owner reviewed (rows 2 to 22 of `afi_all_flagged_rows.xlsx`; ids in `run_prompt_v4.py`). His verdicts: 17 usable, row 11 a fragment, row 17 no question (withheld by the code gate, so not compared), row 21 a wrong spell-out, row 22 the target.
- Set B: every eligible row of AFI 10-2402, AFI 13-550 and AFI 17-203 whose marked sentence is preceded by other text in the same line of the passage (at least 25 characters after the paragraph number): the rows where the failure can occur. Eligible = has a requirement quote and no skip flag.
- Set C: 40 other eligible rows, seeded (`random.Random(47)`), as a regression guard.
- A row is "changed" when the v4 question differs from the stored v3 question after lowercasing and removing punctuation. The rating sheet holds all changed rows of A, up to 15 changed rows of B and up to 10 of C (seeded order, `random.Random(48)`).

**Measures computed by code, no rating.**
- Noise floor: v3 re-run on Sets A and C with the same prompt; share of questions that differ from the stored v3 question.
- v4 change rate against that noise floor, per set.
- Null rate (model answered null) v3 against v4; `unverified_terms` rate v3 against v4.
- Blend proxy: share of questions with at least two words of 5 or more letters that appear in the sentence before the marked one and not in the marked sentence, its "Applies to" line or its parent paragraph. v3 against v4.

**The owner rates** each sheet row as **better**, **same** or **worse** than the v3 question (side by side), as in the explained-layer rating (WP-45.14 practice).

**Adopt v4** only if all of these hold:
1. The target row (2.17.26, "Required courses will be designated...") gets a question the owner rates better, about the designation of required courses by the HAF CARM Program office, without the previous sentence's duty.
2. Rated rows: worse is at most 10%.
3. Of the Set A rows he rated usable under v3, at most 1 is rated worse.
4. Null rate rises by no more than 5 points, and the `unverified_terms` rate does not rise by more than the noise floor.
5. The blend proxy falls.

If v4 fails rule 1, the next step is to split the two rules into separate arms to see which one does the work; no third prompt is tried before then.
Adopting means changing the prompt in `services/audit_questions.py`; every stored question then reads as stale (new input hash) and the questions for the documents must be regenerated with `reqbot questions --doc`. That regeneration is a separate step with its own approval.

## Run

`PYTHONPATH=. python3 eval/spike_results/question_prompt_v4/run_prompt_v4.py --ollama-url http://192.168.90.100:11434`
Writes `outputs/runs.jsonl`, `outputs/measures.json` and the rating sheet (`~/reqbot-work/checklists/question_prompt_v4_rating.xlsx`).

## v4 result and the next round (written after reading the v4 outputs, before any output of the arms below was generated)

Run 2026-10-11, 267 rows compared (Set A 20, Set B 207, Set C 40); 0 model errors. Noise floor: re-running the same v3 prompt changed 7 of 60 questions (12%); v4 changed 27 of the same 60 (45%) and 107 of 207 in Set B, so the change is real.

Against the adopt rules as registered:
1. **Target row:** v4 asks "Are required courses designated by the HAF CARM Program office?" (v3: the blended question). Met, pending the owner's rating.
2. Rated worse at most 10%: not yet rated.
3. At most 1 usable Set A row worse: rows 7 and 10 lost their named actor ("Does SAF/FM provide a finance representative ...?" became "Is a finance representative provided ...?"). Probably not met.
4. **Null rate rise at most 5 points: not met.** 20 of 267 (7.5%) to 35 of 267 (13.1%), +5.6 points; Set B 9.7% to 16.4%, +6.7. Of the 16 questions that became null, my reading is that about 14 are permissions or descriptions that v3 wrongly turned into questions ("This AFI may be supplemented at any level."), one is a duty inside a table ("Malicious code ... should be categorized as Category 1 or Category 2 incidents") that is now lost; that reading is mine, not the owner's.
5. **Blend proxy falls: not met** (6 of 267 both). In Set A it fell 2 to 1; the proxy also fires on rows whose marked sentence points back ("This coordination should occur ...") where the earlier sentence is needed.

Also seen: 24 questions that said "the unit" under v3 now name the actor from the "Applies to" line; row 21 still spells "MA" out wrongly (out of scope for v4).

v4 is **not adopted**. Rules 3 to 5 are kept exactly as registered for the arms below; a waiver of any of them is the owner's call, with the reason recorded, never mine.

**Round 2, all on the same 268 rows, same model and settings, one question per arm per row:**
- Arm S: the scope rule alone (rule 2 as in v3).
- Arm R: the v4 actor rule alone (no scope rule).
- Arm V5: scope rule + an actor rule rewritten to stop the passive wording: "Name who acts and make that the subject of the question. If the requirement itself says who acts (for example "by the program office" or "the commander will"), use that; otherwise use the "Applies to" line. If neither says, ask about "the unit". Do not use the passive voice."

Added measures (code, no rating): "lost actor" = a v3 question that opens "Does/Do <someone other than the unit>" and an arm question that opens "Is/Are/Was/Were"; "gained actor" = v3 "the unit" and an arm question that names someone; and the list of questions that became null, printed for reading.
A rating sheet is built for the best arm only (the same row selection and seeds as v4).

Run: `PYTHONPATH=. python3 eval/spike_results/question_prompt_v4/run_arms.py --ollama-url http://192.168.90.100:11434`

## Round 2 result (the arms ran 2026-10-11, 267 rows, 0 model errors; written after reading the arm outputs)

| Arm | Null (v3: 20) | New nulls | Lost actor | Gained actor | Unverified (v3: 5) | Blend proxy (v3: 6) | Target row |
|---|---|---|---|---|---|---|---|
| v4 (scope + actor) | 35 | 16 | 3 | 24 | 5 | 6 | fixed |
| S (scope only) | 33 | 14 | 2 | 3 | 5 | 6 | **null** |
| **R (actor rule only)** | **19** | **4** | **1** | **25** | **6** | **5** | **fixed** |
| V5 (scope + no passive) | 32 | 15 | 0 | 36 | 3 | 3 | fixed; but "Do you ..." in 6 questions |

- The scope rule does not help and costs: S withholds the target row and writes passive questions on rows 7 and 10 (the named actor lost). The actor rule alone is what fixes the target.
- Arm R: null rate unchanged, 4 new nulls (three permissions or descriptions, one back-reference: all correct to skip), rows 7 and 10 keep their named actor, 25 questions that said "the unit" now name the actor from the "Applies to" line (for example "Does the HAF CARM program office coordinate ..."). Wording changed on 131 of 267 rows (noise floor 12%), most of it the actor.
- Arm V5 uses "you" as the subject in 6 questions: rejected.
- Limits: the blend proxy is weak (6 suspects in 267 under v3, so the original fault is rare, about 1 in 100); row 21's wrong spell-out is not fixed by any arm ("MA" still invented); R writes "Do the HAF CARM Program office designate ..." (grammar) on the target.

Candidate: **R** = rule 2 of prompt v3 replaced by the v4 actor rule, nothing else. Against the registered adopt rules: 1 met (pending rating), 3 expected (no Set A row regressed by my reading, pending rating), 4 met, 5 met (weakly). Rating sheet: `~/reqbot-work/checklists/question_prompt_rating_actor_rule.xlsx` (all changed Set A rows, up to 15 of B and 10 of C). Rule 2 (worse at most 10%) and the owner's rating of rule 1 decide.
