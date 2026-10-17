# HyPE spike, round 2: pre-registration (committed before any round-2 evaluation result exists)

Owner's two points on round 1 (verdict DO NOT BUILD on 15 miss queries): (1) 15 queries is far too small; (2) gate HyPE to records that are auditable, not tiny fragments, because recall is half the product. This round is re-indexing and evaluation only: **no new question generation** (the 13,095 questions of round 1 are reused). Nothing live changes: scratch collections `grc_hype_spike_*` only; the `grc_requirements` / `grc_context` aliases are only read.

## Query set

`retrieval_set_v1.json` (232 queries written from the need, not from the target's wording; median content-word overlap 0.10). All 232 are scored. The 46 `sealed` rows (afpd_17-1, DODI 8410.03, NIST.SP.800-125) are also reported separately; nothing is tuned on them (nothing is tuned at all).

A query is **found at k** if any of the top k results (after collapsing to `requirement_id`) has a `requirement_id` in the row's `requirement_ids`, OR its text contains the row's `anchor_quote`. Text = the record's `parent_stem`, `explained_text` or `source_quote` (any one), compared after lower-casing, dropping everything but letters and digits, and collapsing whitespace. The 18 rows with no `requirement_ids` are matched by the anchor quote only. Only the source row counts as correct, so absolute numbers run low; **the paired comparison between arms is the point.**

## Arms (same queries, same cached query rewrite and HyDE text per query)

- **A** = production retrieval as today (`core.ask.retrieve()` on the live alias).
- **B** = A plus generated questions for every record: scratch collection `grc_hype_spike_20261013_173015` (round 1).
- **C** = A plus generated questions only for **gated-in** records. Gated in = the record's `requirement_id` appears in a checklist row (all 14 library documents, `reqbot checklist --format json`) whose `audit_question` is non-empty (a draft audit question exists). dafi36-2903 has no draft questions, so all its records are gated out. New scratch collection, built by copying the vectors of B (no new embedding, no generation).
- **C2** = C plus a floor: the record's own text (`hype_lib.record_text`) is at least 60 characters. Reported as a variant; the same rule is applied to it for reference.

The share of records gated in is reported for C and C2.

## Decision rule (fixed now; not to be altered)

An arm (C is the one of interest; B and C2 are reported with the same rule for reference) is worth building only if ALL hold:

1. recall@5 over all 232 queries rises by **at least 5 points** over A, and the **paired bootstrap 95% interval** of the difference has a lower bound **above 0** (10,000 resamples of queries with replacement, seed 20261014, percentile interval, difference of mean recall@5);
2. precision@5 on the 22 live-labelled gold queries of round 1 (`eval/gold_retrieval_queries.jsonl` restricted to live ids, same method as round 1) **falls by no more than 2 points** versus A;
3. the gain does not come only from the hard rows: the rise on the queries that are neither `fragment_hard` nor `ambiguous_target` must be **greater than 0 points** (the split is reported in full).

Otherwise record and stop. Also reported, not part of the rule: recall@10, MRR, per document, the sealed subset, and the ids newly found / newly lost versus A at recall@5.

## Rules of conduct

Nothing is tuned after seeing results. If a bug is found it is fixed, said so, and everything is rerun. Scratch collections are left in place and named in the report.

## Limits stated in advance

One run, no repeats of the rewrite or HyDE sampling (shared across arms, so paired); a single correct source row per query understates absolute recall; the gate depends on draft questions written by a model (qwen2.5:14b) that skips fragments, so the gate is partly the question writer's own judgement; gold labels are partly stale (22 of 45 usable).
