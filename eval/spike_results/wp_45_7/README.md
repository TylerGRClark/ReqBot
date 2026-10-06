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

## Step 7: the resolver's development gold and the pre-registered choice rule (`resolver_gold.py`, `score_resolver.py`)

Offline. **This section and the code it describes were written and merged before any resolver run on this gold was scored**, so the rule below
cannot be tuned to results.

**Gold** (`outputs/resolver_gold.json`, frozen; `resolver_gold.py --check` recomputes it): 220 already-labeled records with their quote and
chunk recovered from the pinned pipeline files.

- **Audit, 130 records** (WP-45.1(b)): Tyler's adjudicated verdict per record (82 need a lead-in, 30 are complete, 18 are not requirements) with the
  lead-in text and where it is, and for the 66 records production attached a stem to, his verdict on that stem (25 right, 19 wrong sibling, 12
  fragment chain, 9 wrong other, 1 not needed). The production stem is the paired baseline: 25 of 66 right is the 38% of WP-45.1(b).
- **Cards, 90 records** (WP-45.6): records only the 8B kept, only the 14B kept, or both, labeled real requirement or not by two labelers who agree on all 90
  for that question (79 real, 11 not).
- **Halves**: each record is in the *selection* or the *evaluation* half by a seeded hash of its id (audit 66 / 64, cards 38 / 52; 104 and 116 candidates).
  The tier and the model are chosen from the selection halves and the dev pages only; the evaluation halves are scored once, after the choice is
  frozen, together with the held-out labels (plan 4.4).

**Scoring** (`score_resolver.py`): only `complete` calls count toward quality; an overrun, truncation, failure or untreatable candidate is a failed
resolution, counted by status. Status: a real requirement should get a requirement status, a non-requirement `not_a_requirement` or `scope_or_context`;
`unresolved` is reported on its own. Attachment (audit records that are requirements): when the gold needs a lead-in, *right* if the answer's parent or
actor names Tyler's lead-in (at least 80% of the value's distinctive words, and at least one, are in the lead-in text; function words, modals, generic
role words such as "Director" and one-letter fragments of an abbreviation do not count, so a bare "Director" or "USD(R&E)" never matches "DIRECTOR, DISA" or "DOT&E"),
*incomplete* if it names neither, *misleading* if it names a parent or actor that does not overlap; when the gold is complete, right with no parent and misleading with one.
The baseline is Tyler's verdict on the production stem on the same records (right, or misleading), and by the gold where production attached nothing.
Two audit records have no adjudicated lead-in text and are scored for status only. A failed resolution (a call that was not `complete`, a missing or malformed
answer) stays in every denominator and counts **against** every max-style gate, and a gate requires at least 95% of the candidates to be resolved at all.
Fidelity: answers with a modality error code (zero tolerated); answers with an added token in a generated sentence, or an actor or parent outside the cited spans
(at most 2%; a paraphrased action or target is not counted as invented).

**The choice rule, fixed now.** From the selection halves only, keep the configurations (tier R0, R1 or R2; model 8B or 14B) that satisfy every gate that
applies: at least 95% of candidates resolved; at most 5% of real requirements returned `not_a_requirement` (failures counted as such); real requirements returned `scope_or_context` or `unresolved` at most 10% together;
at least 60% of non-requirements returned `not_a_requirement` or `scope_or_context`; invented party or number rate at most 2%; no modality error; and
"incomplete" attachment (failures counted as incomplete) at most the baseline's plus 5 points. Among those, take the highest attachment-right rate on the audit selection half; ties go to the
lower tier and then to the smaller model. If none passes, take the highest right rate and report it as failing the gate. Nothing in the evaluation halves is
read to choose.

Known limits: 104 selection candidates make every rate wide; the cards carry no attachment gold and the audit records are not the held-out population;
the gold is of production Step C records, which are not what D1 will produce.

## Step 8: held-out discovery runs, **unscored** (`outputs/heldout_runs/`)

Seven runs on the 46 held-out chunks, 2026-10-06, Tyler's Ollama, temperature 0.1, `num_ctx` 8192, with the **frozen** D1 prompt (hash `7da34da9994793c5`) and the production
prompt D0 (hash `dae9584ffa32ae9b`). Each run directory holds the ledger (`discovery.jsonl`, every raw answer) and the run summary (model digest, prompt hash, status
counts, token and time means). Every call in every run was `complete` (46 of 46): no overrun, truncation, failure or untreatable chunk.

| Run | Records |
|---|---|
| D0 8B, repeats 1 and 2 | 141, 139 |
| D1 8B, repeats 1 and 2 | 201, 211 |
| D0 14B, repeat 1 | 55 |
| D1 14B, repeats 1 and 2 | 112, 116 |

The committed ledgers name each record's id `entry_id`. The first version of the runners called it `key`, and gitleaks reads a field named `key` that holds a hash as an API key, so the field was
renamed (the loader still reads old ledgers, and the copies committed here were renamed mechanically; nothing else changed).

These are **counts of records, not scores**: nothing here is measured against labels, and a larger count is not better (plan 4.4). The held-out set is deliberately not scored until
(1) the two labelers' files exist and Tyler has adjudicated the disagreements, and (2) the resolver tier and model are chosen from the development and audit-selection data and
frozen, because the plan allows no configuration choice after the held-out labels are opened. They are committed now only so the raw answers survive the working container.

## Step 9: resolver v1 on the selection half, and the one allowed prompt revision (pre-registered before any v2 result)

**What v1 did on the 8B** (`outputs/resolver_selection_v1_8b.json`, with every ledger behind it in `outputs/resolver_v1_runs/`: each raw answer, evidence bundle, issue list, model digest and run label; the selection half only, 104 candidates; run 2026-10-06 with the v1 resolver prompt, hash
`abaa18ac67ef857a`; every call `complete`, 104 of 104 shape-conformant in all three tiers):

| 8B tier | Attachment right / misleading / incomplete (55 scorable audit records) | Non-requirements rejected | Answers with a modality error | Invented-party rate |
|---|---|---|---|---|
| Production stem (baseline) | 19 / 19 / 17 | n/a | n/a | n/a |
| R0 quote only | 15 / 4 / 36 | 4 of 16 | 43 of 104 | 0% |
| R1 | **38 / 7 / 10** | 1 of 16 | 50 of 104 | 19% |
| R2 | 35 / 7 / 13 | 0 of 16 | 40 of 104 | 14% |

Attachment is much better than production at R1 and R2 (right 69% and 64% against 35%; misleading 13% against 35%). **No 8B configuration passes G2**: all fail the
non-requirement gate (60% needed), the modality gate (zero needed), and R1 and R2 the invented-party gate (2%); R0 also fails the incomplete gate.

**Why, from the answers** (not a re-tuning on the evaluation halves, which are untouched): the v1 prompt had no example of an imperative with no modal, so the 8B gave
class `obligation` with a null phrase (19 answers) and then dropped the modal from its standalone sentence (29); it had no `not_a_requirement` example, so descriptive
sentences were kept as requirements; it never said to copy actor, action and target word for word (29 `not_in_cited_span` on action and target); and it never said to cite the
lead-in span an actor came from, so generated sentences "added" names (11 `added_token`).

**The protocol, fixed now.**

1. The 14B v1 runs were still going when v2 was written. The pre-registered choice rule (step 7) is applied to **all six v1 configurations first**. If any passes
   every gate, it is chosen and v2 is not used.
2. Otherwise this is the plan's one allowed fix on the dev side (plan 4.5, G2): **prompt v2** (this PR) changes only the instructions and adds two invented examples (an
   imperative with no modal; a descriptive sentence that contains "can"), saying to copy values word for word, to cite every span used, to give a null phrase when no
   modal word is cited, and what `not_a_requirement` means. The checker, the phrase table, the gold, the gates and the choice rule are **not** changed.
3. All six configurations are re-run on the same 104 selection candidates with v2 and the rule is applied to the v2 results alone; the v1 numbers stay in the record.
4. If some v2 configuration passes every gate it is frozen with its hash; then the evaluation halves are scored once, and the held-out resolver and end-to-end runs follow.
   **If none passes, G2 is failed on the development side: stop, report it, and do not run the held-out resolver.** No second revision.

v2 adds about 1,060 estimated tokens to the fixed prompt (4,470 against 3,408), which still leaves the bundle budget at 5,075 characters; with it no R2 bundle in the selection
half is cut (checked before running).

## Step 10: the pre-registered rule applied to all six v1 configurations (`score_resolver.py --choose`, `outputs/resolver_selection_v1_*.json`, `outputs/resolver_v1_runs/`)

All six v1 runs (R0, R1, R2 on the 8B and on the 14B; the same 104 selection candidates; every call `complete`) are committed with their ledgers, and the scores in
`outputs/resolver_selection_v1_scores.json` and the choice report in `outputs/resolver_selection_v1_choice.json` are regenerated from those committed ledgers (they match the first
scoring of the scratch ledgers). The rule of step 7 was applied by code (`--choose`), reading only the selection halves.

| Config | Attachment right (55 audit) | Misleading | Incomplete | Non-requirements rejected (16) | Real wrongly rejected | Answers with a modality error | Invented-party rate | Gates failed |
|---|---|---|---|---|---|---|---|---|
| Production stem (baseline) | 19 (34.5%) | 19 | 17 | n/a | n/a | n/a | n/a | n/a |
| R0, 8B | 15 (27.3%) | 4 | 36 | 4 (25%) | 1% | 43 | 0% | incomplete, modality, non-requirement |
| R1, 8B | **38 (69.1%)** | 7 | 10 | 1 (6%) | 0% | 50 | 19.2% | modality, invented, non-requirement |
| R2, 8B | 35 (63.6%) | 7 | 13 | 0 (0%) | 0% | 40 | 13.5% | modality, invented, non-requirement |
| R0, 14B | 15 (27.3%) | 2 | 38 | 11 (69%) | 10.2% | 56 | 4.8% | incomplete, modality, invented, real rejected |
| R1, 14B | 32 (58.2%) | 22 | 1 | 8 (50%) | 1.1% | 47 | 25.0% | modality, invented, non-requirement |
| R2, 14B | 37 (67.3%) | 14 | 4 | 7 (44%) | 0% | 40 | 22.1% | modality, invented, non-requirement |

**Result: no v1 configuration passes G2.** The rule's fallback chooses **R1 on the 8B** (best attachment-right rate, 69.1%) and reports it as failing the gate. What the table shows:

- **Context is what buys the attachment gain**: R0 (quote only) is right 27% of the time, R1 and R2 reach 58 to 69%, against 35% for production's stems; R2's neighbors did not beat R1 on the 8B.
- **The 14B is not better at attachment** and gives misleading answers more often (22 and 14 of 55 against 7 and 7 for the 8B), but at R0 it is the only configuration that rejects most non-requirements (69%), at the cost of rejecting 10% of real ones.
- **Every configuration has a modality-error count in the 40s to 50s of 104** and the invented-party rate is far above 2% wherever context is supplied.

Under the protocol of step 9 this triggers the one allowed revision: **prompt v2** (hash `d0fcb1a2b23684f5`) was merged before this step and the six v2 runs on the same candidates were started 2026-10-06 after this table was fixed. The rule is applied to the v2 results alone; if none passes, G2 fails on the development side and the held-out resolver is not run.

## Step 11: the v2 resolver on the selection half, and the outcome of the protocol (`outputs/resolver_selection_v2_*.json`, `outputs/resolver_v2_runs/`)

Prompt v2 (hash `d0fcb1a2b23684f5`, merged in #220 before this step) was run in all six configurations on the same 104 selection candidates (2026-10-06; every call `complete`,
104 of 104 shape-conformant in every run). The ledgers are committed; the scores and the choice report (`score_resolver.py --choose`, the six registered configurations, the selection
halves only) are regenerated from them.

| Config | v1 attachment right | **v2 attachment right** (misleading / incomplete) | v2 non-requirements rejected (16) | v2 real wrongly rejected | v2 answers with a modality error | v2 invented-party rate | v2 gates failed |
|---|---|---|---|---|---|---|---|
| Production stem (baseline) | 34.5% | 34.5% (19 / 17) | n/a | n/a | n/a | n/a | n/a |
| R0, 8B | 27.3% | 27.3% (3 / 37) | 11 (69%) | 10.2% | 20 | 1% | real rejected, modality, incomplete |
| R1, 8B | 69.1% | 54.5% (16 / 9) | 10 (62.5%) | 6.8% | 30 | 21.2% | real rejected, modality, invented |
| R2, 8B | 63.6% | 50.9% (7 / 20) | 9 (56%) | 2.3% | 26 | 15.4% | non-requirement, modality, invented, incomplete |
| R0, 14B | 27.3% | 27.3% (1 / 39) | 12 (75%) | 11.4% | 20 | 14.4% | real rejected, modality, invented, incomplete |
| R1, 14B | 58.2% | **63.6% (19 / 1)** | 12 (75%) | 2.3% | 40 | 29.8% | modality, invented |
| R2, 14B | 67.3% | 61.8% (17 / 4) | 13 (81%) | 5.7% | 35 | 27.9% | real rejected, modality, invented |

**Outcome.** No v2 configuration passes every gate. The rule's fallback chooses R1 on the 14B (the best attachment-right rate) and reports it as failing the invented-party and modality gates.
By the protocol of step 9 (one revision, no second): **G2 fails on the development side.** The evaluation halves of the gold were not scored, the resolver was not run on the held-out set,
and no end-to-end run was made.

**What v2 changed.** It fixed what the prompt could fix: non-requirements are now rejected 56 to 81% of the time (v1: 0 to 69%, and 0 to 6% on the 8B at R1 and R2), modality-error answers fell on most
configurations (v1 40 to 56, v2 20 to 40), and the 8B's R0 invented-party rate is 1%. It did not fix the invented-party rate wherever context is supplied (15 to 30%) or the modality errors (never zero), and
it lowered the 8B's attachment (R1: 69% to 55%), probably because "copy word for word" made the model leave actors and parents empty more often; the 14B's R1 moved the other way (58% to 64%).

**Where the failures are** (from the committed ledgers; not tuned on): they concentrate in the *composed* fields, `standalone_statement` and `plain_language`, and in the actor and parent values taken from headings, not in
classification. The models expand acronyms from outside knowledge in the plain-language paraphrase ("Controlled Unclassified Information", "Air Force Global Strike Command": `added_token`), drop or add a modal
when paraphrasing (`modality_removed`, `modality_added`, `modality_strengthened`), take an actor from a heading but cite only the quote span for the sentence they build from it, and write an actor
with a leading article ("The Director, DISA" for the heading "DIRECTOR, DISA") that fails the literal containment test.

**What this says about the architecture hypothesis, and what it does not.**

- *Supported:* separating discovery from resolution is worth it for **discovery** (step 6: D1 raises 8B recall on the development pages by about 30 points, at a precision cost that the resolver is meant to recover), and a resolver
  that is given the chunk, heading and stem **attaches the governing clause or party far better than production's rules** (v1 R1 8B 69% and v2 R1 14B 64%, against 35%, with far fewer misleading answers than the production
  stem's 35% for the 8B).
- *Not supported:* a resolver that also **writes** a faithful standalone sentence and plain-language paraphrase under zero tolerance for modality changes and a 2% limit on invented parties, with these models and this prompt. No
  configuration is close on the invented-party gate except the 8B at R0 (which attaches almost nothing).
- *Not tested:* anything on the held-out set; whether the discovery gain holds on documents not used to design D1 (the held-out discovery runs exist but are unscored until labels exist); an extractive-only resolver.

**Decisions this leaves to Tyler** (nothing here is started):

1. *Stop at discovery and attachment.* Treat D1 as the production candidate for discovery (it still needs the held-out confirmation, which needs the two labelers), and do not adopt a generative resolver.
2. *A new, separately pre-registered experiment: an extractive-only resolver.* Return status, actor, parent, modality phrase and class, conditions, exceptions and timing as spans copied from the evidence, with **no** standalone sentence or plain-language
   field; keep the same gold and halves; the fidelity gates then apply to verbatim fields only. This keeps the attachment gain and the non-requirement filtering that v2 showed and removes the fields where the failures concentrate.
3. *The second labeler for the held-out set*, which is needed for the discovery confirmation regardless.

## Step 12: WP-45.7b, the candidate menu and its offline ceiling (S1) (`menu.py`, `measure_menu.py`, `outputs/menu_ceiling_*.json`)

Plan: `docs/PHASE45_WP457B_PLAN.md` (merged in #223). `menu.py` is the deterministic generator that builds, for one candidate quote, a numbered menu of verbatim spans the selection
resolver may pick (the quote's own subject, headings with and without their section number, the nearest colon lead-in, the clause just before the quote, the rule stems, and at R2 the previous
chunk's lead-in). Nothing in it is generated; a unit test checks that every entry is a substring of its source. `measure_menu.py` is S1: for each attachment-scored **selection-half** audit
record, could a perfect choice from the menu be marked *right* by the same `attachment()` rule the resolver is scored with? The evaluation half is refused without `--final`.

| | Scored | Ceiling (all) | Ceiling (needs a lead-in only) | Mean / max menu size | S1 (at least 75%, mean at most 8) |
|---|---|---|---|---|---|
| Revision 0, R1 (first look, `menu_ceiling_rev0_r1.json`) | 55 | 74.5% | 65.9% of 41 | 3.0 / n/a | FAIL (41 of 55; 42 were needed) |
| Revision 0, R2 (`menu_ceiling_rev0_r2.json`) | 55 | 78.2% | 70.7% | 3.4 / n/a | PASS |
| Revision 1, R1 (`menu_ceiling_rev1_r1.json`, hash `a6edfba17feb68d1`; superseded) | 55 | 89.1% | 85.4% | 4.9 / 8 | PASS |
| Revision 1, R2 (`menu_ceiling_rev1_r2.json`; superseded) | 55 | 92.7% | 90.2% | 5.4 / 10 | PASS |
| **Revision 2, R1** (`menu_ceiling_rev2_r1.json`, generator hash `92be12cecb3bd841`) | 55 | **87.3%** | 82.9% | 4.9 / 8 | **PASS** |
| **Revision 2, R2** (`menu_ceiling_rev2_r2.json`) | 55 | **92.7%** | 90.2% | 5.2 / 10 | **PASS** |

**Revision 1** (the first of the two the plan allows) was made from the revision 0 misses on the selection half: a leading section number ("11.", "2.20.") counted as an identifying word and defeated the
0.8 overlap rule, so each heading is now also offered without its number; and a list item whose lead-in is the clause right before it with no colon had no menu entry, so the clause between the previous
sentence boundary and the quote is now offered.

**Revision 2** (the second and last) answers a Codex review finding on #224, not a miss: the nearest colon before the quote was taken as the lead-in even when it governed nothing ("Note: background text. (1) Encrypt data." offered
"Note:"; "https:" and "10:30" produced malformed spans). A colon now counts only when what follows it, up to the quote, is empty or starts with a list marker, and an earlier colon is tried when the nearest does not govern.
It cost the R1 ceiling one record (89.1% to 87.3%) and changed which R2 records are reachable (R089 gained, R011 lost) without changing the R2 total. **The generator is frozen at revision 2** (hash `92be12cecb3bd841`,
recorded in each output); both revisions the plan allows are used, so any further change is out of bounds for this experiment.

How to read it:
- **A ceiling, not a score.** It says the right span is *in* the menu, not that a model will choose it; the model run (S2) measures that, and several plausible spans in one menu is where misleading answers will come from.
- **The 55 include the 14 `complete` records**, which are right by choosing nothing, so the "needs a lead-in only" column is the harder number (85 to 90%). The v2 resolver's best attachment-right rate (63.6%) was over the same 55.
- **Remaining misses** (R1 seven: R009, R011, R043, R089, R090, R109, R112; R2 four: R011, R043, R090, R112) are listed with their menus in the outputs. They were not inspected further and are not chased.
- The "lead-in location" column describes where the human found the lead-in; a different span (for example a heading) can name the same actor, so a record can be reachable from a source other than the labeled one.
- **S1 is per tier.** Both tiers pass; had one failed it would have been dropped from the model runs, and if both failed the plan stops with no model run.

Next (plan stage 3): the selection prompt, the assembler and the runner, with the `--choose` registry for the four configurations.

## Step 13: WP-45.7b, the selection prompt, the assembler, the runner and the registry for four configurations (`selection.py`, `run_selection.py`, `score_resolver.py --registry v3`)

Plan stage 3. **No model has been run yet**; this step is the code and its tests, so that the runs of stage 4 are mechanical.

- `selection.py`: the model sees the evidence bundle plus the menu and answers only `{status, actor, parent}`; actor and parent are an enum of this candidate's menu ids plus `"none"` (Ollama `format`), the status the same enum as before. Five invented worked examples
  (a list item under a named lead-in, a complete sentence, a description, a recommendation, a scope statement) are checked by a test to be valid answers that the **unchanged** checker accepts after assembly. The fixed part of the prompt is about
  1,770 estimated tokens (the generative resolver's was about 4,470); prompt hash `c9ca62bfb5a01a63`.
- `assemble`: actor and parent are the chosen menu texts; the **modality is read by code** (the quote first, then the chosen parent; the chosen actor is never read, so a lead-in picked as the actor with no parent is a malformed choice that fails the checker instead of lending its modal; the ambiguous `can` is not read); every field the model did not choose is null. The answer cites exact-text spans only (the quote
  and one span per chosen entry), never a larger span that contains the entry, because a whole chunk cited as evidence would put its own modals into the answer and be counted against it. A status that contradicts the quote's own modal (for example `obligation` for "should") is
  still a modality error through the checker's status/class check, so the modality gate stays model-dependent, as the plan says after the Codex review.
- `run_selection.py`: the same ledger fields as `run_resolver.py` plus the menu and the raw selection, so `score_resolver.py` reads it as it is. Tiers R1 and R2 only. It reads the selection half of the frozen gold; the evaluation half is refused without `--final`.
  `--num-predict` defaults to 200 (the answers are a few tokens). `--dry-run` builds every menu, bundle and prompt and prints the sizes (it calls nothing and writes nothing). On the 104 selection candidates: no empty menus, **0 untreatable**, mean estimated prompt 2,429 tokens (max 2,871) at R1 and 3,000 (max 3,910) at R2, mean menu 4.8 and 5.0 entries.
- `score_resolver.py --choose --registry v3`: the registry of the four configurations (r1_8b, r1_14b, r2_8b, r2_14b), the same gates as before, plus a gate that the audit attachment-right rate is at least **35 of 55** (63.6%, the best generative result), compared as an exact fraction.
  The default registry is still the six of WP-45.7, so the merged v2 results score exactly as before.

**Known limit of the frozen generator** (found by reading one live prompt, after the generator was frozen at revision 2; **not fixed**, so as not to exceed the plan's two revisions): the revision-2 rule that a colon governs only when list items follow it does not recognize multi-level
section numbers such as "2.1.5.1." as list markers, so a chunk whose lead-in is followed by such numbering gets no `lead_in` entry. On the 104 selection candidates this affects two (audit R011, already on the revision-2 miss list, and card R064); with the rule widened they would gain their lead-in. If the
experiment succeeds, widening the marker rule is an obvious follow-up, made after the evaluation-half verdict and measured as its own change. Also, the `preceding` entry sometimes holds only a list number ("2.1.5.2."), which is useless but harmless: the right answer for it is `none`.

Next (plan stage 4): the four runs (R1 and R2, each on the 8B and the 14B) on the selection half, the choice report with `--registry v3`, and the stop-or-continue decision, as in Step 11.

## Step 14: WP-45.7b, the first selection run on the selection half (`outputs/selection_v3_runs/`, `outputs/resolver_selection_v3_choice.json`)

The four configurations (R1 and R2 by the 8B and the 14B) ran on the 104 selection-half candidates with the selection prompt of step 13 (hash `c9ca62bfb5a01a63`, code as merged in #225, run from a pinned worktree). Every call completed and 104 of 104 answers were shape-conformant in
every run, at about 0.6 to 1.1 seconds per call (the answers are a few tokens). The choice report is `score_resolver.py --choose --registry v3` over these four runs alone. The v2 columns are the best generative result for comparison (R1, 14B).

| Config | Attachment right (misleading / incomplete) | Non-requirements rejected (gate 60%) | Real wrongly rejected (gate 5%) | Answers with a modality error (gate 0) | Invented-party answers (gate 2%) | Gates failed |
|---|---|---|---|---|---|---|
| Production stem (baseline) | 34.5% (19 / 17) | n/a | n/a | n/a | n/a | n/a |
| Generative v2, R1 14B (best) | 63.6% (19 / 1) | 75% | 2.3% | 40 | 29.8% | modality, invented |
| Selection, R1 8B | 54.5% (22 / 3) | 81.2% | 6.8% | 3 | **0** | attachment, real rejected, modality |
| Selection, R1 14B | **58.2%** (20 / 3) | 68.8% | 5.7% | 4 | **0** | attachment, real rejected, modality |
| Selection, R2 8B | 52.7% (21 / 5) | 75.0% | 6.8% | 5 | **0** | attachment, real rejected, modality |
| Selection, R2 14B | 58.2% (20 / 3) | 75.0% | 6.8% | 4 | **0** | attachment, real rejected, modality |

**Outcome of the first run.** No configuration passes. The rule's fallback chooses R1 on the 14B (58.2%) and reports it as failing three gates. By construction the invented-party rate is zero and the modality errors fell from 20-40 answers to 3-5; the misleading rate is
about as high as the generative resolver's, while the model almost never leaves attachment empty (3 to 5 incomplete). What follows is read from the ledgers, not tuned on.

- **Real requirements rejected (five or six per configuration; nine different records in all):** four records are rejected by all four configurations (audit R118 "Mechanisms for enforcement, auditing, and assurance.", audit R128 "Required local event storage requirements (if any).", card R057
  "developing virtualization policy", card R063 "Maximum allowable time from when an event takes place to when it is reported ..."), and the rest differ by run (audit R057, card R061 on R1 8B; audit R057 on R1 14B; audit R058, card R061 on R2 8B; audit R071, card R085 on R2 14B). The records are noun-phrase list items called
  `not_a_requirement`: the model reads a fragment as a description, although each is a list item under a lead-in or heading that assigns a duty.
- **Modality errors: the gated count and a separate, non-gated checker error.** The gate counts the answers with a code in `check_resolution.MODALITY_ERROR_CODES` (`modality_strengthened`, `modality_added`, `modality_removed`, `modality_class`, `unknown_modal_phrase`): 3 to 5 per run. Two kinds among them:
  (a) *Model errors:* `permission` for a descriptive sentence with "can" (audit R033, R100), `obligation` for "will not" (card R039), a `recommendation` the quote does not support (audit R052, card R078). (b) *A limit of the registered checker, not of the model:* card R025 is "Consider using introspection capabilities to monitor the security of ...",
  a modal-free hint that is correctly a `recommendation` under the project's ruling that hints are requirements, but the checker's phrase table has no entry for "consider", so a `recommendation` with no modal phrase is always reported as `modality_class`. It is in the gated list of **all four** runs: a correct answer on that record fails the zero-modality gate, so
  **zero modality errors may not be reachable by honest answers on this half**, whatever the prompt does. This is a property of the gate as registered, reported rather than changed.
  **Separately, `modal_in_evidence` is a checker error that the gate does not count** (it is not in `MODALITY_ERROR_CODES`): a lead-in such as "The DOT&E shall:" picked as the **actor** with no parent (the actor does not lend its modal, so the checker flags the modal in the cited evidence). It occurs in 4 answers on R1 8B, 0 on R1 14B, 9 on R2 8B and 1 on R2 14B, none of them in the table's modality column.
  With status `obligation` such a choice raises only this non-gated code, and the attachment rule can even score it right, because the chosen actor text overlaps the gold lead-in; with `recommendation`, `permission` or `prohibition` it also raises the gated `modality_class`. So the gates alone do not catch it; it is reported here, and it is a malformed choice a prompt can address.
- **Misleading attachments (20 to 22):** for records that need a lead-in, the model often picks a `preceding` entry (the words just before the sentence, sometimes only a list number) or a heading instead of the lead-in; for complete sentences it attaches a heading or a `preceding` entry when `none` is right.

**What the plan allows next:** one prompt revision after this first run (plan section 3, S2), made from these selection-half failures, run on the same four configurations, and judged by the same rule over the revised runs alone. The evaluation half is still unread.

## Step 15: WP-45.7b, the one prompt revision the plan allows (`selection.py`, prompt hash `435a1561313c6d64`)

Made from the selection-half failures of step 14, **before** any run of it, and registered here. Nothing else changes: the generator is still frozen at revision 2, the checker, the gates, the registry and the choice rule are as they were, and the evaluation half is still unread. The revised prompt runs on the same four
configurations and the rule is applied over those four runs alone (the first-run results stay in the repository as the first-run record).

What the revision says, in general terms (the examples are invented; a test checks that none of the corpus acronyms appear in the prompt):
1. **Fragments and list items.** A short phrase or list item, even a bare noun phrase, under a lead-in or heading that says what someone must, should or may do or provide is part of that requirement and gets its status, with the lead-in as its parent; `not_a_requirement` only when nothing in the evidence assigns a duty. (Answers the five or six real noun-phrase items rejected in step 14.)
2. **Actor versus parent.** An entry that ends with a colon or contains a modal word is a governing clause: a parent, never an actor; the shorter entry naming the party is the actor. (Answers the lead-in-as-actor choices, the non-gated `modal_in_evidence` errors.)
3. **`preceding` entries** are only the words right before the sentence and are chosen only if they end with a colon or name the party; a sentence that is complete by itself gets parent `none` even when a heading is on the menu. (Answers the misleading attachments.)
4. **Status from the modal word:** "will not", "shall not", "must not" are prohibitions; "can" or "may" in a description of what something can do is no permission. (Answers the model-side modality errors.)

Two new invented worked examples (a noun-phrase item under a "must include:" lead-in; a "will not" prohibition under a topic heading with a junk `preceding` entry); the fixed prompt grows from about 1,770 to 2,634 estimated tokens, and every selection-half prompt still fits (0 untreatable; largest 3,734 at R1 and 4,773 at R2 by the conservative estimate).

**What this revision does not do, on purpose:** it does not teach the model to relabel a modal-free hint such as "Consider using ..." as an obligation to get past the checker; that record (card R025) stays a correct `recommendation` that the checker's phrase table cannot accept, so the zero-modality gate may still fail on it. If the revised runs miss only on that, the report says so and leaves the gate alone.

## Step 16: WP-45.7b, the revised prompt on the selection half, and the outcome of the protocol (`outputs/selection_v3r1_runs/`, `outputs/resolver_selection_v3r1_choice.json`)

The revised prompt of step 15 (hash `435a1561313c6d64`, code as merged in #227, run from a pinned worktree) ran on the same four configurations and 104 selection candidates. Every call completed, 104 of 104 shape-conformant in every run. The rule (`--choose --registry v3`) was applied over the revised runs alone.

| Config | Attachment right: first run, revised (misleading / incomplete in the revised run) | Non-requirements rejected (60%) | Real wrongly rejected (5%): first, revised | Gated modality-error answers (0): first, revised | Invented | Gates failed (revised) |
|---|---|---|---|---|---|---|
| Production stem | 34.5% | n/a | n/a | n/a | n/a | n/a |
| Generative v2, R1 14B (best) | 63.6% | 75% | 2.3% | 40 | 29.8% | modality, invented |
| Selection R1 8B | 54.5%, **58.2%** (20 / 3) | 81.2% | 6.8%, 8.0% | 3, 2 | 0 | attachment, real rejected, modality |
| Selection R1 14B | 58.2%, 54.5% (22 / 3) | 81.2% | 5.7%, 8.0% | 4, 5 | 0 | attachment, real rejected, modality |
| Selection R2 8B | 52.7%, 54.5% (20 / 5) | 81.2% | 6.8%, 9.1% | 5, 4 | 0 | attachment, real rejected, modality |
| Selection R2 14B | 58.2%, **60.0%** (20 / 2) | 81.2% | 6.8%, **3.4%** | 4, 5 | 0 | attachment, modality |

**Outcome.** No configuration passes. The rule's fallback chooses R2 on the 14B (60.0%) and reports it as failing the attachment gate (needs 35 of 55; it has 33) and the modality gate (5 answers). **By the protocol (one prompt revision, no second), G2 for the selection resolver fails on the development side.**
The evaluation halves were not scored, the resolver was not run on the held-out set, and no end-to-end run was made.

**What the revision did and did not do** (read from the two sets of ledgers):
- It did not move attachment: the revised rates (54.5 to 60.0%) are within a few records of the first run's (52.7 to 58.2%), and individual records flip both ways (R1 8B: six records became right and four became misleading; R2 8B: eight and seven; R1 14B: two and four; R2 14B: three and two). With 55 records the differences between configurations and between the two prompts are inside this noise; the ranking of the four configurations should not be read as a finding.
- Real wrongly rejected got worse on three configurations (to 8.0, 8.0 and 9.1%) and better on one (R2 14B, 3.4%, the only configuration that passes that gate); the noun-phrase items were only partly fixed, and new records were rejected (for example card R025, "Consider using ...", on both 8B runs, where the model now calls a modal-free hint a non-requirement instead of a recommendation; which part of the revised prompt did that was not isolated).
- Gated modality errors stay at 2 to 5. Card R025 is still in the gated list of both 14B runs (the checker-limit record of step 14), so on the 14B the zero gate cannot be met by a correct answer; audit R052 and card R078 ("ensure that policies are updated accordingly as needed.", labeled `recommendation` with no modal anywhere) are model errors. The non-gated `modal_in_evidence` lead-in-as-actor errors fell on the 8B at R1 (4 to 3) and rose at R2 (9 to 7 answers); they are 0 on the 14B.

**Exploratory control, not a gate, selection half only (the same 55 attachment-scored audit records, the same frozen menus):** how well would a trivial deterministic rule do with those menus, without a model? Choosing nothing is right for the 14 complete records only, 25.5%. "Take the lead-in that ends in a colon as parent, and its subject as actor" gives 27.3% (R1) and 29.1% (R2);
"lead-in, else the leaf heading" gives 30.9% at both tiers (17 right, 38 misleading); "lead-in, else a preceding clause that ends in a modal" gives 29.1%. Production's stems were 34.5%, and the menu's ceiling is 87.3% (R1) and 92.7% (R2). So **the model adds a lot over simple rules on the same menus (about 54 to 60% against 25 to 31%)**, and the remaining gap to the ceiling, not the ability to attach at all, is what the registered bar of 63.6% was asking about.

**What the two experiments together say, and what they do not** (selection half only; nothing here reaches the evaluation half or the held-out set):
- *Supported:* for **attachment** (who must act, which clause governs), a model choosing among code-proposed verbatim spans reaches about 55 to 60%, against 35% for production's rules, with **zero invented parties by construction** (the generative resolver had 15 to 30% wherever context was supplied) and much faster calls (0.6 to 1.1 seconds against 6 to 14 seconds per call). For **classification**, non-requirements are rejected 81% of the time with all four configurations.
- *Not supported:* passing the registered G2 as written. The attachment bar (63.6%) is the generative resolver's best result, and the zero-modality gate cannot be met on this half by a correct answer on card R025 because of the checker's phrase table (a limit of the gate, reported, not changed).
- *Not tested:* the evaluation half (116 candidates), the held-out set, a widened list-marker rule in the generator (the known limit of step 13), and any change to the gates or the checker.

**Decisions this leaves to Tyler** (nothing here is started):
1. *Adopt the selection resolver for attachment anyway, as a measured improvement rather than a passed gate.* It is better than production on attachment by about 20 points with no invented text, but it did not meet the bar that was registered; adopting it would be a decision to accept a result that is below the registered threshold, with the evaluation half still unread.
2. *A new, separately registered step that fixes the two defects the gates exposed:* teach the checker's phrase table that a modal-free hint ("consider", "it is advisable") is a recommendation, widen the generator's list-marker rule (multi-level numbers), and re-register the attachment bar from the production baseline and the control above instead of from the generative result. That would be a new pre-registration, with the evaluation half still reserved as the verdict.
3. *Stop the resolver line here* and spend the effort on the second labeler and the held-out discovery confirmation (the discovery gain, +30 points of 8B recall on the dev pages, is the finding that has held up).

## Step 17: WP-45.7c Stage A, the two fixes and the production-anchored bar (`check_resolution.py`, `menu.py`, `score_resolver.py --registry v4`)

Plan: `docs/PHASE45_WP457C_PLAN.md` (merged in #229). Offline only: no model has been run in this step. The prompt is unchanged (hash `435a1561313c6d64`), as are the schema, the assembler, the gold and its halves, and every other gate.

1. **Checker phrase table** (`check_resolution.py`, file hash `55eba79800332624`): `is advisable` and `are advisable` are recommendation phrases wherever they occur, and `consider` is one **only at the start of the text** (after optional list markers), through a small `_StartOnly` wrapper that sits in the phrase list beside
   the ordinary patterns, so both the checker and the generator's `first_modal` use it without other changes. "Consider using ..." and "(1) Consider ..." count; "factors to consider", "considering" and "reconsider" do not; "Organizations should consider X" has the one modal `should`. A correct answer on card R025 (a modal-free hint, which made the zero-modality gate unreachable in step 14) now assembles to a
   clean `recommendation`, and the same answer with `obligation` is still a `modality_strengthened` error (tests).
2. **Menu generator** (`menu.py`, **new frozen hash `e6ff087bb3f0fab5`**, replacing `92be12cecb3bd841`): one change, a multi-level number ending in a dot or a parenthesis ("2.1.5.1.", "3)") is a list marker; as before the marker is looked for only at the start of the text after a colon, so "see 2.1.5.1." inside a sentence and "10:30 daily" are not markers. **S1 re-measured** (selection half, 55 records), no regression:

   | | Ceiling (revision 2, old hash) | **Ceiling now** (`menu_ceiling_7c_*.json`) | Mean / max menu | Misses now |
   |---|---|---|---|---|
   | R1 | 87.3% | **89.1%** | 4.9 / 8 | R009, R043, R089, R090, R109, R112 (R011 regained) |
   | R2 | 92.7% | **94.5%** | 5.3 / 10 | R043, R090, R112 (R011 regained) |

   The dry run on the 104 selection candidates is unchanged in kind: 0 untreatable, no empty menus, largest estimated prompt 3,734 tokens (R1) and 4,773 (R2).
3. **The v4 rule** (`score_resolver.py --choose --registry v4`): the same four configurations and the same gates as v3 except that the absolute 35-of-55 bar is replaced by two gates anchored to the production stems on the same records of the same half, as exact fractions:
   `attachment_gain_over_production` (right at least production's right rate plus 20 points: on the selection half 19/55 + 1/5, so 30 of 55 passes and 29 fails) and `misleading` (misleading plus failed resolutions at most production's misleading rate plus 5 points: 19/55 + 1/20, so 21 of 55 passes and 22 fails). The v2 and v3 rules score as before (tests).

Next (plan Stage B): the four selection-half runs with the unchanged prompt, the v4 rule, and the stop-or-continue decision; Stage C (the evaluation half, once) only for a passing choice.

## Step 18: WP-45.7c Stage B, the four selection-half runs under the v4 rule and the outcome of the protocol (`outputs/selection_v4_runs/`, `outputs/resolver_selection_v4_choice.json`)

The four configurations ran on the 104 selection candidates with the unchanged prompt (hash `435a1561313c6d64`), the table, generator (`menu.py` hash `e6ff087bb3f0fab5`) and v4 rule of step 17, from a pinned worktree at the merge commit of #230. Every call completed; 104 of 104 answers were shape-conformant in every run. The plan allows no prompt revision at this stage.

| Config | Attachment right (misleading / incomplete); gate: at least 54.5% = 30 of 55 | Misleading; gate at most 39.5% = 21 of 55 | Non-requirements rejected (60%) | Real wrongly rejected (5%) | Gated modality-error answers (0) | Invented | Gates failed |
|---|---|---|---|---|---|---|---|
| Production stem | 34.5% (19 / 17) | 34.5% | n/a | n/a | n/a | n/a | n/a |
| Selection R1 8B | **61.8%** (18 / 3) | 32.7% | 81.2% | 8.0% | 4 | 0 | real rejected, modality |
| Selection R1 14B | 56.4% (21 / 3) | 38.2% | 81.2% | 8.0% | 4 | 0 | real rejected, modality |
| Selection R2 8B | 50.9% (22 / 5) | 40.0% | 81.2% | 9.1% | 4 | 0 | attachment, misleading, real rejected, modality |
| Selection R2 14B | **61.8%** (19 / 2) | 34.5% | 81.2% | **3.4%** | 6 | 0 | **modality only** |

**Outcome.** No configuration passes every gate. The rule's fallback chooses R1 on the 8B (61.8%, tied with R2 on the 14B; ties go to the lower tier, then the smaller model) and reports it as failing the real-rejected and modality gates. **By the plan, the evaluation half is not scored and the held-out set is not run.** What changed since step 16: **three of the four configurations clear the new production-anchored attachment bar and the misleading margin**
(61.8, 56.4 and 61.8% against 54.5% needed), and **R2 on the 14B fails only the zero-modality gate**. Card R025 is in no run's modality list (the phrase-table fix did what it was meant to), and audit R011 and card R064 (the two records the generator's marker rule had been missing) now get their lead-in.

**The remaining modality errors (4 to 6 answers per run, seven records in all) are mostly model slips, plus one record the design cannot represent** (read from the ledgers; corrected after a Codex review of this step):
- *The status contradicts a modal the code has already read (audit R011 and its duplicate card R064, on R1 8B and R2 14B):* the model picks the right lead-in "All Service component communication support organizations **should**:" and still answers `obligation` for the imperative item under it.
- *A `recommendation` that cites no modal (audit R052 and its duplicate card R078, in all four runs; card R089 on one):* the sentence that holds the "should" ("Organizations should also be aware ...") **is on the menu** (R052's M5), but the model picks only the subject entry as actor and leaves the parent empty, so the answer cites no modal.
- *A permission for a bare noun-phrase item (audit R100, on both 14B runs):* no modal anywhere.
- *Not a model error: a mixed-modality record (card R081, in three runs).* The quote is "The community strings **shall** be modified from default settings - default 'public' and 'private' strings **shall not** be utilized." It holds an obligation and a prohibition; the model's `prohibition` is defensible, and the assembler reads only the first modal, so the checker reports `modality_strengthened`. A design with one status per candidate cannot represent both requirements; such candidates would need to be split or given more than one modality.

**A gap the gates do not see:** on R2 8B, audit R011 and card R064 choose the subject entry as actor, leave the parent empty and answer `obligation`, while the governing lead-in on the menu says `should`. The checker sees no modal in the cited evidence, so it raises nothing, and attachment scores the actor overlap as right. A wrong status class passes silently whenever the governing modal is not selected.

Also, as before, `modal_in_evidence` (a non-gated checker error: a lead-in picked as actor) appears in 3 answers on R1 8B and 7 on R2 8B and in none on the 14B runs.

**What this says, and what it does not** (selection half only; the evaluation half is still unread):
- *Supported:* with the two fixes, a model choosing among code-proposed spans beats production on attachment by 20 or more points on this half in three configurations (against 25 to 31% for trivial rules in step 16's control, which used the menus from before the marker fix and was not rerun), with zero invented parties by construction and a misleading rate no higher than production's plus the registered margin.
- *Not met:* the zero-modality gate, because in 4 to 6 answers per run the model's **status** disagrees with the modal the code reads from the same text, or cites none (one of the seven records is a mixed-modality sentence, which no single status fits).
- *Not tested:* the evaluation half, the held-out set, and any design in which the code, not the model, sets the status class whenever it reads a modal.

**Decision left to Tyler:** the evidence points at one more design change, not at another threshold change, but it is a larger one than a table lookup. Where the quote or the chosen parent contains a modal, the status class could be set by code (`shall` an obligation, `should` a recommendation, `may` a permission, `shall not` a prohibition), and the model would decide only *whether it is a requirement* plus actor and parent. That would remove the "status contradicts the modal it picked" errors by construction, but two cases need their own design before it is registered:
(a) **a governing modal the model did not select** (the R2 8B R011 case above): code reading only the quote or the chosen parent never sees it, so the step would also have to infer or require the governing parent, for example by reading the nearest lead-in on the menu; and (b) **mixed-modality quotes** (card R081), which need splitting or more than one modality per candidate. It would be a new, separately registered step with the evaluation half still the verdict, and it is not started.

## Step 19: WP-45.7d Stage A, the kind-selection resolver (`kind_selection.py`, `run_selection.py --design kind`, `score_resolver.py --registry v5`)

Plan: `docs/PHASE45_WP457D_PLAN.md`. Offline only: **no model has been run in this step.** The menu generator (`menu.py`, hash `e6ff087bb3f0fab5`), the checker, the gold and its halves and every gate threshold are unchanged.

- **What the model is asked.** `{kind, actor, parent}`: the kind is `requirement`, `scope_or_context`, `not_a_requirement` or `unresolved`; actor and parent are menu ids or `none`, as before. The prompt keeps the fragment, actor-versus-parent and `preceding` rules of the revised prompt of step 15 and drops everything about strengths ("You do not say how strong a requirement is: that is read from its words"). Seven invented worked examples, converted
  from the earlier ones; a test checks that each assembles to exactly the strength the old example had and passes the unchanged checker. Prompt hash `6200fa25a374eb35` (fixed part about 2,574 estimated tokens); dry run on the 104 selection candidates: 0 untreatable, no empty menus, largest estimated prompt 3,674 tokens (R1) and 4,713 (R2).
- **How code sets the status.** For any kind but `requirement` the status is the kind. For `requirement` it is the class of the governing modal, from the first source that has one: the quote; the chosen parent (a chosen parent without a modal **ends the search**: nothing is inferred over the model's choice); when no parent was chosen, the menu's colon lead-in; then, if the quote starts with a lowercase letter, a menu `preceding` clause
  with a modal. The chosen actor is never read. With no modal anywhere: `obligation`, class `none`. The ledger record keeps `modal_source` and `all_modals`; a quote with several modals uses the first for its status (card R081's "shall be modified ... shall not be utilized" is `obligation`, with both modals listed); splitting such a quote into one requirement per modal is a later change. **The first modal is not always the governing one** ("Whether users may obtain access must be recorded" would read as a permission), and no clause-level rule separates them reliably; measured before the plan was registered, 74 of 1,991 production quotes (3.7%) and 4 of the 104 selection-half quotes hold more than one modal. The run summary lists these candidates for a spot check.
- **What the tests pin down:** the order of the sources, the actor never lending its modal (and the resulting `modal_in_evidence` still being raised as the non-gated malformed choice), the lowercase condition (a mutation that drops it, and one that lets a chosen parent without a modal fall through, are both caught), the no-modal default, the modal-free hint, and an exhaustive property test: over seven quotes, four kinds and every actor-and-parent choice on a six-entry menu, **no assembled answer ever raises a gated modality code or an invented-token code**, so those two gates are structural, as the plan says.
- **The runner and the scorer.** `run_selection.py --design kind` runs the same candidates, tiers and ledger as before and also records `modal_source` and `all_modals`; its run summary reports how often each source supplied the modal, the multi-modal candidates, and the **inferred-source candidates** (a modal read from a menu lead-in or a preceding clause), the list the plan promises for the owner's spot check.
  `score_resolver.py --choose --registry v5` is the v4 rule (production-anchored attachment bar, misleading margin, every other gate) for the same four configurations.

Next (plan Stage B): the four selection-half runs, the v5 rule, one registered prompt revision if none passes, and the stop-or-continue decision; Stage C (the evaluation half, once) only for a passing choice.

The v4 and v5 rules are the same arithmetic over different designs, so `score_resolver.py` records which prompt hash wrote each ledger (`prompt_hashes` in `score_run`'s result) and `--choose --registry v4` and `--registry v5` **refuse any ledger not written by that design's prompt** (v4: the status design's `435a1561313c6d64`; v5: the kind design's `6200fa25a374eb35`), so `--registry v5` can never quietly score the old status-design runs as a WP-45.7d result (found in review; tests). The v2 and v3 rules are not tied to a prompt: their first runs predate the check.

## Step 20: WP-45.7d Stage B, the four selection-half runs under the v5 rule, and the frozen choice (`outputs/selection_v5_runs/`, `outputs/resolver_selection_v5_choice.json`)

The four configurations ran on the 104 selection candidates with the kind design merged in #233 (`kind_selection.py` prompt hash `6200fa25a374eb35`, menu generator `e6ff087bb3f0fab5`, checker file hash `55eba79800332624`), from a pinned worktree at the merge commit. Every call completed, 104 of 104 shape-conformant, about one second per call. The rule (`--choose --registry v5`, which verified that every ledger was written by the kind prompt) was applied over these four runs.

| Config | Attachment right (misleading / incomplete); gate at least 30 of 55 | Misleading; gate at most 21 of 55 | Non-requirements rejected (60%, 16 of them) | Real wrongly rejected (5%, 88 of them) | Gated modality errors | Invented | Result |
|---|---|---|---|---|---|---|---|
| Production stem | 34.5% (19 / 17) | 34.5% | n/a | n/a | n/a | n/a | n/a |
| Selection R1 8B | 60.0% (20 / 2) | 36.4% | **56.2%** (9) | 2.3% | 0 | 0 | fails non-requirement rejection |
| Selection R1 14B | 54.5% (21 / 4) | 38.2% | 87.5% | **6.8%** (6) | 0 | 0 | fails real rejected |
| Selection R2 8B | 50.9% (27 / 0) | 49.1% | 50.0% (8) | 1.1% | 0 | 0 | fails attachment, misleading, non-requirement rejection |
| **Selection R2 14B** | **63.6%** (19 / 1) | 34.5% | 81.2% (13) | 3.4% (3) | **0** | **0** | **passes every gate** |

**Outcome: one configuration, R2 on the 14B, passes every gate on the selection half, and it is the choice, frozen here** (R2 evidence tier, `qwen2.5:14b`, kind prompt `6200fa25a374eb35`, menu `e6ff087bb3f0fab5`, the v5 gates as registered). The modality gate is zero in all four runs and the invented gate is zero, as they are structural now; the non-gated `modal_in_evidence` appears in one answer on R1 8B and two on R2 8B, none on the 14B.
**By the plan, Stage C scores this configuration once on the evaluation half (116 candidates, never read); that result is the WP-45.7d verdict.**

How to read this pass, plainly:
- **It is a selection-half pass, necessary and not sufficient.** The margins are thin: attachment 35 against 30 needed, misleading 19 against at most 21, real wrongly rejected 3 against at most 4 of 88, non-requirements rejected 13 of 16 against at least 10. Only one of four configurations passes, and the others fail on different single gates; the 8B runs reject far fewer non-requirements (9 and 8 of 16) with this prompt than the status design did (13 of 16), so the kind question is not equally easy for every model. With 55 attachment-scored records, a pass this narrow could move with a different draw, which is exactly why the unread half decides.
- **What changed against the status design (step 18):** the gated modality errors went from 4 to 6 per run to 0 by construction, and R2 on the 14B went from 61.8% to 63.6% attachment with the same real-rejected rate (3.4%).
- **Spot check the plan promised, for the chosen run:** strength read from the quote in 36 records, from the chosen parent in 23, from an inferred source in 2, from no modal at all (default `obligation`, class `none`) in 43. The two inferred records are audit R052 and card R078 ("ensure that policies are updated accordingly as needed."), where the model picked the subject and no parent, and the code read `should` from the preceding clause "Organizations should also be aware ...": the strength is `recommendation`, which matches the sentence. The four multi-modal quotes (audit R017, card R049, R065, R081) repeat the same class in the first three (should/should, shall/shall, may/may) and mix classes only in card R081 ("shall be modified ... shall not be utilized"), which takes the first modal, `obligation`, as the plan registered.
- **Not claimed:** that the 43 modal-free records are obligations (they are kept, with class `none`, by the over-extraction-friendly default); anything about the evaluation half or the held-out set.

## Step 21: WP-45.7d Stage C, how the one-shot verdict is computed (`score_resolver.py --verdict`), written before the evaluation half is read

The scorer exists, is tested and is merged **before** any evaluation-half number is seen, so that how the verdict is computed cannot be shaped by it. `score_resolver.py --verdict NAME=DIR --registry v5` scores one frozen run on the **evaluation half only** (it does not read the selection half) with the registry's gates, as exact fractions against *that half's own* production baseline:
the attachment-right rate at least production's plus 20 points, the misleading rate (failed resolutions included) at most production's plus 5 points, and every other gate unchanged (valid at least 95%, real wrongly rejected at most 5%, non-requirements rejected at least 60%, scope-or-unresolved at most 10%, incomplete at most baseline plus 5 points, invented at most 2%, gated modality errors zero). It refuses, with a clear error:
- any registry that is not tied to a prompt (v2, v3), and **any registry whose Stage B did not pass every gate**: v4's committed choice report says no configuration passed, so its evaluation half is reserved and v4 has no verdict (a test pins this against the committed files);
- any name but the **frozen choice** read from the committed choice report (v5: `r2_14b`), and any ledger that was not written by that configuration: the prompt must be the registry's own (v5: the kind prompt `6200fa25a374eb35`), and the ledger's tier, model and **model file digest** must each be exactly one value and equal to those of the Stage B run it was chosen from (R2, `qwen2.5:14b`, the digest in `outputs/selection_v5_runs/v5_sel_r2_14b/run_summary.json`);
- a ledger whose **runner parameters** (temperature, context size, answer limit) differ from the frozen run's (0.1, 8192, 200), or that mixes values;
- any change to the **frozen code and gold**: the committed manifest `outputs/frozen_wp457d_code.json` holds the sha256 of the menu generator, the checker, the assembler (`kind_selection.py`, `selection.py`), `bundle.py`, `resolver.py`, `ollama_run.py`, the runners and `resolver_gold.json` as they were at the commit the Stage B runs used (`d97de23`), and the verdict refuses to score if any file in the working tree differs (a test fails the same way, so editing a frozen file forces a deliberate re-freeze);
- a ledger with no evaluation-half records. The run itself needs `run_selection.py --half evaluation --final`, from a worktree whose frozen files match the manifest.

*Not done:* the verdict does not replay the menu, bundle and assembly for each evaluation candidate to compare them with the ledger; it relies on the pinned code, the prompt hash and the recorded run parameters, and on the run being made from the pinned worktree.

The verdict is **pass** only if every gate passes. A pass is the WP-45.7d verdict: on candidates the design never saw (the same 13 documents; the halves were split by candidate, not by document), the frozen configuration beats production on attachment by at least 20 points with no invented text and no gated modality error. A fail is reported as a fail, with the gates that failed; there is no second try on this half. Neither outcome says anything about unseen documents or the held-out set.
