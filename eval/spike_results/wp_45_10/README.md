# WP-45.10 — Docling configuration audit: results

Plan: [PHASE45_WP4510_PLAN.md](../../../docs/PHASE45_WP4510_PLAN.md) (#245). Registered rules: [PHASE45_WP4510_ADDENDUM.md](../../../docs/PHASE45_WP4510_ADDENDUM.md) (#246, commit `25941ca`, on the remote before any measure was read; GitHub rejected pushes for about 15 minutes, so nothing was analysed until it landed). Offline, no LLM, scratch only: nothing in `pipeline/`, no Step C cache, no corpus file and no Qdrant collection was touched. Conversions are cached under `~/wp45_10_cache/` (outside the repository); the results are in `outputs/`.

**Setup.** The 13 pinned documents (source-PDF SHA-256 checked against `wp_44/after_replay_summary.json`). Docling 2.94.0 (the pin; the unpinned transitive packages resolved here to `docling-core` 2.99.0, `docling-parse` 5.7.0, `docling-ibm-models` 3.13.0) against 2.135.0 and 2.122.0 in separate virtual environments. These share the system site-packages, so pip kept the already-satisfying `docling-core` 2.99.0 at first; after review I upgraded it to the newest release (2.100.0) in both and **re-ran 2.122.0 completely (13 documents, chunking, every comparison, the repository tests) with identical results, re-ran 2.135.0 on two documents with the same regression, and re-ran the bisection with the same boundary**. The 2.122.0 numbers below are from the `docling-core` 2.100.0 run; the cache tag `d2.122.0-core2.100.0` holds it and `d2.122.0` the earlier one. Every change is one option at a time on a copy of production's own converter. Chunking runs through the unmodified production function `pipeline.chunk_text.run_structure_aware`; an explicit 256-token chunker was verified record-identical to Docling's default `HybridChunker()` on all 13 documents, and the 256-token re-chunk reproduces the production run's chunk count and markdown-table chunks (afi17-203: 55 chunks, 4 table chunks, both).

## Headline results

| | Finding | Status |
|---|---|---|
| H1 | The default 256-token chunk limit splits lead-ins from their quotes. Labeled lead-ins in the same chunk as their quote: **73.8% at 256, 92.4% at 512, 98.6% at 1,024 tokens** (107, 134, 143 of 145). Chunks starting mid-list: 31, 11, 0. | The registered rule is **not met** (text-preservation gate: 3.1 to 3.3% of word groups lost, 1.0 to 3.9% extra, against at most 0.5%). Cause found: table serialization (below). |
| New | **Today, 9 of the 56 tables reach Step C only as the chunker's flat "Header = Value" text**, not the markdown grid WP-42 built; at 1,024 tokens it would be 37 of 56. All 56 are proper tables with a cell grid in the conversion. | A latent defect in `_chunk_raw_text`, independent of any Docling setting. |
| Upgrade | **2.135.0 is rejected: it breaks structure.** **2.122.0 is a candidate**: every registered rule passes except one by 2 items. | *Not recommended as is* by the registered rule (c); see below. |
| H2 | OCR contributes only figure and diagram text and the cover seal, in 3 documents (0.12% of word groups); `force_backend_text` changes nothing; full-page OCR makes 3.1% of the text worse. | Descriptive; no pilot. |
| H3 | `do_cell_matching=False` and `FAST` change most tables' cell grids (44 and 43 of 56) and repair none of the known defects. | No pilot (rule not met). |
| H4 | All 492 headings come back as level 1 in 2.94.0 (504 in 2.122.0, 209 in 2.135.0). The pipeline's numbering-based depth is the only hierarchy signal. | Descriptive. |

## H1: chunk token limit (default tokenizer held constant)

| Limit | Chunks | Median chars | Co-located lead-ins | Mid-list chunk starts | Text lost vs 256 | Extra | Over Step C window |
|---|---|---|---|---|---|---|---|
| 256 (default) | 839 | 856 | **107 / 145** | 31 | 0 | 0 | 0 |
| 512 | 514 | 1,219 | **134 / 145** | 11 | 3.34% | 1.02% | 0 |
| 1,024 | 390 | 1,258 | **143 / 145** | 0 | 3.18% | 1.91% | 0 |
| 2,048 | 362 | 1,117 | 143 / 145 | 0 | 3.11% | 2.39% | 0 |
| 4,096 | 356 | 1,107 | 143 / 145 | 0 | 3.11% | 3.88% | 0 |

"Co-located" means the labeled lead-in text sits wholly inside the `text` of the chunk that contains the quote (145 labeled items: the audit gold and the fresh gold). The metric checks out against the labelers' own locations at 256: all 31 lead-ins labeled `previous_chunk` are apart, all 59 labeled `section_heading` are together, 48 of 55 `same_chunk` are together. At 1,024, 30 of the 31 previous-chunk lead-ins move into the quote's chunk. Text lost and extra are word 6-gram multiset differences over the emitted `raw_text` of the final chunk records (101,351 baseline 6-grams); the rendered Step C prompt, including the chunk-dependent source-reference hints, stays inside the 8,192-token window with a 1,000-token answer allowance for every chunk at every limit.

**The registered gate fails, and why.** At every limit above 256 the preservation gate (at most 0.5% lost, every difference listed) fails. Reading the differences shows the cause is not lost text but how tables are written. Docling returns generic `DocItem` objects (not `TableItem` or text items) in the metadata of a chunk made by merging several elements; `_chunk_raw_text` decides what to do by item type, finds nothing it recognises, and falls back to the chunker's own flat text, which renders a table as repeated "Header = Value" pairs instead of the markdown grid (WP-42's fix). A larger limit merges more chunks, so more tables take that path: tables reaching Step C only in flat form go from **9 of 56 at 256 to 37 of 56 at 1,024** (the markdown grid from 47 to 15). Verified on a live conversion as well as from the cached document, so it is not a loading artifact. The 9 flat tables today are real tables with cell grids in the conversion (DODI 5200.01 1, DODI 5200.44 1, DODI 5200.48 3, DODI 8551.01 1, afi10-2402 2, afman17-2101 1), and they match the "residual" garbled-table chunks WP-42 could not repair and attributed to Docling failing to produce a grid: the cause is the chunk-level type loss, not the conversion.

**Exploratory variant (not registered).** Resolving each chunk item back to its real type by `self_ref` before `raw_text` is built (scratch only, `rechunk.py --resolve-items`) does not give a clean answer: it changes how every table renders, so 32 of the 145 labeled quotes (those taken from table text in the flat form) no longer appear in `raw_text`, and the rates are not comparable with the registered run (co-located 111 of 145 at 1,024, but 111 of 113 findable quotes against 92 of 113 at 256). It shows the fix is a real design question (the quotes Step C extracts today came from the flat form), not a one-line change.

## Upgrade comparison (registered rules, section 1 of the addendum)

Release 2.135.0 and release 2.122.0 each converted and chunked the 13 documents with their own defaults.

| | 2.94.0 | 2.122.0 | 2.135.0 |
|---|---|---|---|
| Conversions succeeded | 13 | 13 | 13 |
| `code` items (policy prose has none) | 0 | 0 | **62**, up to 47% of a document's characters |
| List items | 1,604 | 1,604 | **442** (afi10-2402 194 to 0; DODI 5200.48 214 to 2) |
| Tables | 56 | 59 (same per document except 3 documents with one extra table each) | 39 (afi10-2402 12 to 4) |
| Headings found | 492 | 504 | 209 |
| Word 6-grams differing (document level, punctuation ignored) | | 0.72% lost, 0.39% extra | 8.6% lost, 8.9% extra |
| Emitted-chunk 6-grams lost / extra vs 2.94.0 | | 0.70% / 0.57% | 9.03% / 206% |
| Chunks; largest chunk (chars) | 839; 10,689 | 845; 10,689 | 770; 36,734 |
| Labeled lead-ins co-located | 107 / 145 | 105 / 145 | 87 / 145 (13 quotes not found) |
| Known caption-in-header table defect (afi17-203 Table 3.2) | present | present | present |
| Repository unit tests in that environment | | 1,359 passed (core 2.99.0 and 2.100.0) | not run |

**2.135.0.** Whole policy passages arrive as one `code` item (for example the "3. POLICY. It is DoD policy that: a. ..." section of DODI 5200.01 arrives as one 2,390-character block), list structure collapses, and fewer headings are found. None of OCR off, embedded-text mode or a stricter layout score threshold changes it on that document. **A bisection** (`bisect_release.py`, one document, one release per virtual environment, each upgraded to the newest `docling-core`) puts the change between 2.122.0 (clean) and **2.123.0** (code items and collapsed lists), assuming the change is monotonic in release order and holds on that one document.

**2.122.0 against the registered rules.** (a) Text items: 76 of 5,029 (1.5%) from 2.94.0 are not found as a word sequence in 2.122.0 once spacing and punctuation are ignored. I read all of them (`outputs/upgrade_2122_items_not_found.json`): glossary and acronym entries (sections the pipeline skips), figure and flowchart labels, cover-seal OCR noise, "TERM DEFINITION" table headers, and a handful of body paragraphs. Of those, three are better in 2.122.0 (2.94.0 had OCR errors such as "specifîc" and "Releasabilitv", and a CUI paragraph with the middle of a sentence missing that 2.122.0 reads whole) and **one is worse** (CJCSI 6510.02G: "(j) In the submission of the request, the petitioning Service will as s s s s s s rs es s rae in Enclosure A", garbled OCR). Body-paragraph differences are about 0.1% of items: pass. (b) Table defects not worse: the caption-in-header defect is unchanged (1 table), no-grid regions 0 in both: pass (not better). Of the 51 tables in documents with the same table count, 24 differ from 2.94.0 only in spacing and punctuation and **12 differ in cell text with the same shape; I did not read those individually**. (c) **Co-location not lower: 105 against 107 of 145. Fails by 2 items**, a 1.4-point shortfall, inside the jitter that changed chunk boundaries cause (845 against 839 chunks); I have not explained the two. (d) Emitted-chunk 6-gram loss 0.70% (at most 1%): pass; every difference is stored. (e) 13 of 13 conversions succeeded: pass. (f) 1,359 unit tests passed on 2.122.0: pass.

**Registered outcome: *not recommended as is*, because rule (c) is missed by 2 items.** Every other rule passes, and the text itself improves in places (OCR errors fixed in two documents' cover and body text). Whether a 2-item shortfall on 145 labeled items should block a pilot is the owner's call; the rule was written before any number was seen, so I report it as written. What the comparison cannot say is whether requirements extraction improves: only a Step C pilot on replayed ingestion can.

## H2: OCR and native text (descriptive)

| Variant | Word 6-grams lost | Extra | Text items lost | What it is |
|---|---|---|---|---|
| `do_ocr=False` | 130 of 111,014 (0.12%) | 15 | 71, in 3 documents | Figure and diagram text: flowchart labels ("4a" to "4g", "Approval for key extension"), diagram words ("Application", "Bare metal"), the cover seal ("UNITED STATES OF AMERICA"). No table, list or heading difference. |
| `force_backend_text=True` | 0 | 0 | 0 | Identical to the default on these born-digital documents. |
| `force_full_page_ocr=True` | 3,422 (3.1%) | 2,705 | 1,055 | Replaces good embedded text with OCR text; worse. |

OCR in the default run is not inert: it recovers the text inside figures in 3 of 13 documents. Whether any of that is requirement text was not scored (no labeled outcome covers it).

## H3: table structure

`do_cell_matching=False` changes the cell grid of **44 of 56** tables and `TableFormerMode.FAST` **43 of 56**; the text outside tables is identical, the afi17-203 header-caption defect is unchanged (1 table in every variant), and no table has a missing grid in any conversion. No labeled outcome says whether a changed grid is better or worse, so neither variant meets the registered "worth a pilot" rule (a known defect repaired, no text lost).

## H4: heading levels

Docling's structural level is **1 for every heading** (492 of 492 in 2.94.0, 504 in 2.122.0, 209 in 2.135.0), so `_estimate_heading_depth`'s numbering-based depth, the pipeline's only hierarchy signal, is not redundant. 225 of 492 headings (all numbered, depth above 1) differ from Docling's level, and that is the whole difference. Whether to use a level from a newer release is a separate plan; none of the tested releases produces a non-trivial level on these documents.

## Deviations from the registered rules and measures, disclosed

Each of these was made after reading an output, to repair a measure that did not behave as defined; none changes a registered threshold.
1. **Caption detector.** The first phrase (the table's title) found 0 tables with the known caption-in-header defect in any release, which did not reproduce a documented defect. The 2.94.0 table showed the merged text is the caption sentence ("This table presents the relationship between the ongoing support activities …") in the dataframe column headers; the detector now uses that and reproduces the defect (1 table).
2. **No-grid detector** now counts a table-labeled item with no cell grid, not only non-`TableItem` objects; it finds 0 in every conversion.
3. **6-gram tokenization** (document and chunk level) changed from whitespace words to alphanumeric words, because 2.94.0 writes "release ." and 2.122.0 "release.", which counted spacing as different text. It does not change same-release comparisons materially.
4. **A word-sequence check of text items** was added to apply the registered item-loss rule modulo formatting; the exact-identity count (914 of 5,037 items for 2.122.0) is also in the output but mostly measures spacing.
5. **A second upgrade candidate, 2.122.0,** was added after 2.135.0 failed, chosen by the bisection above, and judged by the same registered rules. The registered comparison was 2.94.0 against 2.135.0 only.
6. **The exploratory resolved-items variant, the bisection and the release probe** are not registered measures.
7. **`TORCHDYNAMO_DISABLE=1`** was set when converting with 2.122.0 and in the bisection, because some releases (2.120.1 was the first seen) try to compile a torch kernel and this sandbox has no Python headers. It affects speed, not output; on a machine without a compiler a release that needs one would hit the same error.

## Limits

13 documents; labeled lead-ins are the repository's existing labels (the fresh set has one labeler, whose result also depends on the labeler as step 28 of `../wp_45_7/README.md` showed); the co-location metric finds the quote by text and so cannot score a repeated quote's other occurrences; the table-text comparison for 2.122.0 was read only in part; word-level 6-grams do not capture reading order; a bisection on one document and a monotonic assumption. Better chunk or table structure does not by itself mean better requirements, and nothing here ran Step C.

## Reproducibility note

The production install does not pin `docling-core`, `docling-parse` or `docling-ibm-models`; only `docling==2.94.0` is pinned in `pyproject.toml`. This audit recorded the installed versions of all four in every cache manifest and refused to reuse a cache from a different set. A fresh install of the same pin could resolve to a different `docling-core` and change the chunker's behavior (the chunker comes from `docling-core`).

## Decisions for the owner

1. **Chunk limit (H1).** The gain in lead-in co-location is large (74% to 98.6% at 1,024 tokens), but adopting any larger limit first needs `_chunk_raw_text` to handle merged chunks, or it would turn 37 of 56 tables into the flat form and change every chunk id. A fix is a production change with its own plan and a Step C pilot; it also repairs today's 9 flat tables whatever the limit. It forces re-extraction and a reindex.
2. **Upgrade.** Do not move to 2.135.0. 2.122.0 misses the registered rule by 2 of 145 items and improves some OCR text; a pilot (pin move, test run, replayed ingestion on the 13 documents, Step C comparison) is the next step if the owner accepts that shortfall.
