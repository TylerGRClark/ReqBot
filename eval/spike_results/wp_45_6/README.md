# WP-45.6: does a larger local model read the documents better? (qwen2.5:14b against llama3.1:8b)

Measurement only. Nothing in production, the index or the processed files changed; every run wrote to a scratch directory
(`~/reqbot-work/scratch/wp45_6_scratch`). The plan, written before any run, is `docs/PHASE45_WP456_PLAN.md` (local, untracked).

## Question

Some of today's fragment and junk problems might be model skill rather than document structure. This asks whether
`qwen2.5:14b` extracts better than the production `llama3.1:8b-instruct-q4_K_M`, with **the prompt held identical**.

## Result in one line

With the unchanged production prompt the 14B extracts far fewer records (173 against 435 over three documents), is
very precise, and misses roughly 200 real requirements that the 8B finds. It does **not** show a meaningful improvement
under the criteria set before the runs. This is a statement about this model with this prompt, not about the model
in general.

## What was done

- **Documents (3, pinned by the WP-44 manifest):** DODI 8410.03 (42 chunks), afman17-2101 (63), NIST SP 800-125 (109).
- **Only the model differs.** Same chunks, same Step C prompt (prompt hash identical on every chunk in the July run, the
  14B run and the control run), same Step D. The 8B baseline's July extraction was re-run through *today's* Step D
  (`run_model.py --stage D`) so both sides are judged by the same rules.
- **Control run:** Step C samples at temperature 0.1 with no seed, so the 8B differs from itself between runs. A fresh 8B
  run on the same chunks gives the noise floor and a like-for-like speed.
- **Matching rule (fixed before any run):** two records are the same if they are in the same chunk and their
  whitespace-normalized quotes are equal or one contains the other. Counted per side.
- **Blind labeling:** one pooled pack of 90 cards, each showing only the quote, its chunk and the previous chunk, in
  random order with no model name: 40 drawn from the 14B-only records (all 30 that exist were taken), 40 from 8B-only
  records (of 289), 20 from records both found (of 143). Pass A of the WP-45.1(b) rubric, unchanged. Claude (who had seen the aggregate
  counts but not which card was which) labeled and locked the file before scoring it; Codex labeled independently from a folder holding only the pack, rubric and
  checker. The answer key was kept outside the pack and is in `outputs/pack_answers.json`.
- **Scoring:** `score.py`, with the five criteria below fixed in the plan before the runs.

## Counts

| | DODI 8410.03 | afman17-2101 | NIST SP 800-125 | all |
|---|---|---|---|---|
| Records kept, 8B July baseline (today's Step D) | 140 | 144 | 151 | 435 |
| Records kept, fresh 8B (control) | 138 | 139 | 142 | 419 |
| Records kept, 14B | 94 | 70 | 9 | 173 |
| Baseline records with a 14B counterpart / without | 76 / 64 | 62 / 82 | 8 / 143 | 146 / 289 |
| Baseline records with a fresh-8B counterpart / without | 131 / 9 | 136 / 8 | 129 / 22 | 396 / 39 |
| Chunks where the 14B returned an empty list (fresh 8B) | 10 (5) | 25 (6) | 100 (37) | 135 (48) |
| Step D rejections, baseline / 14B | 10 / 2 | 9 / 0 | 4 / 1 | 23 / 3 |
| Fragment composite, baseline / fresh 8B / 14B | 12.9% / 21.0% / 3.2% | 2.8% / 3.6% / 2.9% | 25.2% / 22.5% / 22.2% | |
| Step C mean seconds per chunk, fresh 8B / 14B | 4.83 / 6.6 | 3.27 / 3.11 | 1.52 / 0.52 | |
| Step C wall seconds, fresh 8B / 14B | 203 / 277 | 206 / 196 | 167 / 57 | |

All chunks completed in every run (no failed or truncated chunks). Peak GPU memory: about 6.3 GB (8B), 10.5 GB (14B).

Two effects explain the drop. The 14B gives up on whole chunks (returning `{"requirements": []}`) where the 8B finds
something, in 5, 19 and 63 chunks of the three documents. Inside chunks where both find something it also extracts about
30% fewer (8B 130 against 14B 96 on DODI, 108 against 73 on afman17). The production prompt says a requirement is
"something an organization MUST DO" and that the system's "ONLY task" is to extract actionable requirements; the 14B reads
that literally and the 8B reads it loosely. The size of the drop follows how shall-heavy the document is (formal policy
-33%, guidance prose -94%). That fits the explanation but only one NIST chunk was checked by hand; the mechanism is
**not** tested.

## Labeled sample

Claude and Codex agree on 84 of 90 cards. They agree on exactly which 79 cards are real requirements; the same 11 cards
are not. All six disagreements are about whether a card needs a lead-in or where it comes from (R018, R022, R041, R048,
R059, R079), none about whether it is a requirement. Tyler chose not to adjudicate them because they cannot move any
criterion (the scoring was run twice, once with all six going to each labeler, and every number below is identical both
ways: `outputs/scored_if_disagreements_*.txt`). Only the descriptive "complete" shares depend on them, so they are shown
as ranges.

| Set | Cards | Real requirement | Not a requirement | Reads complete alone |
|---|---|---|---|---|
| 14B only | 30 | 30 (89-100%) | 0 | 21-22 |
| 8B only | 40 of 289 | 29 (72%; 57-84%) | 11 | 13-14 |
| Both | 20 of 143 | 20 (84-100%) | 0 | 11-13 |

## The five criteria (fixed before the runs)

| | Result | Value |
|---|---|---|
| (a) net records gained: (gained - lost) over the 8B's real records, interval above 0 and at least 0.10 | **fail** | -0.505 [-0.551, -0.436] (gained 30, lost 210, 8B real 356) |
| (b) junk share of 14B-only no more than 0.10 above 8B-only | pass | -0.275 [-0.425, -0.150] |
| (c) fragment composite, 14B minus baseline, lower bound at or below 0 | pass | -0.097 [-0.141, -0.054] |
| (d) chunks lost (failed or cut off) no more than 5 points above fresh 8B | pass | 0.000 against 0.000 |
| (e) net unique difference exceeds the fresh 8B's by at least 0.05 | **fail** | 14B -0.595 against fresh 8B -0.032 |

Result: **no demonstrated meaningful improvement under the pre-set rule** (this is not "no difference": the 14B is
clearly different, mostly in the wrong direction for recall).

Read (c) with care. The 14B has fewer fragments partly because it keeps only the clearest, most complete sentences, so
there are fewer chances for a fragment; and the fresh 8B differs from the July baseline by more than the 14B does on DODI
(21.0% against 12.9%), so the 8B's own run-to-run swing on that measure is large.

## What this does not say

- **The prompt was held fixed on purpose.** This measures a model-and-prompt pair. Whether a prompt written for the 14B
  (told to be over-eager) closes the gap is untested; it is a parked follow-up and, as a change to a generation stage, needs
  Tyler's approval first. What is shown is that one fixed prompt behaves very differently across two models.
- **Only relative unique finds.** There is no recall against the source documents yet; WP-45.1(e) will provide that.
- **Three documents, 90 cards, two labelers who share one rubric.** The rubric counts "organizations should ..." guidance
  as a requirement, so the 72% of 8B-only records called real rests on that definition. The 8B-only estimate has a wide
  interval (57-84%).
- **Nothing here concerns frontier hosted models.**
- **Speed is confounded by output length.** The 14B writes less, so its time per chunk is not a clean speed comparison.
- **The matching rule has effects.** A 14B record can contain two 8B records (a merge) and the reverse; the rule counts
  such records as matched. The shared sample was drawn from the 14B side (143 matched records) but is scaled by the 8B-side
  count (146) to estimate how many genuine 8B records there are. `score.py` re-runs the estimate with 143 in place of 146
  (the lower bound if the three extra 8B records were all junk): (a) moves from -0.505 to -0.509 and no verdict changes.
- **No token counts.** The pipeline's raw ledger does not store Ollama's token counts, so none are reported (an earlier
  draft of the comparison files showed them as zero; that was removed). Time per chunk comes from the pipeline log.

## Possible use

Because the 14B is literal and precise, it may suit a second-pass role (is this actionable, and how can it be stated more
clearly for the user) better than broad first-pass extraction. That is a hypothesis for WP-45.3, not a measurement.

## Files

- `run_model.py`, `compare.py`, `pack.py`, `score.py`, and `tests/unit/test_wp45_model_comparison.py`.
- `outputs/comparison_<document>_<model>.json`: per-document counts and overlap ids for the 14B and the fresh 8B control.
- `audit_pack/`: the pack, rubric and checker given to the labelers (hashes in `outputs/pack_manifest.json`).
- `labels/labels_claude_a.jsonl`, `labels/labels_codex_a.jsonl`; `outputs/pack_answers.json` (card id to set and record).
- `outputs/scored_if_disagreements_claude.txt` and `..._codex.txt`: the scoring output under each bound.

Reproduce (needs the pinned inputs and Ollama):

```
python3 eval/spike_results/wp_45_6/run_model.py --doc "DODI 8410.03" --model qwen2.5:14b --stage C
python3 eval/spike_results/wp_45_6/run_model.py --doc "DODI 8410.03" --model llama3.1:8b-instruct-q4_K_M --stage D
python3 eval/spike_results/wp_45_6/compare.py --doc "DODI 8410.03" --new qwen2.5_14b
python3 eval/spike_results/wp_45_6/score.py --key outputs/pack_answers.json --labels-dir <dir with the two label files> \
    --pack-dir eval/spike_results/wp_45_6/audit_pack --new qwen2.5_14b --answers <file of "R018 a: claude" lines>
```
