# ReqBot Phase 44 — Source-Quote Integrity and Junk Requirements

**Status:** WP-44.1 implemented and measured on `feature/wp-44-1-quote-word-coverage` (see §10);
awaiting review and merge. WP-44.2 not started.
**Date:** 2026-10-03
**Preceded by:** Phase 43 (Reranker Spike) — `docs/PHASE43_REQUIREMENTS.md`, complete (measured
No-Go, no default changed). This phase is unrelated to retrieval; it hardens Step D's quote
grounding, which Phase 43's docling-upgrade check (PR #159) happened to surface.
**Followed by:** Not decided. §6 (Backlog) names what is deliberately left out.

---

## Status

| WP | Status |
|---|---|
| WP-44.1 — Close the invented-quote leak (Step D word-coverage check) | Implemented, gate met — in review |
| WP-44.2 — Junk inputs (measure first; code only if the measurement supports it) | Planned, blocked on WP-44.1 |

---

## 1. Phase Framing

**Principle for this phase (Tyler):** ReqBot works today. One change at a time, each proven by a
replay or test before and after, and each stopped if it doesn't help.

ReqBot's rule is that `source_quote` is copied verbatim from the source — "do not invent
obligations." Step D enforces this with a fuzzy grounding gate
(`fuzz.partial_ratio(quote, chunk) >= QUOTE_GROUNDING_THRESHOLD`, 60 —
`pipeline/parse_and_normalize.py`). While checking the docling 2.84.0 → 2.94.0 upgrade (PR #159) on
one table chunk, a model-invented quote passed that gate. This phase measured how widespread that
is before proposing anything.

**Evidence** — the latest ingest of each of 13 documents under `~/documents/processed/`, 1,991 raw
Step C quotes compared against their own chunk text:

| Outcome | Count | Assessment |
|---|---|---|
| Exact substring of the chunk | 1,717 (86%) | fine |
| Formatting-only difference (whitespace, punctuation, ligatures) | 83 | fine, all survive Step D |
| Contains an ellipsis (`...`) | 5 | legitimate elision, survive |
| **Invented** (most words not in the chunk) | **69** | **gate caught 64; 5 leaked through** |
| "Stitched" (list lead-in + item, e.g. "AFGSC will: Chair the AF NLCC/NC3 Council.") | 117 | 88 survive Step D, 29 caught by other gates |

- **The leak is small but real.** The 5 leaked quotes scored 62–76 on the fuzzy match, just above
  the threshold of 60. Their measured token coverage (below) is far lower than every other
  classified quote's. That motivates an additional coverage check; it does not establish *why* the
  fuzzy score accepted them (`partial_ratio` compares character sequences, not word membership).
  One leak is already indexed: "The organization is responsible for conducting a thorough
  Post-Incident Analysis." (afi17-203).
- **The leaks are unsupported independent of the coverage rule.** Each of the 5 was read against
  its chunk and labeled by content (`eval/spike_results/wp_44/labels_and_review.md`): a marking
  table, a bare glossary term, a cover page and a descriptive matrix — none states the obligation
  the quote asserts. Each was also checked
  against the concatenated text of every chunk of its own document (alphanumeric-normalized): none
  appears anywhere. The same holds for 63 of the 64 gate-caught quotes; the exception is a
  one-word quote, "shall". (Caveat: "anywhere in the document" means the chunk text of that run,
  not a fresh read of the PDF.)
- **Stitched quotes are intended and stay (Tyler):** they carry the hierarchical linkage
  (lead-in → item) ReqBot wants. The 88 survivors were checked in two ways. *Automated:* for the 71
  with a colon-delimited lead-in, 43 match the chunk's governing header or section title and 26 more
  have the lead-in verbatim elsewhere in the chunk text (multi-section chunks); 2 lead-ins are not
  verbatim in the chunk (inspected: one is a harmless dropped acronym parenthetical; the other,
  DODI 8410.03 chunk 13, is not a stitched quote at all but a near-verbatim quote with the words
  "limited to" dropped — attribution correct, sense altered, invisible to a coverage check and
  recorded in the evidence notes as a bag-of-words limit); 17 have no lead-in to check. *Read by hand:* 12 random samples with chunk
  context, the ~28 header-mismatch cases (quote vs. header, not full chunk), and one case read in
  full — afi13-550 chunk 33, whose parallel lists repeat the same item under two offices
  (3.3.1.1 AF/A10, 3.3.3.2 AFGSC), each attributed correctly. **No lead-in attached to an unrelated
  item was found in what was reviewed.** That is an absence of evidence in a partial review, not a
  proof; it is why no governance validator is built (§3).
- **Where the invention comes from:**
  - 0 inventions in the 467 chunks that contain obligation language (1,374 quotes). All 69 are in
    chunks with none.
  - 48 of 69 come from chunks whose body is under 200 characters (34 under 100): page headers
    (`CJCSI 6510.02G 20 March 2025`), `(INTENTIONALLY BLANK)`, distribution lines.
  - About 20% (14 of 69) near-copy sentences from this repo's own few-shot examples in
    `PASS1_PROMPT_TEMPLATE` (e.g. "…shall implement multi-factor authentication for all
    privileged user accounts").
  - The prompt instructs verbatim extraction, permits empty output, and the schema has no minimum
    item count. Generic-boilerplate generation by a small model and few-shot copying are
    *hypotheses consistent with these examples*; no controlled prompt experiment has isolated the
    cause.
- **A word-coverage check separates the groups on this corpus.** Coverage is defined in §4. The 5
  leaks score 0.19–0.65; the gate-caught invented quotes max out at 0.71; the lowest of the other
  1,922 quotes is 0.857 (gap 0.71–0.857). A threshold of 0.8 would reject 5/5 leaks and 0/1,922
  other quotes. **0.8 was selected on this same corpus.** Replaying the same data checks the
  implementation and regressions, not generalization to unseen documents; no independent labeled
  sample exists, and that limits the claim rather than blocking the WP.

---

## 2. Goals

1. Block model-invented text from reaching the index, without rejecting any legitimate quote
   (formatting variants, ellipses, tables, stitched lead-in + item).
2. Prove it by offline replay of the existing Step D against saved Step C output — before and
   after, with the expected difference stated in advance.
3. Reduce junk at its source (WP-44.2), but only on the strength of measurement.

## 3. Non-Goals

- **No change to what counts as a legitimate stitched quote.** They stay.
- **No lead-in-governance validator.** Nothing in the corpus shows a lead-in attached to an
  unrelated item; building one would add code for a problem that hasn't appeared. Revisit only if
  a real case is found.
- **No `source_quote` / `parent_stem` split.** The fields already exist on the record
  (`parent_stem`, `embedding_text`, `parent_context`); this phase does not need them. Noted for
  later, not done.
- **No punctuation-stripping in matching.** Punctuation carries numbers, identifiers and clause
  boundaries.
- **No schema, Qdrant, dependency, or retrieval changes.** No new LLM-generation feature.
- **No rewrite of Step C.**

---

## 4. WP-44.1 — Close the invented-quote leak

**Change (one):** add a word-coverage check in Step D, alongside the existing fuzzy gate (which is
unchanged, as are stored quote text and the fuzzy matcher's normalization). One small function and
one constant, `QUOTE_WORD_COVERAGE_THRESHOLD = 0.8`, in `pipeline/parse_and_normalize.py`.

**Coverage, exactly as measured (the code must use this same procedure):**
- Text: `normalize_text()` (lowercase, whitespace-collapsed) applied to the quote and to the
  chunk's `text` field — the same field Step D already grounds against
  (`build_chunk_text_map`; it is what Step C saw, including the breadcrumb line).
- Tokens: `re.findall(r"[a-z0-9]+", text)` on each. Punctuation is ignored *for this calculation
  only*; no text is rewritten.
- Coverage = (number of the quote's token **occurrences** whose token is a member of the chunk's
  token **set**) ÷ (number of quote token occurrences). Whole-token membership, not substring.
- A quote with zero tokens has coverage 0. A coverage of exactly 0.8 passes (rejected only if
  strictly below).
- No ligature handling is added: ligature glyphs are not `[a-z0-9]`. (`pipeline/repair_ligatures.py`
  is a standalone manual tool that `run_pipeline.py` never calls; nothing here establishes that
  these inputs were ligature-repaired.) The observed minimum of 0.857 shows some legitimate quotes
  are *not* fully covered, so this is a threshold, not an exact-match test.

**Integration:** after the existing fuzzy check, inside the existing known-chunk branch, so records
the fuzzy gate already rejects keep their old failure codes and only previously-accepted records
can receive the new code, `quote_words_not_in_chunk`. The failure entry records the measured
coverage and the threshold (alongside the existing `grounding_score` pattern). Behavior for
unknown/missing chunks is unchanged (skipped, as today); the replay reports how many records that
leaves unchecked, and they are not described as having passed grounding.

**Why it is safe to try:** the check rejects only quotes with coverage below 0.8, i.e. with more
than 20% of their tokens absent from the chunk. Observed minimum coverage among all other quotes
is 0.857.

**Known limit (documented, not hidden):** coverage is a bag-of-words check. It cannot detect a
quote built from real words rearranged to change meaning (negation flipped, an exception dropped,
numbers swapped). That has not been observed in the corpus; tests record exactly what passes so
the limit is explicit.

**Replay harness (new, `eval/step_d_replay.py`):** calls the real production Step D entry point
(`parse_and_normalize.run`) with the same inputs both arms — the saved
`*_extracted_requirements.jsonl` and `*_chunks.jsonl`, the **original PDF** (document identity
feeds requirement IDs, so omitting it would make replay IDs differ from the corpus's), and the
same profile — writing to isolated directories outside `~/documents/processed/`. No Ollama, no
Qdrant. Both arms run from the same frozen inputs; the code revision and configuration are
recorded.

**Tests (extend `tests/unit/test_normalize.py`):**
- the 5 known leaks (fixtures from the real corpus) are rejected with the new code;
- pass: exact, formatting-only (whitespace/ligature), ellipsis, stitched lead-in + item, and the
  table-quote cases that originally forced the fuzzy gate (WP-32.1);
- adversarial cases with **expected results fixed before implementation**: quotes made of words
  that all occur elsewhere in the chunk but state something the chunk does not (negation flipped,
  number swapped, exception dropped, unrelated passages joined) are expected to *pass* the check
  (the documented bag-of-words limit — recorded as the bounded contract, not as legitimate
  quotations), alongside quotes of novel words, expected to be rejected;
- edge cases: zero-token quote, coverage exactly 0.8, unknown chunk, empty chunk text;
- the existing grounding/heading-echo/fragment tests stay green unchanged.

**Cleanup of existing bad records — a separate step after the WP merges, with Tyler's approval,
not authorized by this plan:** the new check prevents future leaks; it does not remove the 5
already stored. Re-running Step D would produce a fresh normalized file that the artifact resolver
can prefer over older enriched/gated files, so it could change descriptions and other downstream
fields, not just remove records. The lower-risk option to evaluate first is a **targeted
removal**: delete exactly the 5 known records from the selected final artifacts and from Qdrant
(by point ID), leaving every other record's enrichment and description-gate results untouched. Either
way: record the resolver's selected artifact path before and after, preserve prior manual
quarantines, preview any requirement/checklist/gold references to the 5, keep rollback copies, and
verify the intended IDs are absent from Qdrant afterwards.

---

## 5. WP-44.2 — Junk inputs (measure first)

Measurement and labeling may start any time; only a *production change* waits for WP-44.1 to merge
(its new failure code makes detector hits countable).

**Step 1 — measurement, no code:** classify the tiny / no-obligation chunks and count how many
legitimately yield requirements. A blunt "skip chunks with no obligation verb" rule is expected to
be wrong: 587 real quotes in the corpus came from chunks with no obligation verb in the chunk body
(they inherit obligation from list stems or headings), and some real requirements are tiny
(e.g. "Have load-shedding plan" — 24 characters). "No obligation language" is a **sampling signal
for review, not a rejection rule.**

**Step 2 — candidates, one at a time, only if Step 1 supports them:**
- (a) replace the realistic few-shot example sentences in `PASS1_PROMPT_TEMPLATE` with neutral ones;
- (b) skip chunks that provably match boilerplate patterns (page headers, "(INTENTIONALLY BLANK)").

**Success metric (fixed before experimenting).** The coverage failure code counts only novel-word
inventions; on its own it is not a valid success metric, because a new prompt could produce fewer
novel words but more unsupported recombinations and so lower detector hits without improving
extraction. Instead, compare baseline and candidate Step C output on a fixed chunk sample (suspect
chunks plus legitimate prose, lists, tables and short requirements) against **manually verified
requirements**, reporting separately: unsupported extractions, recovery of the same legitimate
requirements, and coverage/fuzzy rejection counts. Equal legitimate-record *counts* are not
enough — compare identities and content, since different obligations may disappear and appear.
Because Step C is stochastic, use repeated paired runs (e.g. 3 per arm) under the same model,
options and cache policy, record prompt hashes, and confirm the changed prompt generates fresh
output. One candidate at a time; if it does not clearly help, stop and revert.

---

## 6. Backlog (named so it doesn't evaporate)

- `parent_stem` / `source_quote` split for stitched quotes (fields exist; not needed yet).
- A lead-in-governance check — only if a real mis-attribution is ever found.
- Whether the fuzzy gate's threshold of 60 should itself be revisited, once the coverage check has
  been in place and its overlap with the fuzzy gate is measurable.

---

## 7. Process — plan reviewed before implementation

1. Plan written locally (this document, untracked) and reviewed by Codex. Not committed or pushed
   until the first WP is ready to implement.
2. When WP-44.1 starts: sync `main`, create the branch first, then this document ships with that
   WP's PR (or earlier on its own if Tyler prefers).
3. Baseline replay recorded **before** any code change.
4. One WP, one branch, one PR; Codex review before merge; Status table updated when merged.

## 8. Success Gate / Decision Criteria

WP-44.1 passes only if **all** hold, measured by replay over the 13 documents:
- All 5 known leaks are rejected with `quote_words_not_in_chunk`.
- No non-invented raw quote fails the new check in the measured corpus (0 of the 1,922; note that
  29 of them are already rejected by other rules at baseline, so state both views).
- The final normalized output loses **exactly the five verified baseline survivors**, gains no
  records, and leaves all remaining stable fields unchanged (excluding only known-volatile
  metadata such as `run_timestamp`). If deduplication causes another change, investigate and
  revise the expected result explicitly before approval — do not silently exclude it.
- Full `pytest` green; `ruff check .` clean.

If any legitimate quote is rejected: adjust the threshold (and re-verify) or stop; do not ship a
check with false rejections. WP-44.2 candidates use the criteria in §5.

## 9. Verification

- **Preserve the evidence first:** commit the classification script and a report sufficient to
  reproduce the 1,991-record analysis under `eval/spike_results/wp_44/` (precedent: `wp_43/`): a
  manifest of the 13 selected runs (selection rule — latest timestamp per document — input file
  hashes, profile, code revision), per-record identity, category, coverage, fuzzy score, baseline
  Step D disposition, the 5 leaks paired with their chunks and the labeling rationale, and the
  separate counts of automated vs. hand-reviewed stitched quotes.
- Baseline: replay Step D over the 13 documents; record counts per failure code, the surviving
  records, and the number of records with unknown chunks (unchecked).
- After: same replay with the check; diff outputs per §8.
- Report both views: raw Step C output, and what survives Step D — including any false
  rejections (expected: none). Step D replay shows normalized-output behavior only; it does not
  prove current Qdrant membership or final enriched/gated contents, so claims about indexed
  survivors require inspecting the selected artifacts/index separately.
- Findings go in a new §10 once measured.

---

## 10. Findings — WP-44.1

Replay of the real Step D entry point (`eval/step_d_replay.py`) over the saved Step C output of
the 13 documents. Baseline: a clean worktree at `c92bd87` (the commit before the change). After:
`776c2e7`. Summaries, with per-document run directories and chunk / extraction / PDF SHA-256
hashes, are in `eval/spike_results/wp_44/`.

**The comparison is a gate, not a report** (hardened after Codex's two PR #196 reviews):
`--compare ... --expected eval/spike_results/wp_44/expected_gate.json` exits nonzero unless both
runs used identical inputs (run directories and chunk / extraction / PDF hashes); the documents
compared are exactly the expected manifest of 13; nothing was added or changed; the removed
survivors are exactly the 5 approved IDs (whose quotes match the 5 hand-labeled leak fixtures); and,
per document, the failure-code change is exactly `quote_words_not_in_chunk` rising by that
document's removal count with every other code unchanged. Replay itself fails if any selected
document has no PDF instead of silently skipping it. Its failure paths, including each scenario
Codex reproduced, are unit-tested (`tests/unit/test_step_d_replay.py`).

**Replay fidelity (baseline):** 13 of 13 documents reproduce the existing corpus's survivor
requirement-ID set exactly (1,991 raw records → 1,850 survivors); 0 records had an unknown chunk,
so every record was checked.

| | Baseline | After |
|---|---|---|
| Raw records | 1,991 | 1,991 |
| Survivors | 1,850 | **1,845** |
| `quote_not_grounded_in_chunk` | 64 | 64 |
| `unrepairable_fragment_quote` | 31 | 31 |
| `heading_echo_quote` | 24 | 24 |
| `orphaned_list_item_quote` | 4 | 4 |
| **`quote_words_not_in_chunk` (new)** | — | **5** |

**Against the §8 gate:**
- All 5 known leaks rejected with `quote_words_not_in_chunk`: **met** (each had passed the fuzzy
  gate; the failure entries record `word_coverage` 0.188–0.647 against the 0.8 threshold).
- No other quote newly rejected: **met** (removed 5, added 0, changed-field 0; the only change in
  failure codes is the new code's 5).
- Output loses exactly the five verified baseline survivors, gains none, changes no stable field:
  **met.**
- `pytest` green (936 passed: +10 for the check, +20 for the replay gate), `ruff check .` clean: **met.**

**What the evidence does and does not show.**
- Selecting 0.8 and then replaying the same corpus checks the implementation and regressions, not
  generalization. No independent labeled sample exists.
- Step D replay shows normalized-output behavior only. The 5 leaks are present in the existing
  `normalized`, `enriched` and (for 3 of them) `gated` artifacts; whether they are in the live
  Qdrant index was **not** inspected here, and nothing in this WP changes existing artifacts.
- One observed example of the check's known blind spot exists in the corpus (DODI 8410.03 chunk
  13: "limited to" dropped, coverage 1.0, passes). Recorded in
  `eval/spike_results/wp_44/labels_and_review.md`; not addressed by this WP.

**Cleanup of the 5 existing records remains a separate, unauthorized step** (§4).
