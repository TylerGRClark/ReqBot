# Adaptation log (written BEFORE any arm numbers were seen)
- Prompt hash verified: b9b20379...dbc4 (prompt_current.txt == prompt_FROZEN.txt).
- Chunk text: the chunk record's raw_text (not 'text', which adds a breadcrumb line). Heading = parent_header_text; ref = section_ref_path joined with ' > '. 37/38 chunks have a heading, 27/38 a ref.
- Records for the scorer: (document, {requirement_id, chunk_id (chunk's own int id), source_quote = clause text}). Scorer used unchanged (SD.precision_tally, DEV.trace_all via SD.runs_for). Arms are scored on the same 38 chunks the baseline read; chunk_tokens covers all chunks of each doc, as in the checker script.
- Recall = obligations (of 74) whose trace status['extracted'] != 'none' (PREREG2 wording). The scorer's 'primary' (fully covered) recall is also reported as secondary.
- Precision = SD.precision_rate(SD.precision_tally(records)) unscored records (touching no labeled piece) are excluded by the scorer's own rule.
- Baseline = Step D normalized rows of ctl8b r1..r6 (same as checker_strict), mean of six.
- MISMATCH found: old24_ids.json was built from other runs (B0a,B0b,T1,T1b); r1-r6 together actually find 5 of those 24. PREREG2 says "found by no baseline run". Decision: report the given 24 as the primary count (as the caller specified), and also the 20 obligations that no r1-r6 run finds. Neither is a pass condition.
- Batch order: all clauses of the 38 chunks pooled, shuffled with random.Random(seed), batches of 4; seeds 1 and 2. Temperature 0, num_ctx 8192 as in the first test code.
