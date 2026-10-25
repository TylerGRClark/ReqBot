# PREREG12: longer context-index cut and section heading in the requirement text (retrieval)

Written 2026-10-25, before any arm has been run. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything.

## Question
(1) `pipeline/embed_context_index.py` embeds only `text[:1500]` of each chunk. For about 5.9% of chunks (3.4% of rows) the requirement sits past that cut. Does a longer cut (3000, full chunk) improve retrieval?
(2) The requirements index embeds the explained text plus `Ref: <paragraph>`, with no heading (audit item X1). Does putting the section heading in the embedded text improve retrieval?

## Facts found by reading code and one embedder check, before any arm (not results)
- **The context index is not searched.** `core/ask.py` only fetches a chunk from `grc_context` by exact point id (`retrieve_context_chunks`, `client.retrieve(ids=...)`) to show text around a hit; `services/trace_service.py` does the same. The only `query_points` call in production code targets `grc_requirements`. So the 1500 cut changes a vector nobody queries: search hits, rank and MRR cannot change with the cut. The stored `text` payload is the full chunk, and that is what readers see. The cut arms are therefore expected to be inert in the real search path; one probe (below) measures the cut on its own anyway, and a cost-only decision rule applies.
- Embedder: `nomic-embed-text` trained context 2048 tokens (model info), Modelfile `num_ctx 8192`. Ollama truncates silently, no error: two texts that differ only after position ~20,000 characters (3,000 words) embed identically (cosine 1.000000); at 13,000 characters a different tail still moves the vector (cosine 0.997). Text beyond the limit is ignored without notice.
- The retrieval gold set `eval/gold_retrieval_queries.jsonl` (45 queries, WP-37.1/WP-40) names `requirement_id`s from the old list-writing method. Only 22 of its 130 ids exist in the live library (6,773 rows, 2026-10-24 re-run). It cannot be used as is. `idx_cut_gold.py` re-points it by text (rule frozen in that file's docstring): 106 of 130 old ids map to one or more live rows; 24 do not (the new method has no such row); 30 non-zero queries keep at least one gold row, 8 zero queries stay zero, 7 non-zero queries lose all gold rows and are not scored. Result committed as `PREREG12_gold_remapped.jsonl`.
- Production search today: query rewrite on, HyDE on, 3-leg RRF (dense, BM25, HyDE dense), `min_score` from config, **no reranker** (`rerank` defaults to False and no caller turns it on). The harness `eval/retrieval_eval_harness.py` (WP-37.1/43) already runs exactly this path through `core.ask.retrieve()`; it warns that HyDE samples at temperature 0.3 so single runs are noisy, and that same-code reruns differ.

## Arms
Requirements-index arms (full rebuild from the newest run folder of all 23 documents into a throwaway collection `idxtest_<arm>`; production payload including citation; the live collections are never written):
- **control**: `build_embedding_text` unchanged (explained text + `Ref:`). Used for dense and BM25 (the same text feeds both).
- **head**: a first line `Section: <section_title_path joined by " > ">` in front of the control text. Rows with no section title path are identical to control.
- **head1**: same, with only the last (immediate) heading.
- **best combination** = head or head1 (whichever passes) plus a longer context cut. Because the cut cannot reach the search path (above), the combination equals the heading arm; no separate collection is built. A longer cut is judged on the probe and on cost only.

Context-cut arms (probe, **not** the search path): `idx_cut_probe.py` embeds every chunk of the newest run folders at cut 1500, 3000 and full text (dense only, in memory, nothing written to Qdrant), ranks all chunks for each gold question (raw question, no rewrite, no HyDE) and scores the rank of the chunk holding a gold row. This shows what a longer cut would do if the chunk vectors were ever searched. It also reports the share of scored queries whose gold row sits in a chunk longer than 1500 characters, and the share whose gold quote ends past character 1500.

## Runs (one Ollama job at a time, nothing else running; embedder and HyDE/rewrite model only)
- **prod mode** (rewrite + HyDE, no reranker): control x3, head x3, head1 x3. Three runs per arm because HyDE is sampled; the control spread is the noise.
- **nohyde mode** (rewrite on, HyDE off; deterministic given the index): control, head, head1, once each.
- **rerank mode** (nohyde plus the FlashRank reranker, pool 100; a sensitivity check, since production does not rerank): control, head, head1, once each.
- Probe: once.
- Build time of every arm is recorded (embedding plus upsert, seconds, whole library).

## Metrics (non-zero scored queries, expected 30; zero queries reported separately)
hit@1, hit@5, hit@10 (any gold row in the top k), recall@10, MRR (existing harness definition), all per query and averaged; segment means for narrow, broad, parent_child_context, table_derived, messy_pdf_overgrab; zero queries: mean results returned. Prod-mode numbers for an arm are the mean of its 3 runs. Noise = the range (max - min) of the 3 control prod runs on each of MRR and hit@5.

## Pass rule (fixed now)
A requirements-index arm (head or head1) PASSES if all hold in prod mode:
1. Mean MRR >= control mean MRR + max(0.02, control MRR range), and mean hit@5 >= control mean hit@5 + max(0.02, control hit@5 range). (Two points, and clear of the measured noise.)
2. No segment worse: for each of the five segments, arm mean MRR >= control mean MRR - 0.02.
3. Zero queries: mean returned count not more than 1.0 above control.
4. Build time at most 25% above control (embedded text is longer; stated up front because it will be).
EQUIVALENT (adopt only if it is also simpler or cheaper, otherwise no change): MRR and hit@5 each within 0.02 of control and no segment worse by more than 0.02, and build time not higher. Anything else FAILS (including improved on one metric but worse on the other).
Support, not required: nohyde and rerank modes point the same way as prod.

The context-cut change (3000 or full) PASSES only as a cost decision, since the search path cannot show a gain: it is adopted only if (a) the probe's MRR and hit@5 at that cut are at least 0.02 above cut 1500, and (b) context-index build time rises by at most 10%. If the probe shows no gain, the recommendation is to leave the cut alone (or drop the vector, which nothing queries; that is a direction decision for Tyler, not made here).

## Limits stated in advance
30 scored queries; the gold set was written and verified against the old method's rows and re-pointed here by a text rule I wrote (not hand-checked row by row, 24 old ids have no live row, some queries lost all gold rows), so absolute numbers are not comparable with earlier WP-37/43 numbers. The queries were used for earlier retrieval tuning (WP-43/45/46 spikes), so they are not blind. HyDE noise: three runs per arm. One embedding model, one library, no human grader; the author runs and reads the numbers. The probe is a what-if, not production behaviour.

## Safety
Only collections named `idxtest_*` are created and they are deleted at the end (`idx_cut_build.py --delete`). `grc_requirements`, `grc_context`, the live library and the config are read-only for this experiment.
