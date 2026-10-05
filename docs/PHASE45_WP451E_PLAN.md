# WP-45.1(e) plan: a source-based recall sample (measurement only)

Status: executed 2026-10-05; results and the outcome notes below are in `eval/spike_results/wp_45_1e/README.md`. Part of
`docs/PHASE45_REQUIREMENTS.md` (WP-45.1). No production code, index or configuration changes. No new LLM stage.

## Outcome notes (added after the run)

Departures from the plan as written, all fixed before any result was seen unless noted:

- Tokens are NFKC, lowercase, runs of letters and digits (simpler than Step D's normalizer); coverage counts matching runs of at
  least three tokens so scattered common words do not count.
- A piece straddling two consecutive chunks counts as chunked (the plan said "in a chunk").
- Step D survivors are matched to Step C records by chunk and quote text, not by id (the ids differ). A first run that joined by
  id reported zero indexed, was caught as implausible, and was fixed with a sanity check and a regression test.
- The bootstrap resamples all 12 sampled pages, including three with no obligations (a Codex review point on the results PR).
- A disagreement needs a ruling only when it changes whether a piece is an obligation (decided after seeing the labels; it
  changed workload only).
- The result also needs the caveat that the obligation set rests on Tyler's ruling that duty statements without shall or must
  are obligations (18 of the 20 rulings).

## 1. Why this exists

Every number we have so far is measured against what was extracted. The WP-45.1(b) audit asked whether the attached stem
is right. WP-45.1(c) asked whether supplying context helps search. WP-45.6 compared two models on records they found, and
could only say how many each found, not how many real obligations each **missed**. If an obligation was never extracted,
none of those measures can see it. This sample reads the source PDF first, lists the obligations that are really there,
and then asks, for each one, where it was lost. It also closes WP-45.6's open limit: recall against the source for the
8B (production), a fresh 8B run and the 14B.

The question it answers: **of the obligations a careful reader finds in the PDF, how many reach the index today, and at
which step do the rest drop out?** The answer tells us which later WP is worth doing first: parsing (WP-45.9), extraction
(WP-45.2 C4 and prompt work), Step D rules, or nothing at all because recall is already fine.

## 2. Design

**Documents.** The three used in WP-45.6 (DODI 8410.03, 25 pages; afman17-2101, 26 pages; NIST SP 800-125, 35 pages).
Reusing them means the 14B and fresh-8B runs already exist for the same chunks, so the same labels also give their
recall. They span formal policy and guidance prose, the two shapes that behaved most differently in WP-45.6.

**Pages.** Four pages per document (12 pages, about 300 sentence-sized pieces per labeler; pages average 21 to 29
sentence-ish pieces). Pages are drawn by a seeded shuffle from pages with at least 60 words, taking the first n, so the
sample can be extended later without a redraw. The draw and its seed are frozen and hashed before labeling.

**Independent text.** Labelers see page text extracted by **PyMuPDF**, not by Docling, and see **no** extraction output:
no chunks, no records, no stems. If Docling dropped or scrambled text on a page, the labelers still see it, and that
loss shows up as a loss point.

**Segmentation.** A deterministic splitter (written, tested and hashed before labeling) cuts each page into sentences
and list items, keeping each piece's page number and order. Labelers label **pieces**, so there is one answer per piece
and agreement is directly countable. They may add a note.

**Labels, one per piece** (the definitions are the WP-45.4 gold-set ones, so one standard serves both):

| Value | Use when |
|---|---|
| `obligation` | An obligation or recommendation a reader could act on, including "should" guidance, whether it names its party or inherits it from a lead-in. A list item that carries the action is an `obligation`. |
| `lead_in` | The sentence that only introduces a list of obligations ("The Program Manager will:"). Not counted either way; its items are counted. |
| `scope` | Applicability or scoping text ("this issuance applies to ..."). Kept, never counted as an obligation or as junk (Tyler, R088). |
| `not_obligation` | Everything else: definitions, background, headings, citations, boilerplate, tables of contents. |

**Who labels.** Claude and Codex independently and blind, from a folder holding only the pages, the rubric and a checker
(the WP-45.1(b) and WP-45.6 method). Tyler adjudicates the disagreements and spot-checks about 10 agreements. Unlike
WP-45.6, adjudication matters here: a piece one labeler calls an obligation and the other does not changes the
denominator. Pre-set reporting: the adjudicated labels are primary; "obligation only if both agree" and "obligation if
either says so" are shown as the bounds.

## 3. The trace (deterministic, no LLM)

Every piece finally labeled `obligation` is followed through the pipeline and given the **first** step at which it is
lost. The files are the pinned WP-44 corpus (chunks, extracted, normalized) and a read-only look at the live Qdrant
collection.

1. **Never chunked.** The piece's text is not found in any chunk of its document (a parse or chunk loss).
2. **Not extracted.** It is in a chunk, but no Step C record covers it. The chunk's Step C status
   (complete, truncated, failed) is reported alongside, so a failed chunk is not confused with a model that skipped it.
3. **Rejected at Step D.** A Step C record covers it and Step D rejected that record (the rejection code is kept).
4. **Not indexed.** A record survived Step D but is not in the live collection (gate or indexing).
5. **Indexed.** Present in the live collection. (Ranking out of search results is a separate question and is **not**
   measured here; the WP-45.1(c) engine can do it later if this result says it matters.)

**Matching rules, fixed now.** Text is normalized the way Step D does, plus ligature repair, lowercasing and removal of
list markers, then split into tokens. Two different questions use two different rules:

- *Is the piece in a chunk?* The piece's tokens are found in the chunk's tokens (the chunk is the longer text), with
  token-level `difflib` similarity to the best window of at least 0.90. A piece that is not in any chunk is a step 1 loss.
- *Is the piece covered by a record?* Coverage is the **share of the piece's tokens** that the records in that chunk
  reproduce, matched in order. When a piece is split over two records, the share is the union of what they cover. A short
  record that happens to sit inside a long piece (a record of only "access control" against an obligation with several
  actions) therefore covers only a small share of it and does not count.
  - Share at least 0.90: **covered**.
  - Share from 0.50 up to 0.90: **partly covered**. This is the cut-off record, the WP-45.2 fragment story. It is **not**
    counted as found in the primary recall; it is reported on its own line, and recall is also shown with partly covered
    pieces counted as found, so the effect of the choice is visible.
  - Share below 0.50: not covered.

All thresholds (0.90, 0.50) are fixed before looking at any result and are not tuned.

**Secondary traces.** The same pieces are traced through the fresh 8B and the 14B runs left in `~/wp45_6_scratch`,
steps 1 to 3 only (those runs were never indexed). This gives each model's recall against the source.

## 4. What is reported

- Recall at each step for the production run: of N obligations, how many are chunked, extracted, survive Step D, are
  indexed. Uncertainty comes from a **page-level bootstrap** (resample the 12 sampled pages, keeping each page's pieces
  together, because pieces on one page and the pieces of one multi-sentence obligation are not independent), not from a
  binomial interval over pieces. Per-document figures are shown descriptively.
- The loss table: how many obligations are lost first at each step, with the Step D rejection codes and the Step C chunk
  status.
- Recall for the fresh 8B and the 14B, with a paired comparison against the production run on the same pieces, again
  with a page-level bootstrap on the paired difference.
- Obligation density per page and per document, since that decides how far the sample generalizes.

There is **no pass or fail gate**. This is a measurement, and the routing is stated in advance so the result cannot be
bent after the fact. The table is used only when one loss category is clearly the largest: its page-bootstrap lower
bound is above the next category's point estimate. Otherwise the result is reported as "no single dominant loss point"
and no routing is claimed.

| If the largest loss is ... | the next work is ... |
|---|---|
| never chunked | WP-45.9 (parse and chunk fidelity) |
| not extracted | WP-45.2 C4 / prompt work (stop-and-ask: new LLM behavior) |
| rejected at Step D | review the rejection codes (Step D precision rule, WP-45.2) |
| not indexed | an indexing or gate defect to fix first |
| nothing above a few percent | extraction recall is not the constraint; spend effort on fragments and junk |

## 5. Limits stated up front

- Twelve pages across three documents. About 100 obligations are expected. Treated as independent they would give a
  recall estimate of roughly plus or minus 8 to 10 points, but pieces on a page are correlated, so the page-bootstrap
  intervals will be wider, possibly much wider. We report whatever the bootstrap gives. The documents are the real unit
  of generalization and three is few.
- Two labelers who share one rubric can share a blind spot; Tyler's spot-check is the only guard against that.
- PyMuPDF reading order can scramble tables and columns; labelers are told to mark such pieces in a note, and the
  report counts pieces whose text could not be found because of reading-order differences separately if they appear.
- Obligations that span several sentences are labeled piece by piece, so a long obligation is several `obligation`
  pieces; recall is reported per piece.
- Whether a "should" statement is a requirement depends on the definition above; the per-document table shows how much
  of the total is "should" guidance.
- Three documents of 13 in the corpus; nothing here speaks for the others.

## 6. Build order and tests

1. Freeze the page draw and the segmenter (code, tests, hash) before any labeling.
2. Build the pack, rubric and checker; Codex labels in its isolated folder while Claude labels a blind copy.
3. Adjudication sheet for Tyler (disagreements only on obligation versus not, plus spot-checks).
4. Trace script, then the report. Unit tests with synthetic fixtures for the segmenter (determinism, list items,
   page order), the matching rule, and the first-loss-step assignment (one fixture per step).
5. Results, README, one PR.

Estimated labeling per labeler: about 300 pieces, less per piece than the WP-45.1(b) cards because there is no chunk
context to read. Tyler's time: the disagreements (expected 10 to 20% of the obligations, so perhaps 20 to 40 pieces)
and 10 spot-checks, roughly 15 to 25 minutes.

## 7. Questions for review

1. Four pages per document, or fewer pages with a larger stride? (More pages dilute page-level clustering; fewer cut
   labeling time.)
2. Is "should" guidance counted the same as "shall" (the plan says yes, per the WP-45.4 definition)?
3. The coverage share already unions records, so a piece split over several records counts. Should the report also
   show how many covered pieces needed more than one record (a split count), given WP-45.6's matching findings?
4. Is excluding the retrieval step from this WP right, or should a cheap top-20 check be included?
