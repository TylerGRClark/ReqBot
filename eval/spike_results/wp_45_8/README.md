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
