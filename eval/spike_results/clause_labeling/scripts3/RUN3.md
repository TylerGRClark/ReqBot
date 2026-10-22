# Third test run: DAFMAN 17-1304 end to end (run 20261015_043719). Not judged yet.

Method: frozen prompt (sha256 b9b20379..., copied unchanged), splitter and context rule from test 1, model ornith:35b (think off, temperature 0), one request at a time, batches of up to 4 clauses in document order. Raw chunk text of all 148 chunks. Heading = chunk's parent header; ref = last entry of its section-ref path. Matching = the `match` function of miss_diag/step1.py (containment or 60% shared words).

## Counts
- 148 chunks -> 870 clauses. Labels: 364 DUTY, 28 PROHIBITION, 10 PERMISSION, 468 NOT_REQUIREMENT, 0 UNSURE.
- Flagged clauses: 402. Production rows: 450. Ratio flagged/rows = 0.89 (rule b limit is 1.6).
- BOTH: 343 flagged clauses match a row (341 distinct rows matched). NEW: 59 flagged clauses match no row. PROD-ONLY: 109 rows matched by no flagged clause.
- Unparsed batches: 0 of 218 (0%). No clause was over the 1200-character prompt cut.

## Timing and cost
- 218 calls (217 live, 1 duplicate batch served from cache), 565 s of model time, 562 s wall (about 9.4 min, 2.6 s per call) while the overnight job shared the 35B. Local model, no money cost. Run was not interrupted.

## Blind review files (blind/)
- blind_items.json: 119 items, seed 20261022, shuffled, ids R001..R119. 59 NEW (not 60: only 59 exist, so all of them), 40 PROD-ONLY, 20 BOTH. Paragraph = whole chunk text if under 1500 chars, else a 1500-char window around the candidate. Fields: id, document, heading, paragraph, candidate.
- KEY_DO_NOT_SHOW.json: id -> group.

## Honest notes
- NEW is small (59, 15% of flagged) so the NEW sample is the entire group, not a sample; the 60% rule (a) is judged on 59 items.
- PROD-ONLY is large: 109 of 450 rows (24%) are not matched by any flagged clause. Possible causes (not checked beyond counts): production quotes spanning several clauses or sentence fragments below the 60% overlap, or clauses the labeler called NOT_REQUIREMENT. The review of the 40-item sample will tell which.
- Chunk 0 is a guidance memorandum (front matter); production keeps "Compliance ... is mandatory" style sentences from it. No tables were detected as such (no '|' rows among NEW). Boilerplate in headers/accessibility notices was not separately analysed.
- Batches were in document order, not shuffled as in tests 1 and 2; this is a change in ordering only, not in the frozen prompt or rules.
- Files: labels3.json (all clause labels), summary.json, run3.py, analyze.py, cache.jsonl, run3.log.
- Decision rules NOT applied.
