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

## Root restored, explained layer added (second PR for step 4)

The whole-sentence expansion no longer replaces `source_quote`. `source_quote` is the root, exactly what requirement finding returned (trimmed of surrounding spaces); the expansion moves to `explained_text` (with `explained_parts` and `explain_notes`) beside it, built only from pieces of the source: the sentence the root sits in, the exact piece anchoring found when the root has a list number or a few front words that the source lacks, and a glued lead-in when anchoring found it in the chunk or its heading. A root whose last words are not in the source (often a table cell read back as a sentence) is not expanded, because dropping those words would merge rows that differ only there. Records that reach the same sentence in the same chunk are shown once; the other roots are kept in `merged_roots`. The stable ID is hashed from the root. The checklist shows the explained text as the requirement and keeps the root in `extracted_quote`; the embedding text and the Qdrant payload carry the explained text (search display moves in step 12 of the plan).

`root_report.py` re-runs Step D on copies of the 13 reference documents' newest runs (offline) and checks the plan's rules:

| Rule | Result |
|---|---|
| (a) every record's `source_quote` is a quote requirement finding returned | **met** in all 13 documents (a test checks it on a small fixture too) |
| (b) labeled-obligation coverage (74 obligations, 3 sample documents) not lower than the existing run by more than the paired-loss limit of 4 | existing run (sentence rule replaced the quote) 69; new records counted by their root 67; **counted by their explained text 69: met** |
| IDs unique | **met**: no repeated `requirement_id` in any document |
| Records | 2,420 now against 2,419 in the existing run; 71 roots are listed in `merged_roots` because they sit in the same sentence as another root (only roots that were placed in the chunk are merged) |

Counting by the root alone gives 67 of 74, two below the existing run (within the limit of 4, and the root is a fragment more often than the sentence is); the explained text keeps the earlier 69.

## Explained text against the root: the owner's rating (2026-10-09)

`outputs/explained_rating_sheet.md`, 30 rows (8 where only a list number, dash or spacing differs; 22 where the words differ). The owner rated 28 and left 2 blank (rows 23 and 29): **25 better, 3 same, 0 worse = 28 of 28 better or same; step 5's bar of 80% is met** (28 of 30 = 93% even if the two blanks are counted against it).

Three of the "better" ratings carry a note that the row is not a requirement and should be n/a: row 3 is a lead-in line ("In addition to the responsibilities in Paragraph 2.10., the DoD CIO:"), rows 24 and 26 are definitions. The text is better, but screening should mark them; this is the evidence for the screening step (plan step 7).
