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
