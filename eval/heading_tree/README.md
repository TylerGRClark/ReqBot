# Heading-tree experiment preparation

Status: **corpus measurement awaiting original inputs**. No model calls, tree
alternative, production changes, library writes, or Qdrant writes have occurred.
This is a preparation draft, not a completed experiment or merge recommendation.

The preregistration was committed locally as `c28f0a9` before creating the audit
tool or running its synthetic tests. `PREREG.md` defines conditional stages:
measure current failures, implement an alternative only if a real gap warrants
it, then request Tyler's permission for the frozen-model experiment. Do not
renumber this as PREREG13 without coordinating with Claude's parallel work.

## What code inspection establishes

- `pipeline/chunk_text.py::_chunk_raw_text` often joins whole Docling item text
  rather than slicing that text to the HybridChunker token budget. Generic-item
  and fallback paths also exist. “256 tokens severs the list” is therefore a
  hypothesis to test on actual saved artifacts, not a measured fact.
- `pipeline/clause_labeling.py::document_clauses` already calls `find_lead_in`
  with the previous chunk when both reference and title paths agree. A parent
  more than one chunk back, a changed section key, or imperfect list detection
  can prevent this lookup. These are possible failure modes, not corpus counts.
- `services/checklist_service.py::_prompt_windows` and
  `services/checklist_audit.py::prompt_window` recover context for downstream
  question/score prompts. They are not supplied to the frozen clause labeler.
  They cannot restore a clause that the labeler marked NOT_REQUIREMENT.
- PREREG8's historical lead-in treatment improved recall 95.03 → 95.67 and
  precision 87.31 → 88.51 on 624 gold requirements. This is a published prior
  result (`eval/clause_labeling/PREREG8_REPORT.md`), **not a rerun**, and that
  treatment has since been adopted. A tree comparison must use today's baseline.

## Inputs needed from Claude

The shared inbox supplies scope, but not the experiment data. The accessible
GitHub checkout contains the preregistrations, reports and scorer; its drivers
point to private local scratch inputs. `STATE.md` and `tools/rerun_c.py` mentioned
in the note are also absent from this checkout. Binary Hunter's supplied
`labworker` account has the reverse-engineering lab, not these snapshots.

Please place a read-only copy under a new shared project folder, preserving
original hashes/provenance:

1. `~/reqbot-work/scratch/label_ctx/chunks/*_chunks.jsonl` for the seven PREREG8
   documents, not a fresh production re-extraction.
2. The corresponding saved DoclingDocument exports and ancestry. If documents
   were only held in memory, say so and supply the exact PDF inputs plus the
   pinned conversion environment/version record. This needs a design amendment
   before treating a reparse as equivalent to the historical control.
3. `scratch/gold2/gold_both.json`, `scratch/gold2/units_gold2.jsonl`, and
   `scratch/silver/units{,2,3}.jsonl` plus `scratch/silver/labels*/A_{X,Y}_*.jsonl`
   used by `label_ctx_metrics.py`. The reconstructed set must contain exactly
   624 requirements for these documents.
4. `STATE.md`, the `tools/rerun_c.py` safety pattern, and the two review uploads
   referenced in the inbox (ChatGPT a04db544… / Gemini 8052c0ef…).
5. If available, matching normalized/explained requirement records for measuring
   actual downstream passage-window behavior, plus the old PREREG8 result JSONs
   for baseline reproduction checks. Do not share credentials or Ollama config.

## Running the no-model candidate audit

Make a scratch manifest with a `documents` object containing exactly the seven
document names listed in `PREREG.md`. Each entry has:

```json
{
  "chunks": "relative/path/to/afi17-203_chunks.jsonl",
  "chunks_sha256": "sha256 of those original file bytes",
  "docling_export": "optional path for intake inventory only"
}
```

The optional export path is inventory metadata only; it is not opened or used as
truth by this tool. Confirm snapshot hashes against Claude's original run record,
not just a checksum generated from whatever happens to be newest. Then:

```bash
python3 eval/heading_tree/audit.py \
  --manifest /path/to/scratch/input-manifest.json \
  --output /path/to/scratch/new-heading-tree-audit
```

The output path must not already exist. The tool validates all seven chunk
inputs and hashes before writing. It imports the production pure clause/context
functions and checks the frozen prompt; it does not import Docling, parse PDFs,
make HTTP calls, label requirements, or connect to the index.

- `summary.json`: candidate counts, source/code hashes, and explicitly null
  truth/accuracy/passages metrics pending source review.
- `automatic-contexts.json`: exact clause offsets, quotes, recovery routes and
  actual cut labeler blocks, for later comparison.
- `review-sample.json`: deterministic balanced sample, nearby source chunks,
  blank review fields, and **no automatic recovery outputs**. Provide full source
  documents/tree as well; the true parent can lie beyond the included snippets.

“Previous-chunk recovery” means the production lookup returns a lead-in only
when it gets previous-chunk text. It does not establish that this is the correct
parent, nor that the actor is correctly attached. Review-sample fields are
scratch annotations, not changes to ReqBot's JSONL schema. No attachment scorer
or model runner is included yet; both depend on verified source inputs and the
conditional next stage in the preregistration.

## Validation performed locally

Python 3.12, pinned pytest 9.1.1 and Ruff 0.15.22 in temporary tool directories:

```text
pytest tests/unit/test_heading_tree_audit.py -q
13 passed

pytest tests/unit/test_heading_tree_audit.py tests/unit/test_clauses.py \
  tests/unit/test_lead_in.py tests/unit/test_table_header.py \
  tests/unit/test_sentence_expand.py -q
63 passed

ruff check eval/heading_tree tests/unit/test_heading_tree_audit.py
All checks passed!
```

An additional run including `test_clause_labeling.py` had 99 passes and 2 failures
from missing local dependencies (`rapidfuzz`, `qdrant_client`). Those failures
are not reported as passes; no production modules were altered to bypass them.
The full application/Docling environment was not installed locally. Existing
CI and independent review remain pending; Gemini review is required before
owner acceptance under `docs/ENGINEERING_WORKFLOW.md`, and has not been invoked.
No actual-corpus percentages, model quality improvements, or Excel/chapter-view
results are established by these synthetic tests.
