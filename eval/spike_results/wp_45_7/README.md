# WP-45.7: held-out page draw (step 1 of the discovery/resolution experiment)

Measurement only; no LLM, no Qdrant, no production change. The plan, merged in #211, is `docs/PHASE45_WP457_PLAN.md`
(section 4.1 and 4.2). This step fixes the held-out page set and freezes it before anything is labeled or any prompt is
finalized. The set is not opened for tuning.

## Result

16 pages drawn from the ten pinned documents that are not the three development documents, 23 pages to label after closure,
**428 pieces** to label (`outputs/heldout_frozen.json`, pieces sha256 `796a398a97be7602...`). `--check` recomputes the whole
draw from the PDFs and the pinned chunk files (WP-44 manifest hashes) and fails on any difference.

| Document | Drawn pages (reason) | Pages added by closure | Pieces |
|---|---|---|---|
| CJCSI 6510.02G | 27 (one per document) | none | 13 |
| DODI 5200.01 | 10 (one per document) | none | 18 |
| DODI 5200.44 | 9 (one per document), 10 (extra) | none | 30 |
| DODI 5200.48 | 15 (one per document) | 14 | 34 |
| DODI 8551.01 | 6 (one per document) | none | 17 |
| afi10-2402 | 11 (one per document), 25 (extra), 42 and 48 (table) | 10, 26 | 130 |
| afi13-550 | 8 (one per document) | none | 17 |
| afi17-203 | 9 (one per document), 20 (table) | 10, 19 | 63 |
| afpd_17-1 | 8 (one per document), 11 (extra) | 7 | 62 |
| dafman17-1305 | 27 (one per document) | 26 | 44 |

## The rule (fixed in `draw_heldout.py` before the draw)

One page from every document (the first of a seeded shuffle of its pages with at least 60 words), three table pages (pages
touched by a chunk that holds a markdown table), three more from the seeded shuffle of every other eligible page. Seed
`wp45.7-heldout`. Discovery will run on every chunk whose page range touches a drawn page, and **the label set is every drawn
page plus every page any selected chunk touches**, so a record from a selected chunk never lies in unlabeled text (plan 4.2).

## Things worth knowing

- **A first version of the closure left a drawn page unlabeled.** It took only chunk-touched pages; CJCSI 6510.02G page 27 is
  touched by no chunk (the pipeline skipped it), so it would have had no pieces. Found at freeze time, before any labeling
  and before the file was committed; the rule now includes the drawn pages and the draw was regenerated, never edited by
  hand. A drawn page with no chunk is kept on purpose: it makes a loss before extraction visible, as in WP-45.1(e).
- **No control-catalog document.** The plan asked for a control-catalog stratum. None of the ten pinned non-development
  documents is one (the catalog-style document in the pinned set, NIST SP 800-125, is a development document), and
  `CNSSI_No1253.pdf` is in `raw_pdfs` but has not been through Steps A to D. The stratification is therefore formal policy
  (DODI), instructions and manuals (AFI, DAFMAN), a joint instruction and an Air Force policy directive, and tables (three table
  pages from AFI 10-2402 and AFI 17-203). Adding a catalog needs a pipeline run on CNSSI 1253 and is a decision for Tyler.
- **Labeling load is above the estimate.** 428 pieces per labeler, not about 350, because closure added seven pages and
  AFI 10-2402 alone holds 130 pieces. Nothing was dropped to make the number smaller.
- Some drawn pages may turn out to be front matter or references with no obligations; the 45.1(e) sample had the same
  shape (three of twelve pages), and that was not a reason to redraw.
- Pages are 1-based. Piece ids are `<code>-p<page>-<n>` (codes in `draw_heldout.py`). The text is PyMuPDF's, not Docling's.

## Files

- `draw_heldout.py`, `outputs/heldout_frozen.json`; tests in `tests/unit/test_wp457_heldout_draw.py`.
- Reuses `eval/spike_results/wp_45_1e/segment.py` unchanged and `eval/spike_results/wp_45_audit/_inputs.py` for the pinned
  chunk check.

Reproduce (needs `raw_pdfs/`, the pinned processed inputs and PyMuPDF, which is not a project dependency):

```
python3 eval/spike_results/wp_45_7/draw_heldout.py --check
```
