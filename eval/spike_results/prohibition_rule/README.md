# Draft question prohibition rule (an experiment; nothing is wired into the checklist)

Why: when a requirement contains `do not`, `does not`, `is not` or `are not` anywhere, `build_prompt` adds "This requirement forbids something. Ask whether it is avoided
("Does the unit avoid ...?"); do not ask whether it happens." That fires on conditions, descriptions and exemptions, and flips the meaning:
"MAJCOM/DRUs will inform the HAF CARM Program office if this capability does not exist." became "Does the unit avoid informing the HAF CARM Program office ...?";
"Immediately notify contractor company to stop any contractor employee ..." became "Does the Contracting Officer avoid notifying the contractor company ...?"
The rule fires on 145 of 2,475 eligible rows of the 13 indexed documents (63 of 1,418 in the six Air Force documents).

## The change, and only this

The detector `PROHIBITION` is narrowed. It keeps: a modal followed by `not` (shall, must, should, will, may, can, could, would; not "not limited to / only / necessarily"), `cannot`, `never`,
`prohibited`, `forbidden`; and adds a sentence-opening imperative `Do not` / `Does not` and `is/are not authorized | permitted | allowed | to`. It drops bare `do/does/did/is/are/be not` in the
middle of a sentence. The narrowed pattern is a subset of the old one, so no row gains the rule; 71 rows lose it. The prompt text, the model (`qwen2.5:14b`, temperature 0.1), the inputs and the
code gate are unchanged.

## Rules, fixed before any new question was generated

**Rows.** Released rows: every eligible row (requirement quote, no skip flag) of the 13 indexed documents where the old pattern fires and the new one does not (71 rows; 12 in AFI 10-2402, 13-550
and 17-203). Rows where the rule still fires, and rows where it never fired, keep a byte-identical prompt (asserted in code), so their stored questions are reused and need no model call.

**Measures by code.**
- Released rows: the share of questions containing "avoid" (avoid, avoids, avoiding), current against new.
- Null rate (the string "null" counted as no question), current against new.
- Noise floor: the current prompt re-run on the same released rows; share of questions that differ from the stored one.

**The owner rates** the released rows of the three AFIs (better / same / worse than the question now, side by side). I read the other released rows and report that separately, labelled as my reading.
"Worse" includes an inversion: a question that asks the opposite of the requirement.

**Adopt** only if all hold:
1. "Avoid" questions among released rows fall by at least half.
2. Of the owner-rated rows, at most 1 is worse and none of those is an inversion.
3. The null rate on released rows rises by at most 15 points (a description may rightly become no question).
4. Still-firing and never-firing rows have byte-identical prompts (asserted).

Adopting means changing the pattern in `services/audit_questions.py`; stored questions of the 71 released rows become stale and are regenerated with `reqbot questions --doc` (the other rows are reused).

## Run

`PYTHONPATH=. python3 eval/spike_results/prohibition_rule/run_prohibition_rule.py --ollama-url http://192.168.90.100:11434`
Writes `outputs/runs.jsonl`, `outputs/measures.json` and the rating sheet `~/reqbot-work/checklists/prohibition_rule_rating.xlsx`.

## Result (run 2026-10-11, 71 released rows, 0 model errors; written after reading the outputs)

By code: questions containing "avoid": 62 (current) to 0 (new). Null: 9 to 17 (+11.3 points; the limit was 15). Changed 63 of 71 against a noise floor of 8 of 71 (the current prompt re-run).
Rows with an identical prompt, asserted: 2,404. Rules 1, 3 and 4 are met.

My reading (not the owner's rating): the 12 released rows of the three AFIs: 9 clearly better (the inverted "Does the unit avoid informing the HAF CARM Program office ..." became "Does MAJCOM/DRUs inform the HAF CARM Program office ..."), 3 about the same (descriptions that ask a fact-check question or give none), none worse.
The other 59 released rows: nearly all inversions fixed ("Does the Contracting Officer avoid notifying the contractor company ..." became "Did the Contracting Officer immediately notify ..."), many descriptions now get no question, a few get a fact-check question.
Two rows are real prohibitions that lose the rule: DAFMAN 17-1305 3.4.3 ("... requirements outlined are not waivable") and 4.4.5.3.1 ("Waivers are not appropriate for granting time extensions ..."); under the new pattern they got a positive-form question.

**Adjustment before adoption.** `is/are not` followed by `appropriate`, `acceptable`, `permissible` or `waivable` is added to the pattern. It is still a subset of the old pattern, and it restores the rule to exactly those 2 rows, so their prompts and stored questions are the current ones: no new output is involved. Released rows after the adjustment: 69.

## Owner rating of the 12 AFI rows (2026-10-11)

Side by side, question now against new question. Notes are his words, shortened.

| Document, reference | Rating | Note |
|---|---|---|
| AFI 10-2402 2.12.6.4, 2.17.5.1, 2.20.4.1, 3.2.5.1.1, 3.2.5.3 | better (5) | |
| AFI 10-2402 A2.1 | way better | |
| AFI 13-550 1.5.6 (the "(inferred)" row) | better | the new wording asks nothing, which is right: the sentence is a statement, not a requirement |
| AFI 13-550 1.5.6 | duplicate of the row above, same verdict | the same sentence was extracted from two neighbouring chunks, once with no reference (see below) |
| AFI 17-203 1.1.3 | better | he would prefer "Is this instruction being applied to incidents involving ...?" |
| AFI 17-203 1.1.4 | same | neither wording asks a question |
| AFI 17-203 3.4.2 | better | |
| AFI 17-203 A2.1 | better | no question is right: the sentence declares what a list that follows does not contain |

Better 11 (two of them because no question is the right answer, one a duplicate), same 1, worse 0, no inversion.

## Decision: adopted (2026-10-11)

All four rules are met. After the adjustment the released rows are 69: "avoid" questions 60 to 0; null 9 to 17 of 69 (+11.6 points, limit 15); owner rating 0 worse; byte-identical prompts for every other row (asserted).
`services/audit_questions.py` carries the adjusted pattern. One correction in the same change, with no effect on any row of the 13 documents: the tier marker before a sentence-opening "Do not" is read with its hyphen
("(T-1) Do not ..."); the pre-registered `\(\w+\)` did not match it, and no released row starts that way.
The questions he rated are written into the sidecars by `write_rated_questions.py` (dry run: 69 rows written, 2 rows keep the rule, and every row of the 11 changed documents is answered from the sidecar with no model call).

## Found on the way: the same sentence twice

AFI 13-550 1.5.6 has three sentences that appear twice in the checklist: once cited "1.5.6 (inferred)" with no reference, once "1.5.6". Both records anchor to the same characters; they come from neighbouring chunks
(13 and 14), and the finding step returned no reference for the first. De-duplication keys on the quote and the reference, so the empty reference keeps both. Across the 13 documents: 5 such pairs
(AFI 13-550 3, AFI 10-2402 1, NIST SP 800-125 1); none in AFI 17-203. Not changed here.
