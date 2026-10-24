# PREREG10 report: the section heading as the lead-in of a list that has none (PROPOSED, not adopted)

Run 2026-10-24 on main ed320c9 plus the PROPOSED code in this PR. Rules written and committed before any model run: `PREREG10.md` (commit 8e374b9; Amendment 1, dropping the three-word rule for two words and no dangling preposition, committed in d209e65 before any model run, after no-model counts only). Numbers: `PREREG10_metrics.json`; flips and blind grades: `PREREG10_flips.json`; the hand-read sample: `PREREG10_lead_in_sample.txt`. Model `ornith:35b`, frozen prompt v3 (same sha both arms), whole documents, one model job at a time, no unparsed or failed batch in any arm.

## Verdict by the written rule: NOT CONFIRMED (the F3 target is met; the model-side flip rules cannot be judged)
| rule | result |
|---|---|
| 1 F3 down at least 30%; F8 unchanged; F2, F4, F7 not up | HOLDS. F3 377 -> 249 (down 34.0%). F8 0 -> 0. F2 20 -> 19, F4 2 -> 2, F7 45 -> 45. |
| 2 pooled recall within 1.0 point | HOLDS. 95.37 -> 95.13 (change -0.23) |
| 3 pooled precision within 1.0 point | HOLDS. 80.69 -> 79.96 (change -0.72); without CNSSI 89.65 -> 88.77 (-0.88) |
| 4 gold flips, correct >= wrong | THIN (3 judged, fewer than 4): 1 correct, 2 wrong |
| 5 blind-graded flips, heading right >= control right | CANNOT BE JUDGED: 2 flips with agreed verdicts (1 for each arm); Codex and Claude disagree or Claude says UNSURE on the other 3 |
Per the written rule a rule 5 that cannot be judged gives NOT CONFIRMED, not PASS. Adoption is not recommended as built (see "What I would not adopt" below).

## Measurement 1, no model: the explained layer on the 23 documents (6,773 rows)
`renormalize_explained.py` rebuilt only the explained layer, with the heading rule switched off (control, reproduces the baseline exactly: F1..F9 identical to the re-run) and on:
| count | control | heading |
|---|---|---|
| F3 list scraps with no lead-in | 377 | 249 |
| F9 rows with a lead-in | 974 | 1,855 |
| F2 / F4 / F7 / F8 | 20 / 2 / 45 / 0 | 19 / 2 / 45 / 0 |
| F5 / F6 | 157 / 422 | 157 / 421 |
F3 fell by 128, exactly the "heading" row count from the cause classification; those 128 were all resolved. By document (F3): DODI 5200.01 42 -> 6, DODI 8410.03 78 -> 40, CJCSI 6510.02G 55 -> 26, DODI 5200.44 37 -> 27, DODI 5200.48 89 -> 80, afpd_17-1 6 -> 0.
**What the F3 number hides:** F9 rose by 881, not 128. The rule also gives a heading to list items the F3 count does not call list items (paragraphs and bullets whose stored quote has no marker, mostly AF-style numbered paragraphs "2.9.3. Identify ..." under a heading such as "AFNC3C will:"). Where the rule fires it is usually right, but not always (next section). The PREREG5 F3 target (down 50% from 513, to 257 or fewer) is also met by this change: 249.

## The 881 rows that gained a lead-in: hand reading (author, not blind)
Seeded stratified sample of 63 rows (`lead_in_sample.py --n 60 --seed 11`; list in `PREREG10_lead_in_sample.txt`). My reading: right 43 (68%), wrong 15 (24%), unclear 5 (8%).
- The wrong ones cluster: 12 of the 15 are `dafi36-2903` (175 of the 881), where the heading is a topic title that happens to end in a colon ("2PFDU Wear Guidance:", "Occupational, qualification or skill badge order of precedence:") and the rows under it are ordinary rules, not a governed list. The rest are a numbered paragraph with its own subject ("3.15. The General Counsel ... will ..." given "All HAF Functionals ... will:"), a sentence with its own subject given "The SCA:", and a definition sentence given "Capital IUS - is recognized as capital if it meets the following criteria:".
- Without `dafi36-2903` the sample is 51 rows: right 43, unclear 5, wrong 3 (6%).
- Over the 10% warning line of the written rule. It is a warning, not a fail.
Two causes I can name from the cases: (a) a heading that names a topic ends in a colon but does not introduce a list; (b) the chunk's section path is that of the section the chunk started in, so a clause after a later numbered heading in the same chunk gets the first section's heading (3 of the 5 model flips below: "10. CJCS." and "12. CDRUSSTRATCOM." clauses were given "The DOT&E shall:").

## Measurement 2, model: control (current main) vs heading, 11 sealed documents (7,623 clauses)
Pooled (gold reqs 863): recall 95.37 -> 95.13 (-0.23), precision 80.69 -> 79.96 (-0.72), rows 2,543 -> 2,553. Without CNSSI (853): recall 95.55 -> 95.31, precision 89.65 -> 88.77. Seconds 2,943 / 2,865. Label agreement control vs heading 99.3% (7,570 of 7,623).
| document | gold reqs | control R / P | heading R / P | clauses with a different lead-in |
|---|---|---|---|---|
| afi17-203 | 103 | 94.17 / 85.04 | 94.17 / 85.04 | 0 |
| afi13-550 | 69 | 100 / 97.56 | 98.55 / 96.34 | 106 |
| DODI 5200.01 | 62 | 96.77 / 83.33 | 96.77 / 83.33 | 58 |
| afi17-101 | 133 | 94.74 / 90.78 | 94.74 / 90.14 | 90 |
| afman17-204 | 90 | 91.11 / 88.89 | 90.00 / 87.00 | 36 |
| DODI 5200.48 | 110 | 98.18 / 90.60 | 99.09 / 87.70 | 13 |
| DODI 8551.01 | 57 | 96.49 / 81.82 | 96.49 / 81.82 | 0 |
| dafman17-1301 | 88 | 95.45 / 94.32 | 94.32 / 93.18 | 0 |
| dafman17-1203 | 120 | 94.17 / 94.96 | 94.17 / 94.96 | 22 |
| NIST.SP.800-125 | 21 | 100 / 76.92 | 100 / 76.92 | 0 |
| CNSSI_No1253 | 10 | 80.0 / 7.02 | 80.0 / 7.02 | 0 |
**The labeler hardly reacts to the heading.** Of 325 clauses whose lead-in changed, 3 changed requirement-ness (0.9%). But the run noise is just as large: of 7,298 clauses whose lead-in did NOT change, 35 changed requirement-ness between the two runs (0.5%; 17 of them in dafman17-1301, 8 each in afman17-204 and DODI 5200.48). So the per-document dips (dafman17-1301 -1.14 recall with 0 changed contexts; DODI 5200.48 precision -2.89) are mostly or entirely run noise. **The PREREG8 noise floor of "1 clause in 2,289" was too small; this run shows about 5 in 1,000 clauses.** A pooled change of under one point cannot be told from noise with this design, in either direction.

Report-only documents (`--secondary`, 660 clauses, 120 with a different lead-in; burned for prompt tuning, not for this change): pooled recall 96.30 -> 96.71, precision 91.89 -> 91.57; DODI 8410.03 precision 83.93 -> 79.66 (2 requirement flips), CJCSI 6510.02G 94.74 -> 96.81. Noise not separable here either.

## Every requirement flip (5: 3 in the sealed set, 2 report-only), with gold status and the blind grades
| # | doc | change | new lead-in | clause | gold | Codex | Claude |
|---|---|---|---|---|---|---|---|
| 1 | DODI 8410.03 (report-only) | not-req -> DUTY | "The DOT&E shall:" (wrong party) | "The CDRUSSTRATCOM, in addition ..., shall:" | inside, heading wrong | YES (heading right) | UNSURE |
| 2 | afman17-204 | DUTY -> not-req | "The 81st ... Flight will:" | "Refer to Attachment 5 for information request ..." | inside, heading correct | NO (heading right) | NO (heading right) |
| 3 | DODI 8410.03 (report-only) | not-req -> DUTY | "The DOT&E shall:" (wrong party) | "The CJCS, in addition ..., shall:" | outside gold | YES (heading right) | UNSURE |
| 4 | afi17-101 | not-req -> DUTY | "The SCA:" | "This position may be an organic or contracted resource." | inside, heading wrong | YES (heading right) | NO (control right) |
| 5 | afi13-550 | DUTY -> not-req | "Deputy Chief of Staff for Operations (AF/A3) will:" | "AFMC designates the Air Force Nuclear Weapons Center ... as the designated Principle Integrator ..." | inside, heading wrong | YES (control right) | YES (control right) |
(Numbering here is mine; the blind file used a shuffled order. Gold-judged flips: #2 correct, #4 and #5 wrong in the sealed set; #1 wrong in the report-only set.) Agreed blind verdicts in the sealed set: #2 heading right, #5 control right.
Blind method: neutral file with document name, section path, about 600 characters before and after, no arm labels, no gold, shuffled (`heading_blind_build.py`). Codex (`codex exec`) was given no arm information. **Disclosure:** Claude (the author's session) had already seen the arm labels and gold verdicts of all five flips in the metrics output before grading, so its grades are not blind; only Codex was. Graders disagree on 3 of 5.

## What this says in plain words
1. The heading lead-in does what it was built for: F3 down 34% (to 249; PREREG5's 50% line from 513 is also passed), all 128 heading rows fixed, no F2/F4/F7/F8 rise, and the checklist still builds.
2. It does it on a wider base than F3 counts: 881 rows get a heading, and about a quarter of the ones I read are the wrong lead-in (a topic title that ends in a colon, a numbered paragraph with its own subject, a chunk that spans two sections). One document, `dafi36-2903`, is half of the wrong ones.
3. For the labeler the change is close to a no-op (3 requirement flips in 325 changed contexts), smaller than run-to-run noise. Recall and precision stay within a point, but the test cannot tell a gain from a loss.

## What I would not adopt, and what I would try next (needs a new PREREG)
- Not as built: one document in four, a wrong lead-in on about a quarter of new attachments, is a real cost to the checklist reader, for an F3 count that is only a fragmentation proxy.
- A narrower version with two guards: (a) apply a heading only when it names a party with a modal or "that" ("The DoD CIO, shall:", "It is DoD policy that:", "AFNC3C will:"), not when it is a topic title; (b) skip the heading when the chunk contains a later numbered heading line before the item (the chunk's path is the first section's). Rough no-model sizing already seen: a modal-only rule alone loses 73 of the 128 F3 rows (to 304, down 19%), so it would need the party-colon forms ("The DoD CIO:") allowed and a different guard against topic titles. That is a design problem, not a quick edit.
- The other 69 F3 rows (lead-in more than one chunk back) are a separate, equally large lever; some of their matches are wrong too (a sub-list line two chunks up). Not measured.
- 164 of the F3 rows left have no governing line that any lead-in rule could find: standalone lettered or numbered paragraphs (120), the same under the page-header path "UNCLASSIFIED" (15), letter and form templates (15), and an item that itself heads a sub-list (14). Another 16 are a colon line rejected as a sibling (12) or a lead-in sentence that ends in a period (4).

## Limits
Pooled gold covers sampled paragraphs only and 3 of the 11 documents carry most of the heading cases; the pooled difference of 0.2 to 0.7 points is below the measured noise (5 per 1,000 clauses), so rules 2 and 3 "hold" without proving harmlessness or benefit. Rules 4 and 5 had 3 and 2 usable flips. The F3 result is a measurement of the explained layer on the same 23 documents that suggested the fix, not a held-out test. The cause classification and the lead-in sample are author-read (not blind). The checklist's draft-question passage window looks for the lead-in as a line of the chunk text; a heading lead-in is not such a line, so the window may not show it (not measured). No change to the live library, config or frozen prompt.
