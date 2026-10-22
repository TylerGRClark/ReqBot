# Clause labeling vs list extraction: result (2026-10-22)

Rules, arms and pass/fail were fixed in PREREG.md (commit 3845e98) before any result. Prompt wording changed twice on TUNE documents (v1 to v3, `scripts/TUNE_LOG.md`), then frozen (sha256 b9b20379...). EXAM documents were run once per arm, no change afterwards. Scripts in `scripts/`; the data (silver set) is internal and not in this repository.

## Verdict: PASS (both arms)
EXAM pooled, 613 labeled requirements, 6 documents:

| arm | recall | precision | unit skip rate | flagged per 100 labeled | calls / seconds |
|---|---|---|---|---|---|
| B0 stored production rows | 82.2% | 72.6% | 13.9% | 110 | 0 |
| L8 (8B labels every clause) | 95.6% (+13.4) | 77.5% (+4.9) | 3.6% | 123 | 313 / 247 |
| L35 (35B labels every clause) | 92.7% (+10.5) | 92.6% (+20.0) | 5.9% | 99 | 313 / 519 |
| L8 then shipped 35B YES/NO check | 95.1% (-0.5 vs L8) | 83.8% (+6.3 vs L8) | 4.4% | 113 | +700 one-word calls |

Noise floor (TUNE, two seeded batch orders): about 1 point on recall and precision. Rule 1 picks L8 as primary (TUNE recall 94.7% vs 93.9%, a tie within noise); rule 2 (recall +8, precision not worse than -5, gain above noise) is met by L8 (+13.4, +4.9) and by L35 (+10.5, +20.0). L+C success rule (recall loss at most 1, precision up at least 5) is met on L8. Every EXAM document gains recall in both arms.

## What it means
Asking for a label on every clause instead of a list closes most of the gap the miss diagnosis found: paragraphs the extractor silently skipped fall from 13.9% to 3.6% (L8). The 8B finds the most requirements; the 35B is far more precise; the 8B plus the shipped 35B check gets high recall with better precision, at about 3 model calls per 4 clauses plus one short call per flagged clause.

## Limits (read before believing the numbers)
- Wording was tuned on TUNE; EXAM is the honest test. Units are paragraph-sized pieces, so a parent lead-in in an earlier paragraph is not shown (benefit underestimated), and the whole-document path (chunks, tables, cross-references) is not tested.
- Truth is two copies of one model family (owner spot check owed). Precision is relative to their lists, so it is a lower bound: some "false positives" are real requirements both labelers missed (a blind check of that follows in a separate note).
- B0 is the stored production rows, scored on the same units with the same matcher.
- 12 documents; dafpam90-803 (a guidance pamphlet, 38 requirements) is weak for every arm.
- Not tested: running time on a full 300-page document, effects on the checklist, Step D, tags and questions, the cost of re-extracting the library.

## What this does NOT decide
Nothing is adopted. A production version would replace the extraction call design (new model-call pattern, re-extraction of the library): the owner's approval is required before any build.
