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
