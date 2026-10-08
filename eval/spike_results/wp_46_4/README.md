# WP-46.4 — draft audit questions (an experiment; nothing is wired into the checklist)

Plan: [docs/PHASE46_REQUIREMENTS.md](../../../docs/PHASE46_REQUIREMENTS.md) section 2, WP-46.4. A *generation* call (the model writes a short question), unlike the selection resolver, so it is held to a stricter check: the question may use only what the row itself supplies.

**Rules, fixed before any output was read.**
- Sample: 30 rows of AFI 17-203, seeded (`random.Random(46)`), drawn from rows that have a requirement quote; the same prompt for every row; model `qwen2.5:14b` at temperature 0.1 on the owner's server.
- The model gets the row's requirement, its "applies to" heading, its parent paragraph and its passage; nothing else. It must answer with one yes/no question that checks the requirement, or `null` when the row cannot be audited as written (a fragment with no stated duty or actor).
- A code check runs on every question and flags it `unverified_terms` when it contains a number, an acronym or a capitalized word that does not appear in the row's own text. Flagged questions are shown to the rater as such; none is dropped.
- The owner rates each of the 30 as **usable** (as written), **edit** (right idea, needs a small change) or **wrong** (misleading, invented, or not about the requirement); a row for which the model returned no question is rated **right to skip** or **should have asked**.
- **Adopt** (offered as a clearly-labeled draft column on the sheet, never replacing the requirement) only if usable + edit is at least 80% of the questions asked and wrong is at most 10%. Otherwise the result is reported and the column stays empty.

Run: `PYTHONPATH=. python3 eval/spike_results/wp_46_4/draft_questions.py`. It writes `outputs/draft_questions.jsonl` and the rating sheet `outputs/rating_sheet.md`.

## Version 1 result and version 2 (written after reading the 30 version-1 questions)

I read the 30 version-1 questions before anyone rated them. About 20 were grounded and usable; the model never answered `null`, so fragments and definitions received invented duties ("an assessed occurrence that ..." became "Does the unit assess occurrences ...?"; "installation of vulnerable applications, and other breaches ..." became "Does the unit avoid ...?"), "should not result in a self-imposed denial of service" was turned into the question whether it does, and permissions ("may contact", "can be done") became "Can ...?" questions. Only one question was flagged by the unverified-terms check. Version 1 is kept in `outputs/v1_*` as run; **the owner rates the final version (3 below).**

Version 2 changes, and only these: (a) code withholds the question for rows carrying `starts_mid_sentence`, `table_fragment`, `definition_or_description`, `quote_not_located_in_passage` or `no_passage` (the row stays on the sheet); (b) two prompt rules: a prohibition is asked as "does the unit avoid ...", and a permission or description gets `null`. Same 30 rows (same seed), same model, same adoption thresholds as above.

Run: `python3 draft_questions.py --variant 2` (default) or `--variant 1`.

## Version 2 result and version 3 (final)

Version 2's code gate worked (6 rows withheld, all fragments or descriptions; "may contact" and "can be done" now get no question). Its prompt rule about prohibitions backfired: three plain statements ("Tier Two provides ...", "C3MS is the single AF weapon system ...", "The sponsoring MAJCOM Staff element will establish ...") became "Does the unit avoid any action that would prevent ...?", and one lost its named actor. Version 2 is kept in `outputs/v2_*` as run.

Version 3 keeps the code gate and the permission/description rule, and adds the prohibition rule to the prompt **only for quotes that contain a prohibition** (`not`, `never`, `prohibited`). Same 30 rows, same model, same thresholds. This is the third and last version before the owner's rating; there is no further tuning on these 30 rows.

Run: `python3 draft_questions.py` (variant 3 is the default).
