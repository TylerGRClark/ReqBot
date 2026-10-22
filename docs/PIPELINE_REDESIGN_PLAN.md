# Pipeline redesign — plan (partly built: the status table says which steps; section 10 is a new proposal, nothing in it is built)

*Written 2026-10-09 from a discussion with the owner. This is a plan for review: no code, no data and no behavior changes with this PR. Each change below becomes its own PR, with its measurements and pass rules written down before any result is read. A phase number has not been assigned.*

## Status (updated 2026-10-09, evening)

| Plan step | State |
|---|---|
| Plan, documentation rewrite, rename (`--skip-to` takes names) | done (#284, #285, #286) |
| 4 Anchoring (`anchor_*` fields) | done (#287); 92.7% of roots exact |
| Root kept, explained layer beside it, IDs from the root, merged roots | done (#288, #291) |
| 6 Context attaching, rule tier: sentence and verified lead-in stored on the record | done (in #288); citation, section heading, parent paragraph and applies-to are still built per checklist, not stored |
| 5 Rating of the explained text (30 rows) | done: 28 of 28 rated better or same (bar 80%); three rows noted as not requirements (a lead-in line and two definitions), which is the case for screening |
| 7 Screening on the explained text, filters flag instead of reject | **not built**: waits for the owner's decision on colon-ending lead-ins (section 8) and his rating |
| Tagging, typing, description, description check, confidence switched off | done (#289) |
| Readers show the explained text (Ask, Evidence, Trace, Compare, cards, CLI) | done (#289) |
| 8 to 10 Faithfulness check, repair, re-check | not built; own plan and the owner's rating first |
| Model-picks (resolver) for prose documents | not built; waits for rebuilt test groups |
| Data | the 13 reference documents were re-run with the new code, the Qdrant index rebuilt from them, draft questions regenerated |
| Requirement kind (section 10) | **proposed, 2026-10-11**; the owner settled the list of kinds the same day. Stage 1 (write the kind, no behavior change) is next; nothing else is built |

## 1. Principles (the owner's)

1. **The root is never edited.** What the requirement-finding call returned is the *root*. Nothing after it changes it, ever. A glued lead-in, a dropped paragraph number or a few added words are *not* the root; they belong to a later, separate layer.
2. **Layers add; they never overwrite.** Each step reads what the earlier steps wrote and adds fields. A step may not change a field that an earlier step wrote. A test enforces this.
3. **One job per step, and one job per model call.** A step that does several jobs is split.
4. **Steps are named for what they do** (PDF reading, chunking, requirement finding, ...), not by letter. The letters (A, B, C, D, D.5, D.6, E, F) are retired; section 6 maps old to new.
5. **Flag, do not delete**, except for records that are clearly not requirements (empty, a bare heading, a change-log line) or not in the document at all.
6. **Every piece of the explained text that comes from the document is verbatim**, and each piece is labeled with what it is and where it came from.
7. **A model chooses or judges; it does not write text into the explained layer.** There is no plain-language restatement layer (owner's decision). The one exception is the repair step (step 9): it writes, but into its own layer, from the root's exact words, labeled as model-written, and what it writes must pass the faithfulness check again.

## 2. The pipeline today

| Step | Job | Model? | Touches the quote? |
|---|---|---|---|
| A | PDF to a structured document (Docling) | No | n/a |
| B | Cut into chunks of up to 256 tokens (`raw_text`, and `text` with a heading breadcrumb) | No | n/a |
| C | One call per chunk returns quotes that look like duties, plus a reference (8B, inclusive prompt D1) | Yes | Creates it |
| D | Normalize: empty-quote check, fuzzy grounding (threshold 60) against `text`, junk filters (heading echo, cut-off fragment, orphan list item, dangling clause, definitional cross-reference), hierarchy and page metadata, de-duplication, whole-sentence expansion, stable ID | No | **Yes: expansion overwrites `source_quote`** |
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
| 8 | **Faithfulness check** | Does the explained text still mean what the root and its paragraph mean? Flags only | steps 6, 7 | `faithfulness` (`ok`, or a reason: incomplete, confusing, adds meaning, loses meaning, could be improved) | Yes (14B); later, own plan |
| 9 | **Repair** | For a row the check flagged, a model is given everything about it (root, explained text and parts, notes, lead-in, the chunk, the original paragraph) and writes a better version. One attempt. | steps 6 to 8 | `repaired_text`, `repair_notes`, `repair_status` | Yes (14B); later, own plan |
| 10 | **Re-check** | The same faithfulness check on the repaired text, marked as repaired | step 9 | `faithfulness_after_repair` | Yes (14B) |
| 11 | **Totals and final file** | Counts and the final output | step 10 | stats, final file | No |
| 12 | **Search indexing** | Embed the text the record is shown with (section 4) and store it in Qdrant (the requirements and context collections stay separate) | step 11 | Qdrant points | Embeddings |
| on demand | **Checklist building** | Lay the stored fields out as a sheet; derive nothing new | step 7 | sheet | No |
| on demand | **Draft questions** | One audit question per row (unchanged) | checklist rows | sidecar file | Yes (14B) |

**Disabled for now (the code stays, commented out or switched off at the call site; no option flag is added):** tagging and typing (old D.5, part), plain-language description (old D.5, part), the description check (old D.6). `domain_tags`, `requirement_type` and `description` stay in the saved records as empty values, so readers do not break. The reasons: the tags are a cybersecurity vocabulary that would be wrong for the other AFI domains the project is meant to reach, the descriptions were nearly verbatim or blank, and neither fed the checklist. `confidence` is dropped from the default path too (commented out, code kept; section 8).

### Order and why

- **Anchoring comes right after requirement finding**, before anything judges or builds on the quote.
- **Screening comes after context attaching**, because the "can this stand alone?" filters (cut-off fragment, dangling clause, orphan list item) are unfair to a fragment whose lead-in has not been attached yet. Both steps are rule-based, so screening before the model steps spends no model calls on records that get flagged.
- If a later model step produces part of the explained text (section 5), screening moves after it.
- **Repair is a loop of exactly one pass:** check, repair (only flagged rows), check again. Two separate calls, because checking and writing are two jobs. A row that fails the second check is not repaired again.
- **De-duplication is once**, on the root, before the explained layer exists.

## 4. Record layers

| Layer | Fields | Rule |
|---|---|---|
| Root | `source_quote` (kept under its current name so readers do not break), `source_ref`, `chunk_id` | Exactly what step 3 returned. The invariant test compares it, byte for byte, to the line in `<doc>_extracted_requirements.jsonl`. |
| Anchor (metadata about the root) | `anchor_status` (`exact`, `exact_after_marker_removed`, `not_exact`), `anchor_start`, `anchor_end` in `raw_text`, `anchor_text` (the verbatim source span) | A separate set of fields, never merged with the root. When the root is not word for word (for example a lead-in glued onto an item), `anchor_status` says so and `anchor_text` is the closest exact span; the root stays as it is. |
| Explained | `explained_text`, `explained_parts` (each `{kind, text, origin, location}` with `kind` in `lead_in`, `sentence`, `heading`; `origin` in `rule` or `model`), `explain_notes` (for example `leading marker removed`, `expanded to sentence`, `lead-in attached from numbering`) | Built from verbatim pieces only. Nothing here replaces the root. |
| Screening | `screen_flags` | Flags, with a short reason each. |
| Check and repair | `faithfulness`, `repaired_text`, `repair_status` (`not_needed`, `repaired_passed`, `repaired_failed` = flagged, kept), `repair_notes`, `faithfulness_after_repair` | `explained_text` is never overwritten by repair. The repaired text is its own layer, and the guard below applies to it. |
| Identity | `requirement_id` | Hash of the document, source reference and the **root**, so improving the explained layer never changes an ID or detaches an audit note. De-duplication (step 5) uses the same key (source reference plus root), so two records can never share an ID; a test asserts it, because the index derives each Qdrant point from the ID. This changes every ID once; the old index and any draft-question sidecars must be rebuilt. |

The whole-sentence rule moves into step 6 and stops writing to `source_quote`. The root of a glued quote stays glued; the explained layer uses the exact pieces found by anchoring.

## 5. Context attaching

- **Tier 1, rules (built; this plan stores their output).** The whole sentence the root sits in (`pipeline/sentence_expand.py`); the lead-in from the document's own numbering (the parent paragraph in the checklist, 16 of 21 shown rows matched the adjudicated lead-in on 25 labeled AFI records, a small test tuned on the same records) and from lines that end in a colon; the section heading; applies-to from the paragraph numbering. Strong on numbered documents (AFIs, DoDIs), weak on prose (NIST).
- **Tier 2, a model picks from a menu of verbatim spans (not in this plan's scope to build).** This is the WP-45.8 resolver (14B, 65 of 104 right against 41 for the old rules, nothing invented, in the earlier tests). Its evidence is on the *old* records. **It waits for rebuilt test groups on the new runs** (the owner adjudicates lead-ins, about an hour; see the Stage C plan) and for the attach rule to be written down and tested. Until then prose documents get tier 1 only.
- **There is no tier 3.** No model-written restatement.

### Repair (steps 8 to 10)

Proposed by the owner: a row the faithfulness check calls incomplete, confusing or improvable goes to a model that sees all of the record's data (`source_quote`, `explained_text`, `explained_parts`, `explain_notes`, the lead-in, the chunk and the original paragraph) and writes a repaired version; the repaired version goes through the check again, marked as repaired.

Guards proposed for it, because this is the one place a model writes:
- **The root's words stay inside it.** The explained and repaired text are the root plus context, so they differ from the root. The guard (a code check, not the model's word) requires only that the anchored root text appears unchanged somewhere inside the repaired text (when the root is not word for word, the exact source span stands in for it). The model may add words before or after to supply context and may not reword the root itself. The guard is strict (changing "Include" to "includes" fails it); if it blocks too many good repairs, it is loosened after the numbers are seen.
- **Everything stays visible.** The repaired text is labeled `origin: model` and shown as repaired in the checklist; the explained text it came from stays on the record.
- **The row is judged by a second look.** Because a model grading its own rewrite is weak evidence, the re-check is the same prompt on the repaired text, and the owner rates a sample (section 7) before this step is trusted.
- **Which text a reader sees:** `repaired_text` when `repair_status` is `repaired_passed`, otherwise `explained_text`. Indexing, Ask, Evidence and the checklist all use that one rule.
- **A row that fails the re-check is flagged, not deleted (owner's decision, 2026-10-09).** `repair_status` becomes `repaired_failed` and the checklist and sheet show a flag along the lines of "probably not a good requirement". The row stays in the files and in its place in the main sheet; nothing is set aside or dropped. The flag appears only on rows that failed twice, so it does not become a flag on every row.

## 6. Naming map (old letters to new names)

A 1 PDF reading; B 2 Chunking; C 3 Requirement finding; D (grounding) 4 Anchoring; D (de-duplication) 5; D (expansion, parent stem, hierarchy and page metadata) 6 Context attaching; D (junk filters) 7 Screening; D.5 and D.6 disabled; E 11 Totals and final file; F 12 Search indexing; the faithfulness check, repair and re-check (8 to 10) are new. The `--skip-to` option takes the new names and keeps the letters as aliases for one release. `--skip-enrichment` and `--skip-description-gate` become accepted no-ops that print a note.

## 7. Sequence of PRs and what each one must show

Each PR registers its pass rules before any result is read (the project's standing practice); the values below are proposals.

1. **This plan** (docs only).
2. **Documentation rewrite** (its own PR): `ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/CLI.md`, `docs/CONFIGURATION.md`, `CONTRIBUTING.md` describe the new names and steps. Old phase documents stay as history, with the mapping from section 6 at the top of the architecture document.
3. **Rename** (mechanical): step names in code, logs and options, with aliases. **No behavior change; a re-run on a cached run must produce byte-identical outputs** (timestamps aside).
4. **Anchoring, root fields and ID basis.** Pass: (a) the invariant test (root equals the Step C line) passes on all 13 documents; (b) coverage of the 74 labeled obligations is not lower than the noise floor allows (the WP-45.11 floor: two replicate runs, paired-loss limit 4); (c) no record that is rejected today for grounding is kept, and none that is kept today is lost, except by a registered rule; (d) report, per document, the share of roots that are exact, exact after marker removal and not exact (in the 10 documents finished when this was written, 140 of 1,491 records, about 9%, were not word for word: 25 marker only, 57 lead-in glued onto the item, 26 a few words added in front, 18 end differs, 8 table cells or rewording, 6 not in the chunk).
5. **Explained layer (tier 1, stored).** Pass: the whole-sentence rule still meets its WP-45.14 measures when applied to the explained layer only; the owner rates 30 explained rows against their roots, better or same at least 80%; the checklist built from stored fields equals the one built today from derived fields on AFI 17-203 except where the plan says otherwise.
6. **Screening on the explained text.** Pass: no labeled obligation lost; counts of records rescued and newly flagged are reported per document; the owner rates a sample of 30 of each.
7. **Disable tagging, typing, description and the description check; point Ask, Evidence and result cards at the explained text; reindex.** Pass: the Ask and Evidence smoke checks still return grounded answers; the tests pass; the owner compares a few Ask answers with and without the description. The frontend tag and type filters will have nothing to filter on; the PR states what happens to those controls.
8. **Later, each with its own plan:** the faithfulness check (14B, rated by the owner in the way the draft questions were: 30 rows, with a registered bar); the repair step and re-check (the owner rates 30 repaired rows as usable, needs an edit, or wrong, with a registered bar; also reported: how many flagged rows pass the re-check, and how many repaired texts break the guard); the model-picks step (after the rebuilt test groups).

## 8. Decisions

**Settled by the owner (2026-10-09):**
- `source_quote` stays the name of the root.
- `confidence` is dropped from the default path (commented out, code kept; it may return as something real later). When it goes, the Evidence service, which picks each group's representative by highest confidence, needs another rule (for example, the highest search score); that belongs to step 12's PR.
- A row that fails the re-check is flagged and kept, never dropped.
- Screening rejects only an empty quote, a bare heading echo, a change-log entry, and a quote that cannot be anchored and fails the existing grounding thresholds. Every other screening rule flags.
- Tagging, typing, description and the description check are disabled, code kept, no option flag.

**Proposed, and settled unless the owner objects:**
- **One file per step**, each a full copy of the records plus the fields that step adds (the pattern `normalized` to `enriched` to `gated` already follows); nothing is rewritten in place, and readers take the latest file. The artifact resolver's name list is updated in the rename PR.
- **Tags and types in the interfaces:** the web app has no tag or type filter controls (tags appear on the Trace page and in one checklist column, both already handle an empty list). The `domain_tags` and `requirement_types` options of the Ask and Evidence requests stay accepted but answer with a clear message that the filters are off, instead of silently returning no results. The Tags column is hidden in the checklist when no row has a tag.

**Open:**
- **Colon-ending lead-ins.** In the October 2026 run, all 93 records rejected as `unrepairable_fragment_quote` are lead-ins that end in a colon ("CUI training standards must, at minimum:"); judged on the explained text, 91 of the 93 are still lead-ins. Their items carry the duty, and the lead-in is attached to an item when the source backs it. Proposed: keep them out of the checklist rows (they stay in the failures file, which is how they are kept today) and treat them as context, not as requirements; the alternative is to flag them and show them as rows (93 extra rows across the 13 documents).

## 8a. Notes from building step 4

- The sentence rule's merging survives in the explained layer: records that reach the same sentence in the same chunk are shown once, and the other roots are kept in `merged_roots`. De-duplication on the root (step 5) is unchanged, so IDs stay unique.
- A root whose last words are not in the source is not expanded, because those words are often what tells table rows apart.
- Anchoring found that 39 of the 59 glued lead-ins are in the chunk's heading breadcrumb, not its body; they are kept in the explained text and labeled as coming from the heading.

## 9. What this plan does not claim

It does not say the rules are better than a model for context; they are cheaper, auditable and verbatim, and they are weakest where documents have little structure. It rests on the 2026-10-09 re-ingest of the 13 pinned documents; the labeled sets are small and one rater's. Nothing here has been run. The draft-question sidecars and the Qdrant index built before the ID change must be rebuilt after step 4.

## 10. Requirement kind (proposal; nothing in this section is built)

*Written 2026-10-11 from a discussion with the owner, who saw that the pipeline treats every requirement the same way and has too few "if this, then that" paths. This section is a proposal for review: no code, no data and no behavior changes with it. Each stage in 10.6 becomes its own PR, with its measurements and pass rules written down before any result is read.*

### 10.1 What the code does today

The code does branch on what a quote is, in many places, but each place has its own rule and none stores the result. The chart "How one requirement is treated, by kind" in [Architecture](ARCHITECTURE.md) draws every branch. In short:

- **Branches that exist:** Step D can reject a quote for six different reasons (in the October 2026 runs of the 13 documents four occurred: not found in the chunk, 117; cut-off fragment, 93; repeated heading, 40; the earlier change-log check read a generated description, which is always empty, and was removed); whole-sentence expansion and lead-in attachment each have conditions; a citation depends on whether the row sits in a table, a numbered paragraph, an unnumbered paragraph, the cover pages or a form template; `item_flags` marks six sorts of wording; the question writer withholds a question for five flags and adds a rule for negations; two review marks check the question's terms and actor.
- **What does not branch:** requirement finding sends every chunk (paragraph, list, table, definition) through one prompt. No field records what *kind* of statement a quote is (a duty, a prohibition, a permission, a definition, a statement of who the document applies to, a table row, an instruction inside a form). Each later step finds out again, from the wording, only the part it needs, so the same sentence can be handled differently by two steps.

What that costs, measured on the three audit AFIs (779 rows, October 2026):

- 16 rows are instructions for filling in a form template ("Describe what happens to the mission should the asset fail ..."). They are on the sheet with draft audit questions as if they were duties on the unit.
- The negation test fired on 63 of 1,418 rows of the six Air Force documents, 15 of them in the three AFIs, and turned a duty into "Does the unit **avoid** ..." (fixed by a narrower test, under evaluation). With the narrower wording, real prohibitions in the three AFIs number 3 rows (0.4%).
- 32 rows begin by pointing back ("This roster will be maintained ..."): not auditable without the sentence before. 23 rows are cover-page text and 32 are table rows.
- 181 rows (23%) carry no wording cue at all: no modal verb and no imperative verb ("The process begins at the mission owner level ...").

### 10.2 The proposal

One new step, **kind**, between context attaching (step 6) and screening (step 7). It reads the explained text, the citation context and the existing hint flags, and writes its fields beside the root. It does not take a step number yet: steps 7 to 12 keep their numbers in this plan, the status table and the charts. Stage 1 stores the labels in a side file, not in a pipeline step; the step is numbered, and every later step, the status table, the charts and the `--skip-to` mapping are renumbered together in one pull request, when it moves into the pipeline (stage 3 or later).

| Field | Content |
|---|---|
| `kind` | One value from the list in 10.3, or `unknown`. |
| `kind_reasons` | The rule that fired and the words it matched, so the owner can see why. |
| `kind_tags` | Things that are true besides the kind: `refers_back`, `list_item`, `fragment`, and the location of a row whose own words outrank its position (`front_matter`). |
| `kind_by_wording` | Only on a row whose kind comes from where it sits (`table_row`, `form_template_text`, `cover_page_text`): the kind its words alone would give. A duty sentence in a table cell is a `table_row` and, by its wording, a `duty_with_actor`. |

Properties, all from the principles in section 1:

- Rule-based and verbatim: it reads words and position, never a model, and never edits the root or the explained text.
- It flags and labels; it never rejects. `unknown` is a legal answer and is shown as such.
- It follows the one-file-per-step pattern of section 8 (a new file; nothing rewritten in place).
- It moves existing logic to one place. The pieces already in `checklist_audit.item_flags`, the question writer's negation test and the citation labels are read from here in the end, instead of being worked out again in each consumer.

### 10.3 A first list of kinds (a draft for the owner to edit)

Two sorts of kind share this list. Most are decided by the row's **wording** (a duty, a permission, a prohibition, a definition, a statement of who the document covers, a pointer). Three are decided by where the row **sits**: `table_row`, `form_template_text`, `cover_page_text`. A row can be both. The rule, from the owner's rating of 2026-10-11: where a row's own words say who the document applies to, that wins over the front matter it sits in (`applicability`, tagged `front_matter`); otherwise position decides `kind`, and `kind_by_wording` keeps what the words say, so no later step has to guess again and no duty is lost to a position label. Stage 2 chooses question eligibility from `kind_by_wording` for those three kinds, not from `kind` alone.

| Kind | What it is | First rule (wording or position) | Draft treatment |
|---|---|---|---|
| `duty_with_actor` | States what a named party must do | `shall`, `will`, `must`, `is responsible`, `required to`, `ensure` | A question about that party |
| `duty_imperative` | A command with no modal and no stated actor ("Establish partnerships ...") | Opens with an imperative verb; actor read from the heading | A question about the heading's party; flagged when none |
| `recommendation` | Says what should happen | `should`, no stronger modal | Question allowed, marked as a recommendation |
| `permission` | Says what may be done | `may`, `can`, `is authorized to`, no stronger modal | Stays a row; no draft question |
| `prohibition` | Forbids something | a modal followed by `not`, `cannot`, `never`, `prohibited`, `is not authorized / permitted / allowed / appropriate / waivable` | The "is it avoided" question |
| `exemption` | Says something does not apply or is not required | `does not apply`, `is exempt`, `does not have to`, `not required to` | Stays a row; no draft question |
| `definition_or_description` | Defines or describes | no modal and a cue such as `means`, `is defined as`, `such as` | Stays a row; no draft question |
| `applicability` | Says who the document covers | `This Instruction applies to ...` | Kept as context |
| `pointer` | Points elsewhere | `can be found in`, `refer to`, `see paragraph` | Stays a row; no draft question |
| `table_row` | A table cell or row | cited by a table caption | Cited by the table; a question only for a complete sentence |
| `form_template_text` | An instruction or field inside a form template | cited by a figure or attachment caption, in a template of roman-numeral parts | Flagged "instruction for filling in a form"; no draft question |
| `cover_page_text` | Cover-page and preamble text before paragraph 1 | cited as Front matter | Kept; flagged as administrative |
| `unknown` | No wording cue | none of the above | Handled as today; flagged "no wording cue" |

### 10.4 What a first set of these rules says on the three AFIs

A throwaway prototype of the rules above (not repo code), run on AFI 10-2402, 13-550 and 17-203 (779 rows). The rules are first drafts: no rating has been done, and the examples show where they are wrong.

| Kind | Rows | Share | Where the first rule is wrong |
|---|---|---|---|
| `duty_with_actor` | 277 | 35.6% | Includes "To ensure AF capabilities ... can be executed" (a purpose clause, not a duty) |
| `duty_imperative` | 182 | 23.4% | |
| `unknown` | 181 | 23.2% | Third-person present tense ("The CARM Program utilizes ...", "Reviews access lists annually") is a duty in some places and a description in others |
| `permission` | 37 | 4.7% | Includes "so commanders **can** identify ..." (a purpose clause) |
| `table_row` | 32 | 4.1% | |
| `cover_page_text` | 23 | 3.0% | Some are real duties ("Ensure all records ... adhere to ...") |
| `form_template_text` | 16 | 2.1% | |
| `recommendation` | 15 | 1.9% | Includes "... should the asset fail" (a condition) |
| `definition_or_description` | 6 | 0.8% | |
| `pointer` | 5 | 0.6% | |
| `prohibition` | 3 | 0.4% | Includes "TCAs cannot exist without ..." (a description) |
| `applicability` | 2 | 0.3% | |
| `exemption` | 0 | 0% | The rule matched nothing in these three AFIs |

Tags: `refers_back` 32 rows, `list_item` 35 rows.

Two things follow. First, 59% of rows are plain duties that need no special handling, so most of the benefit is in the small kinds and in telling `unknown` from a real duty. Second, `unknown` is the biggest group and the rules cannot split it: that is where a lead-in, a heading or, later, a model label would have to help, which is its own plan.

### 10.5 What reads the kind, in order

1. **The review sheet**: "why it needs a look" reads the kind and tags instead of working them out again.
2. **The draft question writer**: which kinds get a question, and which prompt. This is where the negation fix, the actor rule and the form-template rows meet.
3. **The checklist flags**: `item_flags` becomes a read of the kind, not a second set of rules.
4. **Later, each with its own plan**: the extraction prompt varying by the kind of chunk (a table, a list, a paragraph); search weighting that puts cover-page and template text last.

### 10.6 Stages and measures

Each stage is a separate PR; pass rules are registered before any result is read, as in the previous experiments. The numbers below are proposals for the owner.

| Stage | Change | Pass rules (proposed) |
|---|---|---|
| 1 | Write `kind`, `kind_reasons`, `kind_tags` to a new file for the 13 documents. **No behavior change.** | Kinds computed for every record; the share of each kind reported; the owner rates a seeded sample of 30 rows stratified by kind as right, wrong or unclear: right at least 85% overall and no kind below 70%; the `unknown` share reported. |
| 2 | The draft question writer reads the kind (which kinds get a question; the negation prompt only for `prohibition`). | Same shape as the prohibition-rule test: changed rows against a noise floor, owner rating of the changed rows, no inversion. |
| 3 | The review sheet and `item_flags` read the kind. | Row for row the same flags and reasons as before, except where the owner has settled otherwise. |

### 10.7 Decisions for the owner

**Settled by the owner (2026-10-11):**

1. **The list in 10.3 is kept as drafted** (13 kinds including `unknown`). Stage 1 may start.

**Open, and needed only before stage 2:**

2. **Form-template and cover-page text**: stay on the sheet, flagged, or move to a separate context sheet.
3. **Permission and recommendation rows**: keep a draft question, or none.

**Open, can wait:**

4. **The `unknown` group (23% of rows)**: accept `unknown` for now, or plan a model label for it later (own plan, own rating).

### 10.8 What this does not claim

It does not say rules can recognise every kind: the prototype's `unknown` group and its false matches show where they cannot. It rests on three AFIs and a first set of wording rules that nobody has rated. Real prohibitions are rare in these documents, so the larger gain is likely to come from the form-template, cover-page and `unknown` groups than from prohibitions.
