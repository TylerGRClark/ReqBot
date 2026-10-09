# WP-45.8 Stage C — plan for the resolver pipeline step (not implemented)

*Written 2026-10-09 after the owner said to integrate what had been tested and approved. Stages A and B are done ([README](../eval/spike_results/wp_45_8/README.md)); the registered outcome of Stage B was "proposal for integration". This plan says what Stage C builds, why it was not built the same night as the prompt change, the sentence rule and the audit questions, and what the owner has to decide. It adds no code.*

## 1. Why it was held back

The other three changes were measured on the data they run on. The resolver was not, in two ways:

1. **Its evidence is on the old records.** Stage B used frozen record groups (right, misleading, incomplete, bare, control) and questions written for the old prompt's output. The new prompt (D1) and the whole-sentence rule change which records exist and what they contain, so the groups do not map onto the new runs. The size of the group the resolver is for ("no stem, needs a lead-in", 36 records in Stage B) is now unknown, and the sentence rule may have shrunk it.
2. **The policy was not settled.** Stage B found the gain on records that need a lead-in and a small loss (-0.12 and -0.06 on topic questions in two of four runs) on complete sentences that already stand alone, where the resolver mostly attached an actor. Its own note was: attach only where a lead-in is needed. That rule has not been written down or tested.

A second-labeler check (#244) also found the selection verdict not robust (it flips on 1 to 4 records depending on labeler and scorer; the direction holds).

## 2. What Stage C builds

- **A pipeline step after parent-stem reconstruction (call it D.4), off by default (`--resolver` / config), using `qwen2.5:14b`.** One call per record (about 1 s each, about 30 minutes for the 13 documents). The deterministic reconstruction stays first and is the fallback whenever the step is off, the model is unreachable or the resolver abstains. Every record is kept; `source_quote` is never altered.
- **Port, not import.** The selection resolver (evidence bundle, menu v2, selection prompt and schema, assembler, checker) moves from `eval/spike_results/wp_45_7/` into `pipeline/` with its tests; production code must not import from `eval/`.
- **Attach rule (to be registered before it is measured):** attach a string only when the resolver chose a parent (a lead-in or heading) for a record that does not stand alone; never attach an actor-only string to a complete sentence.
- **Saved fields:** reuse `parent_stem` and `embedding_text` (what Qdrant already embeds), plus `stem_source` (`resolver` or `deterministic`) and `resolver_status`. No change to the Qdrant payload shape; a reindex is needed.
- **Cache:** keyed by the quote, chunk, headings, previous chunk, menu hash, tier, prompt hash, model digest, inference parameters and a hash of the resolver code, so any change misses.

## 3. Gates before it is turned on by default

1. The attach rule above is registered in a PR before any number is read.
2. A new frozen test on the **new** runs: the groups rebuilt from the new records, questions written blind, an in-memory engine as in Stage B, then the same questions against a scratch Qdrant collection (never `grc_requirements` or `grc_context`).
3. Pass = Stage B's rules (G holds; H, R, C not triggered), now with the control group counted as part of R.

## 4. What the owner decides

- Whether to rebuild the frozen groups on the new runs (it needs about an hour of his adjudication of lead-ins, as in WP-45.6; the questions can be written by the model as before).
- Whether the attach-only-where-needed rule is the right shape, or whether actor strings should stay.

Until then the audit checklist does not use the resolver: it gets its parent paragraph from the document's own numbering (WP-46.3), which needs no model.
