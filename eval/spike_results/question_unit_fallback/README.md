# Does the "the unit" default in the question prompt help or hurt? (an experiment; nothing is wired into the checklist)

Why: a check of DoDI 5200.48 (2026-10-15) found 71 of 251 questions saying "Does the unit ..." where the source passage never mentions a unit.
The prompt names "the unit" as the fallback actor (rule 2), frames the job as "whether a unit follows a regulation", and its prohibition example is "Does the unit avoid ...?".
Earlier rounds (question_prompt_v4) changed the actor rule but kept the "the unit" fallback in every arm, so removing it has not been tested.

## Arms (prompt only; same model qwen2.5:14b, same settings, same code gate, same schema)
- **C**: the current prompt (control). Run twice (C and C2) so the noise floor is measured on the same rows.
- **N**: no fallback actor. Opening line becomes "whether a regulation is being followed"; rule 2's last sentence becomes "If neither says, do not name an actor: ask impersonally (for example 'Is X ...?' or 'Are X ...?')"; the prohibition rule asks "Is X avoided?".
- **O**: wording only: "the unit" becomes "the organization" in all three places (fallback, opening line, prohibition rule).

## Rows (fixed before any output)
Five library documents not used in the earlier prompt rounds and not sealed: afman17-2101, dafman17-1305, CJCSI 6510.02G, dafi36-2903, DODI 5200.44.
Eligible rows only (has a quote, no skip flag, same gate as production). 50 per document, seeded `random.Random(51)`. 250 rows.
DoDI 5200.48 is excluded (I read it while designing). Sealed: afpd_17-1, DODI 8410.03, NIST.SP.800-125, never touched.

## Measures by code, no rating
- Invented actor: a question opening "Does/Do the unit|organization" where neither the quote, the "Applies to" line, nor the parent text contains "unit" or "organization" (the word is not in the material).
- Null rate (the string "null" counts as null); unverified-terms rate; question length; share of questions opening Is/Are/Was/Were (passive).
- Change rate of N and O against C, against the noise floor (C2 against C).

## Blind rating
Changed rows only (question differs from C after lowercasing and stripping punctuation, and not a C2 noise change). Two Opus labelers who never see arm names, order randomized per row.
They see the material (applies-to, parent, quote, passage) and the two questions, and give: better / same / worse for question 2 against question 1, judging
(1) faithful: no actor, duty, number or term that is not in the material; (2) one checkable yes/no audit question that asks about the marked requirement.
Disagreements and any "worse" go to Tyler as a 15-row sample, not to me.

## Adopt rules (registered now)
An arm is a candidate only if ALL hold:
1. Of changed rows where the two labelers agree: worse at most 10%, and better minus worse at least 10 points.
2. Null rate up by at most 3 points over C.
3. Unverified-terms rate not above C by more than the noise floor.
4. For N: invented-actor rate falls by at least 80% against C.
If both N and O qualify, N wins only if its rating beats O's. If neither qualifies, the prompt stays as it is.

## Limits stated up front
Same-family labelers (agreement is not correctness; Tyler's sample is the check). 250 rows in 5 documents. Adopting means a prompt change and regeneration of every document's questions (a separate approval).

## Result (ran 2026-10-15; 250 rows, 0 model errors; written after reading the outputs)

By code: invented actor C 52 / N 0 / O 37; rows with no question C 29 / N 14 / O 24; passive opening C 38 / N 225 / O 42; rows changed against C: N 215, O 114 (noise floor, C against C2: 26); unverified-terms rows C 2 / N 3 / O 2.

Blind rating (two Opus labelers, changed rows only, order randomized):
| Arm | Changed rows | Both agree | Better | Same | Worse | Better minus worse |
|---|---|---|---|---|---|---|
| N (no fallback, impersonal) | 215 | 181 | 27% | 39% | 34% | -7 points |
| O ("the organization") | 114 | 102 | 21% | 73% | 7% | +14 points |

Against the registered rules: **N fails rule 1** (worse 34%, limit 10%). Its failure is the passive voice: it drops actors the source names (SAF/FM, the LHC Financial Analyst) and adds questions for permissions and descriptions. **O meets rules 1 to 3** (rule 4 applies to N only). Of O's 114 changed rows, only 35 differ by the swapped word alone; the rest are model variation that the swap set off, so the gain is not mainly about the word. O still invents an actor on 37 rows (15%), against 52.
Labelers are the same model family; the 15-row sheet in `~/reqbot-work/checklists/question_wording_which_is_better.xlsx` is the owner check. Nothing is wired in.

## Owner check (2026-10-15)
Tyler rated 14 of 15 blind A/B rows: the current prompt preferred on 5, "the organization" on 1, same on 8 (one row skipped). This reverses the model raters' +14 points for O: **O is not adopted, the prompt stays as it is.** His notes: where the source names no actor an impersonal question is fine ("Are waivers submitted?"); one O question named positions the source does not. Model-rater agreement over-credited the change.
