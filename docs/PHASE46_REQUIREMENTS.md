# Phase 46 — an audit-ready checklist

*Owner goal (2026-10-08): use the checklist at work to audit units against an AFI within a week. One sheet per document, in document order (scenario checklists are a later goal). Plain statement of need: the whole requirement, not a fragment; where it came from; a blank place to record compliant or not and to take notes; a suggested audit question is worth trying.*

## Status

| WP | What | State |
|---|---|---|
| 46.1 | Audit layout: paragraph citation, role, complete passage, specific flags, compliance and notes columns | planned |
| 46.2 | "Possible missed requirements" section (rule-based scan), same sheet | planned |
| 46.3 | Context attachment from the document's own structure, measured against the model's picks | planned |
| 46.4 | Draft audit questions, marked as drafts | planned |
| 46.5 | Review on AFI 17-203 and one more AFI, with the owner | planned |

## 1. What the checklist is today (read from `services/checklist_service.py`, `pipeline/checklist_export.py`, and the AFI 17-203 output)

One row per extracted requirement: source quote, paragraph reference (`source_ref`), section path, pages, tags, confidence, a status dropdown (not-started, in-progress, compliant, non-compliant, not-applicable) and a notes column already exist. `audit_question` and `evidence_to_request` are empty on every row. For AFI 17-203 (107 rows): 97 have a paragraph reference; **all 107 are flagged "requires review"** because every confidence is below the 0.8 threshold, so the flag carries no information; many rows are fragments with no subject ("Research actions that can be taken to respond to and eradicate the risk and/or threat.") or table scraps ("and the Primary Recipient will be"), or descriptive sentences. A rough scan found 25 of 45 sentences with shall, will, must or should in that document not covered by any row. Recall measurements elsewhere (WP-45.11) say about 6 in 10 known obligations reach the index.

## 2. Work packages

**46.1 Audit layout (deterministic, no model).** Per row, add: `applies_to` (the leaf heading, only where the frozen WP-45.1(d) rule H3 says it names the responsible party), `passage` (the document's own text around the quote: the quote's chunk, preceded by the tail of the previous chunk when the quote starts mid-list or mid-sentence; verbatim, quote located), and `item_flags` (specific, rule-based: `starts_mid_sentence`, `no_subject`, `descriptive_only`, `table_fragment`). `requires_human_review` becomes true only when a specific flag or a missing citation applies; low confidence alone no longer flags every row (the numeric confidence stays in the row). Export: one sheet, document order; columns Ref, Applies to, Requirement, Passage, Status, Notes, Flags, then the trace columns. The checklist envelope goes to `format_version` 1.1; fields are only added. The requirement JSONL, Qdrant payloads and embeddings are not touched. Acceptance: deterministic tests; on AFI 17-203 every row has a passage that contains the quote; the owner reads 30 rows.

**46.2 Possible missed requirements.** A rule-based scan of each document's chunk text for sentences with a modal or obligation phrase, and for imperative list items under a heading that assigns a duty, not covered by any extracted quote (containment either way, 40 characters minimum, as in WP-45.11). They appear at the end of the same sheet under a clear label, flagged `possible_missed`, are not counted as items, and are never auto-promoted. Acceptance: the scan's list on AFI 17-203 is read by the owner; the share that are real obligations is reported, not claimed in advance.

**46.3 Context attachment from structure.** AFIs number paragraphs as a hierarchy (3.6.2.4 sits under 3.6.2, under a role heading). Registered separately before any run: a rule-based parent from the paragraph-number hierarchy and the H3 heading, scored on the WP-45.7 labeled sets (dev: `resolver_gold` selection half; test: `fresh_gold`, once) with the WP-45.7 attachment scorer, against production's stem and the resolver's. It is shown on the sheet only as "Context (auto-detected)" and only where its measured precision is high; the passage is always shown. The model resolver (WP-45.8) is the fallback and needs the owner's answers to the plan's stop-and-ask items before it enters the pipeline.

**46.4 Draft audit questions.** One short question per row drafted from the quote and its context, labeled a draft, never replacing the requirement text. A generation call (not a selection), so it is a new model call at checklist time; first as an experiment (a few documents, scratch, the owner reads 30 and rates each usable / needs edit / wrong), adopted only if most are usable. `evidence_to_request` stays empty until a separate decision.

**46.5 Review.** Generate AFI 17-203 and a second AFI the owner names; he reads a sample; fixes follow.

## 3. Rules for this phase

- Every change is a branch and a pull request reviewed by the bots; merge on green CI.
- Deterministic first. Anything a model produces is labeled as such and never replaces verbatim text.
- Nothing is dropped: rows that look weak are flagged, not removed.
- Measure before claiming: what is read by the owner is reported as a count of what he rated.

## 4. Not in this phase

Scenario checklists, several sheets per document, evidence mapping changes, any change to extraction, chunking or the saved requirement records.
