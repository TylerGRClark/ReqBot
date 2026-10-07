# WP-45.11 — three Docling-related changes, tried one at a time against a measured noise floor (plan, pre-registered)

*Status: plan only; no extraction has been run for it. Follows the Docling audit ([PHASE45_WP4510_PLAN.md](PHASE45_WP4510_PLAN.md), results in #246). The owner asked for a trial of the Docling update and said the chunk-limit change is probably worth doing, but is worried about changing too many things at once and then not being able to tell what each one did. Local model time is free (owner, 2026-10-07).*

## 1. The problem this plan is built around

The audit found three candidate changes: **T1** move Docling from 2.94.0 to 2.122.0; **T2** make `_chunk_raw_text` keep tables as grids in merged chunks (today 9 of 56 tables reach Step C as the chunker's flat text); **T3** raise the chunk token limit (74% to 98.6% of labeled lead-ins land in the quote's chunk at 1,024 tokens). T3 depends on T2: without it a larger limit turns 37 of 56 tables flat. Done together, a change in the extracted requirements could not be assigned to any of them. Step C is also not repeatable: it samples at temperature 0.1 with no seed, so two identical runs differ. Any "effect" has to be larger than that difference to mean anything.

## 2. Design: every arm changes exactly one thing

| Arm | What differs from the arm it is compared with | Compared with |
|---|---|---|
| **B0a, B0b** | nothing: two independent replicate runs of today's pipeline (Docling 2.94.0, 256-token chunks, current code) | each other: this is the **noise floor** |
| **T1** | Docling 2.122.0 (conversion and its default chunker) | B0 |
| **T2** | `_chunk_raw_text` resolves each chunk item to its real type by `self_ref` before building `raw_text`; limit stays 256 | the accepted Docling choice of T1 (B0 if T1 is not adopted) |
| **T3** | chunk token limit (one value at a time, starting at 512 then 1,024, tokenizer unchanged) | the accepted state after T2 (T2 is a precondition: T3 is not run on the unfixed table path) |

An arm is adopted or not **before** the next arm is built on it, so each comparison is one change against an unchanged base. Arms T1 and T2 do not depend on each other, so T2 is also run once on B0 if T1 is not adopted; T3 is always run on the state with T2.

**What is held fixed in every arm.** The 13 pinned documents (source-PDF SHA-256 checked against `wp_44/after_replay_summary.json`); the extraction model `llama3.1:8b-instruct-q4_K_M` on the owner's server, its digest recorded in each run; the Step C prompt, Step D rules and parent-stem reconstruction, all unchanged and run by `pipeline/run_pipeline.py --skip-to C` on a scratch copy of the arm's chunk files; enrichment skipped (it does not change quotes). Each arm writes to its own scratch directory; nothing touches `~/documents/processed`, Qdrant or the repository's pipeline code. Each arm's chunk files are hashed into its manifest, and the Docling and `docling-core`/`docling-parse`/`docling-ibm-models` versions are recorded (the audit showed the transitive packages are unpinned).

## 3. Measures (fixed now)

1. **Recall on the source-based sample** (WP-45.1(e): 74 labeled obligations on 3 documents, `eval/spike_results/wp_45_1e/`). Each arm's Step C output is traced exactly as that work did. Reported as the count extracted, and **paired by obligation**: which obligations are found in the arm and not its comparison, and the reverse. Known limit from that work: an interval of about 44% to 77% for the baseline rate and one piece each way of run-to-run noise.
2. **Run-level, all 13 documents:** Step C records, Step D survivors, Step D failure codes, chunks and calls; overlap of normalized quote sets with the comparison arm, against the overlap between B0a and B0b.
3. **Targeted measure per arm.**
   - T1: structure counts (code items, list items, tables, headings) are already known to be unchanged on these documents; the targeted question is whether extraction on 2.122.0's chunks loses or gains obligations (measure 1) and quotes.
   - T2: every Step C record from a chunk that holds one of the 9 tables that are flat today, before and after, **all read by me**: is the quote now a grid row, is it still grounded in the chunk, did requirements from those tables appear or disappear.
   - T3: of the 145 labeled quotes (audit and fresh gold), the share the arm still extracts (matched by normalized text), the share of those with their lead-in in the quote's chunk, and the share whose production `parent_stem` overlaps the labeled lead-in text (the WP-45.7 overlap rule; a lenient proxy that credits party-less fragments, stated again here).
4. **Cost:** calls and wall time.

## 4. Decision rules (fixed now)

An arm is *adopted for a production pull request* only if all hold; otherwise it is reported and dropped (or revised as a new, separately registered arm):
- **R1 no recall harm.** Recall pieces (of 74) not more than 2 below the lower of B0a and B0b (T1, T2) or of the comparison arm's own replicate range (T3 uses the T2-state run and one replicate of it, since the noise floor is the B0 range).
- **R2 no collapse.** Total Step D survivors across the 13 documents within 10% of the comparison arm's; any single document more than 25% different is listed and read.
- **R3 targeted gain** (T2: at least one of the 9 tables now yields grid-row quotes and none of its previous grounded records disappears without an explanation I read; T3: gold quotes still extracted at least 90% of the comparison arm's, and the co-located share up by at least 5 points). T1 has no gain requirement: it is adopted if R1 and R2 hold and the owner wants the newer release (it carries OCR fixes seen in the audit and a less-pinned risk); the audit's rule-(c) shortfall of 2 items is acknowledged.
- **R4 differences read.** Every obligation that is lost against the comparison arm is shown with its source text and both arms' records.

Anything the noise floor cannot separate (a recall difference of one or two pieces) is reported as **not distinguishable from noise**, never as an effect, in either direction.

## 5. Order and what needs the owner

1. **Now (no approval needed):** B0a and B0b on all 13 documents; the Docling 2.122.0 arm T1 (the owner asked for this trial). The 2.122.0 chunks come from a separate virtual environment; Step C runs the same way.
2. After T1's result: report to the owner; adopt (a separate pull request moving the pin in `pyproject.toml`, also pinning `docling-core` since the chunker comes from it, which is a dependency change) only on the owner's go-ahead.
3. T2: scratch evaluation first; the production fix to `pipeline/chunk_text.py` is its own pull request with tests, after the result and the owner's go-ahead. It changes `raw_text`, so it changes what Step C reads; chunk ids do not change at limit 256.
4. T3: scratch evaluation on the T2 state; adopting a larger limit changes every chunk id, forces Step C re-extraction and a reindex of the live corpus, which is the owner's decision after seeing T3's result.

## 6. What this plan does and does not claim

- It can show that a change does no harm that is larger than noise, and where the changed output differs, read piece by piece. It cannot show a small recall gain: 74 obligations on 3 documents and a noise floor of a piece or two cannot resolve it. The other 10 documents have no recall labels, so only descriptive measures apply there.
- Extraction that finds more obligations is only one of the goals; the lead-in problem (T3) is measured through the labeled gold and the production stem, not through recall.
- B0 is today's pipeline re-run, not the July production data: the code has changed since (WP-42 table serialization and others), so the baseline is built fresh in the same session as the arms.
