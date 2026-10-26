# PREREG12 report: section heading in the requirement text, and the context-index cut

Run 2026-10-25 against PREREG12.md (commit 35812a3) without changes to the rule. Library: newest run folder of all 23 documents (6,773 rows, 2,444 chunks). Throwaway collections `idxtest_control|head|head1` built, scored, and deleted; `grc_requirements` (6,773 points), `grc_context`, the live library and config were not written. Raw numbers: `PREREG12_metrics.json`, `PREREG12_probe.json`. One addition after the commit: `idx_cut_report.py` (the aggregation that applies the pass rule as written).

## Verdict
| Question | Result |
|---|---|
| Raise the context-index cut (3000, full) | No effect on search, by construction and by the probe. Not adopted. |
| Heading in the requirement text, full path (`head`) | FAIL, clearly worse (MRR -0.091, hit@5 -0.067). |
| Heading in the requirement text, last heading only (`head1`) | FAIL (MRR -0.018, hit@5 +0.011; "broad" questions -0.13). Not distinguishable from noise overall, worse on broad. |
| Best combination | Equals the heading arm (the cut cannot reach search); nothing to combine. No code change proposed. |

## 1. Context-index cut
- The vectors in `grc_context` are never searched. `core/ask.py` and `services/trace_service.py` only fetch a chunk by exact id to show text around a hit. The only production `query_points` call targets `grc_requirements`. So no cut value can change a hit, a rank or MRR. The stored text is the full chunk whatever the cut.
- Probe (what-if, chunk vectors ranked against the raw gold questions, 30 scored queries): cut 1500 MRR 0.5955, hit@5 0.667, hit@10 0.80; cut 3000 MRR 0.5958; full text MRR 0.5958, same hit@5 and hit@10. Embed time 10.0 / 10.2 / 10.8 s for all 2,444 chunks. A gain of 0.0003 against a 0.02 bar.
- How often the cut bites here: 217 of 2,444 chunks (8.9%) are over 1,500 characters, 122 (5.0%) over 3,000. Of 30 scored queries, 3 have a gold row in a chunk over 1,500 characters (10%), and only 2 (6.7%) have the gold quote itself past character 1,500; 2 of 118 gold rows. (The 5.9% of chunks in the question's brief did not reproduce on this library; my count is the chunk-length figure above.)
- Ollama truncates silently: texts that differ only after about 20,000 characters embed identically; the trained limit is 2,048 tokens (Modelfile `num_ctx` 8192). Past roughly 2,000 tokens the vector is blurred even before the hard cut.

## 2. Heading in the requirement text (prod mode: query rewrite + HyDE, no reranker; mean of 3 runs per arm, 30 scored queries)
| Arm | MRR | hit@1 | hit@5 | hit@10 | recall@10 | build s |
|---|---|---|---|---|---|---|
| control | 0.642 (runs 0.645, 0.625, 0.655) | 0.489 | 0.844 | 0.911 | 0.657 | 43.2 |
| head | 0.551 | 0.433 | 0.778 | 0.833 | 0.613 | 41.7 |
| head1 | 0.624 | 0.478 | 0.856 | 0.911 | 0.648 | 41.4 |

Noise (control spread over 3 runs): MRR range 0.030, hit@5 range 0.033. The pass rule needed MRR and hit@5 each up by at least max(0.02, range), no segment worse by more than 0.02, zero queries no worse, build time within +25%.

Segment MRR change vs control (prod): head narrow -0.020, broad -0.236, parent_child -0.000, table 0.000, messy_pdf -0.124. head1 narrow +0.004, broad -0.133, parent_child +0.107, table +0.083, messy_pdf -0.023. Build time: no cost (41-43 s each). Zero queries: all arms return 20 results (the search always fills the list), so that rule says nothing.

Both arms FAIL rule 1 (no gain beyond noise) and rule 2 (broad segment worse by more than 0.02). Neither is "equivalent" either: head1 is a trade, up on parent_child_context and table_derived (3 and 2 queries scored), down on broad.

Support modes (single runs): nohyde, control/head/head1 MRR 0.634 / 0.558 / 0.596, hit@5 0.767 / 0.667 / 0.733. rerank (not production), MRR 0.601 / 0.563 / 0.595, hit@5 0.767 / 0.733 / 0.800. Same direction: no mode shows the heading helping overall.

Why the full path hurts, as a reading (not tested): broad questions are answered by many rows spread across a document; the heading words pull a row toward rows that share a section title, so rows from the best sections crowd out rows from elsewhere. Short clauses already carry their lead-in in the explained text.

## Limits
30 scored queries (7 of 37 non-zero queries lost all gold rows in the re-pointing; 24 of 130 old ids have no live row); the gold set was written for the old method and re-pointed by a text rule I wrote and did not check row by row; the queries were used in earlier tuning (not blind). Segment sizes are 2 to 8 queries, so a segment number moves a lot on one query. HyDE noise: 3 runs per arm and a range of 0.03 on MRR. The remap can change which extra rows count as relevant (broad queries gained a few rows), equally for every arm. Author-run, no human grader. The probe is a what-if, not production behaviour. Absolute numbers are not comparable with earlier WP-37/43 reports.

## Recommendation
Do not change the indexed text (no reindex needed) and do not change the cut. If the owner wants the unused context vectors gone, that saves embedding time and Qdrant space for no search loss, but it is a separate decision. A heading variant worth another test only if parent-child questions matter most: head1 helped parent_child and table queries but hurt broad ones; it would need a larger gold set to tell apart from noise.
