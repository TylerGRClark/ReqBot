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
| A — parse | Docling reads layout, headings, tables, and page provenance. | `*_ancestry.json` and an in-memory parsed document. |
| B — chunk | Structure-aware chunking adds section paths and parent context; the profile can exclude sections. | `*_chunks.jsonl` |
| C — extract | Ollama extracts quoted requirements and references from each chunk. Raw responses and parse failures are retained. | `*_extracted_requirements.jsonl` |
| D — normalize | Validate fields and quote grounding, assign IDs, deduplicate, and reject invalid records. Deterministic parent-stem reconstruction follows normalization. | `*_requirements_normalized.jsonl` |
| D.5 — enrich | Ollama adds descriptions, domain tags, and requirement types. | `*_requirements_enriched.jsonl` |
| D.6 — description gate | Check descriptions against source quotes; clear rejected descriptions while keeping the requirements. | `*_requirements_gated.jsonl` |
| E — export | Aggregate the selected output and record statistics. | `*_final_output.json`, `*_stats.json` |
| Index requirements | Embed selected requirement artifacts with dense Ollama embeddings and sparse BM25 features. | Qdrant `grc_requirements` |
| Index context | Embed source chunks with the same dense/sparse strategy. | Qdrant `grc_context` |

The CLI `ingest` command runs indexing by default. The direct pipeline script
writes artifacts by default and requires `--index` to index. See [CLI](CLI.md)
and [Operations](OPERATIONS.md#resume-an-interrupted-run).

### What validation establishes

Step D's known-chunk grounding checks combine fuzzy character matching and a
word-coverage threshold. They reject some invented quotes while preserving
formatting variants and reconstructed list obligations. These are heuristic
checks, not proof that every quote is verbatim or semantically faithful.

Parent-stem reconstruction attaches `parent_stem` and combined `embedding_text`
to fragment records while preserving their `source_quote`.
Generated descriptions are distinct from source quotes. Step D.6 has
deterministic checks and, when the optional MiniCheck dependency is available,
an entailment check. A rejected description is cleared; its requirement remains.

Enrichment failures can fall back to normalized artifacts. A description-gate
failure can fall back to the pre-gate artifact, with a log warning. Inspect logs
and failure artifacts when assessing a run; completion alone does not mean every
optional check executed. Human review of source quotes remains necessary.

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
