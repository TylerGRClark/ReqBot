# Pipeline redesign — plan (nothing in this document is built)

*Written 2026-10-09 from a discussion with the owner. This is a plan for review: no code, no data and no behavior changes with this PR. Each change below becomes its own PR, with its measurements and pass rules written down before any result is read. A phase number has not been assigned.*

## 1. Principles (the owner's)

1. **The root is never edited.** What the requirement-finding call returned is the *root*. Nothing after it changes it, ever. A glued lead-in, a dropped paragraph number or a few added words are *not* the root; they belong to a later, separate layer.
2. **Layers add; they never overwrite.** Each step reads what the earlier steps wrote and adds fields. A step may not change a field that an earlier step wrote. A test enforces this.
3. **One job per step, and one job per model call.** A step that does several jobs is split.
4. **Steps are named for what they do** (PDF reading, chunking, requirement finding, ...), not by letter. The letters (A, B, C, D, D.5, D.6, E, F) are retired; section 6 maps old to new.
5. **Flag, do not delete**, except for records that are clearly not requirements (empty, a bare heading, a change-log line) or not in the document at all.
6. **Every piece of the explained text that comes from the document is verbatim**, and each piece is labeled with what it is and where it came from.
7. **A model chooses or judges; it does not write text into the explained layer.** There is no plain-language restatement layer (owner's decision).

## 2. The pipeline today

| Step | Job | Model? | Touches the quote? |
|---|---|---|---|
| A | PDF to a structured document (Docling) | No | n/a |
| B | Cut into chunks of up to 256 tokens (`raw_text`, and `text` with a heading breadcrumb) | No | n/a |
| C | One call per chunk returns quotes that look like duties, plus a reference (8B, inclusive prompt D1) | Yes | Creates it |
| D | Normalize: empty-quote check, fuzzy grounding (threshold 60) against `text`, junk filters (heading echo, cut-off fragment, orphan list item, dangling clause, change-log entry, definitional cross-reference), hierarchy and page metadata, de-duplication, whole-sentence expansion, stable ID | No | **Yes: expansion overwrites `source_quote`** |
| after D | Parent stem and embedding text (rule-based; rewrites the normalized file in place; run twice) | No | No |
| D.5 | Description, domain tags and requirement type (one call, three jobs) | Yes | No |
| D.6 | Is the description supported by the quote? | Small model | No |
| E | Totals and the final output file | No | No |
| F | Embed and store in Qdrant | Embeddings | No |
| Checklist | On demand: citation, section heading, parent paragraph, applies-to, passage, flags, possible-missed passages | No | No |
| Draft questions | `reqbot questions`, a sidecar file | Yes (14B) | No |

What is tangled:

- Step D does about seven jobs, and the verbatim check (grounding) is one of them, in the middle.
- The junk filters judge the model's raw fragment *before* it can be widened to its sentence or given its lead-in, so records that could be saved are rejected. The WP-41 bypass for dangling clauses was a patch for this order.
- De-duplication runs before the whole-sentence rule, so a second de-duplication was added after it.
- The parent-stem step rewrites the normalized file in place and is called twice.
- Three different texts serve as "the chunk": `text` (the model saw it, and grounding checks it), `raw_text` (expansion and the checklist use it).
- Citation, section heading, parent paragraph and applies-to are derived again for every checklist, so search never benefits from them.
- `confidence` is computed in Step D from whether the record has tags, a description and a reference, none of which the first-pass extractor supplies. In the 2026-10-09 run every AFI 17-203 record is 0.6 or 0.7, under the 0.8 review threshold, so the score carries no information beyond "has a source reference".
- The whole-sentence rule (#280, merged 2026-10-09) overwrites `source_quote`. That breaks principle 1 and is reversed by this plan.

## 3. The proposed pipeline

| # | Step | The one job | Reads | Writes (new fields only) | Model? |
|---|---|---|---|---|---|
| 1 | **PDF reading** | PDF to a structured document | the PDF | ancestry file | No |
| 2 | **Chunking** | Cut into chunks; keep `raw_text` as the one reference text | step 1 | chunks file | No |
| 3 | **Requirement finding** | One call per chunk returns the quotes that look like duties | chunks | `source_quote` (the root, exactly as returned; trimmed of surrounding spaces only), `source_ref` | **Yes (8B)** |
| 4 | **Anchoring** | Find the root in the chunk's `raw_text`; record where, and whether the match was exact | steps 2, 3 | `anchor_status`, `anchor_start`, `anchor_end`, `anchor_text` | No |
| 5 | **De-duplication** | Collapse records with the same source reference and the same root, as today (across chunks too, since neighboring chunks overlap); keep one and record how many were merged | step 4 | `duplicates_merged` | No |
| 6 | **Context attaching** | Build the explained text from verbatim pieces (section 5) | steps 2, 4, 5 | `explained_text`, `explained_parts`, `explain_notes`, plus citation, section heading, parent paragraph, applies-to (stored instead of re-derived per checklist) | No (model step deferred, section 5) |
| 7 | **Screening** | Flag, or reject the clear non-requirements, judging the **explained** text | step 6 | `screen_flags` | No (a model label may be added later) |
| 8 | **Faithfulness check** | Does the explained text still mean what the root and its paragraph mean? Flags only | steps 6, 7 | `faithfulness` | Yes (14B); later, own plan |
| 9 | **Totals and final file** | Counts and the final output | step 7 (or 8) | stats, final file | No |
| 10 | **Search indexing** | Embed the explained text and store it in Qdrant (the requirements and context collections stay separate) | step 9 | Qdrant points | Embeddings |
| on demand | **Checklist building** | Lay the stored fields out as a sheet; derive nothing new | step 7 | sheet | No |
| on demand | **Draft questions** | One audit question per row (unchanged) | checklist rows | sidecar file | Yes (14B) |

**Disabled for now (the code stays, commented out or switched off at the call site; no option flag is added):** tagging and typing (old D.5, part), plain-language description (old D.5, part), the description check (old D.6). `domain_tags`, `requirement_type` and `description` stay in the saved records as empty values, so readers do not break. The reasons: the tags are a cybersecurity vocabulary that would be wrong for the other AFI domains the project is meant to reach, the descriptions were nearly verbatim or blank, and neither fed the checklist. `confidence` is dropped from the default path, or redefined from the anchor result; the owner decides when the PR is written (section 8).

### Order and why

- **Anchoring comes right after requirement finding**, before anything judges or builds on the quote.
- **Screening comes after context attaching**, because the "can this stand alone?" filters (cut-off fragment, dangling clause, orphan list item) are unfair to a fragment whose lead-in has not been attached yet. Both steps are rule-based, so screening before the model steps spends no model calls on records that get flagged.
- If a later model step produces part of the explained text (section 5), screening moves after it.
- **De-duplication is once**, on the root, before the explained layer exists.

## 4. Record layers

| Layer | Fields | Rule |
|---|---|---|
| Root | `source_quote` (kept under its current name so readers do not break), `source_ref`, `chunk_id` | Exactly what step 3 returned. The invariant test compares it, byte for byte, to the line in `<doc>_extracted_requirements.jsonl`. |
| Anchor (metadata about the root) | `anchor_status` (`exact`, `exact_after_marker_removed`, `not_exact`), `anchor_start`, `anchor_end` in `raw_text`, `anchor_text` (the verbatim source span) | A separate set of fields, never merged with the root. When the root is not word for word (for example a lead-in glued onto an item), `anchor_status` says so and `anchor_text` is the closest exact span; the root stays as it is. |
| Explained | `explained_text`, `explained_parts` (each `{kind, text, origin, location}` with `kind` in `lead_in`, `sentence`, `heading`; `origin` in `rule` or `model`), `explain_notes` (for example `leading marker removed`, `expanded to sentence`, `lead-in attached from numbering`) | Built from verbatim pieces only. Nothing here replaces the root. |
| Screening | `screen_flags` | Flags, with a short reason each. |
| Identity | `requirement_id` | Hash of the document, source reference and the **root**, so improving the explained layer never changes an ID or detaches an audit note. De-duplication (step 5) uses the same key (source reference plus root), so two records can never share an ID; a test asserts it, because the index derives each Qdrant point from the ID. This changes every ID once; the old index and any draft-question sidecars must be rebuilt. |

The whole-sentence rule moves into step 6 and stops writing to `source_quote`. The root of a glued quote stays glued; the explained layer uses the exact pieces found by anchoring.

## 5. Context attaching

- **Tier 1, rules (built; this plan stores their output).** The whole sentence the root sits in (`pipeline/sentence_expand.py`); the lead-in from the document's own numbering (the parent paragraph in the checklist, 16 of 21 shown rows matched the adjudicated lead-in on 25 labeled AFI records, a small test tuned on the same records) and from lines that end in a colon; the section heading; applies-to from the paragraph numbering. Strong on numbered documents (AFIs, DoDIs), weak on prose (NIST).
- **Tier 2, a model picks from a menu of verbatim spans (not in this plan's scope to build).** This is the WP-45.8 resolver (14B, 65 of 104 right against 41 for the old rules, nothing invented, in the earlier tests). Its evidence is on the *old* records. **It waits for rebuilt test groups on the new runs** (the owner adjudicates lead-ins, about an hour; see the Stage C plan) and for the attach rule to be written down and tested. Until then prose documents get tier 1 only.
- **There is no tier 3.** No model-written restatement.

## 6. Naming map (old letters to new names)

A 1 PDF reading; B 2 Chunking; C 3 Requirement finding; D (grounding) 4 Anchoring; D (de-duplication) 5; D (expansion, parent stem, hierarchy and page metadata) 6 Context attaching; D (junk filters) 7 Screening; D.5 and D.6 disabled; E 9 Totals and final file; F 10 Search indexing. The `--skip-to` option takes the new names and keeps the letters as aliases for one release. `--skip-enrichment` and `--skip-description-gate` become accepted no-ops that print a note.

## 7. Sequence of PRs and what each one must show

Each PR registers its pass rules before any result is read (the project's standing practice); the values below are proposals.

1. **This plan** (docs only).
2. **Documentation rewrite** (its own PR): `ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/CLI.md`, `docs/CONFIGURATION.md`, `CONTRIBUTING.md` describe the new names and steps. Old phase documents stay as history, with the mapping from section 6 at the top of the architecture document.
3. **Rename** (mechanical): step names in code, logs and options, with aliases. **No behavior change; a re-run on a cached run must produce byte-identical outputs** (timestamps aside).
4. **Anchoring, root fields and ID basis.** Pass: (a) the invariant test (root equals the Step C line) passes on all 13 documents; (b) coverage of the 74 labeled obligations is not lower than the noise floor allows (the WP-45.11 floor: two replicate runs, paired-loss limit 4); (c) no record that is rejected today for grounding is kept, and none that is kept today is lost, except by a registered rule; (d) report, per document, the share of roots that are exact, exact after marker removal and not exact (in the 10 documents finished when this was written, 140 of 1,491 records, about 9%, were not word for word: 25 marker only, 57 lead-in glued onto the item, 26 a few words added in front, 18 end differs, 8 table cells or rewording, 6 not in the chunk).
5. **Explained layer (tier 1, stored).** Pass: the whole-sentence rule still meets its WP-45.14 measures when applied to the explained layer only; the owner rates 30 explained rows against their roots, better or same at least 80%; the checklist built from stored fields equals the one built today from derived fields on AFI 17-203 except where the plan says otherwise.
6. **Screening on the explained text.** Pass: no labeled obligation lost; counts of records rescued and newly flagged are reported per document; the owner rates a sample of 30 of each.
7. **Disable tagging, typing, description and the description check; point Ask, Evidence and result cards at the explained text; reindex.** Pass: the Ask and Evidence smoke checks still return grounded answers; the tests pass; the owner compares a few Ask answers with and without the description. The frontend tag and type filters will have nothing to filter on; the PR states what happens to those controls.
8. **Later, each with its own plan:** the faithfulness check (14B, rated by the owner in the way the draft questions were, 30 rows, with a registered bar); the model-picks step (after the rebuilt test groups).

## 8. Open decisions

- Keep `source_quote` as the name of the root (this plan), or rename it to `root_quote` in the rename PR.
- `confidence`: drop, or redefine from the anchor result.
- Which screening rules reject and which only flag. Proposed: reject only an empty quote, a bare heading echo, a change-log entry and a quote that cannot be anchored and fails the existing grounding thresholds; flag the rest.
- One file per step (clearer, more files) or one record file that grows by layers. The readers that pick `normalized`, `enriched` or `gated` files by name (the artifact resolver) would change either way; the rename PR settles it.
- Whether the frontend tag and type filters are hidden or left empty while the fields are empty.

## 9. What this plan does not claim

It does not say the rules are better than a model for context; they are cheaper, auditable and verbatim, and they are weakest where documents have little structure. It rests on the 2026-10-09 re-ingest of the 13 pinned documents; the labeled sets are small and one rater's. Nothing here has been run. The draft-question sidecars and the Qdrant index built before the ID change must be rebuilt after step 4.
