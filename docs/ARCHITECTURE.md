# Architecture overview

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Operations](OPERATIONS.md)

ReqBot has two main workflows: turn PDFs into validated requirement artifacts,
then query an index built from those artifacts. The CLI, web application, HTTP
API, and MCP server expose those workflows.

## Components and ownership

| Component | Responsibility |
|---|---|
| `pipeline/` | Parse PDFs, chunk source text, extract/validate/enrich requirements, export artifacts, and build indexes. |
| `core/` | Configuration, profiles, artifact selection, retrieval, synthesis, and shared utilities. |
| `services/` | Return structured search, trace, comparison, evidence, checklist, status, and configuration results. |
| `cli/` | CLI and interactive-shell command parsing and presentation. |
| `api/` | HTTP request validation, error mapping, and frontend serving. |
| `mcp_server/` | Local stdio tools over shared services. |
| `frontend/` | Browser screens and presentation; calls the HTTP API. |
| Ollama | Dense embeddings and local extraction, enrichment, query, and synthesis model calls. |
| Qdrant | Rebuildable dense/sparse requirements and source-context indexes. |

Interfaces own presentation and request validation. Retrieval belongs in
`core/ask.py`; pipeline sequencing belongs in `pipeline/run_pipeline.py`.
The [developer reference](../ARCHITECTURE.md) contains the module/import map.

## From document to requirements

| Stage | Work | Main output |
|---|---|---|
| PDF reading (Step A) | Docling reads layout, headings, tables, and page provenance. | `*_ancestry.json` and an in-memory parsed document. |
| Chunking (Step B) | Structure-aware chunking adds section paths and parent context; the profile can exclude sections. | `*_chunks.jsonl` |
| Requirement finding (Step C) | Ollama returns, for each chunk, the quotes that look like duties, with references. The prompt is inclusive: it asks for anything that tells a party what it must, should, may or must not do. Raw responses and parse failures are retained. This output is the **root** of each requirement and is never edited. | `*_extracted_requirements.jsonl` |
| Normalizing and checking (Step D) | One step today, doing several jobs: validate fields and quote grounding, drop junk (headings, change-log lines, fragments), attach page and section metadata, deduplicate, expand each quote to the whole sentence it sits in, and assign IDs. Deterministic parent-stem reconstruction follows. | `*_requirements_normalized.jsonl` |
| Enrichment (Step D.5) | Ollama adds descriptions, domain tags, and requirement types. Scheduled to be switched off (see below). | `*_requirements_enriched.jsonl` |
| Description check (Step D.6) | Check descriptions against source quotes; clear rejected descriptions while keeping the requirements. Scheduled to be switched off with enrichment. | `*_requirements_gated.jsonl` |
| Totals and final file (Step E) | Aggregate the selected output and record statistics. | `*_final_output.json`, `*_stats.json` |
| Index requirements (Step F) | Embed selected requirement artifacts with dense Ollama embeddings and sparse BM25 features. | Qdrant `grc_requirements` |
| Index context (Step F) | Embed source chunks with the same dense/sparse strategy. | Qdrant `grc_context` |

Older documents, log lines and command options name the stages by letter (Step A to
Step F); this page gives both. New work uses the names by job.

### Planned changes

The [pipeline redesign plan](PIPELINE_REDESIGN_PLAN.md) describes where the pipeline is
going; none of it is built yet, so everything above describes the pipeline as it runs
today. In short: the root stays exactly as the model returned it and is never edited;
checking that the root is word for word in the source becomes its own early step
(anchoring); the whole-sentence expansion and lead-in attachment move into a separate
"explained" layer beside the root; screening judges that explained text; Step D is split
so each step does one job; and tagging, typing, descriptions and the description check
are switched off, with the explained text used in their place.

The CLI `ingest` command runs indexing by default. The direct pipeline script
writes artifacts by default and requires `--index` to index. See [CLI](CLI.md)
and [Operations](OPERATIONS.md#resume-an-interrupted-run).

### What validation establishes

Normalizing and checking (Step D) applies known-chunk grounding checks that combine
fuzzy character matching and a word-coverage threshold. They reject some invented quotes
while preserving formatting variants and list obligations the model joined to their
lead-in. These are heuristic checks, not proof that every quote is verbatim or
semantically faithful: in the October 2026 run of the 13 reference documents, 7% of
accepted quotes (172 of 2,419) are not word for word in their chunk (most often a lead-in glued onto a list item, or a dropped
list number), and the checklist marks them `quote_not_located_in_passage`.

Each accepted quote is then expanded to the whole sentence it sits in (verbatim, with
spacing tidied; `pipeline/sentence_expand.py`). Today this replaces `source_quote`; the
redesign plan keeps the original and puts the expanded text in its own field.

Parent-stem reconstruction attaches `parent_stem` and combined `embedding_text`
to fragment records while preserving their `source_quote`.
Generated descriptions are distinct from source quotes. The description check (Step D.6) has
deterministic checks and, when the optional MiniCheck dependency is available,
an entailment check. A rejected description is cleared; its requirement remains.

Enrichment failures can fall back to normalized artifacts. A description-gate
failure can fall back to the pre-gate artifact, with a log warning. Inspect logs
and failure artifacts when assessing a run; completion alone does not mean every
optional check executed. Human review of source quotes remains necessary.

## Checklists

A checklist is built on demand from the newest processed run of a document; building it
never calls a model. Each row is one requirement with its citation, section heading,
the paragraph it sits under (read from the document's own numbering), who it applies to,
the surrounding passage with the quote marked, and hint flags (for example "starts
mid-sentence" or "table fragment"). Passages that look like duties but were not
extracted are listed separately as possible missed requirements. Draft audit questions
come from `reqbot questions`, which writes a sidecar file (`*_audit_questions.jsonl`) that
the checklist reads; they are drafts for the auditor to check.

## Artifacts and the source of record

Keep original PDFs and complete processed run directories. They allow inspection,
resume, later validation, and rebuilding without asking the extraction model
to regenerate the corpus.

| Artifact | Purpose |
|---|---|
| `*_ancestry.json`, `*_chunks.jsonl` | Source structure and the text shown to extraction. |
| `*_raw_responses.jsonl` | Extraction model responses and resume/cache evidence. |
| `*_extracted_requirements.jsonl`, `*_parse_failures.jsonl` | Parsed extraction output and parsing errors. |
| `*_requirements_normalized.jsonl`, `*_normalization_failures.jsonl` | Accepted normalized records and rejection reasons. |
| `*_requirements_enriched.jsonl` | Added descriptions/classifications before description checking. |
| `*_requirements_gated.jsonl`, `*_description_gate_failures.jsonl` | Post-check records and rejected-description evidence. |
| `*_final_output.json`, `*_stats.json` | Aggregated export and run metrics. |
| `*_audit_questions.jsonl` | Draft audit questions written by `reqbot questions`; read by the checklist. |

Some artifacts are absent when their stage is skipped or fails. Reindex and
checklist generation share an artifact resolver: pick the run with the most
recently modified requirement artifact, then prefer gated over enriched over
normalized, provided the higher tier is not older than a lower tier. A stale
gated file must not override a later normalization rerun.

The document-listing service instead counts the latest normalized files. Its
counts describe processed artifacts, not a live Qdrant inventory.

## Search and trace

Search can rewrite the question into retrieval keywords and generate a HyDE
hypothesis. Dense question/hypothesis embeddings and sparse keyword features
retrieve candidates; reciprocal rank fusion combines the ranked lists.
Document, tag, and requirement-type filters constrain results.

An RRF score is a ranking score, not a probability of correctness. Optional
context fetches the source chunks linked to returned requirements from
`grc_context`. It does not alter stored requirements.

Trace looks up a known requirement ID and returns its payload, other records
sharing its citation, and optional surrounding chunk text. Shared references
help comparison; matching `source_ref` values are not proof of equivalent scope.

Answer synthesis is a separate, optional step over retrieved records. It can
use local Ollama, an explicitly configured remote provider, or be disabled.
Local retrieval still requires Ollama when remote synthesis is selected.
The experimental cross-encoder reranker is opt-in programmatically and has not
become a default retrieval step.

## Indexes and identity

`grc_requirements` stores requirement payloads and vectors. `grc_context` stores
source chunks and vectors. Indexed payloads retain embedding model/dimension
provenance; result warnings help identify a corpus built with another model.

- `doc_key`: PDF filename stem used for artifact lookup and checklists.
- `source_pdf`: PDF filename used in source filters and presentation.
- `document_id`: PDF-content-derived identifier in normalized/indexed records.
- `requirement_id`: record identifier returned by search and accepted by trace.
- `chunk_id`: link to the source chunk within that document.

Use returned identifiers instead of fabricating IDs. A filename stem is not
interchangeable with the content hash in every interface.

Reindex builds replacement collections and swaps aliases after each successful
build. Requirements and context have separate swaps; the pair is not one
transaction. Migrating a plain collection to an alias can require a brief
availability gap. See [Operations](OPERATIONS.md#rebuild-the-search-indexes).

## Deployment boundaries

The default API listener is loopback, with no application authentication.
The MCP server is a subprocess using stdio; it is not an HTTP endpoint.
The web GUI requires a frontend build. See [Deployment](DEPLOYMENT.md),
[Connecting AI tools](AI_TOOLS.md), and [API](API.md) for those interfaces.
