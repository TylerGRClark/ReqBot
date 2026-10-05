# WP-45.7: held-out page draw (step 1 of the discovery/resolution experiment)

Measurement only; no LLM, no Qdrant, no production change. The plan, merged in #211, is `docs/PHASE45_WP457_PLAN.md`
(section 4.1 and 4.2). This step fixes the held-out page set and freezes it before anything is labeled or any prompt is
finalized. The set is not opened for tuning.

## Result

16 pages drawn from eleven documents (the ten pinned documents that are not development documents, plus CNSSI No. 1253 as
the control-catalog stratum), 24 pages to label after closure, **454 pieces** to label
(`outputs/heldout_frozen.json`, pieces sha256 `31b24ac851f827b6...`). `--check` recomputes the whole draw from the PDFs,
the pinned chunk files (WP-44 manifest hashes) and the pinned CNSSI 1253 chunk file, and fails on any difference.

| Document | Drawn pages (reason) | Pages added by closure | Pieces |
|---|---|---|---|
| CJCSI 6510.02G | 27 (one per document) | none | 13 |
| CNSSI_No1253 | 64 (one per document), 89 (catalog) | none | 55 |
| DODI 5200.01 | 10 (one per document) | none | 18 |
| DODI 5200.44 | 9 (one per document), 10 (extra) | none | 30 |
| DODI 5200.48 | 15 (one per document) | 14 | 34 |
| DODI 8551.01 | 6 (one per document) | none | 17 |
| afi10-2402 | 11 (one per document), 26 (extra), 42 (table) | 10, 25, 27 | 134 |
| afi13-550 | 8 (one per document) | none | 17 |
| afi17-203 | 9 (one per document), 20 (table) | 10, 19 | 63 |
| afpd_17-1 | 8 (one per document) | 7 | 29 |
| dafman17-1305 | 27 (one per document) | 26 | 44 |

## The rule (fixed in `draw_heldout.py` before the draw)

One page from every document (the first of a seeded shuffle of its pages with at least 60 words); one more catalog page (the
second of CNSSI 1253's shuffle); two table pages (pages touched by a chunk that holds a markdown table); two more from the
seeded shuffle of every other eligible page. Catalog documents are kept out of the table and extra pools. Seed
`wp45.7-heldout`. Discovery will run on every chunk whose page range touches a drawn page, and **the label set is every drawn
page plus every page any selected chunk touches**, so a record from a selected chunk never lies in unlabeled text (plan 4.2).

## Things worth knowing

- **Two rule changes before any labeling, both found in review of this PR or at freeze time, never edited by hand.**
  (1) The first closure took only chunk-touched pages and left CJCSI 6510.02G page 27, which no chunk covers, unlabeled; the
  drawn pages are now always in the label set, which also keeps a loss before extraction visible, as in WP-45.1(e).
  (2) The first draw had no control-catalog document although the plan requires that stratum (Codex, #212). CNSSI No. 1253 was
  run through Step B (`pipeline/chunk_text.py`, no LLM; Docling 2.94.0 / docling-core 2.99.0) into
  `~/documents/processed/CNSSI_No1253_*/`, its chunk file is pinned by sha256 in `draw_heldout.py`, and the draw was
  regenerated with the catalog stratum, which also changed which table and extra pages came up.
- **CNSSI 1253 has 80 table chunks out of 121**, so left in the table pool it would have taken the whole table stratum from the
  policy and instruction documents. It is kept to its two pages. Its pieces are PyMuPDF text from catalog tables and may segment
  less cleanly than prose; the labelers' "badly cut" flag from WP-45.1(e) applies.
- **Labeling load is above the plan's estimate.** 454 pieces per labeler, not about 350. AFI 10-2402 alone holds
  134 pieces. Nothing was dropped to make the number smaller.
- Some drawn pages may turn out to be front matter or references with no obligations; the 45.1(e) sample had the same shape
  (three of twelve pages), and that was not a reason to redraw.
- Pages are 1-based. Piece ids are `<code>-p<page>-<n>` (codes in `draw_heldout.py`). The text is PyMuPDF's, not Docling's, on
  purpose: it is an independent reading of the PDF, so a loss in Docling parsing stays visible and the labelers see no
  pipeline output. PyMuPDF is not a project dependency; it is used only in `eval/` scripts, as in WP-45.1(e).

## Files

- `draw_heldout.py`, `outputs/heldout_frozen.json`; tests in `tests/unit/test_wp457_heldout_draw.py`.
- Reuses `eval/spike_results/wp_45_1e/segment.py` unchanged and `eval/spike_results/wp_45_audit/_inputs.py` for the pinned
  chunk check.

Reproduce (needs `raw_pdfs/`, the pinned processed inputs, the CNSSI 1253 chunk file and PyMuPDF):

```
python3 eval/spike_results/wp_45_7/draw_heldout.py --check
```

## Step 2: labeling packs (`pack.py`, `label_pack/`)

Offline; no LLM, no pipeline output in the packs. Two packs, one rubric (version 2), one standalone checker.

| Pack | Pieces | What the labelers give |
|---|---|---|
| `pack_heldout.md` | 454 (every piece of the frozen held-out label pages) | `label` (obligation, lead_in, scope, not_obligation), `kind` when it is an obligation, `segment_ok`, `note` |
| `pack_devkind.md` | 105 marked pieces (78 adjudicated dev obligations plus 27 non-obligations with permission wording), shown with their pages as context | `kind` (obligation, recommendation, permission, prohibition, or none) and `note` |

Decisions worth knowing:

- **Rubric version 2 differs from the 45.1(e) rubric on purpose.** Version 1 excluded "may" and "can"; Tyler's 2026-10-05 ruling
  is that should-recommendations and may-permissions are requirements and the end user decides what to enforce. Version 2
  counts anything a reader could act on that the document asks of, allows or advises for a party, and keeps descriptions of
  what a technology can do as not an obligation. The held-out set is therefore labeled under the new rule from the start.
- **The dev "kind" pass is also the "may" re-check** the plan asks for (section 0): the 27 extra pieces are the adjudicated
  non-obligations that contain lowercase "may", "can", "permitted to", "authorized to" or "allowed to" (lowercase, so
  "22 MAY 2018" is not caught). Many are descriptive and should come back `none`. The marked pieces are listed in page order and
  carry no earlier label, so the labelers cannot tell which were obligations before. Disagreements go to Tyler, as before.
- **Lead-in labels are a later pass, not in these packs.** The plan has the labelers see the same bounded neighbor spans the R2
  bundle contains, and the bundle builder (the next step) defines them. Packing them now would invent a second definition.
- **Independence protocol (unchanged from 45.1(e)):** each labeler opens only the rubric, one pack and the checker, writes
  `labels_<name>_heldout.jsonl` or `labels_<name>_devkind.jsonl`, runs `check_labels.py`, and does not look at the other's file.
  Nothing is labeled in this PR; `outputs/pack_manifest.json` records the hashes of everything the labelers will be given.
- The adjudication and agreement tooling (disagreement sheet, spot checks) follows with the labels, adapted from the 45.1(e)
  `score.py` functions the pack builder already reuses for the dev labels.

Reproduce: `python3 eval/spike_results/wp_45_7/pack.py` (rewrites the packs and the manifest; the committed manifest is checked by
`tests/unit/test_wp457_label_packs.py`).

## Step 3: the evidence-bundle builder (`bundle.py`, `bundle_stats.py`)

Offline; no LLM. `bundle.py` builds the numbered evidence spans the resolver is shown, in the three tiers the plan defines
(R0 quote only; R1 adds the own chunk, the leaf heading and the governing-clause candidates from the existing stem finders,
marked unverified; R2 adds the bounded previous and next chunk and any cross-referenced section found in the document). It
follows the plan's rules: whitespace normalization shared with the later checks, a conservative 2.5 characters per token
with the whole prompt capped near 6,500 estimated tokens, cuts from the neighbors first and never from the candidate, the
heading or the stem candidates, a pre-call `preflight` and an `untreatable` flag, and standard library only. Tests:
`tests/unit/test_wp457_bundle.py` (13).

Two behaviors worth knowing:

- **References are read from the candidate's own text only.** Scanning the whole chunk would pull in references that belong to
  other sentences. A referenced section always gets its own excerpt, even when the same chunk is also the previous or next neighbor (neighbors are cut first when the budget binds, and a label on a neighbor would vanish with it); a reference that cannot be found in the document is listed in the
  prompt so the resolver can say what is missing.
- **Reference parsing (fixed in review of #214).** Named sections use the section parser's canonical keys (`APPENDIX-A`, `ENCLOSURE-3`, `SECTION-5`), tried before a bare number, so "Enclosure 3" does not land on paragraph 3.  A reference word introduces a list, and every member is returned
  ("Paragraphs 2.2, 4.1, and 11.2"). A bare identifier such as AC-2 counts only if it resolves to a section in the document,
  because `AES-256` and `SHA-384` look the same and are not references; an unresolved bare identifier is never reported as
  "not found". Only reference words, which cannot be mistaken, produce a "not found" line. This took the corpus count of
  records with a not-found reference from 116 to 80 (103 after named sections, subsections and references into other documents were added: they now resolve or are reported; more of the earlier 49 excerpts turned out to cite another document).
- **References into another document (fixed in review of #214).** "section 3.7 of Reference (c)", "Section 3252 of Title 10" and
  "paragraphs 4.(a) through 4.(d) of the January 19, 2017 Memorandum" name a provision of some other document, so they are
  never looked up locally (a local section with the same number would be offered as the wrong provision) and are listed as
  not found, with the qualifier in the text. "of this instruction" and "of this enclosure" are local and still resolve. The rule
  is a capitalized name after "of/in/from" that is not one of this document's own section words; 85 qualified references
  occur in the pinned corpus. Plural named forms ("Enclosures A, B, C, and D", "Appendices A and B") use the canonical keys too,
  with no bare-letter fallback, which would collide with unrelated list ids.
- **Budget (fixed in review of #214).** The bundle budget is the smaller of 3,000 estimated tokens and what the 6,500-token
  prompt cap leaves after the fixed text; the answer reserve is checked once, in the pre-call `preflight`, not taken off the budget
  again. Governing-clause candidates are never clipped: an over-long one makes the bundle untreatable, which is visible.
- **Governing-clause candidates are all of the finders' answers, not only the first**, each labeled with where it came from,
  because the stem rules were right only about 40% of the time (WP-45.1(b)) and the resolver has to be able to reject them.

Smoke measurement on the real pinned corpus (`python3 eval/spike_results/wp_45_7/bundle_stats.py`, 1,991 production Step C
records of the 13 pinned documents, 2,000 estimated tokens of fixed prompt, budget 7,500 characters). Not an evaluation of the
resolver, and these are Step C records, not discovery output:

| Tier | Mean chars | p95 | Max | Cut to fit | Untreatable | With a governing-clause candidate |
|---|---|---|---|---|---|---|
| R0 | 279 | 437 | 743 | 0 | 0 | 0 |
| R1 | 1,295 | 1,838 | 5,314 | 0 | 0 | 420 (21.1%) |
| R2 | 2,667 | 3,386 | 6,632 | 0 | 0 | 420 (21.1%) |

R2 added 33 referenced-section excerpts and left 103 records with an explicit reference ("paragraph 4.2", "Sections 3 and 5") it could not find in the document. At this fixed prompt size
the window is not a binding constraint on these documents; table-heavy chunks and a larger fixed prompt (the seven worked examples)
are what would push a bundle over, and the cuts and `untreatable` flag are tested for that case.

### Known limits of the reference rules

The cross-reference rules are deliberately rule-based and were hardened against real phrases from the pinned corpus over several
review rounds of #214; they will not catch everything. A reference the rules miss is simply absent from the bundle (the resolver
can still answer `unresolved`), and one they mis-read as local would offer the wrong text, which is why the doubtful cases go to
"not found". Known gaps, none measured to matter yet:

- **Ranges list their endpoints only** ("4.(a) through 4.(d)" returns 4.(a) and 4.(d), not 4.(b) and 4.(c)).
- **Local resolution needs the section number in the chunk's section path.** A provision named in running text but never made a
  heading is not found, and a reference whose parent section exists but whose lettered part does not (3.k with only section 3
  present) is reported as not found, not resolved to the parent.
- **The "other document" rule is a capitalized name after of/in/from.** "of the Manual" (capitalized, ambiguous) is treated as
  external; "of the instruction" (lowercase) as local. A reference with no qualifier is assumed local.
- **Bare control identifiers resolve or are ignored**, so a real control id the document does not contain is never reported as
  missing (AES-256 and AC-2 cannot be told apart otherwise).
- **Word forms are English** and listed in `_REF_WORD` / `_NAMED`; a new issuance style may need one more word.

## Step 4: the resolver schema, prompt and answer checker (`resolver.py`, `check_resolution.py`)

Offline; no LLM is called. `resolver.py` holds the resolver's JSON Schema (enums for status, modality class and logic; every other
value a nullable string, each wrapped with its evidence ids), the instructions, and six worked examples with invented text
(inherited list subject, prohibition with an exception, permission, negative recommendation, an unresolved cross-reference, scope
text). The examples are strictly valid JSON, no `a | b` placeholder and no comments is ever shown to the model, and each example
is built into a real `bundle.Bundle` so it renders exactly like a live one. `check_resolution.py` validates an answer against the
bundle it was given, by field type, as plan section 4.6 specifies: extractive containment on whitespace-normalized text, the
modal-phrase table (`should not` is a recommendation, `may not` a prohibition), status equals modality class for requirement
statuses (class `none` is only for a modal-free obligation), the cited operator must be the logic value, and for the composed fields
no new number, acronym or proper name and no new or changed modal of a different class (a subordinate modal the source itself
contains is a faithful copy; the modals are compared per class in both directions, so a dropped primary modal or a subordinate
modal reassigned to another class is caught too). A wrong primitive type in an answer is a shape issue, never a crash. An extractive value must lie inside ONE cited span; two spans that end and begin with the halves of
a name do not count. Tests: `tests/unit/test_wp457_resolution_check.py` (33). **Every worked example must pass the checker against its
own bundle** (a test enforces it), which keeps the prompt and the checker from drifting apart.

Two things the numbers say:

- **The fixed prompt is about 3,380 estimated tokens** (8,446 characters at the builder's conservative 2.5 characters per token),
  well above the plan's estimate of roughly 450 for the template plus 1,000 for the examples. It still fits: 3,380 for the fixed
  text, up to 3,000 for the bundle and 600 reserved for the answer is 6,980 of the 8,192 window. The estimate is deliberately
  pessimistic; the pilot reads Ollama's real `prompt_eval_count`. If it proves too heavy for the 8B, the first lever is fewer
  examples, then terser JSON.
- **Not yet tested against a live model:** that Ollama's schema-constrained generation accepts nullable string types and the enum
  keys on the 8B and the 14B. That is the first thing the 10-call pilot checks, together with structural conformance.

Not in this step: the entailment gate (a model) and the hand audit of faithfulness, which the plan lists separately.

### Known limits of the answer checker

The checker is rule-based and was hardened over four review rounds of #215; it is a first filter, not a proof of faithfulness. The
hand audit and the entailment gate (a model) are separate and still needed. Known gaps:

- **Modal vocabulary is a fixed English table** (`MODAL_TABLE`, with synonyms such as "has to", "needs to", "is advised to"). A
  paraphrase in words outside it ("is expected to", "is supposed to") is an `unknown_modal_phrase` in the modality field and, in
  `plain_language`, a `modality_removed` error even if the meaning is kept; the pilot shows how often that happens and the table
  can be widened. Modality is not validated at all when the status is `unresolved`.
- **A dropped subordinate modal is not caught.** Modals are compared per class in both directions, and the primary modal must
  survive in the standalone sentence and in the plain language, but a subordinate "may" that disappears from a sentence whose primary
  modal is intact passes; faithfulness of conditions and exceptions is left to the hand audit.
- **The new-name test is a heuristic** (numbers, acronyms and mid-sentence capitalized words that the source lacks). A common word
  capitalized for another reason, or a lowercase invented party, can slip past or be flagged wrongly; sentence starts after a
  closing bracket or quote are handled, a start after a colon is not.
- **Extractive containment is literal.** A value that restates a span in other words fails `not_in_cited_span`; that is intended
  (the field is supposed to quote), but it will count against a model that paraphrases.
- **"can" is context-dependent.** It counts as a modal only when the answer declares it as its modality phrase, so a permission written
  with "can" is checked, but an answer that calls a "can" sentence a modal-free obligation is not caught on that word alone.
- **Codes that count toward the zero-tolerance modality gate** are listed in `MODALITY_ERROR_CODES`; `added_token` and shape
  problems are reported separately and are not part of that rule.

## Step 5: the runners and the first live pilot (`ollama_run.py`, `discovery_prompts.py`, `chunk_sets.py`, `run_discovery.py`, `run_resolver.py`)

Measurement only. The shared client records Ollama's own token counts and timings; every run label (arm, model, repeat) has its own directory
and its own ledger, and a ledger key includes the **model digest** and the run label, so a second repeat or the 14B arm can never reuse
an earlier answer. A resolver key also carries the candidate id and chunk id: the same quote can occur several times in a document ("The DOT&E shall:" in
chunks 15, 19 and 21), R0 builds the same bundle for each, and each occurrence must still be resolved and counted. Only `complete` resolver answers
count toward the quality totals; an overrun, a truncation or a failure is a failed resolution, counted by status. A discovery prompt estimated over the prompt cap, or a resolver bundle that cannot fit, is recorded `untreatable` and
never sent; a call whose prompt plus answer reaches `num_ctx` is `window_overrun`; both stay in every denominator as failures. `failed`
records are redone on resume. D0 is the production Step C prompt unchanged; D1 is the plan's inclusive prompt (appendix A) with five invented
examples. Chunk sets: 46 held-out chunks and 38 dev chunks (the chunks that touch the labeled pages). Tests: `tests/unit/test_wp457_runners.py`
(13, with a faked Ollama).

**Pilot against the real server** (Tyler's Ollama, `llama3.1:8b-instruct-q4_K_M` digest `46e0c10c039e` and `qwen2.5:14b` digest `7cdf5a0187d5`,
temperature 0.1, `num_ctx` 8192). A schema and prompt smoke test on a handful of records, not an evaluation:

| Pilot | Calls | Complete | Shape-conformant | Mean prompt tokens | Mean answer tokens | Mean seconds | Answers with no checker error |
|---|---|---|---|---|---|---|---|
| Resolver R1, 8B, 10 production Step C records | 10 | 10 | 10 | 2,339 | 261 | 5.9 | 5 of 10 |
| Resolver R1, 14B, 10 same records (earlier prompt) | 10 | 10 | 10 | 2,350 | 322 | 15.0 | 2 of 10 |
| Discovery D0, 8B, 10 dev chunks | 10 | 10 | n/a | 1,004 | 130 | 3.1 | n/a |
| Discovery D1, 8B, 10 dev chunks | 10 | 10 | n/a | 1,201 | 202 | 5.0 | n/a |

What it settled:

- **The schema works.** Both models accepted the JSON Schema `format` constraint with nullable strings and enum keys; 20 of 20 resolver answers were
  structurally conformant and none failed to parse. That was the main open risk from step 4.
- **The 2.5 characters per token estimate is pessimistic by about 1.6 to 1.8 times** (estimate over real: 1.65 for the resolver, 1.7 to 1.8 for
  discovery). The real fixed resolver prompt is about 1,400 to 1,500 tokens, not 3,400, so windows are far from binding at these sizes (no overrun
  in any pilot call). The budget stays conservative for the experiment; the real counts are in the ledgers.
- **D1 is more inclusive, as designed**: 46 records against D0's 27 on the same ten dev chunks, at about 200 more prompt tokens and 60% more
  time per call. Record count is not the metric (recall and precision against the labels are), and 8-word runs from the D1 examples appeared in
  none of the 46 quotes (the regurgitation check that backlog item 23 asked for).
- **The 14B is about 2.5 times slower per resolver call and not better on this smoke test** (2 of 10 clean answers against 5 of 10, on the earlier
  prompt). Ten records settle nothing; the full runs and labels do.

What the checker found in the 8B resolver answers (so the pilot is also a test of the checker): on fragments whose governing "shall" is in the
bundle, the 8B often copies the quote and cites a "shall" from a span that does not contain it (`not_in_cited_span`), leaves the actor out of
the standalone sentence, gives a null modality phrase with class `obligation`, or invents a modality phrase from nowhere. These are model errors
the experiment exists to measure, not checker artifacts, and **the prompt was deliberately not tuned on this smoke test**. Two checker or prompt
artifacts were found and fixed before the numbers above: "can" in plain language ("who can get into them") was counted as a permission (it now counts as a modal only when the answer itself declares "can" as its modality phrase; "cannot" always counts), and neither
model had been told that `plain_language` and `unresolved_reason` take an empty evidence list (the prompt now says so, which changed its hash).

A `window_overrun` answer is kept in the ledger and counted, but exports no records (its prompt may have lost its instructions), so scoring
cannot credit candidates from an invalid call; the resolver loader serves the pinned catalog document (CNSSI 1253) as well as the WP-44 documents.

Not in this step: Step D on the discovery output, the scoring against labels, and the labels themselves (still waiting on the second-labeler decision).

## Step 6: dev-set discovery results (`score_discovery.py`, `outputs/dev_discovery_scores.json`, `outputs/dev_runs/`)

Offline scoring (needs numpy, like 45.1(e)'s `score.py` it reuses; not a project dependency) of seven real runs on the 38 chunks that touch the 12 labeled development pages (2026-10-05, Tyler's Ollama,
temperature 0.1, `num_ctx` 8192; run summaries with model digests and prompt hashes are in `outputs/dev_runs/`). Recall is the 45.1(e)
rule on the 74 adjudicated obligations with sound segmentation (a piece is covered when the records of its chunk reproduce at least 90%
of its tokens), with its page-level bootstrap interval. Precision uses an overlap rule fixed in the script: a record touching an
adjudicated obligation is a true positive, one touching only non-obligation pieces is a false positive, one touching no labeled piece
is `unscored` and counted in neither. Every call was `complete`: no overrun, truncation, failure or untreatable chunk in any run.

| Run | Recall (74) | 95% interval | Records | True / false positive | Precision | Unscored | Prompt / answer tokens | s per chunk |
|---|---|---|---|---|---|---|---|---|
| D0 8B, repeat 1 | 46 (62.2%) | 45 to 78% | 82 | 53 / 20 | 72.6% | 9 | 988 / 108 | 2.5 |
| D0 8B, repeat 2 | 45 (60.8%) | 42 to 77% | 84 | 52 / 21 | 71.2% | 11 | 988 / 107 | 2.5 |
| **D1 8B, repeat 1** | **68 (91.9%)** | 86 to 96% | 143 | 69 / 55 | 55.6% | 19 | 1,185 / 185 | 4.2 |
| **D1 8B, repeat 2** | **67 (90.5%)** | 77 to 97% | 136 | 68 / 51 | 57.1% | 17 | 1,185 / 174 | 4.0 |
| D0 14B | 24 (32.4%) | 11 to 58% | 35 | 27 / 1 | 96.4% | 7 | 1,034 / 47 | 2.3 |
| D1 14B, repeat 1 | 42 (56.8%) | 34 to 78% | 63 | 50 / 4 | 92.6% | 9 | 1,212 / 78 | 3.7 |
| D1 14B, repeat 2 | 38 (51.4%) | 28 to 73% | 57 | 44 / 4 | 91.7% | 9 | 1,212 / 71 | 3.5 |

**Findings.**

- **D0 on the 8B reproduces the 45.1(e) baseline** (60.8% there; 62.2% and 60.8% here, one piece apart between repeats), so this runner
  and its prompt handling are faithful to production Step C.
- **D1 raises the 8B's recall by about 30 points** (paired difference against D0 repeat 1: +29.7 points, interval +12.7 to +46.2, 26 pieces only D1
  covers against 4 only D0 covers; repeat 2 gives +28.4, interval +9.4 to +41.9, 24 against 3). Both repeats agree in direction and size.
  By document: NIST SP 800-125 from 6 of 16 to 15 of 16, afman17-2101 from 22 of 38 to 34 of 38, DODI 8410.03 from 18 of 20 to 19 of 20.
  D1 misses only 5 of the 74 in both repeats, among them "Ensure, in coordination with DISA ...", "organizations should have policies ..." and an AFMAN
  sentence with "shall be coordinated".
- **The price is precision, as designed**: 55 to 57% against 71 to 73%, from 20 false-positive records to 51 to 55. A sample of D1's false positives is
  mostly descriptive "may" and "can" sentences in NIST background ("Hypervisors can also dynamically alter isolation ..."), scope and boilerplate lines
  ("This Instruction:", "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY"), and statements about what a technology does. These are what the resolver must
  mark `not_a_requirement` or `scope_or_context` (gate G3); under Tyler's over-extract rule they are cheap, flagged rows, not losses.
- **The parked "tell the 14B to over-extract" test is answered**: D1 lifts the 14B from 32% to 51 to 57% and keeps it very precise (92%), but it stays below
  the 8B under either prompt, so the 8B remains the discovery model. The 14B's precision suggests the second-pass role (resolver) rather than discovery,
  which the resolver runs can now test.
- **No regurgitation**: none of the quotes in any D0 or D1 8B run shares an 8-word run with the D1 examples (0 of 82, 84, 143 and 136 quotes).
- **Cost**: D1 adds about 200 prompt tokens and about 75 answer tokens per chunk and 1.6 times the time (4.0 against 2.5 seconds on the 8B).

**D1 is frozen as it stands** (prompt hash `7da34da9994793c5`): none of the two dev revisions the plan allows was used, so the held-out set will
test exactly this prompt. The resolver prompt, bundle tier and model are chosen later, from the dev and audit data, and frozen before the held-out labels
are opened (plan section 4.4).

**What this does not show.**

- **The dev set is not independent of D1.** The failure shapes that D1's definition and examples target (third-person duty lists, imperatives, "should")
  were found on these same pages in WP-45.1(e); the examples are invented, but the dev gain is partly designed in. The held-out set is the test.
- **The labels are rubric version 1**: permission-only pieces were not obligations there, so an arm that correctly returns permissions is under-credited,
  and 78 versus 74 obligations depends on four badly cut pieces left out of the main numbers. The kind pass will say how many dev pieces are affected.
- **Seven runs, 38 chunks, 12 pages**: the intervals are wide (D1's lower bounds are 77 to 86%, well above D0's point estimate, but the 14B figures overlap).
  The 17 to 19 `unscored` D1 records lie in unlabeled text beside the sampled pages (closure was applied to the held-out set, not to dev).
- **Step D has not been run on these outputs**, so the plan's check that rejection codes do not rise is still open; recall here is at extraction.
