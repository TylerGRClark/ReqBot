# ReqBot Phase 45 — Pipeline Integrity and Extraction Quality

**Status:** Plan — draft, revised 2026-10-04 after the pipeline audit; awaiting Codex review. Not started; no
branch yet.
**Date:** 2026-10-04
**Preceded by:** Phase 44 (Source-Quote Integrity) — `docs/PHASE44_REQUIREMENTS.md`. Its §12 findings,
`docs/TODO_future_improvements.txt` items 34-37 and guardrail 11, and an external pipeline audit (ChatGPT,
2026-10-04) whose findings were verified against the code and corpus (Appendix A) are the inputs.
**Followed by:** Phase 46 (retrieval and answerability), proposed in §8. HyPE remains a **separate package**
for its own phase (`TODO_future_improvements.txt`, Retrieval Experiments item 3).

---

## Status

| WP | Status |
|---|---|
| WP-45.0.1 — Reindex coverage guard | **Done** — merged 2026-10-04 (#202, 7a76f76); live corpus verified 1,845/1,845 requirement and 839/839 context points |
| WP-45.0.2 — Step C completion ledger | **Done** — merged 2026-10-04 (#203, ac65c73). Truncated = kept and flagged (Tyler chose B) plus one bounded larger retry; old runs resume with 0 LLM calls; backlog item 46 records the unpinned D.5 window |
| WP-45.1 — Measurement foundations: fragment census, root causes, fair retrieval test, source-based sample | In progress: (a) census **done** (#204, 9898504); (b) attachment audit **done** (#205 pack, #206 results, bd04994; Tyler adjudicated all 16 disagreements and confirmed 10 of 10 spot-checks). Findings: ~40% of attached stems right, ~39% misleading, ~20% incomplete; ~54% of all records need a lead-in, ~860 of 1,644 no-stem records, mostly heading-only. (c) and (d) fair retrieval test **done** (#207, 8b807e1; measurement only): supplying the adjudicated lead-in to stemless records raises recall@10 in every run (+0.11 to +0.26 topical, +0.21 to +0.28 party-named); a wrong stem does not hurt its own record's rank; correct stems matter (removing all stems costs the gold queries ~0.09 recall@10); a selective leaf-heading rule helps party-named questions only (~+0.10 to +0.14, needs BM25 text), 7 of its 49 audited picks name the wrong party; (e) source-based sample **done, merged 2026-10-05 (#210, 35b365c)**: on 12 sampled pages of 3 documents about 60% of the obligations in the source reach the index (45 of 74, interval 44 to 77%); nothing is lost at parsing or chunking, 1 piece at Step D, none at indexing; the loss is at extraction (26 of 74 never extracted). Tyler's rulings counted duty statements without shall or must as obligations; 10 of 10 spot-checks held |
| WP-45.6 — Extraction-model comparison: a larger local model against the 8B baseline (measurement only) | **Done** — merged 2026-10-05 (#208, 8b3d8a9). With the unchanged production prompt `qwen2.5:14b` kept 173 records against the 8B's 435 (-33% formal policy, -94% guidance prose), very precise but missing roughly 200 real requirements; no demonstrated meaningful improvement. Prompt held fixed, so model-and-prompt, not the model alone; recall against the source waits for WP-45.1(e) |
| WP-45.0.3 — Duplicated chunk text from split paragraphs | **Deferred** (Tyler, 2026-10-04): dedup absorbs it; revisit only if the C4 pilot needs it |
| WP-45.7 — Discovery/resolution split: inclusive discovery prompt and an evidence-bundle resolver (measurement only, scratch) | **Approved by Tyler 2026-10-05; plan merged** (#211, 730d678), plan in `docs/PHASE45_WP457_PLAN.md`. Steps, one PR each: held-out draw and labeling pack (no LLM), then the evidence-bundle builder, then runners and checker, then the runs. Follows the WP-45.1(e) finding that the loss is at extraction; overlaps WP-45.2 C4 and WP-45.3, and is the test of which to build. **Dev side done 2026-10-06:** D1 discovery +30 points of 8B recall (held: held-out confirmation needs the second labeler); the generative resolver failed G2 (#222); the WP-45.7b selection resolver (plan #223, generator #224, code #225, runs #226-#228) also failed G2 as registered (best 60.0% attachment vs bar 63.6%, 0 invented, production 34.5%). Evaluation half unread, held-out resolver not run. Options for Tyler in `eval/spike_results/wp_45_7/README.md` step 16 |
| WP-45.2 — Fragment attachment (deterministic fixes, then extraction-side context; one at a time) | Planned, after WP-45.1 |
| WP-45.4 — Junk gold set and detector evaluation (flag only) | Planned, after WP-45.1 |
| WP-45.9 — Quote-fidelity flag (flag only) | Planned, after WP-45.4 |
| WP-45.3 — Grounded standalone statement (LLM; needs Tyler's approval) | Planned, after WP-45.2 and approval |
| WP-45.5 — Review state for flagged records (design first; needs Tyler's approval) | Planned, after WP-45.4 |

Numbering keeps the original WP-45.1 to 45.5 stable for reviewers; the new integrity work is 45.0.x, the model
comparison is 45.6 and the new quote-fidelity work is 45.9.

---

## 1. Phase Framing

**The strength of the extracted requirements is the cornerstone of ReqBot (Tyler):** retrieval, evidence,
comparison, checklists and the MCP surface all inherit it. Phase 44 closed the invented-quote leak (WP-44.1) and
measured what remains (WP-44.2). An external audit of the pipeline was then checked finding by finding against the real code and the
13-document corpus (Appendix A). What that changes:

1. **Wrong parent stems are the largest measured quality problem.** Of 16 same-chunk stem attachments I
   hand-labeled, 7 looked wrong (a sibling bullet used as the stem, or a fragment chain). The mechanism is
   confirmed: any earlier record with no colon, no list marker and no terminal punctuation is accepted as a
   stem. This is a lead (one reviewer, 16 records), to be confirmed by WP-45.1. Fragments themselves remain the
   other half of the problem: of 16 fragment survivors inspected in Phase 44, 10 have a stem, at least 2 look
   wrong, and 6 are embedded bare.
2. **Junk requirements** remain: a hand-labeled random sample of 60 of 1,845 survivors (one reviewer,
   unaudited) was 77% real, 10% borderline descriptive, 5% fragments, **8% pure junk** (roughly 3-18% at 95%
   confidence). No simple text rule separates these.
3. **Two real, cheap, latent integrity defects** (reindex can promote an incomplete index; a failed Step C
   request is treated as finished work on resume) have not damaged the corpus (0 Step C failures, 0 missing
   index points) but would bite a first-time user and weaken any experiment built on top. They are small and go
   first. A third (the chunk adapter re-expands split paragraphs, 1.9% of chunks) is deferred: dedup absorbs it.
4. **Several audit findings do not justify work yet** (identity redesign, scope-splitting chunks, embedding
   truncation): no harm was observed. They are deferred in §7 with reasons.

**Principles (Tyler, 2026-10-04; `TODO_future_improvements.txt` guardrail 11):**
- **Never discard a dangling fragment.** It carries a real obligation and belongs attached to its parent clause
  before embedding. Fixing it is attachment work, not rejection work.
- **Flag, don't delete.** Anything that might be junk goes to a recoverable review state. A detector ships only
  when a labeled gold set shows it stays above an explicit recall floor.
- **No stem beats a wrong stem.** When attachment is uncertain, leave the fragment visible and unattached
  (the Step D precision bias), rather than attach a sibling.
- **ReqBot works today.** One change at a time, each proven by a measurement before and after, and each stopped
  if it does not help. Fix completeness defects before comparing semantic variants.
- **A synthetic probe proves a defect exists, not that it matters.** Only corpus measurement sets priority.
  Phase 44's lesson on generalization stands: a threshold selected on a corpus and replayed on the same corpus
  proves the implementation, not generalization, so build held-out data first.

---

## 2. Goals

1. Make index promotion and Step C resume safe against partial failure.
2. Measure, fairly, how well dangling fragments are found and attached today, and why attachment fails.
3. Raise the share of fragments attached to the *right* parent, and make them usable as standalone requirements.
4. Build a labeled gold set, including obligations never extracted, and use it to evaluate junk and
   quote-fidelity detectors that flag rather than delete.

## 3. Non-Goals

- **No deletion or rejection of fragments.** No silent dropping of any record.
- **No HyPE and no retrieval-side change** (reranker, HyDE, fusion, query handling) in this phase; see Phase 46.
- **No JSONL schema change, Qdrant payload/collection change, new dependency or new LLM-generation feature
  without Tyler's explicit approval** (stop-and-ask list). Where a WP below needs one, it is marked and gated.
- **No re-extraction (Step C) of the live corpus** unless a WP's measurement shows it is needed and Tyler
  approves. Pilot re-extractions (WP-45.2 C4, WP-45.6) write only to a scratch directory.
- **No identity (`REQ-` ID) change.** It would force a reindex and break references; no harm justifies it.

---

## 4. Track 0 — Pipeline integrity (small, guard-style, first)

The first two come from the audit and were reproduced against the real code (`eval/spike_results/wp_45_audit/`).

### WP-45.0.1 — Reindex coverage guard (audit F08)

**Why.** `_reindex_requirements` and `_reindex_context` ignore the count that the indexers return, then swap the
alias and delete the old backing collection. An individual failed embedding is logged and skipped, not raised,
so one failure would replace a complete live index with an incomplete one. Today's live index reconciles
exactly (1,845 expected, 1,845 live), so this is protection, not repair.

**Change.** *(As built: no strict mode in the indexers. The post-hoc coverage check below is authoritative for every
cause, including an embedding failure, and leaves `run()`'s contract and the single-file `ingest` warn-and-skip
behavior untouched. Both indexers gained `*_point_id` and `expected_point_ids` helpers so the guard and `run()`
share one ID formula.)* Reindex refuses to swap when coverage is incomplete,
leaving the live alias and previous collection untouched. Coverage means the **distinct eligible point IDs**
(point IDs are uuid5 of `requirement_id`, so a repeated ID collapses to one point and a row count would not
match), checked against the temp collection itself before promotion, for requirements and for context
independently. Missing context chunk files are listed in the summary rather than only logged, and the plan
must say whether that is a refusal or a flagged skip. Reconciliation proves recorded point identity only, not
payloads, vectors or extraction completeness (Codex review of PR #201).

**Gate.** Unit tests with an injected dense failure and an injected sparse failure, for requirements and for
context, plus a duplicate-ID fixture and a missing-chunk-file fixture: reindex returns failure and the live
alias is unchanged; the normal path produces identical points. Full suite and ruff green. No live
Qdrant action. No approval needed (no schema or payload change).

### WP-45.0.2 — Step C completion ledger (audit F02)

**Why.** `process_chunk` stores a prompt hash even when the request failed (`raw_response` is `ERROR: ...`) or
the output did not parse, and the cache loader accepts every stored hash. A resume therefore skips the chunk and
the requirements file stays empty. Reproduced with the real `run()` and a mocked transport. None of the 839
chunks in the corpus failed, so nothing is missing today; the exposure is a newcomer on CPU-only Ollama, where
the 120-second timeout is easy to hit, followed by a resume.

**Change.** A chunk counts as complete only when its response parsed **completely** and its output is durable
(a valid empty array counts). Step C also recovers objects from a truncated array (`recovered_truncated`), and
that is some recovered JSON, not a complete response: decide whether a truncated chunk is retried, or kept and
flagged, before coding. Failed, unparsed and (per that decision) truncated chunks are retried on resume. Write
the raw record last, after its requirements, so a crash between the writes cannot leave a "completed" raw
record with no output. Writing the raw record last does not by itself make a retry idempotent: a crash after
the requirements write re-extracts and appends the chunk's requirements a second time, so a retry must replace
that chunk's earlier rows (or write them keyed by `chunk_id`). Include `chunk_id` in the cache identity so
unchanged text that moves is not matched to the wrong chunk, and make a model or profile change invalidate
the entry (today it does through the prompt hash; keep a test for it). Note: this invalidates old run directories' caches
once (a resume into a pre-change run re-extracts).

**Gate.** Tests that fail on the current code and pass after: transport error then resume; malformed output
then resume; truncated output then resume; crash between the requirements write and the raw write (no
duplicate rows after the retry); repeated identical chunks; renumbered chunks; changed model or profile; a
valid empty result stays cached. A normal run over a recorded fixture produces byte-identical Step C outputs. No approval
needed (no output or schema change on a normal run).

### WP-45.0.3 — Duplicated chunk text from split paragraphs (audit F01) — DEFERRED

**Decision (Tyler, 2026-10-04): do not build.** When HybridChunker splits one oversized paragraph into segments,
our adapter (`_chunk_raw_text`, which rebuilds each chunk's body so headings and tables serialize cleanly)
gives every segment the paragraph's full text. Reproduced with the real chunker, and 16 of 839 chunks (1.9%, 8
pairs in 5 documents) are such twins. Measured consequence: the twins produced only 16 surviving records in total,
with no exact or near duplicates reaching the index, because dedup collapses them. The cost is about 8 wasted LLM
calls out of 839. Chunk composition is Docling's job; code to change it is not justified by a duplicate that is
already absorbed, and a dropped requirement is worse than a duplicate.

**Revisit only if** the C4 neighbor-window pilot (WP-45.2) is approved and its documents contain twin chunks that
put the same text into a window twice. Two fixes would then be built offline and compared: follow the chunker's
segments (Option A), or merge the twins into one chunk so the paragraph is read once (Option B; the split comes
from the chunker's default 512-token tokenizer, not from Step C's 8192-token context). Recorded as a backlog item.

---

## 5. Track A — Fragments

### WP-45.1 — Measurement foundations (no production code)

All parts feed every later WP, so they come first and are recorded before anything changes.

**(a) Fragment census.** Define "dangling" with documented signals (starts lowercase, ends with a
list-continuation, short, begins with a list marker, no subject/verb) and apply them to all survivors of the 13
documents. Report counts per signal and per document, and per attachment method. Audit baselines: of 839
reconstruction candidates, 142 attach same-chunk, 59 cross-chunk, 2 by heading, 636 get no stem. Add the
177 survivors whose quote is not a contiguous substring of its chunk. Signals are sampling aids, not classifiers.

**(b) Attachment audit and root cause.** Hand-audit a sample stratified by attachment method for attachment
*correctness* (right governing stem / wrong sibling / fragment chain / none), with two independent labelers (Claude and Codex, each blind to the other's labels); Tyler adjudicates the
disagreements and spot-checks a small random sample of the agreements (about 10) to catch mistakes both AI
labelers share. My preliminary label on 16 same-chunk records (7 wrong) is a hypothesis to test, not a result. Classify each
failure: (1) the stem is in a different chunk; (2) docling's hierarchy is missing or wrong; (3) the
reconstruction rules do not cover the shape; (4) **new: an unpunctuated sibling bullet was accepted as the
stem.** Report attachment precision, not just coverage.

**(c) A fair retrieval test.** The Phase 44 probe was weak because its queries reused the fragments' own
words. The test must write each query from the *meaning* of the stem plus fragment, without copying wording,
and report the lexical overlap; use a documented, frozen configuration (HyDE held constant, `top_k`,
`min_score`, collection); measure rank and recall for four groups (correctly attached, wrongly attached, bare, and
a control of ordinary full-sentence requirements); and run against the live index read-only or a test
collection. Queries are written blind to retrieval results; who writes them is decided in review.

*Detailed plan for (c) and (d): `docs/PHASE45_WP451C_PLAN.md` (draft 2026-10-04, awaiting Tyler's review). It compares each record's own embedded text against variants (quote alone, adjudicated lead-in + quote), so query difficulty cancels. A heading arm is under discussion (plan section 6): WP-37.2 measured a regression for a blanket deterministic prefix on 12 topical queries, which does not settle a prefix applied only where informative; it is not in the first build.*

**(d) New: does a wrong stem hurt?** The reconstruction code assumes a false positive is "cheap". Using the
test in (c), compare retrieval on wrongly attached records with `embedding_text` versus the quote alone.

**(e) New: a small source-based sample.** Our recall numbers cannot see obligations that were never extracted.
For two or three documents, the two labelers (Claude and Codex, Tyler adjudicating) label obligations directly in the PDF (page and passage level),
independent of the extraction, then trace each to its first loss point (not extracted / rejected at Step D /
dropped by a gate / not indexed / ranked out). Size and time budget are decided in review; start small.

**Results of (c) and (d) (2026-10-04, #207, `eval/spike_results/wp_45_1c/README.md`).** Paired per record, target-only substitution, queries written blind, groups and queries frozen before any retrieval. (1) Supplying the adjudicated lead-in to the 36 stemless records raises recall@10 in all four runs (plain + three rewrite/HyDE repeats); the largest gain is from same-chunk lead-ins (exploratory), which is where today's stems are most often wrong. (2) Removing a wrong or chain stem never improved recall@10, so wrong stems are a trust/display problem, not a measurable search one for the record itself. (3) Correct stems matter. (4) The leaf heading helps only questions that name the party and does nothing topically; the frozen rule picks the right party for 30 of 31 heading-located records and the wrong one for 7 others, so any heading field needs provenance and a check. Limits: groups of 11 to 36, one target per query, the proposing model wrote the queries, in-memory engine (not bit-identical to the server), 13 documents. Consequence: WP-45.2 C1 (peer lead-in stem rule) now has a retrieval measure as well as an attachment-precision one; context supply is a search gain, not only a readability one (supports WP-45.3 and C4 on retrieval grounds, conditional on a pipeline step reaching adjudicated quality).

**Results of (e) (2026-10-05, #210, `eval/spike_results/wp_45_1e/README.md`).** Plan: `docs/PHASE45_WP451E_PLAN.md` (#209, the first
plan reviewed as a PR; Codex found two real holes, Gemini none). Sample: a seeded draw of 4 pages for each of DODI 8410.03,
afman17-2101 and NIST SP 800-125, cut into 254 pieces from PyMuPDF text (no pipeline output shown); Claude and Codex labeled blind
(232 of 254 agree), Tyler ruled the 20 disagreements about obligation status (18 were one question: AFMAN 2.3.x duty statements
with no shall or must, which he counted as obligations) and agreed with all 10 spot-checks. Result for the production run (July
8B, as indexed): of 74 obligations, 74 are in a chunk, 45 extracted (60.8%, page-bootstrap interval 44 to 77%), 44 survive Step D
and are indexed. First losses: not extracted 26 (35%, 19 to 49%), partly extracted 3, rejected at Step D 1, never chunked 0, not
indexed 0. By document: DODI 17 of 20, afman17 22 of 38, NIST 6 of 16. A fresh 8B run covers the same count (one piece each way);
the WP-45.6 14B covers 27%. Bounds from the labeling choice: 58% (either labeler) to 67% (both agree). By the pre-set routing
rule the work is at **extraction** (WP-45.2 C4 and prompt work, both stop-and-ask), not parsing, Step D or indexing. Exploratory,
small numbers: obligations containing a profile obligation verb reached the index 82% of the time (18 of 22), those without one
50% (26 of 52). Limits: 12 pages, 3 documents, four pages hold 61 of the 78 obligations, covered does not mean good requirement,
ranking in search not measured.

**Output:** baselines, census, audit, root-cause table, all under `eval/spike_results/wp_45_1/` with reproducible
scripts where inputs allow. Record the model digest, Docling and docling-core versions, prompt hashes and input
hashes in every manifest (the resolved docling-core version is not pinned). **Gate:** baselines exist and are
reproducible; the root-cause table names which candidate fix(es) are justified. No production change.

### WP-45.6 — Extraction-model comparison (measurement only; free, local)

**Question.** Does a larger local model read the documents better than the current `llama3.1:8b-instruct-q4_K_M`?
The cornerstone is extraction strength, and some of today's fragment and junk problems may be model skill rather
than structure. This is the cheapest way to find out, and it uses no outside service.

**Design.** After the WP-45.1 baseline is frozen, re-run Step C for two or three documents with `qwen2.5:14b`
(already on Tyler's Ollama) via the existing `--extraction-model` option, writing to a scratch directory with
`--no-index`. Enrichment stays on the 8B model so only one thing changes. Compare against the frozen 8B outputs on
the same chunks: requirement count and overlap, Step D rejections by code, fragment rate, attachment precision and
junk rate on the WP-45.1 and WP-45.4 samples, real requirements lost or gained against the source-based sample,
tokens per second and GPU memory. Decide in review what counts as a "meaningful difference" before looking
(proposed: a fragment or junk improvement larger than the sampling uncertainty, with no more real requirements lost
than the baseline).

**Gate and use.** Report only; nothing changes. If a meaningful difference appears, the next question is whether a
hosted model is worth building an API path for (backlog). **Evidence limit:** 14B versus 8B says nothing certain
about frontier hosted models, and it uses Tyler's GPU for a few minutes.

### WP-45.2 — Fragment attachment

Candidates are chosen from WP-45.1's root-cause table, **one at a time**, deterministic ones replayable offline
(reconstruction needs no LLM), in this order:

- **C1. Stem-acceptance rule (highest expected value).** A candidate stem must carry a governing signal — it ends
  with a colon, contains "to include" / "as follows" / "the following", or has list-structure evidence. An
  unpunctuated sibling bullet no longer qualifies. Unresolved fragments stay unattached and are flagged.
  Evaluate on the labeled sample: precision rises, coverage change is reported, and records already attached
  correctly do not change (byte-compare).
- **C2. Scope guard for cross-chunk lookups.** Require compatible section paths. Zero cross-section attachments
  were observed (0 of 59), so this is cheap insurance, not a measured fix.
- **C3. Merge a chain of fragments from one split sentence** into a single clause before attaching.
- **C4. Extraction-side context (cannot be replayed offline; needs Tyler's approval).** An ablation ladder, each
  rung a separate A/B: (i) show Step C the verified parent evidence (governing stem and heading path) as
  read-only context; then (ii) target chunk plus same-scope previous and next chunks (Tyler's three-chunk
  window). Details below.

**Gate (per candidate):** attachment precision rises on the audit sample; records already attached correctly do
not change; WP-45.1's retrieval test improves for affected groups and does not regress the control; a hand audit
of every changed record in the sample. Evaluate on a test collection, never the live index; reindexing the live
corpus is a separate, approved step. If a candidate does not clearly help, stop.

#### C4 detail: neighbor-context extraction (Tyler's proposal, 2026-10-04)

**Today.** Step C sees one chunk at a time: the section breadcrumb plus that chunk's own text, nothing from its
neighbors. The legacy overlapping chunker was removed in WP-34.1 (Docling's HybridChunker splits on structure
and does not overlap), and post-extraction reconstruction (WP-39.2) only reaches back to the previous chunk for
mid-list splits.

**Idea.** Extract from chunk N while showing the model its context, labeled "extract only from the FOCUS chunk",
then slide forward by one. Each chunk is the focus exactly once, so unlike true overlapping chunks the same text
is never extracted twice and no new fuzzy dedup is needed (today's dedup only catches exact repeats, which is
why extracting everything from every window is a different, riskier candidate). The model can see a governing
stem, a definition or a referent across a chunk boundary, which should produce stronger requirements and
embedded text at the source. A larger model alone cannot do this; it never sees what is outside the chunk.

**Design questions to settle in review, before any code:**
1. **Window shape.** Verified parent evidence only, whole neighbor chunks, or bounded snippets (tail of N-1,
   head of N+1). Step C's `num_ctx` is pinned at 8192 tokens, the template is about 850 tokens, and the largest
   table seen was about 2.7k tokens, so three whole chunks can overrun on table-heavy documents. A cap is needed.
2. **Quote rule.** (a) Quote only from the focus chunk: Step D unchanged, stem still attached by reconstruction,
   but the model decides with the stem in view. (b) Let the model stitch a neighbor's stem into the quote
   (Tyler likes stitched quotes): Step D's known-chunk checks must then cover focus plus neighbors, which
   changes what Step D accepts and needs its own replay proof. A new output field is a schema change
   (stop-and-ask).
3. **Boundaries.** Sequential chunk IDs or only neighbors in the same parent section; `skip_sections`; first and
   last chunks. Twin chunks (audit F01) would put the same text into a window twice; if the pilot documents contain them, handle that then (see WP-45.0.3).
4. **Enrichment.** Step D.5 sees only quotes today. Does it also need the context?

**Cost (estimate from the corpus, not a measurement).** The average Step C prompt is the template (about 850
tokens) plus about 230 tokens of chunk text, so two whole neighbors raise Step C input by roughly 40% (about
0.9M to 1.3M tokens for the corpus), output unchanged. Parent evidence only costs far less. Wall-time impact is
expected to be modest because generation dominates; not measured.

**Measurement.** Same model, same documents, A/B on a small pilot subset written to scratch: the current prompt
versus each ladder rung. Compare, using the WP-45.1 census and audit sample and the WP-45.4 gold set:
dangling-fragment rate; attachment precision; Step D rejection counts by code (including
`quote_words_not_in_chunk`, to see whether the model borrows quotes from neighbors); junk rate; requirement
count and duplicates; real requirements lost against the baseline; tokens and run time. **Gate:** better
fragment and junk metrics on held-out documents with no real requirements lost and no rise in rejected or
invented quotes. **Evidence limit:** nothing yet shows this helps; WP-45.1's root-cause table says how many
fragments are cross-chunk, which bounds the gain. Needs Tyler's approval before the pilot (changes Step C's
prompt; requires re-extraction).

### WP-45.3 — Grounded standalone statement (needs Tyler's approval first)

A correctly attached fragment is still not a checklist-ready requirement. Proposal: for dangling fragments
only, compose **one complete sentence from the stem and the fragment — both verbatim spans already in the chunk —
and nothing else**, written to the existing `description` field (empty or echoing today; no schema change),
validated by the existing WP-35 description-grounding gate pattern. `source_quote` is never changed.

One audit finding is folded in: the gate's premise is the bare quote today, so a faithful sentence that restores
the stem would look unsupported; the premise must include the verified stem. (The checklist builder copies only
`source_quote` and ignores `parent_stem`, `embedding_text` and `description`, so even accurate stems or a good
description leave checklists unchanged. Showing the governing clause there is deferred until stem accuracy
improves, and then still needs its own additive export change. See §7.)

This is a **new LLM-generation feature** (stop-and-ask). Before any code: Tyler approves; a small prototype is
evaluated on the audit sample for grounding-gate pass rate, hand-audited faithfulness (no added obligations, no
dropped conditions, no "may" strengthened to "shall") and checklist usability. Distinct from HyPE: this fixes
*usability*, HyPE fixes *findability*.

**Tyler's broader framing (2026-10-04, after the WP-45.1(b) audit), a candidate, not approved.** A second pass
after extraction: pass one stays pure extraction; pass two reads a larger context (several chunks, or back to the
page and paragraph in the document) and works out **who the requirement applies to** and **under what
circumstances**, producing a refined requirement a person can use directly. The untouched `source_quote` stays as the
evidence for fact-checking and further research (verbatim rule unchanged), so the refined text lives in a separate
field. The audit supports the target: about 54% of records need context to stand alone, and what is missing is
mostly a who (a role named by a heading or a list intro) or a condition (R029, R067, R102, R110, R111, R100).
Open design questions: the input window (stem and quote only, plus heading path, plus +/-1 chunk, plus the PDF page);
the output (a composed sentence, or two fields `applies_to` and `conditions`); grounding (every part must be a
verbatim span of the supplied context, nothing invented, "may" never strengthened to "shall"); and evaluation on the
audit sample, including the multi-level cases (R100) and the cut-off ones (R078).
**Cheap test before any LLM:** for records whose missing context is only a heading (about 550 of the 1,644 without a
stem), the heading is already on the record (`section_title_path`, `parent_header_text`); testing whether prefixing
it (deterministically, no generation) closes most of that pool is a measurement, not a new LLM feature, and belongs
with WP-45.1(c) and (d). Scoping or applicability statements (R088, "this issuance applies to ...") are not
requirements but are worth attaching to the requirements they scope; they need their own class in WP-45.4 (below),
handled by attach, not flag.

**Measured 2026-10-04 (offline, audit sample): the "who" for the heading-only majority is already on the record.** Of the 31 audited records Tyler's rulings place in the section heading, the stored `section_title_path` leaf carries all of the adjudicated lead-in in 30 (11 of 13 documents); the 31st needs a second passage from the chunk body. Use the **leaf heading only**, never the whole path (docling mis-nested "3.14." under "2. Policy. The AF will:" in two records). Weighted to the population that is roughly 600 of the ~1,000 records needing a lead-in (552 of 860 without a stem; wide interval). A deterministic "applies to" field from the leaf heading could therefore supply the who without an LLM; the other ~400 (same chunk, previous chunk, not shown) still need C1/C4 or a second pass. This is a stored/display field, not an embedding change (see WP-37.2).

**Tyler's clarification (2026-10-04, later), still a candidate and still needs his approval before any LLM stage.**
(1) Pass one stays a broad, slightly over-eager extraction, which is fine because junk is flagged, not deleted. (2) Pass
two is **conditional**: records that already carry their who, what and when are left alone (about 46% of the audit
sample were already complete). (3) Pass two looks beyond the chunk (neighbor chunks, the page or paragraph) for
**who it applies to, the circumstances, and trailing qualifiers** such as "in accordance with ...". (4) The verbatim
`source_quote` is never changed; the refined text is a separate field. (5) The **primary consumer is the checklist**
("the Director, NSA will ..."): without it a checklist row is often meaningless without going back to the source. The checklist builder
copies only `source_quote` today (see above), so showing the refined text needs its own additive export change.
(6) The refined text could also be indexed as a **second vector for the same requirement**. That is backlog items 2
(multi-vector, with the rule to collapse to one result per `requirement_id` before display or ranking) and 35 (grounded
standalone statement). It can only be measured once refined statements exist, and then with the WP-45.1(c) apparatus; the
oracle arm of that test (adjudicated lead-in + quote) is already the retrieval ceiling for it.
*Measured the same day, offline:* of 1,847 records, only 36 (about 2%) have a quote that stops before its own sentence
ends inside the chunk (a rough rule: lowercase or comma continuation; it can undercount), plus 189 quotes that are not
contiguous in their chunk (already tracked as audit F07 / WP-45.9). So trailing qualifiers are a small problem next to the
missing lead-in (about 54%).

**Tyler's pass-two role clarification (2026-10-05), after the WP-45.6 result.** Pass two is not only an "is this a
requirement" double check. It is also "how do I make this requirement easier to follow and understand for the user"
(readability and plain statement of who, what and when), always beside the untouched verbatim `source_quote`. WP-45.6
(unchanged production prompt) found the 14B much more literal and conservative than the 8B: 60% fewer records overall
(-33% on formal policy, -94% on guidance prose), but precise. That is the wrong trait for pass one (broad, over-eager)
and a plausible fit for pass two (judge and refine). That fit is a hypothesis, not a measurement; test it when
WP-45.3 is approved. A prompt written for the 14B (told to over-extract) is a separate, cheap follow-up that Tyler
parked for another time (prompt changes to a generation stage are stop-and-ask).

---

## 6. Track B — Junk and quote fidelity

### WP-45.4 — Gold set and detector evaluation (flag only)

**Gold set.** A stratified labeled sample (random plus strata for the WP-45.1 signals and the junk shapes seen so
far), labeled by **two independent labelers** (Claude and Codex, each blind to the other; Tyler adjudicates the disagreements and spot-checks a small sample of the agreements) with written definitions: REAL (an obligation or
recommendation a reader could act on), FRAGMENT (handled by Track A, not junk), DESCRIPTIVE/BORDERLINE, JUNK
(glossary preamble, acknowledgement text, pure fact, cross-reference), and SCOPE (applicability or scoping text; Tyler,
R088: not a requirement, but data worth attaching to the requirement it scopes, so it is kept and attached, never flagged as junk). Record inter-reviewer agreement. Hold out
a portion (for example 30%) and do not look at it while designing detectors. Size: enough to estimate an ~8%
junk rate within a few points (about 300 records; confirmed in review). Include the WP-45.1(e) source-based
sample so recall is measured against the PDF, not only against extracted records.

**Detectors, evaluated offline against the gold set, never applied to the corpus:** deterministic signals for
narrow shapes (cross-references, glossary preambles, acknowledgement text), expected to cover little; and for
descriptive-versus-obligation statements, an LLM judgment in **shadow mode** (it flags, nothing changes; a new
LLM feature, stop-and-ask).

**Gate:** a detector is recommended only if, on the held-out portion, it flags REAL records at or below an
explicit **false-flag floor** (proposed ≤1% of REAL) and reports precision and recall. Every number carries its
sample size.

### WP-45.9 — Quote-fidelity flag (flag only; audit F07)

**Why.** The Step D word-coverage check ignores word order and polarity (`Users shall share passwords.` against
source `Users shall not share passwords.` scores 1.0), and 177 of 1,847 survivors (9.6%) are not contiguous
substrings of their chunk. Of 7 I sampled, 3 were legitimate stitches, 3 formatting, and 1 dropped a content word
("specific work **role** that" became "specific work that") and passed at an alignment score of 98. A heuristic
negation scan (excess negation words inside the aligned span of non-contiguous quotes) found none, but it is
one-sided: it cannot see a dropped negation in a contiguous quote (`Share passwords.` from `Do not share
passwords.`) or one outside the aligned span, so an omitted governing negation is unmeasured. The blind spot is
real and has fired; no polarity flip is known.

**Change (detector only, never a rejection).** For non-contiguous quotes, align the quote to its source span and
flag dropped content tokens and dropped or added negations; send flagged records to the WP-45.5 review state.

**Gate.** Source-clause context is required for the negation part, and the two synthetic challenge cases in
`eval/spike_results/wp_45_audit/README.md` must be caught. Evaluated on the 177 with hand labels (stitch /
formatting / dropped word / other) from two reviewers:
catches dropped-content cases at a stated recall while flagging legitimate stitches and formatting below an
explicit floor. No change to what Step D accepts. This is backlog item 34, now with a measured baseline.

### WP-45.5 — Review state for flagged records (design first; needs Tyler's approval)

How flagged records are represented is a design question, not a default: a sidecar file (no JSONL schema
change) versus a field (schema change), and how a Qdrant payload filter would exclude them from default search (a
Qdrant change — stop-and-ask). Requirements: recoverable, visible in `reqbot status`, excluded from default
search only after validation, one-step reversible. Also surface validation state per run (for example whether
MiniCheck actually ran; audit F13). A design document until Tyler approves a direction; no code before then.

---

## 7. Deferred, with reasons (Appendix A has the verdict for every audit finding)

| Item | Why not in this phase |
|---|---|
| Scope-aware stable IDs and dedup redesign (F03) | No harmful merge observed; changes every ID; forces a reindex. Add a regression test and fix the `_dedup_score` comment only. |
| Splitting chunks at scope transitions (F05) | Measured: 0 of 1,166 raw chunks span two section paths. |
| Replace-on-reingest index semantics (F09) | No stale points today; Operations already says use `reindex`. |
| Token-aware embedding validation (F10) | Longest input is about 204 tokens against 2,048. |
| Structured obligation slots | Large schema change plus LLM generation; overlaps WP-45.3's smaller test. |
| LLM-generated context prefixes | "No invented context". The deterministic section-path version was tried and reverted in WP-37.2 (backlog Retrieval item 6). |
| Docling heading inference | Not available in 2.94.0; an upgrade is its own evaluated change. |
| Hosted-model extraction (Anthropic or similar) | Needs a provider layer across the pipeline roles (embeddings stay on Ollama; Anthropic has none). Backlog feature; revisit if WP-45.6 shows a meaningful difference, and in any case as a general feature. |
| Checklist shows the governing clause and an "unresolved context" flag (audit F06) | Tyler, 2026-10-04: showing today's stems would surface the wrong ones. It does not solve itself: the checklist builder ignores `parent_stem`, `embedding_text` and `description`, so after attachment validation it still needs an additive export change (supplied context kept visibly separate from the quote). Revisit after WP-45.2 C1. |
| Duplicated chunk text from split paragraphs (audit F01) | See WP-45.0.3: dedup absorbs it; revisit only if the C4 pilot needs it. |
| Contiguity or reject rule for quotes | Replaced by the flag-only WP-45.9. |
| Backlog: tiny-chunk pre-filter (item 37), regenerating `*_final_output.json` exports (still contain the 3 removed records), whether to re-extract after any extraction-side change | Unchanged. |

## 8. Proposed Phase 46 — retrieval (not part of Phase 45)

Retrieval sits downstream of extraction, so it is measured against the corrected corpus afterward, on a test
collection, never the live index.

- **R1. Original-query leg (the one new idea).** Add a retrieval leg on the user's unmodified question beside the
  rewritten one; today both dense and sparse legs use the rewrite. Hypothesis: recovers the 8 WP-40 misses
  classified as rewrite/HyDE-caused without regressing the rest. Metrics: recall at 5/10/20, MRR, p95 latency, by
  query shape, on the existing harness with a frozen configuration. Gate: a gain on the affected queries beyond
  noise and no regression elsewhere. Check Phases 24, 37 and 40 for prior art before starting.

Everything else the audit suggested for retrieval is already recorded or already tried, and should not be rebuilt:
a deterministic section-path prefix on the embedded text was tried and reverted in WP-37.2 (backlog Retrieval
item 6); a score-based "not answerable" floor was measured in WP-41 and cannot work with RRF scores (a calibrated
signal is needed; backlog item 4); a raw-context search route is backlog item 5 (the 18 WP-40 extraction and
missing-context misses are its evidence); the reranker was a No-Go in Phase 43 (item 1); HyPE and multi-vector
retrieval are items 3 and 2.

## 9. Sequencing

1. **Track 0 first, one at a time:** WP-45.0.1, then WP-45.0.2. Neither changes outputs on a normal run.
2. **WP-45.1** next, entirely measurement. Freeze the baseline.
3. **WP-45.6**, the free local model comparison, right after the baseline is frozen (it needs that yardstick).
4. **WP-45.2** candidates C1 to C4 in order, each gated; C4 only with approval.
5. **WP-45.4**, then **WP-45.9**, then WP-45.3 and WP-45.5 once their approvals and the earlier WPs they build on
   are in place. WP-45.4 can be planned in parallel with WP-45.2 but implemented one at a time.
6. Each WP: sync `main`, branch first, baseline recorded before any change, Codex review before merge, Status
   table updated when merged.

## 10. Success Gate / Decision Criteria

Phase-level: the Track 0 guards are in with failure-injection tests; WP-45.1's baselines exist and are
reproducible; each later WP either clears its own gate on held-out evidence or is stopped. Nothing is deleted. No
real requirement is lost: any change that removes or hides a real requirement on the gold set fails its gate.

## 11. Open Questions for Review

1. WP-45.3: does Tyler approve a grounded LLM composition for fragments as a candidate?
2. Decided (Tyler, 2026-10-04): Claude and Codex label independently, Tyler adjudicates disagreements and spot-checks a few agreements. Open: the sample sizes.
3. WP-45.5: sidecar file versus a field, and is a Qdrant payload filter acceptable?
4. The false-flag floor (proposed ≤1% of REAL) and the gold-set size.
5. Scope: stay with the 13 documents, or include newer ones?
6. C4: verified parent evidence only, whole neighbor chunks or bounded snippets; may quotes be stitched across
   chunks; which two or three documents form the pilot?
7. Decided (Tyler, 2026-10-04): WP-45.0.3 is deferred, and the checklist governing-clause column is deferred until
   stem accuracy improves.
8. Decided (Tyler, 2026-10-04): the free local model comparison (WP-45.6) runs right after the baselines. Open:
   what counts as a "meaningful difference" (proposed in WP-45.6); a hosted-model path waits on that result.

---

## Appendix A. Audit findings and verdicts

Source: an external, read-only pipeline audit (ChatGPT, 2026-10-04, against commit `4b17eac`). It ran no ReqBot
dependencies or real data. Each finding was checked here against the real code and the 13 documents pinned in
`eval/spike_results/wp_44/manifest.json` (839 chunks, 1,847 normalized records, 1,845 indexed points; the 2 differ because the afi17-203 records quarantined
in WP-42 stay in the normalized tier, so F04/F07 and the reconciliation are different populations). Scripts and
outputs are in `eval/spike_results/wp_45_audit/`. The audit itself is input only and is not kept.

| # | Finding | Holds? | In our corpus | Where it goes |
|---|---|---|---|---|
| F01 | Chunk adapter re-expands split items | Reproduced (real chunker) | 16 of 839 chunks (1.9%) duplicated, 8 pairs; 0 duplicates reach the index | Deferred (WP-45.0.3) |
| F02 | Failed Step C requests become cache hits | Reproduced (real `run()`) | 0 failures in 839 chunks | WP-45.0.2 |
| F03 | Dedup and stable ID merge scoped duplicates | Reproduced (probe) | No harmful merge; 17 of 23 cross-chunk merges are F01 twins, 3 a repeated page heading | Test and comment fix only |
| F04 | Stem lookup attaches siblings | Reproduced; mechanism confirmed | 0 of 59 cross-chunk attachments cross a section; 7 of 16 sampled same-chunk attachments judged wrong (one reviewer) | WP-45.1, WP-45.2 |
| F05 | One ancestry per mixed-scope chunk | Reproduced (probe) | 0 of 1,166 raw chunks span two section paths | None |
| F06 | Enrichment, gate and checklist ignore the stem | Code-read | By construction | WP-45.3 (gate premise); checklist column deferred |
| F07 | Quote gate ignores polarity and dropped words | Reproduced (probe) | 177 of 1,847 quotes non-contiguous; 1 of 7 sampled dropped a content word; 0 excess negations in aligned spans (one-sided heuristic; omitted governing negation unmeasured) | WP-45.9 |
| F08 | Reindex ignores embedding failures | Code-read | Live index reconciles exactly (0 missing, 0 stale) | WP-45.0.1 |
| F09 | Incremental index keeps stale points | Code-read | 0 stale points, 0 multi-edition PDFs | Deferred |
| F10 | Embedding inputs truncated | Code-read | Longest input about 204 tokens against 2,048 | None |
| F11 | Rewrite replaces the user's wording | Code-read | WP-40: 8 misses classified rewrite/HyDE-caused | Phase 46 R1 |
| F12 | Context lookup cannot rescue unextracted text | Code-read | WP-40: 9 extraction failures, 9 missing-context misses | Backlog Retrieval item 5 |
| F13 | Validation states not distinguishable | Code-read | By construction | WP-45.5 |

Evidence limits: counts are from the 13 pinned documents only; the F04 rate rests on 16 records and one reviewer;
no hosted-model or retrieval experiment was run, so Phase 46 items are proposals. Over-weighted by the audit: F01
and F03 as top priority, F10 as a problem. Under-stated: F04, the only finding with measured damage. Docling
2.94.0 has no heading-hierarchy option (verified), so "just enable heading inference" is not available without an
upgrade. The reranker verdict (No-Go) agrees with our WP-43 result, noting the MiniLM reranker raised MRR (0.627
to 0.678) at 3.9 times the latency.
