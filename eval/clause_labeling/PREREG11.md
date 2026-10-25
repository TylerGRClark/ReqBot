# PREREG11: table header row (and caption) in the labeler's context for table-line clauses

Written 2026-10-25, before any labeling run. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything.

## Question
Each table grid line is one clause, shown to the labeler without its column headers. A cell value such as "Yes", "(T-1)" or a bare noun phrase loses what it answers. Table lines are about 18% of library clauses (3,161; CNSSI_No1253 about 2,200, dafi36-2903 about 340, dafman17-1203 about 195). Does showing the table header row (and the table caption when there is one) for table-line clauses improve labeling? (Design note D7: "separate test adding the header row".)

## What the inspection found (descriptive, before any run; script `~/reqbot-work/scratch/table_hdr/inspect.py`)
- Chunking already repeats the header: every chunk that holds a table starts that table with its header row and separator line (Docling `repeat_table_header`). In the six documents every grid line has a header row above it in its own chunk text (CNSSI_No1253 2,142 of 2,223 grid lines; the other 81 are the header rows themselves; dafi36-2903 323/338 (15 header rows); dafman17-1203 181/195 (14); dafpam90-803 107/128 (21); afi17-203 20/24 (4); afi10-2402 29/34 (5); no grid line lacks a header in its chunk).
- The labeler does not see it. `clause_block` shows Heading, Paragraph and "Lead-in line above" (`find_lead_in`), and `find_lead_in` returns nothing for a '|' line: in CNSSI_No1253 (2,223 grid lines) and dafman17-1203 (195) the lead-in is empty for every grid line. A grid line reaches the model as `Context: <heading> | Clause: | CP-10 | Information System Recovery ... | | | X | ...`.
- So the header is present in the data and absent from the model's view. This test changes only that.
- Header-row clauses themselves are already labeled; the frozen prompt lists "table headers" as NOT_REQUIREMENT. They get no table context in the header arm.
- Captions ("Table D-1: NSS Security Control Baselines") sit above a table's first chunk only; later chunks repeat the header but not the caption. Rule below carries the caption forward by matching the header text. Share of grid lines that get a caption under the rule: CNSSI 1,945 of 2,142; dafi36-2903 50 of 323; dafman17-1203 124 of 181; dafpam90-803 13 of 105; afi17-203 16 of 20; afi10-2402 9 of 29. Known limit: where Docling made the first data row the "header" (CNSSI glossary table), that row is shown as the header.

## Arms (frozen)
- Base: origin/main 8de5492, worktree `~/wt-tablehdr`, branch `feat/table-header-context`. Model `ornith:35b` (config `extraction_model`), frozen prompt v3 (sha b9b20379...), batch 4, num_ctx 8192, num_predict 300, as in PREREG8/9. Driver `eval/clause_labeling/table_hdr_run.py` (copy of the `label_ctx_run.py` pattern: production `document_clauses`, `make_batches`, `build_prompt`, `label_batch`; the arm changes the context only).
- `control`: current main, nothing changed.
- `header`: for every clause whose text starts with '|' and that is not itself the table's header row, the context gets one extra field `Table context: <caption>. Column headers: <cells>` (cells joined with " | ", empty cells dropped, whitespace collapsed; caption cut at 100 characters, whole field at 300). The rule is `eval/clause_labeling/table_header.py`: header = the line right above the table's first separator line; caption = the nearest non-blank line above the table in the same chunk that starts "Table <id>", else the caption last seen above a table with the same header text in an earlier chunk. No other clause's context changes; the prompt template file is untouched (the new field is added to the context string in the driver's copy of `clause_block`, which the driver asserts is byte-identical to production for clauses without the field).
- `control2`: a second control run (noise floor).
- One model job at a time, never two; no `local_review.py` during runs. Order: control, header, control2.
- Clauses labeled: every clause of every chunk that contains at least one grid line (table chunks), in document order, batched over that sequence (same sequence in all arms). Only those clauses can differ between arms. Non-table chunks are not labeled (their context is identical in both arms).

## Documents
CNSSI_No1253 (2,498 clauses in 81 table chunks), dafman17-1203 (233; 14), dafpam90-803 (229; 21), afi17-203 (40; 4), afi10-2402 (69; 5), dafi36-2903 (343; 15; run last, table chunks only, about 6 minutes). Newest library chunk files (run 2026-10-24) snapshotted into the scratch folder. None has been run in any arm of this test; CNSSI_No1253 and dafman17-1203 were used in PREREG9 (lead-in context, a different field) and afi17-203/afi10-2402 in earlier tests; the table context is new to all of them.

## Metrics
1. **Flips (primary).** A grid-line clause is a flip if its status (row = any label other than NOT_REQUIREMENT, vs not a row) differs between control and header. All flips are graded blind (see grading). If there are more than 80 flips, all flips outside CNSSI_No1253 plus a seeded random sample of CNSSI flips (seed 11) up to 80 are graded; the report states how many were not graded.
2. **Label agreement and noise floor.** Control vs control2: share of clauses with a different label and with a different row status, per document and pooled. Header vs control: same. Expected noise about 0.5% flips (PREREG8: 1 of 2,289).
3. **Rows.** Rows (non-NR clauses) in table chunks and among grid lines, per arm; fragmentation on table rows: F5 (shown text contains a pipe) and F6 (not a complete sentence, `is_complete` on the tidied clause) per arm. Reported, not judged.
4. **Gold.** The PREREG8 scorer (`label_ctx_metrics.py` functions unchanged: recall = gold requirements covered by a row; precision = rows inside the gold paragraphs that match a gold requirement; match = containment or 0.6 token overlap) on the units of these documents that exist (gold2 exam units, CNSSI gold2 extension with 10 agreed requirements, silver exam units), restricted to clauses that were labeled (table chunks), the same restriction in every arm. Gold only judges what is in sampled paragraphs; most table lines are outside it.
5. Seconds per arm, unparsed or failed batches (any invalidates that arm; fix and rerun the arm).

## Grading (as in `~/reqbot-work/notes/blind_flips_result_2026-10-24.md`)
- Each graded flip is shown as the clause, the document name, the table's header row and caption exactly as found in the chunk text (shown identically for every flip, whichever arm was right), and about 600 characters of source before and after (previous or next chunk appended at chunk edges). Order shuffled. No arm labels, no gold labels, no model labels.
- Standard: is the clause a duty, prohibition or permission on a stated party, or a required value or setting for something, that an auditor could check, read with its column headers? YES / NO / UNSURE. UNSURE counts as no verdict.
- Two graders: Codex (`codex exec`, no arm information in the prompt) and Claude (me), who grades independently before Codex output and before the key is opened. The key (which arm said what) is written to a separate file and not opened or printed until both graders are saved. I do not print arm labels while checking formats.
- A flip is "agreed" when both graders gave YES/NO; then the header arm is right if (grade YES and header said row) or (grade NO and header said not a row); both graders must agree on that judgement.

## Pass rule (all must hold)
1. Agreed judged flips >= 10, and agreed header-right >= 2 x agreed control-right, and agreed header-right minus control-right >= 5.
2. Pooled gold (documents with gold, table-chunk clauses): Recall(header) >= Recall(control) - 1.0 point and Precision(header) >= Precision(control) - 1.0 point (1.0 = the PREREG8 noise floor, rounded up). CNSSI_No1253 alone is also printed; its gold has 10 requirements, so it is coarse and a loss there is reported but only the pooled numbers decide.
3. The number of grid-line status flips between control and header exceeds 2 x the number between control and control2 on the same documents (otherwise the effect is not distinguishable from noise and the verdict is "no measurable effect", not a pass).
- FAIL: agreed control-right >= agreed header-right, or the gold rule broken. NOT CONFIRMED: everything else (fewer than 10 agreed judged flips, or a ratio between 1:1 and 2:1).
- A pass driven by one document (more than 70% of agreed header-right flips in one document) is called out. Per-document agreed counts are printed.
- If it passes, the smallest code change goes in a separate commit marked PROPOSED, with tests; the test of production behavior is that control prompts stay byte-identical for clauses with no table context.

## Limits stated in advance
Six documents, one run per arm; author is one of two graders (the other is Codex, a second model family); table lines that are bare numbers or X marks with no requirement meaning make most flips ambiguous; the standard for "required value" in parameter tables is judgment; CNSSI gold has 10 requirements; dafman17-1203 gold is silver (older, weaker); only table-chunk clauses are labeled, so whole-document recall and precision are not measured here; one header per table (multi-row headers or a data row mistaken for a header are shown as found).
