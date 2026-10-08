# WP-46.4 — draft audit questions (an experiment; nothing is wired into the checklist)

Plan: [docs/PHASE46_REQUIREMENTS.md](../../../docs/PHASE46_REQUIREMENTS.md) section 2, WP-46.4. A *generation* call (the model writes a short question), unlike the selection resolver, so it is held to a stricter check: the question may use only what the row itself supplies.

**Rules, fixed before any output was read.**
- Sample: 30 rows of AFI 17-203, seeded (`random.Random(46)`), drawn from rows that have a requirement quote; the same prompt for every row; model `qwen2.5:14b` at temperature 0.1 on the owner's server.
- The model gets the row's requirement, its "applies to" heading, its parent paragraph and its passage; nothing else. It must answer with one yes/no question that checks the requirement, or `null` when the row cannot be audited as written (a fragment with no stated duty or actor).
- A code check runs on every question and flags it `unverified_terms` when it contains a number, an acronym or a capitalized word that does not appear in the row's own text. Flagged questions are shown to the rater as such; none is dropped.
- The owner rates each of the 30 as **usable** (as written), **edit** (right idea, needs a small change) or **wrong** (misleading, invented, or not about the requirement); a row for which the model returned no question is rated **right to skip** or **should have asked**.
- **Adopt** (offered as a clearly-labeled draft column on the sheet, never replacing the requirement) only if usable + edit is at least 80% of the questions asked and wrong is at most 10%. Otherwise the result is reported and the column stays empty.

Run: `PYTHONPATH=. python3 eval/spike_results/wp_46_4/draft_questions.py`. It writes `outputs/draft_questions.jsonl` and the rating sheet `outputs/rating_sheet.md`.
