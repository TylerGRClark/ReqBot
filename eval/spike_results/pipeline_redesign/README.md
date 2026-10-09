# Pipeline redesign — measurements

Plan: [docs/PIPELINE_REDESIGN_PLAN.md](../../../docs/PIPELINE_REDESIGN_PLAN.md).

## Anchoring (step 4), first PR: fields only

`pipeline/anchor.py` records, beside each root quote, where it sits in its chunk's `raw_text` and how exact the match is. It adds `anchor_status`, `anchor_start`, `anchor_end` and `anchor_text` (plus `anchor_lead_in`, `anchor_words_trimmed`, `anchor_matches` or `anchor_score` where they apply) to each normalized record. It changes nothing else: no record is accepted or rejected on this basis, and `source_quote` is not touched by it. (The whole-sentence expansion still replaces `source_quote` in this PR; moving that out of the root is the next PR.)

`anchor_report.py` re-runs Step D on copies of the 13 reference documents' newest runs (October 9, 2026; no model call) and writes `outputs/anchor_report.json`.

| anchor_status | Records | Share |
|---|---|---|
| exact (in the chunk once, word for word) | 2,242 | 92.7% |
| words_trimmed (exact once a few words are taken off the front or end) | 50 | 2.1% |
| marker_removed (exact once a dash, bullet or list number is taken off) | 42 | 1.7% |
| lead_in_from_heading (an exact list item with a lead-in glued on that is in the chunk's heading breadcrumb, not its body) | 39 | 1.6% |
| lead_in_joined (an exact list item with a lead-in glued on that is in the chunk body before it) | 20 | 0.8% |
| exact_ambiguous (the root, or a piece of it, occurs more than once in the chunk) | 10 | 0.4% |
| fuzzy (no exact piece; closest span at least 85% similar) | 8 | 0.3% |
| not_found (nothing close in the chunk) | 8 | 0.3% |
| Total | 2,419 | |

(`lead_in_not_in_source`, an exact item whose glued lead-in is nowhere in the chunk, exists as a status; no record in these 13 documents has it.)

**Pass rules from the plan, for this PR:** (c) the accepted records are identical with and without the anchor fields in all 13 documents (every field other than the new `anchor_*` fields and the run timestamp is equal): **met**. (d) per-document shares are in `outputs/anchor_report.json`: **reported**. Rule (a), that the root equals the line requirement finding wrote, and rule (b), labeled-obligation coverage, belong to the next PR, which is the one that stops the expansion from overwriting `source_quote`; this PR cannot change either.

Where the 177 roots that are not plain "exact" are: the glued lead-ins are concentrated in DODI 8410.03, dafman17-1305 and afi13-550; `words_trimmed` in DODI 8551.01 (11) and AFI 17-203 (14). Only 8 roots (0.3%) have nothing close in the chunk; 8 more are close but reworded. Of the 59 glued lead-ins, 39 are in the heading breadcrumb the model saw (for example "Air Combat Command shall:" under a heading of that name), so the model was reading the heading, not inventing the actor.
