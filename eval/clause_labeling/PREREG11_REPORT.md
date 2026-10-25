# PREREG11 report: table header row (and caption) in the labeler's context

Run 2026-10-25 against `PREREG11.md` (commit 614146c, unchanged). Code: `table_header.py`, `table_hdr_run.py`, `table_hdr_metrics.py`, `table_hdr_flips.py` (this folder). Raw files: `~/reqbot-work/scratch/table_hdr/` (arms, grading, metrics.json). No bug found; each arm ran once; no batch unparsed or failed.

## Verdict: PASS (all three rules), with the limits below

## 1. Is the header already there?
Yes in the chunk text, no in the model's view. Every grid line has its table's header row above it in its own chunk (Docling repeats it per chunk): CNSSI 2,142 of 2,223 grid lines (the other 81 are the header rows themselves), dafi36-2903 323/338, dafman17-1203 181/195, dafpam90-803 107/128, afi17-203 20/24, afi10-2402 29/34; none lack one. `find_lead_in` returns nothing for a '|' line, so the labeler's context for a grid line was Heading and Paragraph only. The caption sits only above a table's first chunk; the rule carries it forward by header text.

## 2. Setup
6 documents, table chunks only (3,412 clauses, 2,942 of them grid lines), control / header / control2, one 35B job at a time, about 22 minutes per arm.

## 3. Results
| | control | header | control2 |
|--|--|--|--|
| rows (all clauses) | 216 | 265 | 216 |
| rows among grid lines | 137 | 180 | 137 |
| F5 (table rows with a pipe) | 137 | 180 | 137 |
| F6 (row not a complete sentence) | 113 | 150 | 113 |

- Noise floor: control2 vs control, 0 label differences in 3,412 clauses (the runs are repeatable). So every flip below is caused by the context change.
- Header vs control: 67 grid-line status flips of 2,942 (2.3%): 55 became rows, 12 stopped being rows. CNSSI 50, dafman17-1203 13, dafpam90-803 4, the other three 0. Rule 3 (flips > 2 x noise): met.
- Blind grading of all 67 flips (Codex inline, Claude independent, saved before the key was opened):

| | header arm right | control arm right | no verdict |
|--|--|--|--|
| Codex | 57 | 10 | 0 |
| Claude | 49 | 11 | 7 |
| Both agree | 49 | 6 | 12 |

  Agreed 49 : 6 (8 : 1), 55 agreed flips, rule 1 (>= 10 flips, >= 2:1, margin >= 5): met. By document (agreed): CNSSI header 38 / control 5; dafman17-1203 header 8 / control 0; dafpam90-803 header 3 / control 1. CNSSI is 38 of 49 (78%), above the 70% call-out line: the result is mostly the CNSSI parameter table (Table E-1: "| AC-7 | a. [organization-defined number] | 3 |" now reads as a required value). Outside CNSSI: header 11, control 1. Where both graders gave a verdict and disagreed with each other (Claude NO / Codex YES) the flips are four dafman17-1203 condition-code definition rows ("F | Use when the asset may still be utilized"): I call them not requirements, Codex calls them requirements; not counted.
- Gold (table-chunk units only, PREREG8 scorer): pooled recall 20.83 -> 20.83 (10 of 48 both); precision 8.77 -> 8.00 (-0.77 points; rule: no worse than -1.0): met, but close. CNSSI gold (2 requirements in these units, 97 table rows inside gold units) 0 / 0.0 both arms; dafman17-1203 25.0 / 100.0 unchanged; dafpam90-803 precision 33.3 -> 20.0 (1 of 3 -> 1 of 5). The precision loss is rows the gold calls not-requirements and the blind graders called requirements (one CNSSI SC-28 parameter row, graded YES by both). The gold and the grading standard disagree about parameter-value rows; gold has almost nothing to say about tables.

## 4. Unanticipated finding
16 clauses that are NOT grid lines also flipped (CNSSI 11, dafpam90-803 4, afi10-2402 1), though their own context did not change: they sit in the same batch of four as a changed clause, or they are table cell continuation lines (a wrapped cell like "At least annually if not otherwise defined in formal organizational policy." that does not start with '|'). The rule gives no header to those continuation lines. They were not graded (outside the registered metric). Batch neighbours influence labels; this is a property of the labeler, not of the rule.

## 5. Limits
Six documents, one run per arm; the labeling standard for "required value" in parameter tables is judgment, and a stricter reading ("a table cell is not a requirement") would reverse most of the 55 header-right CNSSI calls, so the pass depends on counting a parameter value as an auditable requirement (Tyler's call); CNSSI dominates; only table-chunk clauses were labeled; the author is one of two graders; gold is coarse here; headers where Docling mistook a data row for a header are shown as found; continuation lines are not covered; the header arm adds 49 rows (+23%) in table chunks (43 among grid lines, 6 on other clauses), so the checklist grows with parameter-value rows.

## 6. Recommendation
Adopt, as a separate decision for Tyler because it changes the labeler's input for table lines and so needs the table chunks of the library re-labeled (a stop-and-ask item): the change is small and context-only. A PROPOSED commit follows on this branch.
