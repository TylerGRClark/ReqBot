# WP-45.13 — trial of the inclusive extraction prompt (D1x) on the 13 documents (results)

Plan and rules: [docs/PHASE45_WP4513_PLAN.md](../../../docs/PHASE45_WP4513_PLAN.md) (merged before the run). One change: Step C's prompt replaced by the frozen D1 text (rendered prompt hash `7da34da9994793c5`, checked equal), everything else unchanged (model, chunk files `d2.94.0:T2_256`, Step D, parent stems). The prompt lives on a trial branch that is not merged. Baseline and noise floor: the two existing runs T2a and T2b. Scripts: `analyze_d1x.py`; outputs in `outputs/`.

Code note: the baseline ran at `cc0b67e`, the trial at main `f7cb892` plus the prompt change. Between them only the prompt file and four checklist-presentation files differ (`pipeline/checklist_export.py`, `services/checklist_audit.py`, `services/checklist_missed.py`, `services/checklist_service.py`), which Step C, Step D and the parent-stem reconstruction never import; the scorer was told to exclude exactly those five files (`--allow-code-diff`), so its same-code check was narrowed, not switched off.

## Registered rules

| rule | result |
|---|---|
| **R1 no loss** (at least 44 of 74; at most 4 paired losses) | **met**: 68 found (T2a 46, T2b 47); 3 obligations found by both baseline runs are not found (AFMAN-p004-013, AFMAN-p010-006, DODI-p012-003) |
| **R3 gain** (at least 6 above the higher replicate, 47) | **met**: +21 over the higher replicate; 23 obligations found by D1x and by neither baseline run |
| **R2 the added records are read** (owner rates a seeded sample of 40 of the added survivors; at least 60% requirement or partial) | **pending the owner's rating** of `outputs/d1x_additions_rating_sheet.md` (40 of 717 survivor quotes present in D1x and absent from both baselines, seeded 4513) |
| R4 losses read | the three losses are in `outputs/d1x_arms_report.json` (pairs `T2a vs D1x`, `T2b vs D1x`, with both arms' records) |

Where the 23 gains are: 11 on afman17-2101 pages 9 and 10 (the list region that flickers between identical baseline runs), 10 on NIST SP 800-125 (recommendations written with "should"), 2 on DODI 8410.03.

## Reported, not gating

- **Records grow a third:** 2,501 Step D survivors against 1,880 and 1,890 (+33%). By document: NIST SP 800-125 +115% (309 against 144 and 153), DODI 8551.01 +45%, AFI 17-203 +41%, DODI 5200.48 +38%, the others +15% to +32%.
- **Step D rejects more:** unrepairable fragments 87 (baseline 33 and 32), quotes not grounded in the chunk 92 (59 and 57), heading echoes 40 (25 and 24). Step C records rose from about 2,025 to 2,752 (+36%).
- **The same paragraphs, cut differently:** on AFI 17-203 the share of the 198 paragraph units covered by a survivor is unchanged (100, against 99 and 100), yet the document has 157 rows against 111 and 115, and the survivor quotes overlap the baseline at 0.35 (against 0.85 between the two baseline runs). The inclusive prompt returns finer pieces of paragraphs that were already covered, not new paragraphs.
- **More fragment hints on the AFI sheets:** AFI 17-203 rows with `starts_mid_sentence` 13 (baseline 6), `table_fragment` 14 (3), `quote_not_located_in_passage` 24 (4), `no_stated_actor` 11 (9); `possible_missed` 13 (12). AFI 13-550: 31 possible-missed against 13, 6 mid-sentence against 13. AFI 10-2402: 36 possible-missed against 50, 2 table fragments against 9.

## What this says

For the owner-labeled sample the inclusive prompt is a large, clean gain: 68 of 74 obligations against 46 and 47, with 3 losses, spread over all three labeled documents. For the AFIs that the checklist is for, it does not find more paragraphs; it re-cuts the ones already found into more and smaller records, with more fragment hints. Whether it is an improvement for the checklist therefore turns on the owner's rating of the added records and on whether finer pieces are wanted. Nothing is adopted. Adopting the prompt would also drop the profile's `obligation_verbs` line (the owner has paused the domain-profile work) and needs three tests to be updated (`test_wp_20_3.py` twice, `test_wp457_runners.py` once), forces re-extraction and a reindex, and is the owner's decision.

## Limits

Single model; the 74 labeled obligations are on three documents, two of which supplied the pages D1 was designed on; noise floor from two runs; the owner rates 40 of 717 added records, so a rating describes that sample.
