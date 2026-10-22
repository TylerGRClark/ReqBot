# Clause labeling, second test (independent labeled set): results
Run 2026-10-22. Method frozen (prompt hash b9b20379...dbc4 verified). Pre-registration: wt-clause/eval/spike_results/clause_labeling/PREREG2.md. Code and raw outputs: this folder.

## Summary
1. The 35B (L35) PASSES the pre-registered rule: recall 94.6% vs baseline 70.9% (+23.6 points), precision 93.7% vs 76.1% (+17.6), noise floor 2.7 points.
2. The 8B (L8) FAILS only on the precision condition: recall 91.2% (+20.3 points, far above its 1.4-point noise), but precision 69.5%, which is 6.6 points under baseline (limit is 5).
3. Of the 24 obligations never found before, L35 finds 22 and 23 (two runs); L8 finds 21 and 21. (See the caveat on what "never found" means below.)
4. Workload: L35 flags 118.9 rows per 100 obligations (baseline 112.8); L8 flags 156.8, i.e. 39% more review work than the baseline.
5. Caution: the pages were used to design the baseline prompt, the set is 74 obligations on 3 documents (1 obligation = 1.4 points), and the scorer's match rule is lenient (a flagged clause that touches half of an obligation counts as finding it).
6. Nothing was tuned; both arms ran exactly once per seed with the frozen method.

## Table (mean of runs; baseline = mean of 6 stored 8B Step D runs)
| Arm | Recall (of 74) | Precision | Flagged / 100 obligations | Never-found (24) found | Gain vs base | Noise floor | Verdict |
|---|---|---|---|---|---|---|---|
| Baseline r1-r6 | 70.9% | 76.1% | 112.8 (83.5 rows) | 3-5 each run (5 in union) | - | - | - |
| L8 (seed1, seed2) | 91.9%, 90.5% = 91.2% | 71.6%, 67.3% = 69.5% | 154.1, 159.5 | 21, 21 | +20.3 | 1.4 | FAIL (precision -6.6) |
| L35 (seed1, seed2) | 93.2%, 95.9% = 94.6% | 93.6%, 93.8% = 93.7% | 117.6, 120.3 | 22, 23 | +23.6 | 2.7 | PASS |

Baseline per run: recall 70.3/71.6/73.0/71.6/70.3/68.9, precision 77.5/75.3/75.6/76.0/75.3/76.7 (spread of baseline recall 4.1 points; all arm gains are far beyond it).

## Per-document (recall / precision / flagged rows; obligations: afman17-2101 38, DODI 8410.03 20, NIST SP 800-125 16)
| Arm | afman17-2101 | DODI 8410.03 | NIST 800-125 |
|---|---|---|---|
| L8 s1 | 92.1 / 74.0 / 55 | 95.0 / 78.6 / 34 | 87.5 / 58.3 / 25 |
| L8 s2 | 86.8 / 74.5 / 52 | 95.0 / 75.9 / 35 | 93.8 / 48.4 / 31 |
| L35 s1 | 89.5 / 97.3 / 40 | 100 / 88.0 / 31 | 93.8 / 93.8 / 16 |
| L35 s2 | 92.1 / 97.4 / 41 | 100 / 91.7 / 30 | 100 / 88.9 / 18 |
(The per-document baseline was not broken out; only pooled.) L8's precision loss is concentrated in NIST (48-58%): the 8B flags descriptive sentences as duties (about 26-32 non-obligation hits overall vs 4-5 for the 35B).

## Decision rules applied mechanically
PASS = recall gain >= 8 points AND precision >= baseline - 5 points AND gain > noise floor. PROMISING = gain 4-7.9 with precision condition. L35: +23.6, precision +17.6, 23.6 > 2.7 -> PASS. L8: +20.3, precision -6.6 (fails the -5 floor) -> FAIL. Noise floor = absolute difference between the arm's two runs.

## Problems, adaptations, and what I could not verify
- The scorer accepted the records unchanged (records = {requirement_id, chunk_id, source_quote = flagged clause}); no new metric. Adaptations were logged before arm numbers in ADAPT_LOG.md (raw_text used, heading/ref from the chunk record, recall defined as status != 'none').
- "Never-found 24": old24_ids.json was built from other runs (B0a, B0b, T1, T1b), not from r1-r6. The six baseline runs here actually find 3-5 of those 24 (5 in union). So "24 never found" is not exactly "found by no baseline run". Alternative set: 20 obligations that no r1-r6 run finds; L8 finds 17 and 17 of them, L35 finds 18 and 19. Reported only, not a pass condition.
- Recall uses the scorer's lenient status != none; the scorer's stricter "primary" (fully covered) recall came out identical for every arm and baseline run except baseline (baseline mean 69.6%), so conclusions do not change.
- Baseline rows are after Step D filtering/normalizing, while arms output clauses straight from the raw chunk text; this is as PREREG2 specified, but the arms' quotes are whole clauses, which may match more easily than model-rewritten quotes. Whether clause-level recall this high holds for the downstream pipeline (checklist quality) was not tested.
- Unscored flagged rows (touching no labeled piece, 9-12 per run) are excluded from precision by the scorer; they are not counted as errors or successes.
- L35 ran with the unrelated cleanup job possibly active; it affects speed only (temperature 0). L8 took ~12 min per run, L35 ~2.5 min.
- Two seeds only; noise floor from two runs is a rough estimate. Llama 8B unparsed batches: 0 in all runs.
