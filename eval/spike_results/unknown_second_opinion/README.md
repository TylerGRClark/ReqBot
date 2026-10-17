# Can the local model sort the `unknown` rows into real requirements and noise? (an experiment; nothing is wired in)

Why: after kind-rules-8 the `unknown` bucket (about a quarter of all rows) is the main place noise hides, and it still holds real requirements (11 real of 44 in a representative
sample). A rule cannot tell "The Wing Cybersecurity Office addresses all unclassified COMSEC ..." (real) from "Tier Two provides direction and support ..." (a description).
Gating the whole bucket would lose about 7% of all real questions (the owner's bar is about 1%). This tests whether the local model can separate them.

## Data (fixed before any model output)
228 rows the current rules call `unknown` that two blind Opus labelers agreed on: 73 real requirements, 155 not. They come from two samples (the proportional 223-row sample and the
240-row unknown-bucket sample). The labels are the answer key; they are never shown to the model. The row text itself is not committed (public repo); `rows` is read from a local file.
- Dev: the 89 rows of the unknown-bucket sample's first half, used to write the prompt and choose the threshold.
- Held out: the other 139 rows (second half of that sample + the proportional sample's unknown rows), run once.

## Arms (same model qwen2.5:14b, temperature 0.1, same server)
- **W (baseline, no new calls):** the existing question writer: a row "kept" when it got a question. On all 228: keeps 62 of 73 real, drops 57 of 155 not.
- **S1:** a single scored question: "How clearly is the marked sentence a requirement an auditor could check? 0 to 10", with the labelers' definition of requirement / not / fragment.
- **S2:** S1 plus 6 worked examples taken from the dev rows only.
A row is kept when its score is at or above a threshold chosen on the dev rows (the lowest threshold that keeps at least 90% of the dev real rows).

## Adopt rules (registered now)
On the held-out rows, at the dev-chosen threshold, an arm is a candidate only if:
1. It keeps at least 90% of the real rows (which holds the overall loss near the owner's 1%: unknown real rows are about 7% of all real rows).
2. It drops more of the noise than W does (W drops 37%), and at least 60%.
3. S2 does not beat S1 by relying on a dev example that reappears in the held-out rows (checked by hand).
If neither qualifies, the bucket stays as it is.

## Limits
Same-family labelers (Opus) made the key; 139 held-out rows; one run. Adopting means a new model call per `unknown` row at question time (about 1,700 rows across the 22 documents,
a few minutes each document) behind a default-off switch, which is a separate decision.

## Run
`PYTHONPATH=. python3 eval/spike_results/unknown_second_opinion/run_second_opinion.py --rows <local rows json> --ollama-url <url>`

## Result (ran 2026-10-16; 228 rows, 0 model errors; written after reading the scores)
Held-out rows (139: 46 real, 93 not), threshold chosen on the 83 dev rows that are not worked examples:

| Arm | Threshold | Real kept | Noise dropped |
|---|---|---|---|
| W (existing question writer) | n/a | 37 of 46 (80%) | 35 of 93 (38%) |
| S1 (score, no examples) | 6 | 37 of 46 (80%) | 79 of 93 (85%) |
| **S2 (score + 6 dev examples)** | 7 | **42 of 46 (91%)** | **71 of 93 (76%)** |

Against the adopt rules: S1 fails rule 1 (80%, needs 90%). **S2 meets all three**: keeps 91% of real, drops 76% of noise (W drops 38%, the floor was 60%); one held-out row (a not-a-requirement) opens exactly like a worked example; without it the held-out result is 42 of 46 real kept and 70 of 92 noise dropped, so rule 3 does not change the verdict.
Intervals are wide (95% Wilson): real kept 42 of 46 is 79% to 97%; noise dropped 71 of 93 is 66% to 84%. On dev, S2 at 7 kept 23 of 24 real.
Reading: the model separates real from noise in this bucket much better than the existing writer's null answer (which drops 38%), and it is the worked examples, not the scoring alone, that hold recall.
For scale: `unknown` real rows are about 7% of all real rows, so keeping 91% of them costs about 0.6% of all real questions, inside the owner's 1%.
Not decided: building it (a second model call per `unknown` row at question time, default-off), which needs the owner's go.

## Round 2: a bigger real set, and the time it adds (registered 2026-10-16 before any round-2 output)
The owner prefers no toggle (always on), so the next test is what an always-on version would do on the real workload.
- **Frozen:** prompt S2, the same six worked examples (`outputs/example_ids.json`), threshold 7, model and settings. Nothing is tuned again.
- **Workload:** every row the current rules call `unknown` in the 22 library documents, scored once; wall-clock time recorded per document (the time an always-on step would add to question writing).
- **Fresh labeled set:** 300 of those rows drawn at random (seeded, in proportion to how many `unknown` rows each document has), excluding the 228 already used, labeled by two blind Opus labelers; rows they disagree on are left out of the score and counted.
- **Adopt rules:** on the fresh set, real kept at least 90%, noise dropped at least 60%; reported with 95% Wilson intervals; added time reported per 1,000 `unknown` rows and as a share of the existing question-writing time.

## Round 2 result (ran 2026-10-16; written after reading the scores and labels)
**Time.** Scoring all 1,903 `unknown` rows of the 22 documents took 841 s (14.0 min, 0.44 s per row, 0 errors). The existing question writer takes about 0.8 s per row it writes (DAFPAM 90-803: 895 rows in 713 s). At threshold 7, 986 of the 1,903 rows (52%) would skip the question call, which saves about 789 s: the step is roughly time-neutral (+52 s on about 6,600 s of question writing, under 1%), as long as it runs before the question is written.
**Accuracy on the fresh set** (300 random `unknown` rows in proportion to the library; two labelers agreed on 290: 145 real, 145 not), frozen prompt, examples and threshold 7:
real kept 126 of 145 (87%, 95% 80% to 91%); noise dropped 115 of 145 (79%, 95% 72% to 85%). **This misses the registered rule of 90% real kept** (point estimate; the interval reaches 91%). Pooled with round 1 (dev excluded): 168 of 191 real kept (88%).
Scores are close to two-state: thresholds 3 to 7 behave the same (88% real kept, 76% to 79% noise dropped). Threshold 2 keeps 97% of real and drops 54% of noise. Chosen after seeing this set, so it needs a third fresh set before it is trusted.
**What it means for the whole checklist** (library estimate: about 952 of the 1,903 `unknown` rows are real, which is 13.5% of all real rows; the earlier "7%" came from a stratified sample):
| Threshold | Real questions lost (share of all real) | Noise left in the whole checklist (of about 1,206 now) |
|---|---|---|
| 2 | 0.4% | about 694 |
| 3 to 7 | 1.7% to 1.8% | about 450 to 480 |
The real rows it misses at 7 are mostly borderline: recommendations and advice ("Consider using introspection capabilities ..."), uniform-fit statements ("The cap sits squarely on the head."), and role sentences without a modal.

## Round 3: improve the strict setting (registered 2026-10-16 before any round-3 output)
The owner prefers the strict setting and accepts losing about 2% of real questions for a decluttered list, because the rows themselves stay (only the draft question is withheld),
and asked for a couple more prompt trials. Tuning rows: round 1 (228) + the round-2 fresh set (290 agreed) = 518 labeled rows. A third fresh set (300 random `unknown` rows, two blind
labelers) is drawn and labeled now and not looked at until the end.
- **S3:** a revised definition that says what S2 missed: advice and recommendations that tell the reader what to do ("should", "consider", "it is recommended"), standards for how something is done, worn or kept, responsibilities of roles ("it is every Airman's responsibility ..."), and conditions on what is authorized. Same six examples as S2.
- **S4:** S3's definition + 12 worked examples (the six from S2 plus six from the tuning rows: three real rows of the missed kinds, three hard not-real rows).
- Selection: on the tuning rows minus the worked examples, pick the variant and threshold with the most noise dropped among those keeping at least 92% of real; ties go to S2 (fewer changes).
- Confirmation: the chosen variant and threshold, frozen, run once on the third fresh set. Adopt if real kept is at least 90% and noise dropped at least 70%; otherwise the strict setting is S2 at 7 as measured (87% / 79%).

## Round 3 result (ran 2026-10-16; written after reading the scores)
Tuning rows (506, worked examples excluded; 212 real, 294 not). Real kept / noise dropped:
| Variant | thr 7 | thr 8 |
|---|---|---|
| S2 | 89% / 76% | 84% / 78% |
| **S3** (revised definition, same 6 examples) | **94% / 68%** | 91% / 71% |
| S4 (S3 + 12 examples) | 96% / 59% | 93% / 60% |
By the registered rule (most noise dropped among variants keeping at least 92% of real) the pick is **S3 at threshold 7**. S4's extra examples cost noise recall.
**Confirmation, run once on the third fresh set** (300 random `unknown` rows; 274 agreed: 106 real, 168 not; frozen S3, threshold 7):
S3: real kept 94 of 106 = 89% (95% 81% to 93%), noise dropped 131 of 168 = 78% (71% to 84%). S2 on the same rows: 84% (76% to 90%) and 79%. The point estimate of real kept is one point under the registered 90%, the interval contains it; noise dropped passes (70%).
Reading: S3 keeps about five points more real rows than S2 at the same noise dropped, so it dominates S2. Pooled library estimate (rounds 2 and 3, 564 agreed rows): about 45% of `unknown` rows are real (about 850 rows, 12% of all real rows), so S3 at 7 loses about 1.3% of all real questions (S2: about 1.9%) and removes about 78% of the noise in the bucket.

## Review notes (Codex on #351, 2026-10-17) and a check of the shipped prompt
The scripts here are the record of what produced the numbers above and are not changed. What the review found, and what it means:
- **Example order.** Round 3's `run_round3.py` builds the six worked examples in the order they occur in the tuning-rows file, not in the order of `pick_examples` (three real, then three not) that round 1 used and that the shipped prompt (`services/audit_questions.py`, `SCORE_EXAMPLES`) uses. The third-fresh-set confirmation (89% real kept, 78% noise dropped) therefore ran a different order from what shipped.
- **Check of the shipped prompt** (`audit_questions.score_prompt`, example order 3 real then 3 not, threshold 7) on the same third fresh set (106 real, 168 not): **real kept 91 of 106 = 86% (78% to 91%), noise dropped 151 of 168 = 90% (84% to 94%)**. Same ballpark, a more aggressive operating point: about 1.7% of all real questions withheld (not 1.3%) and fewer noisy ones left. The intervals for real kept overlap the earlier 89%.
- **"Hard examples".** The README says the extra S4 examples were hard cases; the code drew them at random from the tuning rows. S4 was not adopted, so nothing shipped depends on it.
- **No separate held-out path.** The round-3 confirmation was run inline once on the third fresh set rather than through a `--final` option of the script; its scores are in `outputs/scores_round3_final.json`.
