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
