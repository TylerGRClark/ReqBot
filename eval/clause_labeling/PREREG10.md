# PREREG10: the section heading as the lead-in of a list that has none (PROPOSED, not adopted)

Written 2026-10-24 on main ed320c9, committed BEFORE any model run for this experiment. The only things computed so far are no-model counts on the 23-document re-run (`~/reqbot-work/scratch/full_rerun_2026-10-24`) that sort the 377 F3 rows by cause. Do not edit after a result exists; if a bug is found, fix it, say so, and rerun everything.

## The finding this acts on
After the switch to clause labeling, `fragmentation.py` on the full 23-document re-run (6,773 rows, 0 failed batches) shows **F3 = 377** list-item rows with no lead-in attached (before the switch: 513; PREREG5 wanted a 50% drop, so 257 or fewer). PREREG5's F3 target is therefore not met (down 26.5%).

## What the 377 are (cause classification, no model)
Sorted by `eval/clause_labeling/f3_causes.py` (heuristics, first match wins; I read about 60 rows across the groups by hand, not a blind review). Counts from the scratch version of the same logic, which the committed script is expected to reproduce:

| cause | rows | example |
|---|---|---|
| 1. Heading lead-in: the nearest real section heading ends in a colon or modal ("The DoD CIO, shall:") and the chunk text starts at the list | 132 | DODI 8410.03 chunk 6: path `['1. DoD CHIEF INFORMATION OFFICER (DoD CIO). The DoD CIO, shall:']`, text begins `- a. Provide strategy, policy ...` |
| 2. Lead-in is in the text but more than one chunk back (finder looks back one chunk only, and a sibling list item that ends in a colon sends it further back) | 69 | CJCSI 6510.02G chunk 10: `The process will be as follows:` two chunks up; some of these are wrong matches (see below) |
| 3. A colon line earlier in the chunk that the finder rejected as a sibling | 12 | DODI 5200.48 chunk 0 "Establishes ..." bullets after `Originating Component:` (a front-matter field, not a lead-in) |
| 4. The item itself ends in a colon (it heads a sub-list; it has no lead-in of its own) | 14 | DODI 5200.48 chunk 70 "e. To ensure CUI protection, the following measures will be implemented:" |
| 5. Form or letter template with numbered statements | 15 | dafman17-1305 "2. I must meet annual continuing education requirements ..." |
| 6. The lead-in is a sentence that ends in a period | 3 | dafpam90-803 "The ETBA involves five basic steps as shown at Figure A4.1." |
| 7. Nothing governs the item: standalone lettered or numbered paragraph, bullet after a plain sentence | 110 | DODI 5200.48 chunk 64 "a. The USD(I&S) will notify ..." under a heading with no colon |
| 8. Same, and the path entry is page-header junk (CJCSI 6510.02G, `UNCLASSIFIED`) | 22 | CJCSI 6510.02G chunk 26 "k. Provide COMSEC keying materials ..." |
| lead-in in previous chunk but blocked by a junk-changed section path | 0 | - |

Notes. (a) 28 rows in all have `UNCLASSIFIED` as the last path entry (21 as the whole path); skipping it recovers a heading for only 1 of them, because the real heading is not in the path at all on those pages. (b) The heading cause (132) is the number Tyler's note named. (c) In 27 of the 132 a text lead-in more than one chunk back also exists; in the cases I read it names a different role than the heading (DODI 8410.03 chunks 11-12: a DISA paragraph two chunks up, but the list is the DoD CIO's), so the heading is the better lead-in there. (d) Cause 2 (69 rows beyond the 27) is a second, separate fix (look back further) that is NOT part of this change, and its matches are not all right (DODI 8551.01 chunk 9 would get "Appoints a DoD military officer ...:" as a lead-in). It is listed as a follow-up. (e) A heading that ends in a colon is not always a lead-in: CJCSI 6510.02G memo header `Reply to :` (4 rows) is a label. The proposed rule therefore requires at least three words (see below).

## Proposed change (the arm "heading"; code in this PR, not merged)
`pipeline/lead_in.find_lead_in` gets an optional `heading_path` (the chunk's `section_title_path`). When the finder finds no lead-in AND the item is a list item (marker style, not a plain sentence and not a bare-number line) AND no plain paragraph comes before the item in its chunk or in the previous chunk of the same section, the lead-in becomes the nearest governing heading:
- the nearest path entry that is not page-header junk (junk = `UNCLASSIFIED`, `CUI`, `FOUO`, a classification banner, a bare page number); only that one entry is looked at (never climb past it);
- it counts only if it ends in a colon (also after a tier tag, as the finder already allows) or in a modal word (shall, will, must, should, may);
- its text is the last sentence of the entry without its paragraph number or heading number ("1. DoD CHIEF INFORMATION OFFICER (DoD CIO). The DoD CIO, shall:" becomes "The DoD CIO, shall:"), at most 300 characters (same cap as now), and at least three words ("Reply to :" and "SCENARIO:" are labels, not lead-ins).
Both consumers pass the heading: `document_clauses` (the labeler's "Lead-in line above:") and `explain_records` (the explained text; part kind `lead_in`, origin `rule`). Nothing else changes: frozen prompt text and sha, model, temperature, batch size, clause cuts. The root (`source_quote`) is never touched. No opt-in switch (Tyler's replace rule); if it fails the pass rules it is not merged.

## Measurement 1, no model: F3 and the other counts
Re-run only the normalizing step (`explain_records`) on the existing 6,773 rows of the 23-document re-run, with and without the change, into scratch copies; then `fragmentation.py` on each. Labels are unchanged in this step, so only the explained layer moves.
- **F3** must fall by at least 30% overall against the 377 baseline (to 263 or fewer). Per-document numbers are reported.
- **F8** must stay exactly as it is (0 expected; the root is never changed). **F2, F4, F7 must not rise.** (Tyler's note said "no change". A lead-in in front makes the shown text longer and capitalised, so F2/F4/F7 can fall; a fall is good and is reported with the reason. A rise is a fail.) F5, F6 reported; F9 will rise by about the F3 drop and is reported.
- Every row that gains a lead-in is listed; I hand-read at least 40 random ones (all of them if fewer) and report how many are the wrong lead-in. More than 10% wrong in my reading is a warning, not a fail (author-read, not blind).

## Measurement 2, model: labeler arms on the sealed gold documents
Arms (one model job at a time, never two; no `local_review.py` while running): **control** = current main behaviour (find_lead_in without heading, which is the unchanged function), **heading** = the change. Same frozen prompt v3 (sha b9b20379...), `ornith:35b`, batch 4, num_ctx 8192, num_predict 300, whole documents, driver `heading_run.py` (copy of the PREREG8/9 driver, two arms, same clause list and batches; only the lead-in text differs). A document whose contexts do not change is still run in both arms (the batches are identical, so it also measures run noise).
Documents (11, the PREREG8 seven and the PREREG9 four, gold and silver exam units as in PREREG8/9, scorer = PREREG8/9 scorer unchanged; CNSSI_No1253 gold file as in PREREG9): afi17-203, afi13-550, DODI 5200.01, afi17-101, afman17-204, DODI 5200.48, DODI 8551.01, dafman17-1301, dafman17-1203, NIST.SP.800-125, CNSSI_No1253.
Exposure honesty: the heading fix was designed after reading the F3 rows of all 23 documents, so DODI 5200.01, DODI 5200.48 and DODI 8551.01 (heading cases among them) were seen as text but no model output of these arms exists. No document is tuned on: nothing changes after a run. Only 3 of the 11 contain many heading cases; the gold sample covers only some paragraphs, so judged flips will be few.
Secondary, reported not judged, run only after the primary result is saved: DODI 8410.03, CJCSI 6510.02G, DODI 5200.44, where most heading rows are (all three are burned for prompt tuning in REPORT4/silver; the change is not tuned on them). Gold exists for them only as TUNE units.

## Pass rules (all must hold; fixed now)
1. F3 down at least 30% (measurement 1); F8 unchanged; F2, F4, F7 not up.
2. Pooled over the 11 documents: recall(heading) >= recall(control) - 1.0 point.
3. Pooled over the 11: precision(heading) >= precision(control) - 1.0 point. (1.0 = the PREREG8 noise floor of 1 clause in 2,289, rounded up; the pooled-without-CNSSI numbers are also printed.)
4. Gold flips: among requirement flips (row <-> not a requirement) whose clause lies in a gold unit, correct >= wrong (verdict as in PREREG8/9). Fewer than 4 judged flips is "thin": reported, and rule 5 decides.
5. Blind grading of all requirement flips: the flips are written to a neutral file (clause, document name, about 600 characters of source before and after, order shuffled, no arm label, no gold label, no earlier grade) and graded by two graders, Claude (graded before reading the other) and Codex (`codex exec`, second model family, prompt carries no arm information), as in `~/reqbot-work/notes/blind_flips_result_2026-10-24.md`; standard: a duty, prohibition or permission placed on a stated party that an auditor could check; UNSURE counts as no verdict. Among flips where the two graders agree, "heading arm right" >= "control arm right".
Verdict PASS only if 1 to 3 and 5 hold, and 4 holds or is thin. Otherwise FAIL. If rule 5 cannot be judged (fewer than 4 agreed verdicts) the verdict is NOT CONFIRMED, not PASS. A PASS means the change did not measurably hurt and removed fragmentation; adopting it still needs Tyler's decision and a library re-run (it changes the explained text and what the labeler sees).

## Also reported (not part of the pass)
Flip list with old context, new context, label change and gold status; label agreement control vs heading; rows, seconds, unparsed or failed batches (any unparsed or failed batch invalidates that arm and it is rerun); how many clauses get a different context (no model, before any run); the 69 "lead-in more than one chunk back" rows as the next candidate fix.

## Limits stated in advance
One run per arm; no repeat arm (noise floor from PREREG8: repeat control differed on 1 of 2,289 clauses); gold is two model families, precision a lower bound; the F3 test is on the same 23 documents that suggested the fix (it is a measurement of the explained layer, not a held-out test); the cause classification is heuristic and author-read; the author reads the lead-in samples; blind graders are two models, no human.

## Amendment 1 (2026-10-24, still before any model run; only no-model counts exist)
Writing the code showed that the "at least three words" rule in the proposal drops legitimate lead-ins such as "DISA will:" and "CCDRs will:" (15 of the heading rows). Replaced by: at least two words, and the heading's last word is not a preposition (to, of, for, by, with, from, on, in, at, per), which still excludes the memo header "Reply to:". Nothing else in the proposal or the pass rules changes. The committed script `f3_causes.py` is the authoritative classification (the table above came from a scratch version with slightly different tie-breaking). Its counts on the 377 rows, first match wins:

| cause (script name) | rows |
|---|---|
| heading (rule above applies) | 128 |
| further (lead-in more than one chunk back, other fix) | 69 |
| self_head (item ends in a colon) | 14 |
| sibling (colon line rejected as a sibling) | 12 |
| form (letter or form template) | 15 |
| period (lead-in sentence ends in a period) | 4 |
| none_junk (nothing governs; path entry is `UNCLASSIFIED`) | 15 |
| none (nothing governs) | 120 |
| junk_blocked | 0 |

Rows with `UNCLASSIFIED` as the last path entry: 21 (not 28). Expected F3 after the change if every heading row resolves: 377 - 128 = 249 (down 34.0%); the 30% line is 263, so at most 14 of the 128 may fail to resolve for the F3 rule to pass.
