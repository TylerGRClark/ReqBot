# Pre-registration: splitting compound audit questions (spike, nothing live changes)

Written and committed 2026-10-14 BEFORE any model call of this experiment. Branch `feat/compound-question-split-spike`, from origin/main.

## Question

Can the local model (qwen2.5:14b, the model that writes today's questions) break a long, stacked audit question into one short lead question plus 2 to 5 short
yes/no parts, without dropping or adding anything, so an auditor can check one thing at a time? Or say "keep" when the question is already one thing?
Tyler's constraints (STATE.md, 2026-10-14): a rewrite only has to be easier, never different; the source quote stays beside every question; a dropped qualifier is
the danger (a permission turning into a duty); the author does not grade.

Nothing in services/, pipeline/, the sidecars, the index or the checklist is touched. Today's questions are never edited; proposals are only recorded.

## Data

Checklists built with `reqbot checklist --doc DOC --format json` (no model call), from the extraction runs of 2026-10-13; today's question = the row's `audit_question`.

- TUNE set (may be looked at and tuned on): afi10-2402, afi17-203, dafman17-1305.
- TEST set (frozen after tuning, run ONCE, no edits afterwards): afi13-550, afman17-2101, afpd_17-1, DODI 5200.48, DODI 8551.01.

## Candidates

A row with a question is a candidate when (a) the question is over 30 words, or (b) it joins 3 or more parallel items (a run of two or more commas closed by
and/or, or two or more bare and/or) AND is at least 20 words long. Rule (b)'s 20-word floor was added after counting: without it about 35% of all questions qualified
(13 to 19 word questions such as "Does the unit confirm and document the METs/MEFs that are assigned and executed?" are one glance already) and the call budget
would have been exceeded. Pool sizes found (rows with a question / candidates): afi10-2402 363 / 158, afi17-203 124 / 57, dafman17-1305 321 / 150, afi13-550 193 / 102,
afman17-2101 174 / 76, afpd_17-1 73 / 40, DODI 5200.48 251 / 123, DODI 8551.01 72 / 37.

Sample (to keep calls modest): at most 40 candidates per document, drawn with a seeded random sample (seed `compound-split-2026-10-14`, candidates sorted by row id first).
TUNE = 120 rows; TEST = 197 rows. The sampled ids are in `outputs/candidates_tune.json` and `outputs/candidates_test.json` (committed before any call).
Budget: 2 tune rounds x 120 + 1 test run x 197 = about 440 model calls. Temperature 0.1, same context and schema style as `services/audit_questions.py`.

## Model output

For each candidate: `{"decision": "keep"}` or `{"decision": "split", "lead": ..., "parts": [...]}`. Inputs: the row's "Applies to" line, the requirement (source quote)
and today's question. Prompt v1 is in `prompts.py` (id `8f788afd15e2d0f6` = hash of model + schema + template).

## Mechanical checks (all must pass, else the row falls back to today's question unchanged)

1. **qualifiers**: every number (digits, or two..ten, twelve, thirty, sixty, ninety, hundred, twice, both) and every condition word in today's question appears in the lead or some
   part. Condition words: if/when/whenever/once/upon/where, unless, only, until, within, at least/minimum, no later than, no more than/not to exceed/up to/maximum,
   before/prior to, after/following, except/other than/provided that, annually/yearly, quarterly, monthly, weekly, daily, biennial/semiannual, not/never/no/without/avoid/prohibited,
   all/each/every/any/both, as required/appropriate/needed/applicable/directed/tasked and when requested/tasked/directed/required, immediately/promptly. Family members count
   for each other (before = prior to). Deliberately strict: a word swapped for a synonym outside the family fails.
2. **terms**: no capitalised term, number or acronym in the split that is absent from today's question or the row's own text (requirement, Applies-to line, parent paragraph),
   using `services.audit_questions.unverified_terms`. (The surrounding passage is not counted, which is stricter than the live flag.)
3. **shape**: 2 to 5 parts; the lead is a yes/no question (opens with Does/Do/Is/Are/...) ending in "?"; each part is a yes/no question of at most 25 words, or a noun-phrase check
   of at most 10 words with no question opener and no final full stop.
4. **pronouns**: no they/them/their/it/its/he/she/his/her/these/those/such (not "such as")/this appearing in the split that is absent from today's question, and no piece whose subject
   is a pronoun ("Does it ...?").
5. **modality**: if the source or today's question holds may/can/could/might/permitted/authorized/allowed/encouraged/recommended/should, the split adds no must/shall/required/
   mandatory/need to/have to that was not already there, and still holds a permission word; if the source is a duty with no permission word, the split adds no may/can/permitted/
   allowed/authorized/encouraged/optional.
6. **coverage**: each comma / and / or segment of today's question that carries a content word has MORE than half of its content stems (first 5 letters of words of 4+ letters, minus
   a stoplist) somewhere in the split (so a list item dropped fails; 1 of 2 stems fails, 2 of 3 passes).
7. **actor** (added by this experiment, not in the brief): the first three words after today's opening auxiliary ("the HAF CARM program office") are kept at the start of the lead.

A split that fails any check falls back to today's question. Fallbacks are reported by check name (a row can fail several).

## Targets (TEST set)

- 0 rows dropped (every candidate row appears with either today's question or its split; model errors fall back to today's question).
- At least 80% of the splits the model proposes (decision = split) pass all seven checks without falling back.
- The longest piece falls: report median and 90th percentile of longest-piece word count before (today's question) and after (longest of lead / parts, or today's question for
  a fallback or keep), for all candidates and for changed rows only.
- Report how many candidates the model says "keep".

These are mechanical targets only. They say nothing about whether a split is faithful or easier. **A different blind reviewer, not the author, grades faithfulness and ease**
(sheet: `outputs/review_sheet_test.md`, written after the test run; the author does not grade and does not choose which rows are shown).

## Rounds

At most 2 prompt rounds on the TUNE set (v1, then at most one revision v2 fixed by what the TUNE failures show). Then the winning prompt is frozen: its id is written
into the "Freeze" section below and committed BEFORE the TEST run; the TEST set is run once with it and the result is reported whatever it is. If both rounds are
equal or round 2 is worse, v1 is the one frozen.

## Freeze

Frozen 2026-10-14 after two TUNE rounds, before any TEST call. **Prompt v2, id `5b796513781e2fd4`** (model qwen2.5:14b, temperature 0.1, schema as in `prompts.py`), with the checks
as they stand in `checks.py` at this commit. No further edit to the prompt, the checks, the candidate rule or the sample is allowed before the TEST run. The TEST set is run once.

### What happened in tuning (TUNE set, 120 rows, 90 / 87 proposed splits; mechanical checks only, not graded for faithfulness)

| | v1 | v2 (frozen) |
|---|---|---|
| model says keep | 30 | 33 |
| splits proposed | 90 | 87 |
| splits passing all 7 checks (checks as frozen) | 38 (42%) | 65 (75%) |
| fallbacks by check (a row can fail several) | coverage 26, pronouns 20, qualifiers 20, shape 4, actor 3, modality 2 | pronouns 11, shape 6, coverage 2, qualifiers 2, modality 2, actor 1 |
| passing splits whose longest piece is still over 80% of today's question | 1 | 16 |

Round 1 (v1) failed 20 splits on pronouns (the model wrote "they / it / this") and 20 on dropped qualifiers ("as appropriate", "within", "if", "up to"), 26 on dropped items.
v2 changed only the prompt text: lead = today's opening cut before the list ("... do all of the following"); name the subject in every part; keep a closing "as appropriate" /
"when requested" on every part it covers; keep may / should; max 5 parts, group extras.

Check changes made during tuning (after seeing round 1; all are loosening of demonstrated false failures, or one added flag; listed so a reader can discount them):
- shape: an "If applicable, is ...?" opener counts as yes/no; a short noun-phrase check written with a question mark counts (a who/what/how question does not).
- pronouns: "Does this publication ...?" is fine when today's question has the same two words; "IT" (Information Technology) is not the pronoun "it" when today's question says IT.
- coverage: "including / include / along" are not content words; a long title that the split replaces by its parenthetical acronym (AF/9) is not "dropped".
- actor: compares the names and acronyms of the subject (and the parenthetical acronym), not three raw words that included the verb.
- NOT a fallback reason: "gain" flag (longest piece more than 80% of today's question). Added after seeing the TUNE data, so it is reported, not enforced. When it is
  enforced the v2 TUNE pass rate falls from 75% to 56%.

Known over-strictness left in on purpose: "within" used for a place rather than a time limit fails check 1 when the split says "in"; a synonym outside a word family fails;
check 6 counts a dropped trailing purpose clause as a dropped item (usually it is one).

## Result of the single TEST run (appended after the run; nothing above was changed)

197 TEST candidates (5 documents), 197 model calls, frozen prompt v2. Model said keep for 67; proposed a split for 130; 80 passed all 7 checks (61.5%, target 80%: NOT met);
50 fell back (shape 26, actor 11, pronouns 9, coverage 3, terms 3, qualifiers 2, modality 1; 47 failed exactly one check). Rows dropped: 0 (target met).
Longest piece, all candidates: median 28 to 24, 90th percentile 38.4 to 36.0; changed rows: median 28 to 19, 90th percentile 37.2 to 30.0.
Faithfulness and ease were NOT graded: the blind review sheet is `outputs/review_sheet_test.md`. Exploratory (not registered) looks in `posthoc.py`: of the 80 passing splits,
25 have a longest piece over 80% of today's question, 11 add an unsourced "as appropriate / as required / when applicable", 3 have a lead that ends mid-sentence;
44 are free of all three. Full table in `report.md`.
