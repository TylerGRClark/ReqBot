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
  records with a not-found reference from 116 to 80 (87 after named sections and references into other documents were added: they now resolve or are reported).
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

R2 added 49 referenced-section excerpts and left 87 records with an explicit reference ("paragraph 4.2", "Sections 3 and 5") it could not find in the document. At this fixed prompt size
the window is not a binding constraint on these documents; table-heavy chunks and a larger fixed prompt (the seven worked examples)
are what would push a bundle over, and the cuts and `untreatable` flag are tested for that case.
