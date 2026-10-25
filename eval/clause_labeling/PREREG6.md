# PREREG6: does the chunk size still need to be small now that requirement finding is clause labeling?

Written 2026-10-23, before any chunk was re-made at a new size and before any label was run. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything.

## Question (Tyler's hypothesis)
Requirement finding is now clause labeling (`pipeline/clause_labeling.py`, frozen prompt v3, `ornith:35b`). The model sees 4 clauses per call plus a short context (heading, paragraph number, the lead-in line above), never a whole chunk. So the Docling `HybridChunker` size may no longer need to be small. Larger chunks should (a) cut fewer sentences at chunk ends and keep more list lead-ins in the same chunk, and (b) give the same extraction quality.

## Prior art (so this is not repeated blind)
WP-45.10 / 45.11 (`eval/spike_results/wp_45_10`, `wp_45_11`) already tested 512 and 1,024 tokens with the OLD finder (8B model writing a list). Lead-ins in the same chunk as their quote rose 73.8% (256) to 92.4% (512) to 98.6% (1,024), but the 8B finder extracted less from longer chunks and the registered rules failed, so the limit stayed 256. Two things changed since: the finder (it now labels clauses, and each call is independent of chunk length) and the table fix (#249). This experiment asks only whether the NEW finder behaves differently. WP-45.10 also found that a merged (larger) chunk made `_chunk_raw_text` write tables in the flat "Header = Value" form instead of the grid; rule R5 below guards that.

## What is measured
- Arms: **control** = the default `HybridChunker()` (Docling 2.94.0: `max_tokens` 256 with the `sentence-transformers/all-MiniLM-L6-v2` tokenizer; confirmed by running it), **512**, **1024** (same tokenizer, only `max_tokens` changes). Production code unchanged: `pipeline.chunk_text.run_structure_aware` with the profile's skip sections, then the real pipeline from requirement finding (`run_pipeline.py --skip-to requirement-finding`, model `ornith:35b`, prompt v3, BATCH_SIZE 4).
- Documents (4): afi17-203, afi10-2402, afi13-550, dafman17-1304. Same Docling parse for all arms of a document (cached parse where one exists, one fresh parse for dafman17-1304).
- Jobs run one after another on the model server, never two at once. Order: control, 512, 1024 for each document in turn.

## Metrics (all on the new files, from `eval/clause_labeling/chunk_size_metrics.py`)
1. **End cuts** (the judged boundary metric): chunk records whose last non-empty line (a) does not start with `|` (not a table row), (b) has more than 6 words (not a heading or label), and (c) does not end in `. ! ? : ;` (optionally followed by closing quote/bracket, or a `(T-n)` tag). Counted over all chunk records of the 4 documents. **Start cuts** (reported, not judged): chunks whose first line, after removing a bullet, list label or paragraph number, begins with a lower-case letter.
2. **Fragmentation F1 to F10**, exactly as `fragmentation.py` defines them (F2 starts mid-sentence, F3 list item with no lead-in attached, F8 anchor not exact), run on the checklist built from each arm's folder. Reported; only F8 is judged.
3. **Lead-in in the same chunk** (reported): of the clauses that are list items, the share whose "lead-in line above" is found inside their own chunk.
4. **Rows kept**: number of requirement rows (labeled not NOT_REQUIREMENT) per document and arm.
5. **Quality against the labeled sets** (paragraph units; the match rule is the one used since PREREG3/4: a labeled requirement counts as found when some output row contains it or it contains the row, or they share at least 60% of words; a row counts as right under the same test; recall = found / labeled, precision = right rows / rows that fall inside the sampled paragraphs; a row falls in a unit when its text is contained in the unit text or the reverse). Truth is unchanged: the silver labels (two blind copies, requirements both list) and the gold2 labels (two model families plus owner rulings). Rows are read from the arm's `*_extracted_requirements.jsonl`, so no labeled set depends on chunk boundaries.
   - **Sealed set (judged)**: afi17-203 silver EXAM units (all three tranches) and afi13-550 gold2 EXAM units, pooled. Neither document was used to tune the prompt or the splitter; both were EXAM documents run once on the frozen prompt in PREREG3/4. This run uses them a second time for a different question; no setting is tuned afterwards.
   - **Burned (reported only)**: afi10-2402 silver TUNE units (the prompt and splitter were tuned on this document).
   - **No labels**: dafman17-1304 (not in any labeled set): rows lost and rows added against control, counts only; up to 30 of each listed in the scratch folder. Reading them is the author's own reading, not a blind grade, and no verdict depends on it.
6. **Label time**: wall seconds of the requirement-finding step (from the pipeline log: "Starting requirement finding" to "Starting normalizing"), summed over the 4 documents.
7. **Table integrity**: number of lines starting with `|` in all chunk `raw_text`, summed over the 4 documents.
8. **Clause flips** (reported): among clauses whose text is identical in control and a larger arm, how many changed label.

## Pass rule (per larger size; all five must hold; evaluated literally)
- **R1** End cuts (all 4 documents pooled) fall by at least 50% against control.
- **R2** On the sealed set pooled, recall is not more than 2.0 points below control AND precision is not more than 2.0 points below control. (For scale only: the seed noise floor measured earlier was 1.2 points recall and 1.9 precision; this run is deterministic at temperature 0, so changes come from the chunking alone. A value within 0.5 point of a line is called "borderline" in the report, but the verdict still follows the line.)
- **R3** F8 (anchor not exact) summed over the 4 documents is not above control, and the verbatim rule holds: every row's `source_quote` is found verbatim in its chunk text (whitespace-tidied), which is what F8 counts.
- **R4** Label time summed over the 4 documents is at most 1.5 times control.
- **R5** Table grid lines (metric 7) are at least 95% of control.

Verdict words: PASS (R1 to R5 all hold), FAIL (any fails), AMBIGUOUS only if a run could not be completed or a metric could not be computed as defined; the report then says what and does not guess.

## What a pass does and does not mean
A pass says the larger limit would not hurt the checked quality on four documents; it does not by itself change anything. Changing the shipped limit changes every chunk id and forces re-extraction, which is on the stop-and-ask list and is Tyler's decision. This PR changes no pipeline code.

## Limits stated in advance
Four documents. Quality is judged on two sealed documents (about 230 sampled paragraphs, a few hundred labeled requirements); precision is relative to the agreed lists and is a lower bound. Labels are model-written plus owner rulings, not a full human audit. One model, one prompt, one run per arm (temperature 0, so rerunning would repeat it).
