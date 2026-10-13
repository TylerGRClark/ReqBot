# WP-45.8 Stage B addendum — details the registry leaves open, fixed before any Stage B number exists

*Written after Stage A ran (the resolver strings exist) and before any Stage B retrieval was computed. Adds no rule to [PHASE45_WP458_REGISTRY.md](PHASE45_WP458_REGISTRY.md) (#250); it fixes how the registry's words are computed so none is chosen after seeing results.*

## 1. Inputs

- **Resolver strings:** Stage A run 1 over the 13 pinned processed runs (`wp458_shadow_processed`, 1,853 records; the pinned runs are the newest runs, checked). A record gets a string only if its Stage A row is unflagged (no `checker error`, no abstention) **and** none of its returned spans is among the six that are not substrings of the document (Stage A report); otherwise it has **no resolver string** (resolver arm: quote alone; hybrid arm: production's text). The string is the plan's: actor span and parent span joined with ` | `, whatever the kind the resolver chose.
- **Layout:** the embedded text is built by the production `build_embedding_text` with `embedding_text = string + "\n" + quote`, the layout of production stems and of the apparatus' oracle arm.
- **Index and queries:** the apparatus unchanged (`wp_45_1c`: frozen groups and questions verified against `queries_frozen.json`; an in-memory copy of the live index read once; target-only mode primary). The four runs are the plain run and the three production-path repeats **using the saved rewrite/HyDE inputs** `prod_inputs_r1..r3.json`, so every arm of a run sees identical query vectors. The snapshot digest is compared with the one in the earlier results and any difference is reported.
- **Arms run:** production (base), resolver, hybrid, each in target-only mode (the 111 tested records) and cohort mode (the policy on **every** indexed record at once, for the 35 gold queries and as a secondary view of the targets). The apparatus' none and oracle arms are not re-run; the registry's cells are resolver minus production.

## 2. How the registry's words are computed

- **A cell** = (group, question style, run). Groups: right, misleading, incomplete, bare (no stem but needs a lead-in), control, and **pooled stemmed** = right + misleading + incomplete. The party style leaves out records flagged `no_party`, as the apparatus does. Metric: recall@10, resolver minus production, paired by record.
- **Interval:** the apparatus' 95% percentile bootstrap over records (`lo`, `hi`), under the best-case and the worst-case tie reading. **Inconclusive** = either reading's interval is wider than 0.40 (`hi - lo > 0.40`). Inconclusive cells are excluded before H and G; R uses point estimates and does not exclude them.
- **Meaningful decrease / increase** = the apparatus' rule (`|mean| >= 0.10`, interval excludes zero) holding under **both** tie readings with the same sign.
- **H:** a group (including pooled stemmed) with a meaningful decrease, in a non-inconclusive cell, in two or more of the four runs on the same question style.
- **R:** for the right group, pooled stemmed or control, the point-estimate mean is at most -0.10 under **both** tie readings in all four runs on the same question style. (The registry says "point estimate"; requiring both readings keeps R at least as strict as a "meaningful" cell about direction and is the same convention the apparatus uses for a verdict.)
- **G:** the bare group has a meaningful increase, in a non-inconclusive cell, in three or more of the four runs for at least one question style.
- **C:** cohort mode, the 35 gold queries, resolver minus production, paired per query: the 95% interval of the change in recall@10 has `hi < -0.02` in two or more of the four runs.
- **Outcome:** exactly the registry's: a proposal only if G holds and none of H, R, C is triggered; any trigger means no proposal and the records behind it are read; no trigger and no G is "no demonstrated benefit".
- **Reported beside, never gating:** the hybrid arm; the same cells for MRR and recall@5/@20; per-cell inconclusive flags; the number of records with and without a resolver string in each group.

## 3. Limits stated again

Small groups, questions written by the proposing model, an in-memory engine and 13 documents (registry section 4). Attachment accuracy is not measured here. The six non-verbatim spans are treated as "no string"; with them included the numbers would differ by at most those records.
