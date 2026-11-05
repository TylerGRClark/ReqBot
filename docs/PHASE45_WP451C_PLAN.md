# WP-45.1(c)/(d) — Fair retrieval test: plan (draft, local, untracked)

*Draft 2026-10-04, **revised the same day after Codex's review (`docs/PHASE45_WP451C_REVIEW.md`; changes marked "Codex")**. Nothing in this plan has been built or run. The parts marked
"measured today" are read-only checks I ran while writing it; they changed no files in the repo and wrote nothing to
Qdrant.*

## 1. The question, and what decision it feeds

WP-45.1(b) showed that about 40% of attached stems are right, 39% misleading and 20% incomplete, and that about
1,000 of the 1,847 records need a lead-in they do not carry. That is a **reading** problem. This test asks whether it
is also a **search** problem, because that decides what the later work packages are for:

- If missing or wrong context costs search rank, fixing attachment (C1–C4) is partly a retrieval fix and can be
  judged by retrieval metrics.
- If it does not, the fixes are about trust and readability, and the retrieval metrics are only a "did not get worse"
  guard.

Four questions, each answered by comparing **the same record under different embedded text**, so query difficulty
cancels out:

| # | Question | Records | Compared texts |
|---|---|---|---|
| Q1 (d) | Does a **wrong** stem hurt? | wrongly attached (40) | production (stem + quote) vs quote alone |
| Q2 (d) | Does a **right** stem help? | correctly attached (25) | production vs quote alone |
| Q3 | What is the **ceiling** for supplying the right context? | records Tyler's rulings say need a lead-in (82) | production vs adjudicated lead-in + quote |
| Q4 (c) | How findable is each group as it stands? | all four groups | production only, descriptive |

Q4 compares different records and different queries, so it is confounded by query difficulty. It is reported but is
**not** evidence by itself; Q1–Q3 are the evidence.

## 2. Prior art and facts established while writing this plan

1. **WP-37.2 tried a cheap approximation of contextual embeddings. It did not test the industry method, and its test
   could not have shown the benefit this phase cares about.** Checked today against `docs/PHASE37_REQUIREMENTS.md`,
   the saved results and the live index:
   - *What was built:* document title + the full `section_title_path` as a header line + a 100-character excerpt of
     `parent_context`, prepended to **every** record for both the dense and the BM25 vectors. The code was reverted
     before merge (PR #178 holds only docs and results), so the exact string per record cannot be rebuilt from the
     repo; only the written spec and one example survive.
   - *What the industry method is:* Anthropic's Contextual Retrieval has an LLM write a short situating description
     for each chunk. The backlog (item 6) marks that LLM version **untested**. 37.2 measured concatenated metadata,
     not that.
   - *What it was tested on:* 12 scored queries (7 narrow, 5 broad) plus 4 zero-answer queries, every one topical
     ("what are the requirements for X"). None asked who is responsible. The gold set has since grown to 45 queries
     (35 scored). The four broad queries that regressed carried most of the loss.
   - *Whether the heading was right for each record:* no. The leaf headings of the records those queries should find
     are a mix. Topical: "4.1 Hypervisor Security", "3. NM USE OF SNMP". Naming an actor: "2.17. MAJCOM/DRUs",
     "2.12. Air Force Deputy Chief of Staff, Operations (AF/A3)". Procedural, saying nothing about the topic:
     "3.3.1. Objectives.", "1.2. POLICY.", "3.7.2. Methodology.", "Actions", "3.2. DECLARATION.". A blanket prefix is
     informative for some records and noise for others, which fits the recorded hypothesis. It is still a hypothesis.
   - *What is supported:* a blanket, deterministic prefix on topical queries hurt. **Not** supported: "headings never
     help", or that a prefix chosen per record would hurt. My earlier word "killed" overstated it, and "do not repeat
     it" in the backlog is about the blanket version.
   - *Consequence:* the heading question is open in its selective form. See section 6, which sets out an extension that
     reuses this plan's apparatus and ends with a cheap ceiling test before any LLM stage is considered.
2. **The no-LLM question that remains is not a retrieval question. It is "is the 'who' already on the record?"
   Measured today, offline, on the audit sample.** Of the 31 sampled records Tyler's rulings place in the section
   heading, the stored `section_title_path` leaf carries every word of the adjudicated lead-in in **30**; the
   31st (R111) needs a second passage from the chunk body. They come from 11 of the 13 documents. In two cases an
   ancestor heading is also a "will:" line that is wrong (docling mis-nested "3.14." under "2. Policy. The AF
   will:"), so the usable rule is **leaf heading only**, never the whole path. Weighted to the population, about 600
   of the roughly 1,000 records that need a lead-in are heading-located (552 of the 860 without a stem). The sample
   is small (31) and the weighted interval is wide, so read this as "most", not as 60%.
   Consequence for WP-45.3: a deterministic "applies to" field taken from the leaf heading would supply the "who"
   for the heading-only majority with no LLM. The other half (same chunk 182, previous chunk 98, not shown 121)
   still needs C1/C4 or a second pass. This is a display/representation field, not an embedding change.
3. **A rebuilt text embeds to the live vector.** For 16 random records (6 with a stem), `build_embedding_text(payload)`
   re-embedded with `nomic-embed-text` on Tyler's Ollama gave cosine 1.000000 to the vector stored in the live
   collection. So variants embedded now are directly comparable with the live vectors.
4. **An in-memory copy of the live index ranks almost like the live server.** I scrolled all 1,845 points with
   vectors (read-only) into `QdrantClient(":memory:")` and ran 15 gold queries through the real `retrieve()`
   (HyDE and rewrite off) against both. Top-20 sets were identical in 13 of 15 queries and differed by one record in
   the other two; scores differ in the third decimal, so the order within near-ties differs. Conclusion: good
   enough for **relative** comparisons if every variant runs in the same engine, and that limit is reported. A
   scratch collection on the real server would be exact but writes to Tyler's Qdrant (see decisions).
5. **Group sizes from the final rulings, with exclusions resolved (Codex).** Of the 130 audited records, 18 are
   "not a requirement" and one stem was "not needed" (the same record as one of the 18), leaving **112 eligible**.
   Explicit ID lists are frozen in `groups.json` before any query is written. Groups: right stem 25; **misleading** stem
   22 (14 wrong sibling, 8 wrong other); **incomplete** stem 11 (fragment chain, kept apart because removing a useful
   partial stem may behave differently from removing a wrong one); no stem but needs a lead-in 36 (16 heading, 11 same
   chunk, 8 previous chunk, 1 not shown); no stem and complete (control) 18. 12 of the 58 stemmed records have a quote
   that is already complete; they are reported as their own subgroup. The earlier "40 wrong stems" counted records
   later excluded. None of the 130 has an identical quote elsewhere in the corpus (46 of 1,847 records do), so "the
   target" is unambiguous. These are small groups: **only large shifts can be told from noise**, and a null result
   cannot be read as "no harm".

## 3. Design

**Records.** The 112 eligible audited records, with explicit ID lists in `groups.json` (hashed), taken from the final
adjudicated labels in `audit_results/`. No new labeling. The Q3 oracle set is the 82 that need a lead-in (46 with a
stem, 36 without).

**Queries (written once by Claude, before any retrieval, frozen and hashed).** For every eligible record, two queries
written from the *meaning*, kept together as one unit per record:
- *topic*: what an analyst would ask about the obligation's subject, without naming the responsible party unless the
  party is part of the obligation itself;
- *party + topic*: the same question naming who it applies to (from Tyler's adjudicated lead-in or heading).

The writer sees the record's full intended meaning (quote plus adjudicated lead-in), **not** its group (records are
shuffled, group labels held out), and no retrieval output. Natural wording is kept; ordinary terminology overlap is not
leakage (Codex), so overlap is reported per query rather than policed, and results are also shown restricted to queries at
or below the median overlap. About 224 queries. A spot-check of a small selection happens before the first run; the 35
scored gold queries and the topic-only queries stay in as counterchecks. One-target recovery measures whether the
expected record was found, not whether other returned records could also answer; that limit is stated with the results.

**Index and substitution (Codex: isolate the target from its competitors).**
- *Engine:* in-memory copy of the live corpus (all 1,845 points' vectors read once, read-only), with the live vector
  configuration preserved (checked: dense 768 cosine; sparse BM25 with no IDF modifier, matching the live collection).
- *Primary diagnosis, target-only substitution:* for each target and each arm, replace **only that target's** dense and
  sparse vectors, run that target's queries, restore. Every competitor keeps its production vector. This isolates
  whether the target's own text change helps or hurts. Replacement vectors are built once and reused; the text variants
  themselves are saved and hashed, not just the recipes.
- *Secondary check, cohort-wide substitution:* apply the policy to the whole cohort (all 203 stems removed; all oracle
  contexts applied; a heading arm applied wherever its rule fires) and report what that does to the search result as a
  whole. Reported separately from the primary effect and never merged with it.
- Arms: production (live vectors); quote alone (the 58 eligible stemmed records, `source_quote` + `Ref:`); oracle
  (adjudicated lead-in + quote + `Ref:` for the 82). The oracle is an **informative benchmark**, not an upper bound
  on retrieval (Codex): correct context can still dilute an embedding or promote competitors, and concatenation tests one
  representation of correct context, not every use of it.

**Retrieval configuration (frozen and recorded).**
- *Headline run:* `hyde` off and `no_rewrite`, so query vectors are identical across arms.
- *Production-path run (8B model allowed without asking, per Tyler):* rewrite and HyDE generated **once per query and
  repeat**, text and vectors saved, then reused for every arm; three repeats, each kept paired (Codex: otherwise a changed
  invented hypothesis can pass for a change in document context). Done by patching `rewrite_query` and
  `generate_hyde_hypothesis` in the eval script only, so the real `retrieve()` runs with fixed inputs.
- *Depth (Codex, verified in `core/ask.py`):* `retrieve(top_k=100)` would change per-leg prefetch from 100 to 500. At
  `top_k` 20 and `min_score` 0.02 it prefetches 100 per leg, fuses 60, filters by score, returns 20. The eval adapter
  therefore issues the same legs itself with the same 100-per-leg prefetch and a wider fused limit, labelled as a
  diagnostic, and derives the returned list exactly as production does. **Before any result is used, the adapter is checked
  to reproduce the real `retrieve()` output on the gold queries with the same cached inputs.** Reported per record:
  raw fused rank, whether the target survives the score threshold, and whether it is in the returned 20.

**Metrics.** Recall@5, @10, @20 and reciprocal rank per record and arm, with ties reported as best and worst case.
Paired differences with a **record-level bootstrap** (10,000 resamples, fixed seed; a record's two query styles stay
together, and repeats are not extra records), plus a document-level bootstrap as a sensitivity check. Topic and party
queries are reported **separately**; pooling can hide the benefit the heading hypothesis predicts. Every table shows n.

**Decision rules, set before looking (Codex edits).** "Meaningful" = a paired change in recall@10 of at least 0.10
whose interval excludes zero, under both tie conventions. A point estimate under 0.05 with a wide interval is **not
evidence that context has little value**; it is reported as "no demonstrated improvement".
- D1. Misleading stems cost rank if quote-alone beats production by a meaningful amount on that group (incomplete
  stems judged separately).
- D2. Right stems have retrieval value if production beats quote-alone on the right-stem group.
- D3. Supplying adjudicated context improves search if the oracle beats production meaningfully on the needs-lead-in
  group, topic and party queries separately. Otherwise: no demonstrated improvement.
- D4. Q4 (findability of each group as it stands) stays **descriptive** whatever its apparent significance.
- Regardless of D1 to D4, correcting wrong actors stays worthwhile on attachment precision (Codex).

**What this cannot tell us.** Whether real users phrase questions like these queries (the same model that proposed the
hypotheses writes them; mitigated by blindness to results, frozen files, the overlap report and a Codex spot-check, not
removed). Records that were never extracted (45.1(e)). Anything beyond these 13 documents.

## 4. Deliverables and process

One branch, `eval/wp-45-1c-retrieval-test`, branched from `main` first. Under `eval/spike_results/wp_45_1c/`:
`groups.json`, the frozen `queries.jsonl` and its writing instructions, the retrieval-test scripts (in-memory index,
variants, adapter, scoring), a README with results, and `outputs/` with per-record ranks and a manifest (live
collection name and point count, a digest of the scrolled ids and vectors, hashes of the saved text variants and cached
query inputs, code digests, model digests, config). Unit tests for the pure pieces: group construction, variant text
builders, tie-aware rank, paired bootstrap, overlap measure, and a test pinning the adapter's returned-list logic to the
production constants. No production code changes. Codex reviews this plan (done), then the PR; Gemini reviews the push.

## 5. Decisions

Answered by Tyler 2026-10-04: Claude writes the queries; the 8B model may be used freely; the heading arm goes to Codex
(done, `PHASE45_WP451C_REVIEW.md`); and he asked me to take the remaining calls on the strength of that review.

- **Engine:** in-memory first (Codex and my recommendation). If an apparent win depends on small ordering differences,
  that candidate is re-validated against server-backed scratch collections before anything is recommended. That step
  writes to Tyler's Qdrant, so it is asked about then, not now.
- **Heading arm:** included as section 6, starting small.
- **Scope of this work:** measurement only. No production change, no new LLM feature, no write to the real Qdrant.

## 6. Extension: the heading, tested selectively

*Why.* 37.2 does not settle whether a heading helps when applied only where informative, and Tyler's second-pass idea is
exactly the selective form. Step D.5 today sees only `source_quote` and `source_ref`, never the heading or stem. The
pipeline's two generation calls are Step C (extraction, one chunk at a time) and Step D.5 (enrichment: description,
domain tags, requirement type, many quotes per call).

*First run (Codex): H0, H3 and H4 only.*
- **H0 production** (control).
- **H3 leaf heading, only where a deterministic rule calls it informative** (the leaf ends in "shall:" or "will:", or is
  an actor heading, and is not on a short list of procedural labels such as Objectives, Policy, Methodology, Actions,
  General, Declaration). **The rule and the label list are frozen before any retrieval.** Codex reviews H3's assignments
  for source correctness against the audit, without seeing retrieval results, because an actor-shaped leaf heading is not
  necessarily the actor governing every record below it. That check must pass before any "applies to" display field is
  recommended.
- **H4 selection by Tyler's rulings:** leaf heading added only for the audited records placed in the heading (31). An
  informative benchmark, not a bound on what any selection or generated description could do.
- Each arm with the prefix in dense only and in dense + BM25, since BM25 may be where boilerplate words do the damage.
- **Later, only if the selective comparison leaves a question open:** H1 (reconstruction of 37.2) and H2 (leaf heading on
  every record). H1 cannot reproduce the historical experiment on today's corpus, models and query set, so it is background,
  not a prerequisite.

*Queries:* the party + topic and topic queries from section 3, with the 35 scored gold queries as a counterweight so a
gain on party questions that costs topical ones is visible.

*Reading the result.* If verified headings show no convincing benefit, deferring the LLM experiment is a **resource
decision** (it has not earned priority), not proof an LLM could not help (Codex). If H4 helps and H3 captures most of
it, a rule is enough. If H4 helps and no rule gets close, a D.5 prompt change is worth proposing; that is a new LLM
behavior and needs Tyler's approval, and per backlog item 6 it must be told to skip procedural headings.
