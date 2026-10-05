# WP-45.7 plan: does separating discovery from resolution improve extraction? (measurement only)

Status: **proposal, not approved** (2026-10-05). Part of `docs/PHASE45_REQUIREMENTS.md`. Everything below runs in a scratch
directory against frozen inputs. No production code, prompt, schema, index or configuration changes. It adds a new LLM stage
(the resolver) in scratch only, so it needs Tyler's approval before any code is written.

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
| **Validation** | Code checks: cited ids exist, value found in cited span, modal word unchanged, no new numbers or names; the existing grounding check applied unchanged to discovery quotes | New Step D rules |
| **Caching** | Scratch cache keyed by chunk id + prompt hash (discovery) and quote hash + bundle hash + prompt hash + model digest (resolver) | Changes to the WP-45.0.2 ledger |
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
- Prompt examples are **invented text** (a fictional agency and system names), never taken from the dev or held-out pages.

### 4.2 Runs

| Run | What | Models | Repeats |
|---|---|---|---|
| **D0** | Production discovery prompt (baseline). Dev already measured: fresh 8B equals production, noise floor 1 piece each way. Run on held-out | 8B | 2 |
| **D1** | Discovery v2 (appendix A): inclusive definition plus new examples. **Same output schema, same Step D** | 8B | 2 |
| **D1-14B** | Same D1 prompt on the 14B. This is the parked "14B told to over-extract" test; it costs one more run and answers whether the 14B's literalness was the prompt | 14B | 2 |
| **R0 / R1 / R2** | Resolver (appendix B) on **oracle candidates** (the labeled obligations and the audit records, so resolver quality is not confounded with discovery). Bundle tiers: R0 quote only (today's D.5 information); R1 adds own chunk, the leaf heading and the code-found stem candidates labeled "unverified"; R2 adds the bounded tail of the previous chunk and head of the next | 8B and 14B | 1 (temperature 0.1; any disagreement between a rerun and the first run on 20 sampled items is reported) |
| **E2E** | D1 output through the resolver at the best tier, compared with D0 and D1 alone on the same chunks | 8B discovery; resolver model chosen from the R results | 2 for discovery |

Discovery runs only on the chunks that overlap the sampled pages (their ids are in the frozen manifests), not on whole
documents; the metric only looks at those chunks. A 10-call pilot measures latency before any full run.

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

### 4.4 Rules fixed before any run

- Tune on the dev set only, at most two revisions per prompt; then freeze (hash recorded) and run the held-out set once.
- Two repeats for every discovery arm. Backlog item 23 showed a single A/B can flip on rerun, so a result counts only if both
  repeats agree in direction.
- Report counts next to percentages. With 74 dev obligations an interval is wide (the 45.1(e) interval is plus or minus
  about 17 points); a gain is called real only if it clears the repeat noise and the pooled dev plus held-out bootstrap interval
  excludes zero.
- No arm is chosen for having more records.

### 4.5 Gates (set now, applied after)

| Gate | Pass | If it fails |
|---|---|---|
| **G1 discovery** | D1 recall on held-out at least 10 points above D0 in both repeats, no fall on dev, regurgitation count 0 after Step D, Step D rejection codes not up | Stop the prompt direction; record why; C4 and pass two remain the options |
| **G2 resolver** | Attachment "right" above today's 40% and "misleading" at or below today's 39%; **zero** strengthened modality (code check, and no case in the hand audit); invented party or number rate at or below 2% | Fix the prompt or tier once on dev; if still failing, stop and report |
| **G3 separation** | E2E recall keeps at least 80% of D1's recall gain, and precision (kept set, `unresolved` shown separately) is within 5 points of D0 | Report that broad discovery alone or the resolver alone is the better half, whichever the numbers show |
| **Evidence limit** | Passing means "improves on these documents and this labeling," not that production quality is proven | State it in the report |

## 5. Build list (scratch only, each testable)

1. `bundle.py`: deterministic evidence-bundle builder (own chunk, leaf heading, existing stem finders' candidates marked
   unverified, bounded neighbors, cross-reference detector for patterns like "paragraph 2.3", "Section 4", "AC-2"); token
   cap so the prompt fits the pinned 8192 window; unit tests including a bundle that would overflow.
2. `run_discovery.py` and `run_resolver.py`: call Ollama with pinned `num_ctx`, write the raw answer before parsing (as Step C
   does), record model digest and prompt hash.
3. `check_resolution.py`: the code validations in section 4.3 (ids exist, value found in span, modal word equal, no new numbers
   or names, example-regurgitation scan).
4. Reuse of `loss_trace.py` and `score.py` for recall, plus a small precision tally.
5. A labeling pack for the resolver outputs and the held-out pieces, built like the 45.1(e) pack.

## 6. What this plan does not decide

- Whether a resolver stage ships, whether discovery's schema gains `kind` or a verbatim `lead_in` span, whether "should"
  recommendations and permissions become first-class records, or whether `modality` becomes a stored field. Each is a
  production change and a separate approval, informed by the numbers above.
- The model-requested retrieval loop. The unresolved-case labels size it; it is built only if those cases justify it.
- Any fix to the checklist, which still ignores stems and descriptions (audit F06).
- Whether the resolver should run on the 14B for precision and the 8B for discovery. The R runs report both; the choice
  follows the data.

## Appendix A: discovery prompt v2 (draft, for review before any run)

Replaces the opening definition and the example block of `PASS1_PROMPT_TEMPLATE`. The output schema, the verbatim-quote rule,
the "do not extract" bullets and the `{source_ref_hints}` and `{chunk_text}` slots stay as they are. Examples are invented.

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

One candidate per call. Code builds the bundle; the model never sees the whole document.

```
You are resolving ONE candidate requirement using only the evidence below. Do not use outside knowledge.
Every populated field must cite evidence ids. If the evidence does not support a field, use null.

Evidence (each span has an id; "unverified" spans were found by a rule and may be wrong):
[E1] candidate quote: "..."
[E2] same chunk: "..."
[E3] heading (leaf): "..."
[E4] possible governing clause (unverified): "..."
[E5] previous chunk, last lines: "..."

Return JSON:
{
 "status": "obligation" | "recommendation" | "permission" | "prohibition" | "scope_or_context" | "not_a_requirement" | "unresolved",
 "actor":      {"value": ..., "evidence": ["E#"]},   // the party that must act. An approver or authorizer is NOT the actor.
 "action":     {"value": ..., "evidence": [...]},
 "target":     {"value": ..., "evidence": [...]},
 "modality":   {"value": "shall|must|should|may|will|must not|shall not|imperative|none", "evidence": [...]},  // copy the word; never change it
 "applicability": {"value": ..., "evidence": [...]}, // who or what it applies to
 "conditions": [{"value": ..., "evidence": [...]}],
 "exceptions": [{"value": ..., "evidence": [...]}],
 "timing":     {"value": ..., "evidence": [...]},
 "parent":     {"evidence": ["E#"]},                  // the governing clause span, if any
 "logic":      "AND" | "OR" | "NONE",                 // how this item relates to sibling items, only if the text says so
 "standalone_statement": ...,   // one sentence built only from cited spans; keep modality, conditions and exceptions
 "plain_language": ...,         // one sentence, no new facts
 "unresolved_reason": ...       // what is missing, and where it might be (previous page, section X)
}

Rules: never turn "may" or "should" into "shall". Never name a party that no span names. A list item inherits its subject from
the lead-in span you cite. If the standalone statement cannot be built from the spans without adding a fact, return null for it.
```

Worked examples to include (fictional), each as bundle plus expected JSON:

1. Inherited subject: candidate "Reviews disposal schedules each year." with E4 "The Records Officer will:" gives actor
   "The Records Officer" from E4, modality `none` (third-person duty, from E1 and E4), timing "each year" from E1.
2. Prohibition with exception: "Contractors shall not transmit logs offshore unless the Program Manager approves in writing."
   gives status `prohibition`, actor "Contractors" (not the Program Manager, who is the approver), exception cited.
3. Permission not strengthened: "The Authorizing Official may grant a waiver" gives `permission`, modality `may`, never `shall`.
4. Recommendation: "Administrators should rotate shared secrets every 90 days." gives `recommendation`, modality `should`.
5. Nested requirement: sub-item "(2) Key custodians shall be named in writing." under "(a) Backups shall be encrypted"
   gives `parent` = the span for (a), `logic` NONE.
6. Cross-reference needing context: "Comply with the requirements of paragraph 4.2." where no span contains 4.2 gives
   `unresolved`, with `unresolved_reason` "paragraph 4.2 is not in the evidence".
7. Scope text: "This manual applies to all Air Force network operators." gives `scope_or_context`, kept and not a requirement.
