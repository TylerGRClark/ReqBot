# PREREG9 report: confirmation of the lead-in labeler context (arm `rule`) on four untouched documents

Run 2026-10-23/24, base main 3c0990a + proposed commit 5b5c511, `ornith:35b`, frozen prompt v3 (same sha both arms), whole documents, one model job at a time, no unparsed or failed batch in either arm. Rule written and committed before any run: `PREREG9.md`. Numbers: `PREREG9_metrics.json`; every flip and the number-start cases: `PREREG9_flips.json`. Scorer = PREREG8 scorer (`label_ctx_metrics.py`) unchanged plus the CNSSI gold file (`confirm_metrics.py`). Nothing tuned.

## Verdict by the written rule: NOT CONFIRMED (not a fail)
- Rule 1 recall within 1.0 pooled: HOLDS (94.14 -> 94.14, change 0.00).
- Rule 2 precision within 1.0 pooled: HOLDS (64.64 -> 64.27, change -0.37; without CNSSI 93.07 -> 92.27, -0.80).
- Rule 3 net flips against gold, correct > wrong: CANNOT BE JUDGED. Only 12 requirement flips occurred in the four documents (of 5,334 clauses) and none lies inside a gold paragraph, so 0 judged flips (the rule needs at least 4). Per PREREG9 that is "not confirmed".
Plainly: the rule did nothing harmful that the gold can see, but the gold sample is too thin on the flipped clauses to confirm the earlier gain. The earlier PREREG8 gain (+0.6 recall, +1.2 precision) is not reproduced here and not contradicted.

## Numbers (gold requirements: 239 pooled; 229 without CNSSI)
| scope | gold reqs | control R / P | rule R / P | change R / P | rows control / rule |
|---|---|---|---|---|---|
| pooled 4 | 239 | 94.14 / 64.64 | 94.14 / 64.27 | 0.00 / -0.37 | 1370 / 1380 |
| pooled without CNSSI | 229 | 94.76 / 93.07 | 94.76 / 92.27 | 0.00 / -0.80 | 1169 / 1182 |
| dafman17-1301 | 88 | 95.45 / 94.32 | 94.32 / 93.18 | -1.14 / -1.14 | 464 / 467 |
| dafman17-1203 (silver gold) | 120 | 93.33 / 95.73 | 94.17 / 94.96 | +0.83 / -0.77 | 575 / 586 |
| NIST.SP.800-125 | 21 | 100 / 76.92 | 100 / 76.92 | 0 / 0 | 130 / 129 |
| CNSSI_No1253 (tables) | 10 | 80.0 / 7.02 | 80.0 / 7.02 | 0 / 0 | 201 / 198 |
Seconds (control / rule): 2093 / 2075 pooled. Label agreement control vs rule: 98.8% (5,268 of 5,334 clauses). Clauses whose context changed: 239 (dafman17-1301 45, dafman17-1203 93, NIST 61, CNSSI 40); only 12 changed row / not-row.
Single-document dips of 1.14 points on dafman17-1301 are 1 requirement of 88 and 1 row of ~88 in gold units (one clause), i.e. at the size of the noise floor (PREREG8: repeat control differs on 1 of 2,289 clauses); the pooled rule is the one that counts.
CNSSI: gold has only 10 requirements and 201 rows were flagged in a document of ~2,000 table lines, so its 7% precision says the gold is not informative on tables, not that the labeler is poor; recall 8 of 10 in both arms. Tables: rule changed 40 contexts and 5 labels in CNSSI, all in prose lists (see below), none in table lines as far as the flips show.

## Every requirement flip (12), with my hand reading (author, not blind; none is in a gold paragraph, so none is scored)
| # | doc | change | old context -> new context | clause | my reading |
|---|---|---|---|---|---|
| 1 | dafman17-1203 | not-req -> DUTY | "IT assets ... managed by this manual if" -> none | "The IT components meet the requirements of paragraph 2.4.3 or 2.4.4 ... (T-1)." | right (tier tag) |
| 2 | dafman17-1203 | DUTY -> not-req | none -> "Capital Assets will:" | "Have a valid fund code assigned within DPAS." | wrong (a "will" duty) |
| 3 | dafman17-1203 | not-req -> DUTY | none -> "Capital Assets will:" | "POC for fund codes will be the servicing resource advisor ..." | unclear (assigns a role) |
| 4 | dafman17-1203 | not-req -> DUTY | none -> "To perform an asset inventory, the PC will:" | "- digitally signed email or memorandum certifying ... (T-1)." | right |
| 5 | NIST 800-125 | not-req -> DUTY | none -> "Aspects of the solution that should be evaluated include the following:" | "The virtualization solution does not interfere with ... guest OSs." | right (should counts) |
| 6 | NIST 800-125 | DUTY -> not-req | same lead-in | "The internal networking ... can be configured to conform to the organization's security policy." | wrong (same list as #5) |
| 7 | NIST 800-125 | DUTY -> not-req | same lead-in | "Administrators can configure and manage the solution effectively and securely." | wrong (same list as #5) |
| 8-12 | CNSSI | DUTY -> not-req (5 items) | none -> "The common controls identified in Table D-2 are based on the following assumptions:" | five "- Common controls may be allocated ...", "Organizations have established services ...", "Information systems are located in physical facilities ...", "Authorization boundaries have been established ...", "A single authorization boundary will be established ..." | right (assumptions, not duties) |
Tally by my reading: right 8 (1, 4, 5, 8-12), wrong 3 (2, 6, 7), unclear 1 (3). Same direction as PREREG8 but unscored, clustered (3 lists), and author-read.

## Number-start failure (the "24 AF is designated as ..." case)
Over the four documents, 19 clauses start with a bare number and a word. `rule` gave a lead-in to 2 (10.5%), both in CNSSI: "2 Examples of systems that may diverge from the assumptions include ..." and "8 All of the guidance in NIST SP 800-53, Section 3.2 applies to NSS ...". Both are footnote-style plain sentences, so the lead-ins ("...The NIST SP 800-53 assumptions are:" and "To tailor the initial security control set, complete the following activities:") are wrong; both clauses were not-requirement in BOTH arms, so no label changed. The "13. (b) Sentence" form: 0 cases. So the failure exists at a small rate (2 of 19) but did no harm here (0 label changes from it). It is the cause of one of the 7 wrong flips in PREREG8, so tightening `find_lead_in` for a bare number not followed by a marker remains a cheap, separate fix.

## Limits
Four documents, one run per arm, no repeat (PREREG8 noise floor reused; labeler near-deterministic there). Gold is sampled paragraphs only and none of the 12 flips fell in one: the test is underpowered on exactly the clauses the change touches (only 12 of 5,334). dafman17-1203 gold is silver (older, weaker). CNSSI gold has 10 requirements. Flip reading is by the author. Gold units of three documents were exposed to this frozen prompt in REPORT4 (not tuned). Wall-clock timing unaffected by the rule (2,075 s vs 2,093 s).

## What would settle it
Hand-grade the 12 flips plus a sample of the 239 changed contexts with a blind reviewer, or label the flipped neighbourhoods as new gold units. The decision to adopt #372's commit does not depend on this: the rule is neutral on the scored measures here and positive on the PREREG8 seven.
