# WP-45.1(c)/(d): a fair retrieval test of stems, lead-ins and headings

Measurement only. No production code, index or configuration changed, and nothing was written to the real Qdrant (the live
collection was read once, with its vectors). The plan, written and reviewed before any of this ran, is
`docs/PHASE45_WP451C_PLAN.md` with Codex's review in `docs/PHASE45_WP451C_REVIEW.md` (both local, untracked).

## Question

WP-45.1(b) showed that about 54% of records need a lead-in they do not carry and that about 40% of attached stems are right.
That is a reading problem. This test asks whether it is also a **search** problem, and whether a lead-in or a heading,
supplied correctly, would help. Each record is compared with itself under different embedded text, so question difficulty
cancels out.

## What was done

- **Records:** the 112 audited records that are requirements (right stem 25, misleading stem 22, incomplete chain stem 11, no
  stem but needs a lead-in 36, no stem and complete 18). One control record (R053) is in the pinned corpus files but not in the
  live index and is left out, so 111 are tested. Lists are frozen in `groups.json`.
- **Queries:** two per record, written by Claude from the record's full intended meaning (quote plus Tyler's adjudicated lead-in),
  blind to stem verdict, group and any retrieval output: a *topic* question and a *party + topic* question
  (`queries.jsonl`, `QUERY_WRITING.md`). `query_check.py` enforces the writing rules and reports wording overlap with the card
  (median content-word overlap 0.38 topic, 0.61 party). Twenty records carry a `no_party` flag (the card supports no party, or the subject is a thing); their party question is a
  rewording and is left out of party-style results.
- **Order of events is in the git history:** the groups, queries, packet and checker were committed and hashed first
  (`outputs/queries_frozen.json`); then the engine, runner, analysis and the heading rule (with its source-correctness table,
  `outputs/h3_assignments.json`); only then were results produced. The runner refuses to run if a frozen file changed.
- **Engine:** an in-memory copy of the live index (1,845 points, digest recorded) with the live vector configuration. The adapter
  in `engine.py` issues the legs `core.ask.retrieve()` builds and returns the same list: identical ids and scores on 12
  plain-mode and 8 cached production-path gold queries. The in-memory copy is not bit-identical to the real server (top-20 sets
  matched on 13 of 15 queries in an earlier check, differing by one record on the other two), so only relative comparisons made
  inside the same engine are reported, and no production change is recommended from this alone.
- **Arms:** production (live vectors); *quote alone* (the stem removed); *oracle* (Tyler's adjudicated lead-in in the stem's
  place); *H3* (leaf heading, where the frozen rule `heading_rule.py` applies, 873 of 1,847 records); *H4* (leaf heading, for the
  31 audited records Tyler's rulings place in the heading). Heading arms change the dense vector only, or both the dense and BM25
  vectors.
- **Modes:** *target-only* (primary: only the queried record's vectors change; every competitor keeps its production vector) and
  *cohort* (secondary: the policy applied to every record it covers).
- **Query inputs:** *plain* (no rewrite, no HyDE; identical query vectors in every arm) and *production path* (rewrite and a HyDE
  hypothesis generated once per repeat on the 8B model, cached in `outputs/prod_inputs_r*.json`, reused for every arm; 3 repeats).
- **Decision rule (fixed in the plan):** "meaningful" = a paired change in recall@10 of at least 0.10 whose 95% record-bootstrap
  interval excludes zero, in the same direction under best- and worst-case tie ranks. Anything else is reported as *no
  demonstrated difference*, never as *no effect*. A document-level bootstrap is also shown as a sensitivity check.

## Results

Paired change in recall@10 (arm minus production, target-only, best-case ties; interval in brackets). The four numbers are the
plain run and the three production-path repeats. Full tables: `outputs/report_*.txt`, `outputs/key_cells.txt`.

| Question | Group (n topic / party) | Plain | Prod r1 | Prod r2 | Prod r3 | Reading |
|---|---|---|---|---|---|---|
| **Q1** misleading stem removed | misleading (22 / 17) | -0.09 / -0.12 | -0.09 / 0.00 | -0.14 / -0.06 | **-0.18 [-0.36,-0.05]** / 0.00 | removing a wrong stem never improved recall |
| Q1 chain stem removed | incomplete (11 / 11) | 0.00 / -0.09 | -0.09 / -0.18 | -0.09 / -0.09 | 0.00 / -0.09 | same |
| **Q2** right stem removed | right (25 / 21) | -0.12 / -0.10 | -0.08 / -0.10 | -0.08 / -0.10 | -0.12 / -0.10 | small loss; not meaningful by the rule |
| **Q3** adjudicated lead-in added | no stem, needs lead-in (35 / 29) | **+0.17 [+0.06,+0.31]** / **+0.28 [+0.14,+0.45]** | **+0.26** / **+0.21** | **+0.11** / **+0.28** | **+0.14** / **+0.28** | meaningful in every run, both styles |
| Q3 lead-in replaces a wrong stem | misleading (11 / 11) | -0.09 / +0.09 | 0.00 / 0.00 | 0.00 / -0.09 | -0.09 / 0.00 | recall not demonstrated; party MRR +0.19 to +0.41 |
| Q3 lead-in replaces a chain stem | incomplete (11 / 11) | 0.00 / +0.27 | +0.09 / +0.27 | +0.09 / +0.18 | 0.00 / +0.27 | recall not demonstrated at n=11; party MRR +0.24 to +0.35 |
| **Heading H3** (rule), dense + BM25 | no stem, needs lead-in (36 / 29) | +0.03 / **+0.14 [+0.03,+0.28]** | +0.08 / +0.10 | 0.00 / +0.10 | +0.03 / +0.10 | party only; not meaningful under rewrite + HyDE |
| Heading H3, dense only | same | +0.03 / +0.03 | +0.08 / 0.00 | -0.03 / +0.03 | +0.03 / 0.00 | about nothing |

Gold counterchecks (the 35 scored topical queries, paired per query, cohort-wide):

| Policy | recall@10 change, plain | production-path repeats | Reading |
|---|---|---|---|
| Remove **every** stem (all 203) | **-0.096 [-0.202,-0.009]** | -0.082, -0.093, -0.102 (intervals exclude zero in all three) | existing stems help topical retrieval |
| Adjudicated lead-in on the 80 oracle records | -0.017 [-0.049, 0.000] | -0.032, -0.027, -0.031 | no harm shown |
| H3 heading on 873 records, dense + BM25 | -0.003 [-0.010, 0.000] | -0.009, -0.007, -0.010 (MRR +0.013 to +0.026) | no harm shown |

Also, for the same records and plain run: with the stem removed fewer targets clear the production score floor (95.7% to 87.9%
of 116 target queries) and fewer reach the returned 20 (87.9% to 77.6%); with the adjudicated lead-in more do (95.0% to 98.8%,
and 85.0% to 95.0%, of 160).

**Findability as it stands (descriptive only, confounded by query difficulty).** Recall@10 under production text, topic /
party: control 0.94 / 1.00, right stem 0.80 / 1.00, misleading stem 0.91 / 0.94, no stem 0.81 / 0.72, incomplete chain stem
0.64 / 0.73. By meaning-written queries almost every group is findable most of the time; the incomplete-chain group is the
weakest and the stemless group is weak on party questions.

**Exploratory, not pre-registered (n is small; do not rely on it alone; this split was added to `analyze.py` after the main results had been read).** By where the adjudicated lead-in lives, recall@10
change with the lead-in added (plain run), topic / party: heading-located -0.03 / **+0.13 [+0.03,+0.26]** (n=31); same chunk
**+0.19 [+0.06,+0.34]** / **+0.28 [+0.12,+0.48]** (n=32 / 25); previous chunk 0.00 / +0.07 (n=17 / 14). So a lead-in that is only a
role name in a heading helps questions that name the role and does nothing for topical ones, while a lead-in that sits in the
same chunk, and carries topical words, helps both.

## What it supports, and what it does not

- **A wrong stem does not hurt its own record's rank.** In no run did removing a misleading or chain stem improve recall@10; in
  one production-path repeat it made the misleading group worse by a meaningful margin. So a wrong stem is a trust and display
  problem, not (measurably) a search problem for that record. That says nothing about other records: a wrong stem could still pull
  a record into results where it does not belong, which a one-target measure cannot see.
- **Correct stems matter.** Removing right stems costs a little for the record and removing all stems costs the gold queries
  about 0.09 recall@10 (every run). Any attachment fix must leave records attached correctly untouched (already a gate in WP-45.2).
- **Supplying the right lead-in to records that have none is a real search gain**, about +0.11 to +0.26 recall@10 on topical
  questions and +0.21 to +0.28 on questions that name the party, in every run. The largest gain comes from same-chunk
  lead-ins, which is where today's stems are most often wrong (WP-45.1(b) C1). This is an informative benchmark made of
  human-adjudicated text, not a forecast for whatever a pipeline step produces.
- **The heading is informative in some cases and not others, and a selective rule is enough.** The leaf heading, added to the
  dense and BM25 text, improves party-style recall@10 on stemless records by about +0.10 to +0.14 (meaningful in the plain run only)
  and does nothing for topical questions or the gold queries; dense-only does nothing. The rule (H3) captures the whole benefit
  of the rulings-based selection (H4). Against the audit the rule fires on 49 of the 111 tested records: 30 of the 31 whose lead-in
  is the heading are selected. Of the other 19: in 8 the heading is part of a longer lead-in, in 4 the record is already
  complete, and in 7 (R023, R024, R055, R063, R087, R089, R108) it names a different party than the adjudicated one. That is the "correct in some cases, not every case" answer,
  and it argues for a stored, provenance-carrying field and a check before anything is embedded or displayed from it.
- **This does not overturn WP-37.2.** That test prefixed every record with title, full path and a `parent_context` excerpt and
  measured 12 topical queries on an older index; this one adds only the leaf heading, on selected records, and sees no harm on the 35
  scored gold queries. Different prefix, queries, corpus and engine: a narrower prefix did not regress here, nothing more.

## Limits

- Small groups (11 to 36 records). Only large shifts can be told from noise; an interval that touches zero means *not
  demonstrated*. At document level (13 documents) the topical Q3 interval touches zero, so that result is less certain than the record
  level suggests (document bootstrap, plain run: +0.00 to +0.32).
- One target per query. A returned record other than the target might also answer the question; wrong or extra context could
  help or hurt records that are not the target. The test measures whether the expected record was found.
- The same model that proposed the hypotheses wrote the queries (mitigated by blindness, freezing, the overlap report and
  review; not removed). Party questions name the party that the oracle and heading text contain, so their gains partly reflect
  term matching by construction; the topical results do not have that built in. Restricted to queries at or below the median
  overlap (`outputs/report_plain_low_overlap.txt`) the party gain holds (+0.38 [+0.15,+0.62], n=13; the median is taken over the 92 party queries the analysis uses, not the 20 `no_party` ones) and the topical gain keeps its direction
  but is not demonstrated (+0.21 [0.00,+0.43], n=14).
- The cached rewrite/HyDE inputs record the model and the `core/ask.py` hash that produced them and are refused if either differs.
- In-memory engine, not the real server (see above). The conclusions here are large, directional ones and do not depend on tie
  ordering, but this is the reason no production change follows directly.
- 13 documents; the gold set is 35 topical queries; R053 is not in the live index.

## Files

| Path | What |
|---|---|
| `groups.py`, `groups.json` | frozen record groups from the final rulings |
| `query_packet.py`, `query_packet.md`, `query_ids.json` | the writer's packet and its id map |
| `QUERY_WRITING.md`, `queries.jsonl`, `query_check.py` | writing rules, the 112 query pairs, the rule checker |
| `freeze_inputs.py`, `outputs/queries_frozen.json` | hashes taken before any retrieval |
| `heading_rule.py`, `outputs/h3_assignments.json` | the frozen H3 rule and its source-correctness table |
| `engine.py`, `variants.py`, `run_test.py` | the in-memory engine and adapter, text variants, the runner |
| `analyze.py`, `key_cells.py` | the pre-registered analysis and the cross-run table |
| `outputs/results_*.json`, `outputs/report_*.txt`, `outputs/key_cells.txt` | per-record ranks with manifests, and the reports |
| `outputs/text_variants.jsonl`, `outputs/prod_inputs_r*.json` | every embedded text variant, and the cached rewrite/HyDE inputs |

Reproduce from the repo root (needs the live Qdrant and the Ollama host in the config):

```
python3 eval/spike_results/wp_45_1c/run_test.py --inputs plain
python3 eval/spike_results/wp_45_1c/run_test.py --inputs prod --repeat 1     # uses outputs/prod_inputs_r1.json
python3 eval/spike_results/wp_45_1c/analyze.py eval/spike_results/wp_45_1c/outputs/results_plain.json
python3 eval/spike_results/wp_45_1c/key_cells.py
```
