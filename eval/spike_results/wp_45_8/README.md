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
