# WP-45.8 Stage A — shadow run of the frozen selection resolver (tooling)

Plan: [docs/PHASE45_WP458_PLAN.md](../../../docs/PHASE45_WP458_PLAN.md) section 3, Stage A. Nothing here touches the pipeline, the Step C cache, any `*_requirements_*.jsonl`, Qdrant or the repository's data; ledgers and outputs go to `~/wp45_8_scratch/<label>/`.

```
python3 shadow_run.py drills                        # failure drills (no model)
python3 shadow_run.py run    --source processed     # every record of the newest run of each processed document (or --source arm:NAME)
python3 shadow_run.py report --source processed     # counts, routes, seeded sample of changed records, span gate -> outputs/
python3 shadow_run.py rerun  --source processed     # seeded 200-record determinism rerun -> outputs/
```

- The resolver is the one frozen in WP-45.7e (menu_v2, kind prompt, tier R2, model, digest and inference parameters from the frozen choice), run through the frozen `run_selection.run_candidates` and `run_stage_c._menu_module`. `check_code()` compares every file of the frozen manifest with the tree; the only allowed difference is `pipeline/chunk_text.py` (the merged T2 table fix, #249), and only if the one function the resolver imports from it (`_normalize_heading`) is byte-identical to the frozen version.
- The string that would be attached (fixed by the plan before Stage B): the chosen actor span and the chosen parent span, joined with ` | `, empty when neither.
- Gate: zero crashes (drills), zero dropped records (one output row per input record, flagged where the resolver abstained or the record was not sent), zero returned spans that are not a substring of the document after the resolver's own normalization; determinism differences are listed, not hidden.

## Stage A results (2026-10-08, run overnight, scratch only)

Two runs of the frozen resolver (WP-45.7e: menu_v2, kind prompt `6200fa25a374eb35`, tier R2, `qwen2.5:14b`, same digest and parameters as the frozen run; `check_code()` found only the declared `pipeline/chunk_text.py` difference, whose one imported function is byte-identical to the frozen version). Reports: `outputs/wp458_shadow_processed_report.json`, `outputs/wp458_shadow_arm_T2a_report.json`, `outputs/wp458_shadow_processed_determinism.json`.

| | newest processed runs (the 13 pinned runs Stage B reads) | arm T2a (current pipeline output) |
|---|---|---|
| input records = output rows | 1,853 = 1,853 | 1,880 = 1,880 |
| calls, all `complete` | 1,853 | 1,880 |
| mean seconds per call / total | 1.01 / 31 min | 1.01 / 31 min |
| kind: requirement / not_a_requirement / scope_or_context | 1,642 / 175 / 36 | 1,661 / 182 / 37 |
| records with a resolver string | 1,577 | 1,598 |
| empty menus | 0 | 0 |
| flagged `checker error` | 2 | 3 |
| records where production has a stem | 41 | 205 |
| production none -> resolver some | 1,542 | 1,418 |
| both some, different / same | 14 / 21 | 109 / 71 |
| production some -> resolver none | 6 | 25 |

**Gate on Stage A (plan section 3), as registered.**
- Zero crashes: **met** (six failure drills, including a server that is down when the run starts: every record kept, flagged, no calls).
- Zero dropped records: **met** (one output row per input record, both runs).
- Zero returned spans that are not a substring of the document after normalization: **not met as written.** Six records in the first run (four in the second), about 0.3% of records. None of the spans was written by the model: all are menu entries produced by existing code. By record: **three** match the document once punctuation is ignored (the subject extractor and the stem finder change commas and hyphens, e.g. "The DoD Components with DISA support", "Have load-shedding plan", "The organization"); the other **three** carry the same string, "Wing/Delta Cyberspace Offices (formerly known as Cybersecurity Offices) shall:", which is Step C's own stem and drops the parenthetical "(WCO/DCO)". They are listed in the report. Stage B and any later step should treat a record whose span is not verbatim as "no resolver string".
- Determinism differences reported, not hidden: **194 of 200 identical** on a seeded rerun at temperature 0.1 without a seed; six differ (an actor chosen in one run and not the other, a different lead-in extent), listed in `outputs/wp458_shadow_processed_determinism.json`.

**What the output looks like (arm T2a).** Of 1,598 strings, 1,089 are a parent (lead-in or heading) only, 299 an actor only, 210 both. Production's own stem is present on 11% of these records (205 of 1,880) and the resolver attaches something to 85%, so most of the count in "production none -> resolver some" is the resolver naming the actor or a heading for records production leaves bare; whether that helps search is Stage B's question, not this one's.

**Seeded sample of 40 changed records, read by me (one reader, my judgement, not scored against the labeled gold).** About 28 look right (e.g. "Sign a formal statement of assigned cybersecurity responsibilities (T-0) ." -> "Individuals (Contractor Personnel) shall:"; "Coordinate and facilitate the review of DIMA cyberspace capabilities and investment." -> "Deputy Chief of Staff for Intelligence, Surveillance, and Reconnaissance (AF/A2) will:"; "(7) Address the required physical safeguards ..." -> "In accordance with ISOO Notice 2016-01, CUI training standards must, at minimum:"), 3 are arguable, and 9 are weak or wrong: two clear misses ("Volume 2 of DoDM 5200.01 requires DoD intelligence producers ..." -> "[Add a point of contact when needed.] (2)"; "The nominated TCAs will be reviewed and validated ..." -> "(T-1) Responsibility for asset data entry into the AF CARM system ..."), and several weak ones (a parent that only repeats the start of the quote; a bare heading such as "CARM WG." or a sentence that is not a lead-in). This is consistent with the WP-45.7e verdict: more right than production, not free of misleading answers.

**Limits.** The check is on shape, speed, determinism and a read of 40 records; it says nothing yet about retrieval (Stage B) and does not settle accuracy beyond the WP-45.7e labeled sets. Nothing was written to the pipeline, the Step C cache, any `*_requirements_*.jsonl` or Qdrant.

## Stage B results (2026-10-08): the retrieval test, under the registry's rules

Rules: [registry #250](../../../docs/PHASE45_WP458_REGISTRY.md) and [the Stage B addendum](../../../docs/PHASE45_WP458_STAGEB_ADDENDUM.md), both merged before any number was computed (`stage_b_run.py`, `stage_b_analyze.py`). Four runs (plain, three production-path repeats on the saved rewrite/HyDE inputs), 111 tested records, target-only mode. The index digest equals the WP-45.1(c) run's. The resolver string (Stage A, run 1) exists for 1,562 of the 1,845 indexed records and for 101 of the 111 tested ones (the rest are abstentions, `not_a_requirement` rows with nothing selected, or flagged; the six non-verbatim records get none). Reports: `outputs/stageb_report.json` (every cell, both tie readings, other metrics, string coverage per group), `outputs/stageb_results_*.json`.

**Registered outcome: H, R and C not triggered; G holds -> "proposal for integration"** (resolver arm; the hybrid arm, reported beside, gives the same).

Resolver minus production, recall@10 (paired by record; best-tie mean with its 95% interval; the worst-tie readings are identical in every row shown except pooled stemmed, party, repeat 1, where the worst reading is 0.00; the incomplete-stem group, not shown, also differs, see the report):

| group (n topic / party) | question | plain | prod r1 | prod r2 | prod r3 |
|---|---|---|---|---|---|
| **no stem, needs a lead-in** (36 / 29) | topic | **+0.14** [+0.03, +0.25] | **+0.19** [+0.08, +0.33] | +0.08 [0.00, +0.19] | **+0.11** [+0.03, +0.22] |
| | party | **+0.24** [+0.10, +0.41] | **+0.21** [+0.07, +0.34] | **+0.24** [+0.10, +0.41] | **+0.24** [+0.10, +0.41] |
| right stem (25 / 21) | topic | 0.00 | 0.00 | 0.00 | 0.00 |
| | party | -0.05 [-0.14, 0.00] | -0.05 | -0.05 | -0.05 |
| misleading stem (22 / 17) | topic | -0.05 [-0.14, 0.00] | 0.00 | 0.00 | 0.00 |
| | party | 0.00 [-0.18, +0.18] | +0.06 | +0.06 | +0.06 |
| pooled stemmed (58 / 49) | topic | -0.02 [-0.05, 0.00] | 0.00 | 0.00 | 0.00 |
| | party | +0.02 [-0.06, +0.10] | +0.02 | 0.00 | +0.04 |
| control: no stem, complete (17 / 13) | topic | -0.12 [-0.29, 0.00] | -0.06 [-0.18, 0.00] | 0.00 | 0.00 |
| | party | 0.00 | 0.00 | 0.00 | 0.00 (one run inconclusive) |

Bold = "meaningful" under the apparatus' rule (at least 0.10 with an interval excluding zero, under both tie readings). The gain is on the group the resolver is for: 34 of its 36 records receive a string. For scale, the owner-adjudicated lead-in on the same group in the earlier test gave +0.17 [+0.06, +0.31] (topic, plain, n=35), so the resolver recovers most of what a perfect lead-in would. The gold cohort check (the policy applied to all 1,845 records, 35 queries): recall@10 change -0.013 [-0.081, +0.053], +0.004 [-0.038, +0.047], +0.004 [-0.024, +0.042], +0.002 [-0.029, +0.040]; no run has its upper bound below -0.02, so C is not triggered. MRR on the gold queries moves by -0.015, -0.021, -0.026, +0.035.

**What is not clean, read in the numbers.**
- **The control group** (complete sentences with no stem; 14 of 17 get a string, mostly an actor) loses 0.12 on topic questions in the plain run and 0.06 in repeat 1, nothing in the other two. That is a point-estimate loss in two of four runs, not all four, so R is not triggered, but it is the direction a "mislabel the complete sentences" design would hurt in; a later step should attach only where a lead-in is needed. The right-stem group loses 0.05 on party questions in every run (one record, 21 records; interval touches zero).
- **Evidence limits (registry section 4, unchanged):** groups of 11 to 36 records, questions written by the proposing model, an in-memory engine and 13 documents. The gain's lower bounds are small (+0.00 to +0.10 on topic questions; the party ones are firmer); one topic cell (repeat 2, +0.08, interval to 0.00) is not meaningful on its own. "Proposal" means the registered retrieval test did not find harm and did find the expected gain; it does not say the attachments are accurate (WP-45.7e: 65/104 right against 41, 39 misleading against 36, one labeler; a second labeler did not reproduce the pass).

**What follows.** Nothing is integrated. Stage C (a pipeline step) needs the owner's answers to the plan's four stop-and-ask items: a new LLM call in the pipeline; a second model (the 14B) alongside the 8B; the saved-record schema (kind, strength and chosen spans, or reuse of `parent_stem`/`embedding_text`); and what Qdrant embeds (a reindex). The check of the same questions against a scratch Qdrant collection built from the shadow output, before anything ships, remains part of Stage C.
