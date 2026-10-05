# WP-45.1(e): a source-based recall sample

Measurement only. No production code, index or configuration changed; the live Qdrant collection was read once (ids only)
and the scratch runs from WP-45.6 were read. The plan, reviewed in #209, is `docs/PHASE45_WP451E_PLAN.md`.

## Question

Every earlier number was measured against what was extracted, so an obligation that was never extracted was invisible.
This sample starts from the PDF: of the obligations a careful reader finds on a sample of pages, how many reach the index,
and at which step do the rest drop out?

## Result in one paragraph

On 12 sampled pages of three documents, the production pipeline (the July 8B extraction, as indexed) has **about 60% of the
obligations** in the source (45 of 74; page-level interval 44% to 77%). Nothing is lost at parsing and chunking (74 of 74
are in a chunk), almost nothing at Step D (1 piece) and nothing at indexing. The loss is at **extraction**: 26 of 74 (35%;
interval 20% to 49%) were never extracted, and 3 more were extracted only partly. By document: DODI 8410.03 17 of 20,
afman17-2101 22 of 38, NIST SP 800-125 6 of 16. A fresh 8B run gives the same total (the run-to-run noise is one piece
each way); the 14B from WP-45.6 gives 27%.

## What was done

- **Sample (frozen before labeling, `outputs/pages_frozen.json`):** a seeded draw of 4 pages per document of the three WP-45.6
  documents, cut into 254 sentence-sized pieces by a deterministic PyMuPDF segmenter (`segment.py`, hash recorded). The text
  is PyMuPDF's, not Docling's, and no pipeline output appears in the pack.
- **Labels:** Claude and Codex labeled every piece independently and blind (`obligation`, `lead_in`, `scope`,
  `not_obligation`, plus whether the piece was cut correctly). They agree on 232 of 254 (91%). Claude found 80 obligations
  and Codex 64.
- **Adjudication:** 22 pieces differ. Two differ only between non-obligation labels (scope against not an obligation) and
  need no ruling. Tyler ruled on the other 20 (`labels/adjudication.txt`): 18 were one question, whether third-person duty
  statements with no shall or must ("Provides direct provisioning oversight...", AFMAN 2.3.x) are obligations when their
  "will:" lead-in is not on the page. His rule: a statement of what someone does or provides is a "do it" if it is attached
  to a party; role descriptions that nobody can act on or audit (2.3.15.1 to 3) are not. He also ruled AFMAN 1.1.2 (DISA
  must do things on the DODIN) an obligation and NIST p26 "Guest OS images ... would need to be destroyed..." not one. One
  piece (AFMAN 1.1.4) he did not rule on in so many words; Claude applied his rule and said so. The 10 seeded spot-checks of
  agreements have **not yet been reviewed**; any change would be a rerun of `score.py report`.
- **Adjudicated result:** 78 obligations, of which 4 sit in pieces someone flagged as badly cut; those 4 are left out of
  the main numbers (74) and put back in a sensitivity line (78).
- **Trace (`loss_trace.py`):** each obligation is followed through Step C records, Step D survivors and the live index. A
  piece counts as covered when records in its chunk(s) reproduce at least 90% of its tokens (union over records; runs of at
  least three tokens), partly covered from 50% to 90%, not covered below 50%. Thresholds were fixed in the plan.
- **Uncertainty:** a page-level bootstrap (the 12 pages are resampled with their pieces together), because pieces on one
  page are not independent.

## Results

| Stage (production, July 8B, 74 obligations) | Covered | Share | Interval |
|---|---|---|---|
| In a chunk | 74 | 100% | 100 to 100 |
| Extracted (Step C) | 45 | 60.8% | 44 to 77 |
| Survives Step D | 44 | 59.5% | 43 to 76 |
| In the live index | 44 | 59.5% | 43 to 76 |

Counting partly covered pieces as found: 64.9% extracted. First loss: not extracted 26 (35.1%, interval 20 to 49), partly
extracted 3 (4.1%), rejected at Step D 1 (1.4%; AFMAN 2.3.15, `unrepairable_fragment_quote`), never chunked 0, not indexed 0.

How much the labeling choices matter (production, extracted stage):

| View | Obligations | Extracted share | Interval |
|---|---|---|---|
| Adjudicated, segmentation OK (main) | 74 | 60.8% | 44 to 77 |
| Adjudicated, including the 4 flagged pieces | 78 | 60.3% | 42 to 75 |
| Only where both labelers say obligation (segmentation OK) | 58 | 67.2% | 45 to 86 |
| Where either labeler says obligation (segmentation OK) | 78 | 57.7% | 40 to 74 |

Models, same 74 pieces, steps up to Step D (the runs from WP-45.6 were never indexed):

| Run | Extracted | Survives Step D |
|---|---|---|
| Production (July 8B) | 60.8% | 59.5% |
| Fresh 8B | 60.8% | 59.5% |
| 14B | 27.0% | 27.0% |

The fresh 8B and the production run cover the same count but not the same pieces (1 piece each way), so a page-level
interval for that pair is degenerate and the swap count is the noise floor. The 14B covers 1 piece the production run
does not, and the production run covers 26 the 14B does not (difference -33.8 points, interval -47 to -14). This is the
recall against the source that WP-45.6 could not give.

**Routing, from the plan's pre-set rule.** The largest first-loss category is "not extracted"; its interval lower bound
(20%) is above the next category's point estimate (4.1%), so the rule names **extraction** as the place to work next
(WP-45.2 C4 and prompt work, both of which need Tyler's approval), not parsing, Step D or indexing.

## An exploratory look, not pre-registered

Of the 22 obligation pieces that contain one of the profile's obligation verbs (shall, must, ensure, ...), 18 reached the
index (82%); of the 52 that contain none, 26 did (50%). So the modal wording matters but does not explain everything: half of
the verb-free obligations were found. This was looked at after the main result, on small numbers, and is a pointer.

## What this does not say

- **Twelve pages, three documents.** The intervals are wide and three documents are few. Three of the twelve pages were
  front matter or a references list (DODI 3 and 6, NIST 3) and contain no obligations, and four pages (AFMAN 9 and 10,
  NIST 25, DODI 12) hold 61 of the 78 obligations, so the result leans on a few pages. The page-level bootstrap accounts
  for that in the intervals, but not in what these pages happen to be.
- **The obligation set rests on a definition.** It counts "should" recommendations, and, by Tyler's ruling, duty statements
  without shall or must. That ruling decided 18 of the 20 disagreements and about a fifth of the sample's obligations; the
  "both agree" and "either" views above bound it (57.7% to 67.2%).
- **Covered means the quote reproduces the obligation text, not that it is a good requirement.** A covered piece can still
  be a fragment that needs a lead-in (the WP-45.1(b) problem).
- **Not measured:** whether an indexed requirement can be found by a search query (ranking), and requirements that exist in
  the source but were not on the sampled pages.
- **Two labelers share one rubric and one adjudicator.** The spot-checks of agreements, the only guard against a shared blind
  spot, are not yet done.
- **PyMuPDF text is not Docling text.** The two agree where it matters here (every obligation was found in a chunk), but a
  reading-order difference would have appeared as "never chunked", and none did.

## Two things worth knowing about how this was built

- A first run of the trace reported **zero** records indexed. That was a bug in my trace, not a finding: Step C ids
  (`R-<chunk>-<n>`) and Step D ids (`REQ-<hash>`) differ, and I had joined them by id. Step D survivors are now matched by
  chunk and quote text, a sanity check aborts the report if no survivor is in the live index, and a regression test covers
  the id difference. No result was reported from the bad run.
- After seeing the two label files I changed the code so that only disagreements about obligation status need a ruling
  (workload only; no number depends on it).

## Files

- `segment.py`, `draw.py`, `pack.py`, `loss_trace.py`, `score.py`; tests in `tests/unit/test_wp45_source_sample.py` and
  `tests/unit/test_wp45_source_trace.py`.
- `outputs/pages_frozen.json` (the draw and every piece), `outputs/pack_manifest.json`, `audit_pack/` (pack, rubric, checker).
- `labels/labels_claude_a.jsonl`, `labels/labels_codex_a.jsonl`, `labels/adjudication.txt`.
- `outputs/results.json` (all numbers above) and `outputs/traces.jsonl` (one line per obligation per run).

Reproduce (needs the pinned inputs, the Qdrant index and the WP-45.6 scratch runs):

```
python3 eval/spike_results/wp_45_1e/draw.py --check
python3 eval/spike_results/wp_45_1e/score.py report --labels-dir eval/spike_results/wp_45_1e/labels \
    --answers eval/spike_results/wp_45_1e/labels/adjudication.txt --out-dir eval/spike_results/wp_45_1e/outputs
```
