# WP-45.7 plan: does separating discovery from resolution improve extraction? (measurement only)

Status: **approved by Tyler 2026-10-05** (the resolver stage in scratch, and the held-out labeling), with the decisions in
section 0. Part of `docs/PHASE45_REQUIREMENTS.md`. Everything below runs in a scratch directory against frozen inputs. No
production code, prompt, schema, index or configuration changes.

## 0. Decisions (Tyler, 2026-10-05)

- **The resolver idea is approved** for scratch measurement. Tyler is confident it will help; the gates in 4.5 still decide
  whether anything reaches production.
- **"Should" and "may" statements are requirements.** A recommendation ("you should ...") or a hint at one, and a permission,
  are extracted, because sources such as NIST rarely say "must". The stored record keeps the modality so an end user decides
  what to enforce in an audit. The sample's labeling already counts "should" recommendations as obligations; permissions
  (`may`) now count too, so the precision tally treats a correctly kept permission as a true positive, not a false one. The
  dev labels were made before this ruling for permissions: any dev piece whose only modal is "may" is re-checked by Tyler
  before it enters the precision tally.
- **Lean toward over-extraction.** Deleting a row is cheap; missing a whole clause is not. Consequence for the gates: recall is
  the primary measure, and a precision cost is acceptable if every kept-but-doubtful candidate is flagged and recoverable
  (status `unresolved` or `scope_or_context`), never silently dropped. G3 below reflects this.
- **Process: every iteration is a PR.** This work runs in a remote session with no local Codex, so each plan revision, tool and
  result is pushed as its own small PR for the Codex connector and the Gemini workflow to review. One open branch at a time.

Prior art checked first (per the "check prior art" rule): this overlaps WP-45.2 C4 (neighbor window), WP-45.3 (pass two and
grounded standalone statement), the parked "14B over-extract prompt", and backlog item 23 (Step C prompt changes are "the
riskiest lever demonstrated": reference-list leakage fixes were unstable across two runs, and a longer prompt made the 8B
regurgitate its few-shot examples verbatim). This plan does not replace those. It is the smallest test that tells us which of
them is worth building, and it carries the regurgitation risk as a measured outcome.

## 1. The question

WP-45.1(e) put the loss at extraction: 26 of 74 source obligations were never extracted (35%), 3 more only partly. Two ideas
follow from that and from the review notes Tyler brought in:

- **H1 (discovery).** A discovery prompt written to be inclusive about *candidate* source spans (third-person duty statements,
  imperatives, "should", prohibitions, permissions, list items) finds more of the source obligations than today's "MUST DO"
  prompt, on the 8B.
- **H2 (resolution).** A second call that takes one candidate plus a code-assembled evidence bundle can (a) say whether the
  candidate is really an obligation (so broad discovery does not cost precision), and (b) resolve actor, modality, conditions,
  exceptions and the governing clause with every field tied to a source span, better than today's deterministic stem rules
  (about 40% right, 39% misleading, 20% incomplete in the WP-45.1(b) audit).

The separation is only worth building if **H1 raises recall and H2 gives the precision back and improves attachment**, on
documents we did not tune on. Either half alone is a different, smaller decision.

## 2. What the research says, and where it does not transfer

I read Haque and Singh in full for Sections 3 to 4 (arXiv 2404.02269) and the Galli et al. ICAIL 2025 version
(`doi.org/10.1145/3769126.3769260`, open access) including its repository's prompts (`github.com/thiagordp/obligation_extraction_for_compliance`,
`data/raw/prompts/`). The journal version (Computer Law & Security Review) returned 403, so its Section and Appendix numbering
may differ from the ICAIL text I read; the workflow and prompts are the same ones the repository ships.

| Finding | Source | What it means for us | Where it does not transfer |
|---|---|---|---|
| Three separate calls: candidate detection (regex), classification into definition / constitutive / obligation / entitlement / authorisation / prohibition / not applicable, then structured analysis | Galli 4.1 to 4.3 | Supports splitting "is it an obligation" from "what does it say". The class list is a ready vocabulary for the resolver's status | Their detection is a **keyword regex** ("shall", "must", "should", "has/have to"), so it cannot find verb-free duty statements, which are most of our misses. Their coverage was never measured |
| Sentence plus paragraph, and for analysis the whole article plus explicitly cited provisions | Galli 4.1, 4.3 | Evidence bundle should include a governing clause and cross-references, not just the quote | EUR-Lex XML gives clean paragraph and article boundaries. Our context comes from Docling chunks with a measured 39% wrong-stem rate, so our bundle must label unverified context as unverified |
| Each element carries an `extraction_method`: Stated / Context / Citation / Background-Knowledge / None, and they report it reduced hallucination | Galli 4.3 | Adopt per-field provenance. Our version is stricter: the model cites evidence span ids and **code** checks them, and Background-Knowledge is not allowed (Tyler's constraint) | The model's own provenance label is self-reported and was not independently checked in the paper |
| Accuracy: filtering 0.84; analysis type 0.94, addressee 0.90, but GDPR specifications 0.61 and pre-conditions 0.45 | Galli 5.3 | Conditions and specifications are the weak fields even for a 70B model; we should expect it to be our hardest axis | LLaMA 3.3 70B, 30 sentences per regulation, two raters, **accuracy only**; the authors state the design "does not take into account false positives or negatives". It says nothing about recall |
| Clearer definitions of norm types and party roles, with the direction of the relationship stated, beat rewording; wording tweaks mattered little | Haque 3.2 | Put effort into definitions and examples, not paraphrasing. Spell out that the approver or authorizer is not the actor | ChatGPT on 150 contract clauses, single sentences, no document context |
| Error types: "may" extracted also as a commitment (confuses must-do with can-do), missing conditions and dates, hallucinated expansion of an acronym, conjunctions split wrongly; they propose a separate prompt to break conjunctions down first | Haque 4 | These are the failure modes the resolver must be tested for: modality strengthening, dropped conditions, invented names, AND/OR | Qualitative examples, no rates in the sections I read |

Limits I want on the record: neither paper is a benchmark for ReqBot's material (policies, instructions, guidance prose, tables
from PDFs). Neither measures recall. Both used models far larger than the 8B we run. Their results motivate the design; our own
measurements decide it.

## 3. Review of today's calls (what the code does, verified in this branch)

Nothing here is assumed absent: the neighbor window (C4), the pass-two idea and the heading prefix are *planned*, not built.

The "Kind of change" column names the layer a production fix would touch. This experiment changes only the scratch resolver's
own output schema; it does not change the discovery output or any production schema (see the table after Call 2).

### Call 1: Step C extraction (`pipeline/llm_extract_requirements.py`, `PASS1_PROMPT_TEMPLATE`)

Input: one chunk's text (Docling breadcrumb injected into it) plus a regex-found list of candidate source refs. No neighbors.
Output: `{source_quote, source_ref}` only, constrained by a JSON schema. `num_ctx` 8192, `temperature` 0.1.

| # | Weakness | Evidence | Kind of change |
|---|---|---|---|
| C1 | The task is defined as "something an organization **MUST DO**", with "ONLY task" and an obligation-verb list (`shall, must, ..., will, are to`). A literal reader (the 14B) obeys it and drops whole chunks | WP-45.6: 173 vs 435 records; WP-45.1(e): 14B covers 27% of source obligations vs 61% | Prompt |
| C2 | The verb list has no `should`, no prohibition forms, no `may`. The sample's labeling (and Tyler's ruling) counts "should" recommendations and verb-free duty statements as obligations | WP-45.1(e) never-extracted pieces (26): 13 are AFMAN 2.3.x third-person duty items ("Provides / Serves as / Reviews ..."), 3 are AFMAN imperatives or a "responsibility to provide" sentence, 8 are NIST imperatives or "should" / "needs to" statements, 2 are DODI conditional "shall" sentences (read from the trace, not yet classified by a second reader) | Prompt, and a product decision about recommendations |
| C3 | All three few-shot examples are either "shall" sentences or an "enforces" sentence, or a no-requirement case. None shows a list item with an inherited subject, an imperative, a prohibition, a recommendation, a permission, an exception or a cross-reference | Prompt text | Prompt |
| C4 | The only "not" categories are definitions, change logs, headings, cross-references and "general background". Scope text ("this issuance applies to ...") has no home, though Tyler wants it kept and attached | Tyler 2026-10-04 | Prompt plus a keep-and-flag bucket |
| C5 | Binary output: keep or drop. An uncertain span has nowhere to go but out, which is exactly the loss we measured | No `uncertain` or `kind` field | Schema (scratch only here) |
| C6 | The quote must be one contiguous verbatim span under 500 characters, so a list item cannot carry its stem. This is right for fidelity but means the governing clause is never captured at discovery | Step D grounding rules | Schema (optional second field, later) |
| C7 | Context is one chunk. A stem or definition across a chunk boundary is invisible | `docs/PHASE45_REQUIREMENTS.md` C4 detail | Context assembly |
| C8 | Few-shot regurgitation risk: a longer prompt made the 8B emit its examples verbatim on a clean chunk, twice | Backlog item 23 | Validation (measure and gate it) |

### Call 2: Step D.5 enrichment (`pipeline/enrich_requirements.py`)

Input: **only the quote** (batch of N, or single) plus the ref. Output: one-sentence `description`, domain tags, `requirement_type`.

| # | Weakness | Evidence | Kind of change |
|---|---|---|---|
| E1 | The call never sees the chunk, the heading, a stem or a neighbor, so it *cannot* resolve actor or conditions; a fragment gets a description that either echoes it or invents the missing part | Backlog item 23 category 3 (most dangerous); audit F06 | Context assembly |
| E2 | `requirement_type` (policy / technical-control / ... / guidance) mixes category with modality; nothing records shall vs should vs may | Profile `requirement_types` | Schema |
| E3 | The entailment gate's premise is the bare quote. A faithful sentence that restores a verified stem would look unsupported | Audit F06; WP-45.3 note | Validation |
| E4 | Deterministic stem reconstruction runs after the LLM, with about 40% right and 39% misleading attachments; downstream treats it as fact | WP-45.1(b) | Validation (provenance and a "may be wrong" label) |
| E5 | The checklist export ignores `parent_stem`, `embedding_text` and `description`, so any improvement above is invisible to users until an export change | Audit F06; WP-45 section 7 | Downstream display (out of scope here) |

### What changes where (so a prompt gain is not credited to a context gain)

| Layer | In this experiment | Not in this experiment |
|---|---|---|
| **Prompt** | Discovery v2 definition and examples (D1); resolver prompt (R) | Enrichment prompt rewrite |
| **Context assembly** | Deterministic evidence-bundle builder, three tiers (R0, R1, R2) | A model-requested retrieval loop (sized from the unresolved cases, built only if they justify it) |
| **Schema** | Scratch-only resolver output; scratch-only `kind` field is *not* added to discovery in the first run | Any change to production record fields |
| **Validation** | Field-specific code checks (section 4.6): cited ids exist; extractive fields found in the cited spans after whitespace normalization of both sides; modality phrase copied verbatim and consistent with its class; categorical fields checked by derivation rules; composed fields checked for added numbers, names and modality; the existing grounding check applied unchanged to discovery quotes | New Step D rules |
| **Caching** | Scratch cache keyed by chunk id + prompt hash + **model digest + run label** (discovery; "model digest" is the `digest` Ollama reports for the exact model file, a sha256 of its manifest, read from `/api/tags`, so a replaced model file changes the key; each repeat and each model is its own run label with its own ledger, so a second repeat or the 14B arm can never reuse an earlier answer) and quote hash + bundle hash + prompt hash + model digest + run label (resolver) | Changes to the WP-45.0.2 ledger |
| **Display** | Nothing | Checklist or GUI changes |

## 4. The experiment

Smallest design that can answer section 1. One change per run, each proven against the same labeled pieces. Everything lands in
`eval/spike_results/wp_45_7/` (scratch), reusing `loss_trace.py`, `score.py`, the 254 labeled pieces and the page bootstrap from
WP-45.1(e).

### 4.1 Inputs

- **Development set (already labeled).** The 12 pages and 254 pieces of WP-45.1(e), 78 adjudicated obligations (74 with sound
  segmentation), including the 26 never-extracted and 3 partly extracted pieces. This is where prompts may be tuned.
- **Resolver gold (already labeled).** The WP-45.1(b) attachment audit records with Tyler's adjudicated lead-ins (the governing
  clause or party each record needs), plus the 90 labeled 8B-only / 14B-only disagreement cards from WP-45.6 (real requirement
  or not, agreed by two labelers on 79). These are the "troublesome fragments and disagreements".
- **Held-out set (new, to be created).** A seeded draw of 16 pages from at least five documents **not** among the three dev
  documents, stratified across formal policy, guidance prose, a control-catalog style and a table-heavy page, cut and labeled by
  the same pipeline as 45.1(e) (`draw.py`, `segment.py`, `pack.py`): Claude and Codex label independently and blind, Tyler
  adjudicates disagreements about obligation status and spot-checks a few agreements. **Frozen (page list and piece hash)
  before either new prompt is finalized, and not opened for tuning.** Rough load: about 350 pieces per labeler, perhaps 25 to
  30 disagreements for Tyler, the same shape as the last sample.
- **Kind labels (new, small, needed for the G2 status-agreement gate).** The existing labels say obligation or not, not which
  kind. Every adjudicated obligation in the dev set (78) and the held-out set gets one more label, `kind`: `obligation`
  (mandatory wording, including "will" and a verb-free duty under a mandatory lead-in), `recommendation` ("should", "is
  recommended", "should not"), `permission` ("may", "is authorized to") or `prohibition` ("shall not", "must not",
  "is prohibited from"). Claude and Codex label `kind` blind and independently in the same pack as the held-out pieces (for
  dev, a small extra pack of 78 items), Tyler adjudicates disagreements, and this is also where the dev pieces whose only
  modal is "may" get their re-check (section 0). The resolver gold for `status` is this label. The 90 disagreement cards need
  no kind (they are scored real or not).
- Prompt examples are **invented text** (a fictional agency and system names), never taken from the dev or held-out pages.

### 4.2 Runs

| Run | What | Models | Repeats |
|---|---|---|---|
| **D0** | Production discovery prompt (baseline). Dev already measured: fresh 8B equals production, noise floor 1 piece each way. Run on held-out | 8B | 2 |
| **D1** | Discovery v2 (appendix A): inclusive definition plus new examples. **Same output schema, same Step D** | 8B | 2 |
| **D1-14B** | Same D1 prompt on the 14B. This is the parked "14B told to over-extract" test; it costs one more run and answers whether the 14B's literalness was the prompt | 14B | 2 |
| **R0 / R1 / R2** | Resolver (appendix B) on **oracle candidates** (the labeled obligations and the audit records, so resolver quality is not confounded with discovery). Bundle tiers: R0 quote only (today's D.5 information); R1 adds own chunk, the leaf heading and the code-found stem candidates labeled "unverified"; R2 adds the bounded tail of the previous chunk and head of the next | 8B and 14B | 1 (temperature 0.1; any disagreement between a rerun and the first run on 20 sampled items is reported) |
| **E2E** | D1 output through the resolver at the frozen tier, compared with D0 and D1 alone on the same chunks | 8B discovery; resolver tier and model as **frozen from the dev and audit R results before the held-out labels are opened** (section 4.4) | 2 for discovery |

Discovery runs only on the chunks that overlap the sampled pages (their ids are in the frozen manifests), not on whole
documents. **Label set closed over the selected chunks:** a Docling chunk can span pages, and a real requirement from an
unsampled neighboring page has no label to match, so it would be wrongly counted as a false positive (differently for D0 and
D1). Two rules prevent that. (1) Held-out: after the draw, the page set is extended to every page any selected chunk touches
(`_chunk_page_range` gives the range) and all of those pages are labeled before any run; the freeze records the closed set.
(2) Dev: chunks whose page range reaches beyond the 12 labeled pages are listed up front; a record whose quote is found only
in unlabeled text is **unscored**, reported by count for every arm, and never counted as a false positive or a miss. If unscored
records exceed 10% of an arm's records, that chunk set is dropped from the precision tally and the report says so. A 10-call
pilot measures latency, the resolver's structural conformance (below) and these counts before any full run.

### 4.3 Measures (all against source-labeled pieces, never against record counts)

| Axis | How |
|---|---|
| **Obligation recall** | Share of adjudicated obligations whose chunk records reproduce at least 90% of their tokens (the 45.1(e) trace rule, unchanged), with the page-level bootstrap interval; reported at extraction and after the resolver |
| **Precision** | Share of kept records that overlap an adjudicated obligation piece; records overlapping only non-obligation pieces are false positives, split into scope text, background, role description and cross-reference-only. Uncertain candidates kept as `unresolved` are counted in their own bucket, not hidden in either side |
| **Scope fidelity** (resolver) | Per record, two blind labelers, a fixed checklist: modality unchanged (shall / should / may / must not preserved), conditions kept, exceptions kept, timing kept, no invented party or number, AND/OR preserved. Code pre-checks the modal word and any new numbers or proper names |
| **Attachment correctness** | Resolved actor and governing clause against Tyler's adjudicated lead-in on the audit records: right / misleading / incomplete, the same three categories as today's baseline |
| **Unresolved cases** | Rate; and for each, a labeler says whether wider context would have resolved it and where (same page, previous page, a cross-referenced section). That sizes any later retrieval loop without building it |
| **Cost** | Ollama's own `prompt_eval_count`, `eval_count` and `total_duration` per call; extrapolated to the corpus (about 1,845 records, which the resolver would call one by one) as a stated estimate, labeled as such |
| **Health only** | JSON validity, Step D rejection codes, regurgitation count (any 8-word run from a prompt example appearing in an output). Valid JSON is never reported as a success measure |
| **Structural conformance** (resolver pilot) | Per field, the share of outputs whose shape is what the schema asked for and not merely parseable, using each field's own shape: most fields need `value` and `evidence`; `modality` needs `verbatim` (string or null), `class` (obligation, recommendation, permission, prohibition or none) and `evidence`; `conditions` and `exceptions` need arrays of `value` and `evidence` objects; and evidence ids must come from the bundle. If `conditions` or `exceptions` are often malformed on the 8B, the fallback is a flat list of strings with the evidence taken from the whole bundle, or more examples, decided before the full run |

### 4.4 Rules fixed before any run

- Tune on the dev set only, at most two revisions per prompt; then freeze (hash recorded) and run the held-out set once.
- **Every configuration choice is made and frozen before the held-out labels are opened for any run:** the discovery prompt,
  the resolver prompt, the bundle tier (R0, R1 or R2) and the resolver model (8B or 14B) are chosen from the development
  pages and the existing audit data (the WP-45.1(b) records and the WP-45.6 cards) only, and recorded with hashes. The held-out
  run then uses exactly that frozen configuration, once; the held-out set is never used to pick between R0/R1/R2 or 8B/14B.
- Two repeats for every discovery arm. Backlog item 23 showed a single A/B can flip on rerun, so a result counts only if both
  repeats agree in direction.
- Report counts next to percentages. With 74 dev obligations an interval is wide (the 45.1(e) interval is plus or minus
  about 17 points); a gain is called real only if it clears the repeat noise **and the held-out pages' own bootstrap
  interval excludes zero**. The development pages were used for tuning, so their interval is reported descriptively and is never
  pooled into the confirmatory test. Sixteen held-out pages give a wide interval; if the held-out point estimate passes the gate
  but its interval includes zero, the outcome is **inconclusive** (extend the held-out set before deciding), not a pass.
- No arm is chosen for having more records.

### 4.5 Gates (set now, applied after)

| Gate | Pass | If it fails |
|---|---|---|
| **G1 discovery** | D1 recall on held-out at least 10 points above D0 in both repeats, no fall on dev, regurgitation count 0 after Step D, Step D rejection codes not up | Stop the prompt direction; record why; C4 and pass two remain the options |
| **G2 resolver** | Attachment "right" above today's 40% and "misleading" at or below today's 39%; **zero** strengthened modality (code check, and no case in the hand audit); invented party or number rate at or below 2%; **status accuracy** against the adjudicated labels: at least 90% of real obligations (oracle candidates) must receive a **requirement status** (`obligation`, `recommendation`, `permission` or `prohibition`); at most 5% may be returned `not_a_requirement`; every oracle obligation returned `scope_or_context` or `unresolved` is listed and hand-read, and together those two may not exceed 10% (so no single catch-all label can stand in for a decision, and a resolver that never distinguishes requirements fails); the status must also match the adjudicated kind (`should` as `recommendation`, `may` as `permission`), reported as an agreement rate. On the labeled non-obligation candidates (the 90 disagreement cards plus non-obligation pieces D1 returns) at least 60% must come back `not_a_requirement` or `scope_or_context` rather than `unresolved` or a requirement status | Fix the prompt or tier once on dev; if still failing, stop and report |
| **G3 separation** | E2E recall keeps at least 80% of D1's recall gain; precision of the kept set, with `unresolved` candidates **counted as kept** (so a resolver that marks everything `unresolved` restores nothing and fails), is within 10 points of D0; and `unresolved` is at most 25% of kept candidates. Tyler's over-extract lean (section 0) is honored by retaining doubtful candidates as flagged and recoverable, never by letting `unresolved` stand in for a decision | Report that broad discovery alone or the resolver alone is the better half, whichever the numbers show |
| **Evidence limit** | Passing means "improves on these documents and this labeling," not that production quality is proven | State it in the report |

### 4.6 Resolver validation, by field type

A blanket "value is found in the cited span" check would reject correct output and weaken the provenance claim, so each field
type gets its own check. Every containment test runs on whitespace-normalized text on **both** sides (the same normalization
function as the bundle builder), so raw Docling spacing or soft hyphens cannot cause a false failure.

| Field type | Fields | Check |
|---|---|---|
| Extractive | actor, action, target, applicability, conditions, exceptions, timing, parent (the governing-clause text must be found in a cited span, so an invented or paraphrased parent fails) | Value found in at least one cited span (normalized); cited ids exist |
| Modality | modality | `verbatim` found in a cited span (normalized); `class` consistent with the phrase through a fixed mapping table with synonyms (obligation: shall, must, will, is required to, has to, is to; recommendation: should, is recommended, and the negative forms should not and ought not, which stay `recommendation` (a negative recommendation is never strengthened to `prohibition`); permission: may, is authorized to, is permitted to; prohibition: shall not, must not, is prohibited from, never, forbidden); a null phrase must come with class `none` and is not string-matched |
| Categorical | status, logic | Derivation rules where a rule exists (`recommendation` needs a recommended phrase, `permission` a permitted phrase, `prohibition` a prohibited phrase; `logic` other than `none` needs and/or text in a cited span); no literal-containment test, since `obligation` or `unresolved` never appear in the text. Statuses with no rule (`scope_or_context`, `not_a_requirement`, `unresolved`) are scored by the labelers, not by code |
| Composed | standalone_statement, plain_language | `standalone_statement` adds no number, acronym or proper name absent from **its cited spans** (the rule ignores a sentence's first word and a stoplist of common capitalized words such as articles, pronouns and prepositions, and compares tokens case-insensitively, so reordering a sentence or starting it with "The" does not fail; a token counts as new only if it is all capitals, contains a digit, or is capitalized mid-sentence, and has no match in the spans); `plain_language` is checked against the same set (the spans cited by `standalone_statement`, and the standalone sentence itself), and must be null when `standalone_statement` is null, so a faithful rendering that keeps "90 days" or an actor name passes and an added one fails; modal class unchanged; the entailment gate with the evidence bundle as premise (the WP-45.3 change to the gate); hand audit for faithfulness |
| Explanatory | unresolved_reason | Not validated by code; read in the unresolved-case labeling |

## 5. Build list (scratch only, each testable)

1. `bundle.py`: deterministic evidence-bundle builder (own chunk, leaf heading, existing stem finders' candidates marked
   unverified, bounded neighbors, cross-reference detector for patterns like "paragraph 2.3", "Section 4", "AC-2", run on whitespace-normalized
   text: collapse newlines and repeated spaces and rejoin soft-hyphenated line breaks, since Docling output carries such
   artifacts, with unit tests on "Section\n4" and "paragraph  2.3"). **Window safety:** the builder budgets with a conservative
   2.5 characters per token (dense JSON and Docling text tokenize worse than the 3-per-token fallback the pipeline uses when
   Ollama reports no count) and caps the whole prompt at about 6,500 estimated tokens, leaving room for the answer inside the
   pinned 8,192. Because Ollama does not stop or error when a prompt overruns the window (it drops the start of the prompt, which
   holds the instructions), the runners also read `prompt_eval_count` after every call and mark any call where
   `prompt_eval_count` plus `eval_count` (both Ollama token counts, never character lengths) reaches `num_ctx` as a **window overrun**. An overrun is a **failure, never an exclusion**: dropping those calls would remove the longest and
   likely hardest inputs, and the larger-prompt arms (D1, R2) are the most exposed, so an arm could look better by overrunning.
   Obligations in an overrun chunk stay in the recall denominator as misses; for the resolver the call counts as a failed
   resolution; and every arm is also required to have an overrun rate of at most 2% to pass its gate, with the count reported. Unit tests include a bundle that would overflow and must be truncated from the neighbors
   first, never from the instructions. Standard library only: the experiment needs and plans no new dependency (no tokenizer
   package; the post-call count is the check).
2. `run_discovery.py` and `run_resolver.py`: call Ollama with pinned `num_ctx`, write the raw answer before parsing (as Step C
   does), record model digest and prompt hash. No hardcoded endpoint or model: `--ollama-url` and `--model` arguments, with
   defaults read from `~/.config/reqbot/config.json` and `REQBOT_*` overrides (CLAUDE.md: pipeline scripts must be given the
   URL explicitly, since `localhost` is this container, not Tyler's machine), and the project's argparse validators for numeric options
   (`_positive_int` for integers such as `--num-ctx`, `_non_negative_float` for `--temperature`). The runners take page and chunk
   manifests, not domain-tag or requirement-type filters, so no filter-flag normalization is needed. If such a flag is ever
   added, it reuses the production normalization; moving that helper out of `cli/console.py` into a shared module so a
   pipeline script can import it without a layer violation is a separate refactor, not part of this experiment.
3. `check_resolution.py`: the field-specific validations in section 4.6, plus the example-regurgitation scan for discovery.
4. Reuse of `loss_trace.py` and `score.py` for recall, plus a small precision tally.
5. A labeling pack for the resolver outputs and the held-out pieces, built like the 45.1(e) pack.

## 6. What this plan does not decide

- Whether a resolver stage ships, whether discovery's schema gains `kind` or a verbatim `lead_in` span, whether "should"
  recommendations and permissions become first-class records, or whether `modality` becomes a stored field. Each is a
  production change and a separate approval, informed by the numbers above.
- **Production migration of a changed Step C prompt.** Any edit to `PASS1_PROMPT_TEMPLATE` changes the prompt hash and so
  invalidates every cached Step C result for the corpus (resume is keyed by chunk id and prompt hash; a full re-extraction, plus
  re-enrichment and reindex, follows). If G1 passes and Tyler approves a production change, the migration plan, with the cache
  invalidation and a before/after index comparison, is its own WP and its own PR. This experiment never touches the production
  cache; scratch runs use their own ledger.
- **How `standalone_statement` and `plain_language` relate to today's `description`.** They are scratch outputs here. If the
  experiment passes, deciding whether they replace or sit beside `description` (and `source_quote` stays the untouched
  evidence either way) is a production schema decision with its own approval; nothing in this plan assumes the answer.
- The model-requested retrieval loop. The unresolved-case labels size it; it is built only if those cases justify it.
- Any fix to the checklist, which still ignores stems and descriptions (audit F06).
- Whether the resolver should run on the 14B for precision and the 8B for discovery. The R runs report both; the choice
  follows the data.

## Appendix A: discovery prompt v2 (draft, for review before any run)

Replaces the opening definition and the example block of `PASS1_PROMPT_TEMPLATE`. The output schema, the verbatim-quote rule,
the `{source_ref_hints}` and `{chunk_text}` slots stay as they are. The existing "do not extract" bullets are **replaced** by the list below, in particular the old "General background, context, or informational text" bullet, which would drop scope text before the resolver sees it. Examples are invented.

```
You are finding CANDIDATE requirement passages in a cybersecurity compliance document.
Be inclusive: a later step decides which candidates are real, so do not drop a passage because you are unsure.

A candidate is a passage that tells a party what it must, should, may or must not do. Return passages such as:
- shall / must / is required to / will statements
- "should" or "is recommended" statements (recommendations)
- "shall not", "must not", "is prohibited" statements (prohibitions)
- "may" or "is authorized to" statements (permissions)
- Third-person duty statements with no modal verb, often list items under a lead-in such as "The Director will:",
  for example "Reviews access lists annually." Return the item itself, even if its lead-in is not in this text.
- Imperative instructions, for example "Disable unused services."
- When a sentence contains a condition or exception (if, unless, except, provided that), copy the whole sentence.
- Scope or applicability statements ("This manual applies to all network operators"). They are not requirements, but the next
  step keeps and attaches them, so return them.

Do NOT return:
- definitions, change logs, tables of contents, headings
- a cross-reference by itself ("See also AC-3")
- background that describes how something works and tells nobody to do anything
- statements of what a role is or is located in, with no action anyone could perform or be audited on
```

Examples to add (fictional):

1. Inherited list subject. Text: `4.2 The Records Officer will:\na. Provides quarterly retention reports to the Program Office.\nb. Reviews disposal schedules each year.\nc. Is based in the Northern Annex.`
   Output: items a and b as separate candidates; c is not returned (a location, not a duty).
2. Prohibition, recommendation, permission. Text: `Users shall not share accounts. Administrators should rotate shared secrets every 90 days. The Authorizing Official may grant a waiver for up to six months.`
   Output: three candidates, each quoted whole.
3. Exception and nested items. Text: `Contractors shall encrypt backups unless the Program Manager grants a written exception.\n(1) Keys must be stored apart from the data.\n(2) Key custodians shall be named in writing.`
   Output: the first sentence whole (exception kept), then (1) and (2) as separate candidates.
4. Cross-reference. Text: `AC-9 Review. See also AC-3 and IA-2. Where paragraph 4.2 applies, the Agency shall comply with Section 6.`
   Output: only the "Where paragraph 4.2 applies ..." sentence.
5. No candidates. Text: `Virtualization is the practice of running several operating systems on one machine. It is widely used in data centers.`
   Output: `{"requirements": []}`.

Expected size: the template grows by roughly 500 to 600 tokens (to be measured, against the window and the cost estimate in
the Phase 45 plan).

## Appendix B: resolver prompt v1 (draft, for review before any run)

**How this is shown to the model.** The block below is a specification for reviewers, not the literal prompt text. The model is
shown (a) the field list and the allowed values in plain prose, and (b) the worked examples as strictly valid JSON with no
comments and no placeholder tokens; the shape itself is enforced by the JSON Schema `format` constraint. A pseudo-JSON
template with comments and unquoted alternatives is not put in the prompt, because 8B models tend to copy such placeholders
into the answer. A test renders the final prompt and fails if any example in it does not parse as JSON.

Fields that may be empty are nullable in the JSON Schema (`standalone_statement.value`, and every `value` that can be "not
stated"), so a literal `null` is valid output, not a parse failure.

Size estimate (to be measured in the 10-call pilot): the template below is about 450 tokens at the 3-characters-per-token
estimate (about 540 at the 2.5 the builder budgets with); the seven worked examples add roughly 1,000; the evidence bundle is
capped at 3,000; the answer is expected under 600. That is about 5,000 of the pinned 8,192, so the bundle cap, not the
template, is what protects the window.

One candidate per call. Code builds the bundle; the model never sees the whole document.

```
You are resolving ONE candidate requirement using only the evidence below. Do not use outside knowledge.
Every field is an object with a `value` and the evidence ids that support it. If the evidence does not support a field, its `value` is null and `evidence` is empty.

Evidence (each span has an id; "unverified" spans were found by a rule and may be wrong):
[E1] candidate quote: "..."
[E2] same chunk: "..."
[E3] heading (leaf): "..."
[E4] possible governing clause (unverified): "..."
[E5] previous chunk, last lines: "..."

Return JSON (the allowed values below are enforced by a JSON Schema `format` constraint with `enum` keys, as Step C does with
`_PASS1_FORMAT_SCHEMA`; the prompt lists them in prose too, never as `a | b` unions the model might copy literally):
{
 "status":     {"value": one of obligation, recommendation, permission, prohibition, scope_or_context, not_a_requirement, unresolved, "evidence": [...]},
 "actor":      {"value": ..., "evidence": ["E#"]},   // the party that must act. An approver or authorizer is NOT the actor.
 "action":     {"value": ..., "evidence": [...]},
 "target":     {"value": ..., "evidence": [...]},
 "modality":   {"verbatim": the exact modal phrase copied from a cited span ("shall", "is required to", "is prohibited from", "should", ...) or null for an imperative with no modal,
                "class": one of obligation, recommendation, permission, prohibition, none, "evidence": [...]},  // the phrase is copied, never edited; the class is the strength it carries, in the same words as status
 "applicability": {"value": ..., "evidence": [...]}, // who or what it applies to
 "conditions": [{"value": ..., "evidence": [...]}],
 "exceptions": [{"value": ..., "evidence": [...]}],
 "timing":     {"value": ..., "evidence": [...]},
 "parent":     {"value": the governing clause text, or null, "evidence": ["E#"]},
 "logic":      {"value": one of and, or, none, "evidence": [...]},  // how this item relates to sibling items, only if the text says so
 "standalone_statement": {"value": a string or null, "evidence": [...]},  // one sentence built only from the cited spans; keep modality, conditions, exceptions
 "plain_language": {"value": a string or null, "evidence": []},     // one sentence, no new facts; derived from standalone_statement, so the evidence list stays empty and code checks it adds no number or name
 "unresolved_reason": {"value": a string or null, "evidence": []}   // what is missing and where it might be (previous page, section X); explains an absence, so the evidence list stays empty
}

Rules: never turn "may" or "should" into "shall"; the modality class must match the phrase you copied ("should" is a recommendation, never an obligation). Never name a party that no span names. A list item inherits its subject from
the lead-in span you cite. If the standalone statement cannot be built from the spans without adding a fact, return null for it.
```

Worked examples to include (fictional), each as bundle plus expected JSON:

1. Inherited subject: candidate "Reviews disposal schedules each year." with E4 "The Records Officer will:" gives actor
   "The Records Officer" from E4, modality phrase "will" (class `obligation`) inherited from the lead-in in E4 (`null` phrase and class `none` are only for an imperative with no modal anywhere in the cited spans), timing "each year" from E1.
2. Prohibition with exception: "Contractors shall not transmit logs offshore unless the Program Manager approves in writing."
   gives status `prohibition`, actor "Contractors" (not the Program Manager, who is the approver), exception cited.
3. Permission not strengthened: "The Authorizing Official may grant a waiver" gives `permission`, modality `may`, never `shall`.
4. Recommendation: "Administrators should rotate shared secrets every 90 days." gives `recommendation`, modality `should`.
5. Nested requirement: sub-item "(2) Key custodians shall be named in writing." under "(a) Backups shall be encrypted"
   gives `parent` = the span for (a), `logic` NONE.
6. Cross-reference needing context: "Comply with the requirements of paragraph 4.2." where no span contains 4.2 gives
   `unresolved`, with `unresolved_reason` "paragraph 4.2 is not in the evidence".
7. Scope text: "This manual applies to all Air Force network operators." gives `scope_or_context`, kept and not a requirement.
