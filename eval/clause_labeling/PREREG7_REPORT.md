# PREREG7 report: element-boundary chunks (merge_peers off), lead-in glue, and the passage window

Run 2026-10-23 on main c4b8136 (all five arms labeled again with the current splitter; `ornith:35b`, prompt v3; sequential jobs). Rules and thresholds: `PREREG7.md` (committed before any result; two dated amendments, both before any A/C result was read). Raw numbers: `results_prereg7/`.

## Answer in one paragraph
Letting a chunk end where a document element ends (arm A, and A plus lead-in glue, arm C) is WORSE, not better: end cuts rose from 33 to 53 and lead-in attach barely moved. Reason: in these PDFs a paragraph is often split into several elements by page and column breaks, and Docling's merge step is what stitches them back together; without it the pieces become separate chunks (chunks go from 403 to 688, median 261 characters, start cuts 5 to 14). Larger merged chunks (1024 tokens) do achieve the goal (end cuts 33 to 13, lead-in attached 159 to 255 rows) with sealed quality unchanged, but only if the reader cut-offs (1,500 / 1,200 characters) are replaced by a window around the requirement; as the cut-offs stand, 45% of rows would have their requirement cut off.

## Numbers (4 documents pooled; sealed = afi17-203 silver EXAM + afi13-550 gold2 EXAM)
| | control (256) | B512 | B1024 | A (no merge) | C (A + glue) |
|---|---|---|---|---|---|
| chunks | 403 | 234 | 165 | 688 | 655 |
| chars median / p90 / max | 826 / 1134 / 10689 | 1376 / 2182 / 10689 | 1742 / 4050 / 10960 | 261 / 1090 / 10689 | 282 / 1203 / 10689 |
| end cuts (R1) | 33 | 18 (-45%) | 13 (-61%) | 53 (+61%) | 53 (+61%) |
| F9 lead-in attached (rows) | 159 | 193 (+21%) | 255 (+60%) | 173 (+9%) | 191 (+20%) |
| F3 list item without lead-in | 9 | 9 | 9 | 9 | 9 |
| list-item clauses with lead-in in own chunk | 1/66 | 11/66 | 12/66 | 4/66 | 12/66 |
| sealed recall (172 labeled) | 97.7 | 97.1 | 97.1 | 97.1 | 97.1 |
| sealed precision | 90.9 | 90.7 | 89.9 | 91.6 | 92.5 |
| F8 | 0 | 0 | 0 | 0 | 0 |
| label seconds, 4 docs (clean timing) | 803 | 781 | 786 | 809 | 808 |
| table grid lines | 67 | 67 | 67 | 67 | 67 |
| quote beyond first 1500 chars of passage (as shipped) | 2.4% | 22.0% | 45.5% | 19.7% | 20.3% |
| quote beyond first 1200 chars (criticality) | 6.8% | 33.9% | 53.8% | 25.5% | 26.3% |
| chunk text beyond 1,500 chars (context index cut) | 7.5% | 20.9% | 43.7% | 16.7% | 16.7% |
| rows with window rule: quote inside (cap 1500 and 1200) | 100% | 100% | 100% | 100% | 100% |
| rows with a lead-in: lead-in inside, as shipped 1500 / window 1500 | 92.5 / 98.7 | 78.8 / 98.4 | 45.5 / 98.0 | 66.5 / 97.1 | 68.1 / 97.4 |

(Lead-in coverage as shipped is the share of rows with a lead-in whose lead-in text lies in the first 1,500 characters of the passage; control 147 of 159.)

## Verdicts (PREREG7 rule, evaluated literally)
- **A: FAIL** (P4: end cuts +61%, F9 +9%).
- **C: FAIL** (P4: end cuts +61%, F9 +20% under the 25% line; lead-in in own chunk rose 4 to 12 of 66, so the glue works as designed, but the main problem is the boundaries, not the lead-ins).
- **B512: FAIL** (P4: end cuts -45% and F9 +21%, both just under their lines; borderline).
- **B1024: PASS with window rule; fails as shipped** (P6: 45% of rows would lose the requirement under the 1,500 cut-off). P1 to P5 hold (recall -0.6, precision -1.0 against control; time 0.98x; tables equal).
All arms: F8 = 0, time within 1.5x, tables equal. Quality differences are within the 2-point line (sealed set is 172 labeled requirements, so one requirement is 0.6 points).

## Passage window rule (designed here, not merged; `chunk_size_windows.py`)
Take the element lines that hold the requirement; add the lead-in line the pipeline already resolved (if any); then grow one line after, one line before, never across a section change and across chunk borders when needed, until 1,500 characters (the requirement is never cut). With it, 100% of rows have the requirement inside in every arm, lead-in coverage is 97-98.7% in every arm (control as shipped: 92.5%), and the passage length is about the same for every arm (median about 1,385 characters), so reader quality no longer depends on chunk size. Side effect to know: it is longer than today's control passage (median 927), so draft-question and criticality prompts grow by about 50%. Coverage only counts that the text is present; whether it is enough for a human auditor was not graded blind.

## Recommendation
Do not switch to element-boundary chunking (A or C). If chunking is changed at all, change to merged 1024-token chunks AND adopt the window rule for the question and criticality readers AND raise the context-index embed cut (44% of chunk text would otherwise be outside the 1,500 characters embedded). That is a re-extraction plus prompt change, which Tyler can approve since the library is disposable; benefit is modest (end cuts 33 to 13 of about 1,060 rows, lead-ins attached +96 rows), with no measured loss of recall. Not measured: retrieval quality of the context index with bigger chunks, the checklist as read by a human, and the effect of a longer question prompt on question quality.

## Limits of the evidence
Four documents, one model, one prompt, one run per arm (temperature 0). Sealed quality rests on about 170 labeled requirements from two documents already used once in PREREG6; differences under 2 points are noise-level. Precision is a lower bound. F9/F3 counts are small (F3 is 9 everywhere). The window rule was tested on control and 1024 while being built (amendment 1), so its numbers for those two arms are not blind to the rule. Label times for runs that overlapped another job on the model server (16:00-16:40 UTC) were replaced by clean reruns (afi17-203, afi13-550 all arms; afi10-2402 A, C, control, 512); afi10-2402 B1024 started at 16:40 and was kept. Arms A and C were also labeled once on the pre-merge splitter (#365 era); those runs were not used.
