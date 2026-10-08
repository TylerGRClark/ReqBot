# WP-45.11 addendum — T3 (chunk limit): how the registered rules are applied

*Status: written while the T3 arms were running, before any T3 arm output was read. Adds no rule to [PHASE45_WP4511_PLAN.md](PHASE45_WP4511_PLAN.md); it fixes the details that plan left open so none is chosen after the numbers are visible.*

## 1. State being tested

- **Base (the T2 state):** merged table fix (#249, `main` at `cc0b67e`), Docling 2.94.0 with the pinned set (#254), 256-token chunks. Run twice on all 13 documents: **T2a**, **T2b**.
- **T3 arms (one change each):** the same code, chunk limit **512** (`T3_512`), then **1,024** (`T3_1024`). Tokenizer unchanged. Chunk files `d2.94.0:T2_256`, `T2_512`, `T2_1024`; regenerated from `main` and found byte-identical to the files used (13 of 13 for each of 256, 512, 1,024).
- Run order interleaved (T2a, T3_512, T2b, T3_1024) from the pinned worktree at `cc0b67e`, one at a time, so server drift is spread over base and treatment. `score_arms.py` checks one chunk spec, one model digest and identical pipeline code across arms.

## 2. How each rule is computed

- **R1, R2, R4:** `score_arms.py --arms T2a T2b T3_512` (and `T3_1024`), unchanged from T1/T2: recall of the 74 obligations, paired losses against the larger one-way replicate difference plus 2, survivors within 10%, any document more than 25% different listed, every lost obligation printed with its source text.
- **R3 (T3):** `analyze_t3.py`. Both conditions are required:
  1. *Gold quotes still extracted.* Fixed set = the labeled lead-in items (audit and fresh gold, "needs a lead-in", with adjudicated lead-in text; 145) whose quote is findable in the chunks of both specifications. An item counts as extracted when a Step D survivor's normalized `source_quote` contains, or is contained in, the normalized gold quote (both at least 40 characters). The arm's count must be at least 90% of the **lower** of the T2a and T2b counts (the same lenient choice as R1(i)).
  2. *Co-located share up by at least 5 percentage points* on the fixed set (the chunk holding the quote also holds every piece of the labeled lead-in text; computed from the chunk files).
- **Validation first:** `analyze_t3.py` runs the same refusals as `score_arms.py` (all 13 documents finished, no failed Step C chunk, one chunk specification per arm and the one declared on the command line, one model digest, identical pipeline code) before computing anything.
- **Reported, not gated:** the production `parent_stem` overlapping the labeled lead-in text (WP-45.7 rule, `score_resolver.overlaps`; lenient, credits a party-less fragment), as paired change against each base replicate with the item ids gained and lost; items findable in only one chunk specification, listed.
- **Limits stated now.** The 145 labeled items were drawn from production's own extracted records, so "still extracted" can only fall, not discover new items; it measures loss, and recall of the 74 (R1) remains the measure of gain. Prompt size at 1,024 tokens fits the 8,192-token window in the WP-45.10 estimate; a chunk that fails Step C makes `score_arms.py` refuse the arm rather than score it.

## 3. Disclosure

A plumbing check of `analyze_t3.py` on baseline arms (not T3 arms) printed the chunk-file co-location for 256 vs 512 tokens before this addendum merged: 73.8% to 92.4% (+18.6 points; 145 of 145 items findable in both). It depends only on chunk files, not on any model output, and repeats the WP-45.10 finding. No T3 arm output had been read.

## 4. After the result

Whatever the outcome, adopting a larger limit changes every chunk id, forces Step C re-extraction and a reindex of the live corpus: the owner's decision, not part of this work.
