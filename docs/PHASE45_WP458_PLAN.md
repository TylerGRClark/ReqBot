# WP-45.8 — bring the selection resolver toward the pipeline: a shadow run on the whole corpus, then a retrieval test, before any pipeline code (plan, pre-registered)

*Status: plan only, no code and no model runs yet. Follows the WP-45.7e PASS ([PHASE45_WP457E_PLAN.md](PHASE45_WP457E_PLAN.md), verdict in #242). The owner said the new method is "worth keeping and integrating" and asked to plan it; this plan does not touch the pipeline.*

## 1. What is established, and what is not

Established (WP-45.7e, one-shot, fresh candidates, one labeler): the selection resolver (menu `menu_v2.py`, `qwen2.5:14b`, kind prompt `6200fa25a374eb35`, tier R2) attached the right lead-in or actor to 65 of 104 candidates against production's 41, with 0 invented parties, 0 modality errors and about one second per call. It misled on 39 (production 36) and left nothing unconnected (production 27).

Not established, and why this plan is not "write the pipeline step":
- **Attachment accuracy is a proxy.** WP-45.1(c)/(d) showed that a *correct* stem is what raises recall@10, and that a wrong stem does not hurt its own record's rank. Nobody has measured the resolver's stems in retrieval. That is the test of whether the work pays off.
- **The test candidates were a sample.** The resolver has never run over a whole document or the corpus: records with no menu, very long chunks, tables, records from the 8B's other extraction shapes.
- **One labeler, thin margins** (3 and 2 records), and a second labeler did not reproduce the pass. A blind second Claude (a subagent given only the pack and rubric; the isolation was an instruction, not a lock, and its transcript shows it opened only those files) labeled the same 114 cards. Agreement: 109 of 114 on complete / needs a lead-in / not a requirement; 59 of 66 on where the lead-in is; 44 of 58 on whether production's stem is right. The resolver's saved answers (not re-run), rescored under its labels with the same gates: attachment right 58 of 100 (bar 62; production 42), misleading 42 of 100 (limit 34; production 29), incomplete 0 (production 29), real rejected 0, non-requirements rejected 9 of 11, 0 invented, 0 modality errors. Two gates fail, by 4 and 8 records; the other seven pass. The verdict itself stands (it was registered against the first labels and run once); the point is that the *size* of the gain depends on the labeler. Direction does not: the resolver beats production's right rate by 16 points (second labeler) to 23 points (first), leaves nothing unconnected, and invents nothing. Details are reported in a separate PR (README step 28 of `eval/spike_results/wp_45_7/`). A second labeler's result is **not** a gate of this plan; it is why Stage B (retrieval) matters more than the attachment rate alone.
- **Determinism and failure behaviour** are untested outside the experiment harness.

## 2. Things that need the owner's approval before pipeline code (stop-and-ask list)

Writing the pipeline step would touch four items on the standing stop-and-ask list. None is decided here; Stages A and B are built so they need none of them, and the answer is requested only after Stage B:

1. **A new LLM call in the pipeline.** It is *selection*, not generation (the model chooses ids; every returned span is a verbatim substring of the document, and code writes the kind and strength), but it is a new place Ollama is called and the owner decides whether that qualifies and where it sits.
2. **A second model requirement.** The pipeline today extracts with the 8B; the resolver was frozen on `qwen2.5:14b`. Shipping it means a second model must be present (size, air-gapped installs, speed on non-GPU machines).
3. **JSONL schema.** Production writes `parent_stem` and `embedding_text`. The resolver also yields a kind (requirement, scope or context, not a requirement, unresolved), a code-set strength with its source, and the chosen actor. Reusing `parent_stem`/`embedding_text` changes the *meaning* of an existing field; adding fields changes the schema. Either needs approval.
4. **Qdrant text.** `embedding_text` feeds the index; changing what it holds changes what every record embeds and needs a reindex.

## 3. Stages

**Stage A — shadow run (offline; nothing in the pipeline, nothing in the corpus).**
Scratch scripts in `eval/spike_results/wp_45_8/`, writing to a scratch directory only; no Step C cache and no `*_requirements_*.jsonl` is touched. The resolver as frozen in WP-45.7e (code-hash manifest reused, no change to the menu, prompt, checker or model) is run over every record of the newest run of each processed document, from the saved Step C output and chunk files.
- The string that would be attached is fixed here, before Stage B: the chosen actor span and the chosen parent span (each verbatim), joined with ` | ` when both exist; empty when neither. Stage B retrieves exactly that string.
- Reported: record count and calls; seconds per call and total; how many records got a stem, a kind other than `requirement`, or no menu; how many differ from production's `parent_stem`, and by what route (production none → resolver some, both some and different, production some → resolver none); a seeded sample of 40 changed records printed for the owner to read; **determinism** (a seeded 200-record rerun; every answer identical or the differences listed); **failure drills** (Ollama unreachable, empty or oversize chunk, a record with no chunk id) — each must end in "no change, flag only", never a crash and never a dropped record.
- Gate on Stage A: zero crashes; zero dropped records (the output has every input record, with a flag where the resolver abstained); zero spans that are not a verbatim substring of the document; determinism differences reported, not hidden.

**Stage B — retrieval test (the question that decides integration).**
Reuse the WP-45.1(c)/(d) apparatus (`eval/spike_results/wp_45_1c/`: frozen groups, blind-written queries, in-memory engine) as it stands. Three arms on the same frozen groups: production stems, resolver stems from Stage A, no stems. The gate shape, with thresholds registered in a short registry PR *before* any Stage B number is computed (the same discipline as v3 to v6): recall@10 for the resolver arm not worse than production's by more than a registered tolerance on the **`right` group** (records whose production stem is correct, which the resolver would replace whenever it does not abstain; WP-45.1(c) found that removing correct stems costs recall) and on the control group; better than production on the stemless group by at least a registered margin; the party-named question group reported separately. The WP-45.1(c) limits stand: small groups, the proposing model wrote the queries, 13 documents.
- If Stage B does not pass, integration is not proposed; the result is recorded and the owner chooses (menu tightening for the 39 misleading answers, a reviewer pass, or stop).

**Stage C — pipeline step (separate plan, after Stage B and the owner's answers in section 2).**
Not designed here beyond constraints already known: the deterministic production reconstruction (WP-39.2) keeps running first and is the fallback whenever the resolver is unavailable or abstains, as its own docstring requires; results are cached by everything that shapes the answer (the rendered bundle hash plus the menu hash, which cover the quote, chunk, previous chunk, headings and Step C stem candidates, together with tier, prompt hash, model digest, inference parameters and the code-manifest hash, as the experiment runner already keys them in `run_selection.py`) so unchanged reruns and resume make zero calls and any changed input cannot reuse a stale selection; every record is kept (flag, never delete); no `source_quote` is ever altered.

## 4. What this plan does and does not claim

- It claims nothing about retrieval yet. The 65-of-104 attachment result does not by itself say searches improve; Stage B does.
- It does not enlarge the evidence for attachment accuracy: the second labeler and the held-out pack (454) remain separate, reported items.
- It adds no model, field or pipeline code. If the owner prefers to decide the section 2 items first, Stages A and B are unaffected.
