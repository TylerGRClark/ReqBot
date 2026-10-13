# HyPE spike: pre-registration (committed before any result exists)

Question: do pre-written, index-side questions (HyPE) find requirements that meaning-queries currently miss?
Plan source: the owner-approved test plan of 2026-10-13 (docs/TODO_future_improvements.txt item 3).

## Arms

- **A** = today's retrieval, unchanged: `core.ask.retrieve()` against the live `grc_requirements` alias (hybrid dense + BM25 + HyDE, RRF), config defaults, top 20.
- **B** = the same retrieval against a scratch copy of the same points plus up to 3 generated questions per record, each stored as an extra point that carries its record's `requirement_id`. Hits are collapsed to `requirement_id` (best-ranked point wins) before the top 20 is cut and scored.
- Query rewrite and the HyDE hypothesis are generated once per query and reused by both arms, so the arms differ only by the extra points (HyDE samples at temperature 0.3; unshared, it would add noise).
- Nothing live changes: scratch collection `grc_hype_spike_<timestamp>`; questions are never written to requirement JSONL or to `source_quote`.

## Question generation

Same local model the draft audit questions use (`services.audit_questions.MODEL`), temperature 0, up to 3 questions per record. A question is kept only if every number, acronym and capitalised term in it appears in its own record's text (`services.audit_questions.unverified_terms`).

## Query sets (fixed here, before any result)

1. **Miss set**: `miss_queries.jsonl`, 15 queries written from the meaning of the record (stem plus fragment), avoiding the fragment's own wording. They come from the WP-40 audit's 9 `missing_context` misses (4 ids changed in the re-ingest; all 9 were re-found by exact quote text) and 6 of the WP-44.2 dangling fragments that still exist.
2. **Gold set**: `eval/gold_retrieval_queries.jsonl`, scored on precision@5. Many gold ids no longer exist in the live collection (re-ingest), so labels are restricted to ids that exist live; queries left with none, and the zero-truth queries, are not scored.

## Decision rule (do not alter)

B is worth building only if recall@5 on the miss set rises by at least 15 points AND precision@5 on the gold queries falls by no more than 2 points. Otherwise record and stop. Machine-readable copy: `decision_rule.json`.

## Known limits, stated in advance

- 15 miss queries: one query is 6.7 points, so a rise of 15 points needs at least 3 more queries found (20 points); 2 more (13.3) does not pass.
- The miss queries were written by an agent that had read the target records; "from meaning" is a judgement, not a guarantee.
- The miss set is not all "misses": arm A may already find some, which leaves less room to rise. Arm A's recall on it is reported.
- One run, no repeats; the local model is deterministic at temperature 0 but not guaranteed bit-identical across runs.
- Gold labels are partly stale (see above); the precision comparison is still paired on identical labels.
