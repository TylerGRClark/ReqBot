# PREREG7: should a chunk end where an element ends (merge_peers off), and what passage window do readers need?

Written 2026-10-23, before any chunk was re-made with `merge_peers=False`, before any label was run for a new arm, and before any window was computed. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything. Follows PREREG6 (PR #368), whose results (control, 512, 1024) are reused unchanged.

## Question (Tyler's intuition)
A smart chunk should end where a paragraph or section ends, and the size limit should only be an upper bound. PREREG6 raised `max_tokens`; that made chunks bigger because Docling's `HybridChunker` (default `merge_peers=True`) first makes one chunk per document element and then MERGES neighbouring small chunks that share the same headings until `max_tokens` is full. This experiment changes the merge instead of the size: `merge_peers=False` keeps element boundaries and splits only an element that is itself over the limit. It also asks what the readers of chunk text (draft-question prompt keeps 1,500 characters of the passage, criticality prompt 1,200, context index embeds 1,500) need, since those cut-offs are ReqBot settings, not constraints (Tyler, 2026-10-23).

## Arms (4 documents as in PREREG6: afi17-203, afi10-2402, afi13-550, dafman17-1304; same cached Docling parses)
- **control** = default `HybridChunker()` (256 tokens, merge_peers on). Reused from PREREG6.
- **B512**, **B1024** = merge_peers on, 512 / 1024 tokens. Reused from PREREG6.
- **A** = `merge_peers=False`, `max_tokens=1024`, same tokenizer. Only an element longer than 1,024 tokens is split.
- **C** = A plus a "lead-in glue": after chunking, a chunk whose last non-empty line ends in a colon (optionally followed by a tier tag) is joined with the chunk right after it, when both carry the same headings and the joined text is at most 1,024 tokens (same tokenizer). One glue per chunk, no chaining beyond the next chunk. Reason, from PREREG6 data: with control chunks only 1 of 66 list-item clauses had its lead-in in its own chunk, and the risk of A is that a list becomes its own chunk, separated from the line above that governs it. C is the smallest change that removes that risk. If A already attaches lead-ins as well as C, C is not needed; both are run so that is measured, not assumed.
Production code is unchanged; the arms are made by wrapping `HybridChunker` in the scratch driver (`eval/clause_labeling/chunk_size_make_arms.py`), then `pipeline/run_pipeline.py --skip-to requirement-finding` with `ornith:35b`, prompt v3, BATCH_SIZE 4, exactly as in PREREG6. Jobs run one after another, never two at once, order A then C, documents in the PREREG6 order.

## Metrics (computed by the PREREG6 scripts plus `chunk_size_windows.py`)
1. End cuts (R1 of PREREG6, same definition), pooled over the 4 documents. Start cuts reported.
2. Lead-in attach, two readings, both reported: **F9** (checklist rows with a lead-in attached, which includes the look-back of `pipeline/lead_in.py` into the previous chunk), **F3** (list scraps: list item with no lead-in), and the share of list-item clauses whose lead-in is inside their own chunk. All summed over the 4 documents.
3. Chunk count and size: median, p90, max characters of `raw_text`; chunks over 1,500 characters; chunks under 150 characters; share of chunk text beyond the first 1,500 characters (what the context index embeds).
4. Sealed quality (judged): pooled afi17-203 silver EXAM units + afi13-550 gold2 EXAM units, the PREREG6 matching rule, recall and precision. Burned afi10-2402 silver TUNE units reported. dafman17-1304 rows lost and added against control, counts only. Clause flips against control reported.
5. F1 to F10 of `fragmentation.py`; F8 judged.
6. Label time: wall seconds of the requirement-finding step summed over the 4 documents.
7. Table grid lines (lines starting with `|`) summed over the 4 documents.
8. Passage window (below).

## Passage window: measured and a rule designed (not merged)
The checklist passage of a row is the text of the chunk holding the quote (plus the tail of the previous chunk for list items and mid-sentence rows), with the quote marked `>> <<`.
- **Coverage as shipped** per arm and per cut-off (1,500 for draft questions, 1,200 for criticality): share of checklist rows whose marked quote lies wholly inside the first N characters of the passage. Also the share of rows with a lead-in attached whose lead-in text lies inside the first N characters (lead-in coverage), from the record's `explained_parts`.
- **Window rule (designed here, applied in the script only):** given the row's quote and the document's chunk stream, take (1) the element lines (lines of `raw_text`, which is one line per document element) that hold the quote; (2) if the quote is a list item, the nearest earlier line that ends in a colon and is not itself a list item, within the same chunk or the end of the previous chunk, plus the lines between; (3) extend alternately one line after, one line before, only through lines of chunks with the same section path as the quote's chunk, while the total stays at most **1,500 characters**; (4) if the quote plus its lead-in alone exceeds the cap, the window is the quote plus lead-in uncut (the quote is never cut); a side that is cut is marked with an ellipsis. The window does not depend on how big the chunk is, so the same rule serves every arm. The 1,200-character criticality reader would take the first 1,200 characters of the window around the quote (window cut to the quote's neighbourhood by the same alternating rule at cap 1,200); reported as a second cap.
- Window coverage per arm: share of rows with the quote wholly inside (should be about 100%), share of rows with a lead-in whose lead-in is inside, median and p95 window length, share of rows whose window reaches a line outside the quote's own chunk.
Coverage numbers are exact counts on the checklist rows; no model is involved.

## Pass rule (per arm A and C; all must hold; evaluated literally; B512 and B1024 are evaluated by the same rule for comparison)
- **P1 Quality.** Sealed recall not more than 2.0 points below control AND sealed precision not more than 2.0 points below control (borderline within 0.5 point is called out, verdict follows the line).
- **P2 Verbatim.** F8 summed over the 4 documents is 0 (not above control, which is 0).
- **P3 Time.** Label time summed over the 4 documents at most 1.5 times control.
- **P4 Improvement (at least one).** (a) End cuts fall at least 50% against control; or (b) lead-in attach: F9 summed rises at least 25% against control AND F3 summed does not rise.
- **P5 Tables.** Table grid lines at least 95% of control.
- **P6 Passage coverage.** Evaluated twice. **As shipped:** the share of rows whose marked quote lies beyond the first 1,500 characters (draft questions) is at most control's share + 2.0 points, and the same for 1,200 (criticality). **With the window rule:** at least 99% of rows have the quote wholly inside the window, and the lead-in coverage of rows with a lead-in is at least control's lead-in coverage as shipped. 

Verdict per arm, per reading: **PASS as shipped** (P1 to P5 and P6-as-shipped), **PASS with window rule** (P1 to P5 and P6-with-window, but not as shipped; this means the arm is usable only if the reader cut-offs change to the window rule), **FAIL** (P1 to P5 any fails, or P6 fails both ways), **AMBIGUOUS** only if a run could not be completed or a metric could not be computed as defined; the report says what and does not guess.

## What a pass does and does not mean
A pass says the setting would not hurt the checked quality on four documents; it does not change anything. Changing the chunker changes every chunk id and forces re-extraction, and changing the reader cut-offs changes prompts; both are on the stop-and-ask list and are Tyler's decision. Tyler has said the library is disposable experimentation, so re-extraction cost is not a factor in the verdict. This PR changes no pipeline code.

## Limits stated in advance
Four documents, one model, one prompt, one run per arm (temperature 0). Quality is judged on the two sealed documents (about 230 sampled paragraphs); they were already used once in PREREG6. Precision is a lower bound (relative to the agreed lists). The F9/F3 counts are small (tens per document). Coverage of the window is a count of whether the text is present, not a judgment that the context is sufficient for a human auditor; that would need a blind reader and is not done here. Retrieval quality of the context index with the new chunks is not measured; only the size facts that bear on it are.

## Amendment 1 (2026-10-23, written before any result of arm A or C was read)
While building `chunk_size_windows.py` I ran it on the existing control and 1024 arms (not on A or C) to test that it works. Step 2 of the window rule as written above (nearest earlier colon line that is not a list item) found the lead-in for only 123 of the 154 control rows that have one, because many lists are inline in one element line. Step 2 is changed to: "if the row has a lead-in as `pipeline/lead_in.py` resolved it (stored in the row's `explained_parts`), the window starts no later than the nearest line at or above the quote that holds it (same section path, at most 40 lines back, crossing into earlier chunks); the lines between are included when they fit, else the lead-in line alone". Nothing else changes. The control and 1024 numbers I saw during that test (window lead-in coverage 152/154 and 245/250 after the change) are therefore not blind to the rule, and the report says so. All thresholds are unchanged.
