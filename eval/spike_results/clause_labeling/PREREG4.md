# Clause labeling, round 2: a bigger, harder, two-family test set and proper prompt tuning (pre-registration, 2026-10-22, before any new label exists)

Owner direction (2026-10-22): 74 obligations is too small; build new test sets, repeat tests, and spend effort tuning the prompt instead of expecting the first one to be right.

## New test set "gold2"
- Documents never used in any earlier tuning or test with labels: TUNE = afi17-130, afi99-1, dafi36-2903 (table- and list-heavy), DODI 8410.03, afpd_17-1; EXAM = dafman17-1301, afi13-550, CNSSI_No1253 (non-Air-Force, table-heavy), DODI 5200.01, NIST.SP.800-125. (DODI 8410.03 and NIST 800-125 were used in the 74-obligation set; they keep that status: 8410.03 only as TUNE, NIST 800-125 as EXAM only for a clearly marked "reused document" line in the report.)
- Units: paragraph-sized pieces drawn by the same seeded sampler as the silver set (seed 20261023), about 80 per document where the document has that many, table-containing chunks oversampled to about a third for dafi36-2903 and CNSSI_No1253.
- Labels: two blind labelers from DIFFERENT model families, same written rules as the silver set (LABELING_RULES.md): A = a Claude copy, B = Codex. Each works in a private folder and sees only the paragraphs. A requirement is real if BOTH list it (as before); the share of items only one lists is reported per document.
- Owner check: a seeded sample of 50 agreed items and all-or-up-to-30 disputed items goes to the owner as a spreadsheet; his rulings are reported next to the model labels (agreement of the labelers is not correctness).
- Baseline B0: the stored production rows of each unit (as in the silver set).

## Prompt tuning protocol
- Starting point: the frozen v3 prompt (sha256 b9b20379...). It is also the control and is run on gold2 EXAM at the end unchanged.
- Tuning is done on gold2 TUNE only, with the 35B (primary candidate) and the 8B. At most 6 rounds; each round changes ONE thing, is logged (what, why, TUNE numbers before and after, noise floor) before the next. Candidate changes, in this order: (1) batch size 1 versus 4; (2) wording that separates a duty from a system description; (3) show tier tags (T-n) and the document title in the context line; (4) ask for a one-line reason before the label; (5) few-shot examples taken only from the silver TUNE units (never from gold2); (6) two-step decomposition (is it normative? then which kind?). A change is kept only if TUNE recall or precision improves by more than the noise floor with the other not worse by more than 1 point.
- Then FREEZE the best prompt (sha256 recorded) before any gold2 EXAM unit is labeled by a model run.

## EXAM run and decision rules (fixed now)
- Frozen best prompt and the control v3, 35B and 8B, 3 seeded batch orders each. B0 on the same units.
- PASS for the best prompt (35B): mean recall at least B0 + 8 points on gold2 EXAM pooled, precision at least B0 + 10 points OR at least B0 - 5 with recall at least B0 + 12, gain larger than the noise floor, and no single EXAM document worse than B0 by more than 5 points on recall.
- Also reported, not pass conditions: table-containing units separately; per-document numbers; recall against the owner-ruled sample; the blind precision audit on a sample of unmatched flagged rows (a different reviewer, as before).
- Cross-check: the 74-obligation set and the silver EXAM numbers are re-run with the frozen best prompt as regression checks (a drop of more than 3 points versus v3 on either blocks adoption).

## Limits stated now
Two labelers now from different families but still models; owner sample is small; prompt tuned on gold2 TUNE only 5 documents; everything is paragraph-sized units, so whole-document behavior needs a separate test; no cost test beyond timing.

## What this does NOT decide
Production adoption. That needs the owner's approval of the design.
