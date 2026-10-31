# Heading-tree experiment: staged preregistration

Written 2026-10-27 against ReqBot `a835f37064f8e9b825f52d76c78ff372c1eee949`,
before corpus measurement, tree implementation, or model runs. Commit this file
before running the corpus audit. Amendments must be separate dated files; do not
rewrite rules after observing results. This is an experiment, not an adoption PR.

## Question and scope

Does the current chunk-based clause source lose governing lead-ins or actors,
after accounting for existing recovery? If so, does a Docling-tree clause source
improve extraction enough to justify replacing it? Chapter-view work is unrelated.

The outside reviews named in Claude's inbox note are not available in this
checkout; their claims are hypotheses, not independently verified findings.
In particular, `_chunk_raw_text` often rebuilds text from entire Docling items;
the HybridChunker token limit alone does not establish sentence fragmentation.

## Inputs and integrity

Use exactly the seven PREREG8 documents: afi17-203, afi13-550, DODI 5200.01,
afi17-101, afman17-204, DODI 5200.48, DODI 8551.01. Obtain read-only copies of
PREREG8's exact chunk snapshots, corresponding saved DoclingDocument exports
(or the exact PDFs if exports were not saved), ancestry, original gold2 and
silver annotations, and relevant STATE.md standing rules. Hash every input.
Do not silently substitute the newest processed folder. The original scoring
functions in `eval/clause_labeling/label_ctx_metrics.py` remain unchanged.
Reconstruction must produce exactly 624 gold requirements before quality scoring.
If the old document exports are absent, report that limitation; reparsing even
with the pinned family may confound a source-only comparison. Agree a dated
amendment before comparing different conversion outputs.

Production JSONL schemas, source quotes, Qdrant text, configuration and live
library remain unchanged. Experiment JSON is a separate scratch artifact, not a
new extraction schema. Keep Docling 2.94.0 / core 2.99.0 / parse 5.7.0 /
ibm-models 3.13.0. No model job, embedding call, or full library re-extraction is
authorized by this preregistration. Tyler's approval is required first, per the
inbox's quoted STATE.md rules. A draft PR must stay draft to avoid paid review.

## Stage A: measure before implementing an alternative

Run the current `document_clauses` on all seven snapshots with zero model calls.
Record whole-corpus clause and chunk counts, list-shaped clauses, same-chunk vs
previous-chunk recovery, and exact source offsets. Counts of candidates and
recovered context are not counts of *true* governing relationships.

For review, select up to 10 list-shaped and 10 other clauses per document by
SHA-256 rank of `heading-tree-v1|document|chunk_id:clause_index`, without using
labels, gold hits or recovery outcomes. Keep all candidates when a stratum has
fewer than 10. Report stratum denominators; a balanced sample is not a census.
A reviewer reads the document/tree and records each true governing lead-in and
actor as an exact source span with its chunk ID, or marks none/ambiguous. Actor
and lead-in are separate judgments; a colon is not proof of an actor. Record
whether multiple chunk occurrences make the source anchor ambiguous. Never
resolve ambiguous cases by choosing the occurrence that makes an arm look good.
Review without showing automatic context-recovery outputs, record the reviewer
identity and whether they are independent/blind, then hash/freeze annotations.

Report, separately for lead-in and actor, the fraction of judged relationships
outside the clause's chunk, and correct/incorrect/absent existing attachments.
Show same-chunk, previous-chunk, heading-only, and more-distant source cases.
For every judged case, test context availability separately at:
1. the actual labeler block (`clause_block`, including its cuts),
2. the checklist's stored passage,
3. the question and score prompt windows (1500 / 1200 characters).

Availability (text present) is not semantic attachment accuracy. The passage
window is downstream of labeling and cannot recover a discarded clause. For
window measurements use real saved normalized/explained requirement records
where available; an all-clause simulation is descriptive only, because it lacks
the production explanation's rule-lead-in trigger. Never label it production
recovery. Unknown annotations stay in the unknown denominator, not as successes.

Tree implementation is warranted only if review confirms at least 5 residual
missing/wrong governing relationships in the sampled clauses, across at least
2 documents, that tree structure can represent. Otherwise report NULL or THIN,
with examples and denominators, and stop without changing the clause source.
This is an engineering gate, not a statistical significance claim.

## Stage B: isolated alternative, conditional on Stage A

Before implementing, freeze a dated design supplement identifying exact tree
node kinds, list-parent and lead-in lookup rules, heading/section boundaries,
table handling, exclusions, and source-anchor mapping. Commit the supplement
before running that implementation on the corpus. Do not tune on arm outcomes.

The sole treatment is the clause source: walk the same converted document's
paragraph/list nodes before token chunking, apply the existing sentence splitter
to each text node, and expose source-backed parent lead-ins in the existing
context field. This includes the structural lead-in rule; it is not a
clause-cut-only experiment. Do not add a second actor field or change the prompt.
Tables, filters and ancestry rules must remain equivalent; inability to preserve
them is a documented feasibility failure. Quote = original node substring, never
lead-in concatenation or rewriting. Source mapping and stable-ID consequences
must be explicit, with no production schema migration.

Control = current production clause source and context, including adopted
`find_lead_in` and table context. The old PREREG8 control predates those changes
and cannot stand in for today's baseline. Freeze template SHA
`b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4`,
model `ornith:35b`, batch size 4, temperature 0, num_ctx 8192, num_predict 300,
thinking off. Consecutive batches follow each source's document order. Different
clause cuts necessarily change batch membership; report that confound explicitly.

## Stage C: model experiment, only after Tyler approves

Fresh scratch control, control-repeat and tree runs over whole documents; no
ledger reuse between arms and no automatic warm-up inference before approval.
Check with Claude before scheduling; one model job at a time. Record exact
input, code, prompt and filled-batch hashes, model identity, settings, wall time,
failures and parse counts. No model runner is provided in the preparation PR.

Score with the original PREREG8 gold-matching rules on exactly 624 requirements.
UNSURE counts as a row. Report whole-corpus and gold-unit counts, per-document
metrics, clause lengths/truncations and all requirement flips with source spans.
Do not compare clause-key label agreement when the sources cut different clauses;
use original source spans for the comparison and report unmappable cases.

Set noise margins in percentage points:
`Nr = max(1.2, abs(recall(control-repeat) - recall(control)))` and
`Np = max(1.9, abs(precision(control-repeat) - precision(control)))`.
Tree PASSES only when all conditions hold:
- Recall and precision each no worse than the control mean minus Nr / Np.
- Recall improves by more than Nr OR precision improves by more than Np.
- At least 20 sampled, unambiguous governing relationships are evaluable in both
  sources. Tree improves correct attachment by at least 10 percentage points,
  fixes at least 5 control errors across at least 2 documents, and introduces at
  most 1 new incorrect attachment. Score lead-in and actor separately; a gain on
  one requires the other not to regress. Missing is an error when truth exists.
- No lost source anchors, edited quotes, failed batches, or missing documents.
  Unparsed rate does not exceed the worse control by more than 1 per 100 batches.

INSUFFICIENT/THIN applies to missing inputs, fewer than 20 evaluable relationships,
or inadequate source mapping. Otherwise a missed rule is FAIL, even if another
metric improves. NULL is a valid Stage A outcome. A pass supports a separate
adoption decision; it does not authorize merge, a live rerun or schema changes.

## Limits

These documents and sampled gold units are previously exposed evaluation data.
The gold is model-agreement based with owner rulings, not a comprehensive human
audit; precision is a lower bound. Context relationships cluster within lists.
The balanced attachment sample does not estimate corpus prevalence without
stratum weighting. Code reading, synthetic tests and partial inputs cannot
establish real-document attachment accuracy or recall/precision improvement.
