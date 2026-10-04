# Developer architecture reference

For a component and pipeline overview, read [Architecture](docs/ARCHITECTURE.md).
For setup, commands, and defaults, use the [documentation index](docs/README.md).
This page maps implementation ownership and change dependencies for contributors.

## Package and module map

| Package/module | Responsibility |
|---|---|
| `cli/reqbot.py` | argparse entry point; command handlers, CLI formatting, ingest/index/reindex orchestration. |
| `cli/console.py` | Interactive shell and session settings over command handlers. |
| `core/config.py` | stdlib configuration loader and authority registry. |
| `core/profiles.py` | Profile discovery and schema validation. |
| `core/artifact_resolver.py` | Anchored artifact suffix parsing and latest-run/fresh-tier selection. |
| `core/constants.py` | Shared context UUID namespace. |
| `core/ask.py` | Query rewriting, dense/sparse/HyDE retrieval, filtering, RRF, context lookup, and optional synthesis. |
| `core/synthesis.py` | Local/remote/disabled synthesis abstraction and prompts. |
| `core/reranker.py` | Optional FlashRank cross-encoder wrapper for the reranker experiment. |
| `services/ask_service.py` | Canonical structured search envelope over core retrieval. |
| `services/docs_service.py` | Normalized-artifact inventory and source-PDF resolution. |
| `services/status_service.py` | Service health, model availability, and artifact inventory. |
| `services/trace_service.py` | Requirement lookup, same-reference matches, linked context. |
| `services/compare_service.py` | Exact citation or hybrid topic comparison. |
| `services/evidence_service.py` | Evidence retrieval/grouping, context, and optional synthesis. |
| `services/checklist_service.py` | Artifact-backed checklist envelope, stable item IDs, and review flags. |
| `services/config_service.py` | Shared configuration read/write path for init and settings API. |
| `api/app.py` | FastAPI assembly, CORS, route registration, and SPA static-file serving. |
| `api/routes/` | Request models, interface validation, service calls, HTTP error mapping. |
| `mcp_server/server.py` | FastMCP stdio tools over the services, with interface input validation. |
| `models/` | Reserved package; currently no populated shared schema implementation. |
| `profiles/` | Packaged domain profile JSON files; test fixtures are excluded from package data. |

### Pipeline modules

| Module | Stage / responsibility |
|---|---|
| `pipeline/run_pipeline.py` | In-process stage sequencing, resume boundaries, stage failure/fallback behavior. |
| `pipeline/section_parser.py` | Docling PDF conversion and ancestry/page/parent metadata. |
| `pipeline/chunk_text.py` | HybridChunker, breadcrumbs, section exclusions, and chunk artifacts. |
| `pipeline/llm_extract_requirements.py` | Pass-1 prompts, Ollama extraction, response parsing, prompt-hash cache. |
| `pipeline/parse_and_normalize.py` | Normalization, quote checks, deduplication, document/requirement identity. |
| `pipeline/enrich_requirements.py` | LLM descriptions/classification plus deterministic parent-stem reconstruction. |
| `pipeline/entailment_gate.py` | Description checks, optional MiniCheck scoring, gated artifact/failure output. |
| `pipeline/aggregate_and_export.py` | Aggregated output and statistics. |
| `pipeline/embed_and_index.py` | Dense/sparse requirement vectors, Qdrant schema and payloads. |
| `pipeline/embed_context_index.py` | Dense/sparse context vectors and linked chunk identity. |
| `pipeline/checklist_export.py` | CSV/JSON/Markdown/XLSX serialization and spreadsheet formula handling. |
| `pipeline/repair_ligatures.py` | Text repair helper. |

### Frontend

`frontend/src/App.tsx` owns browser routes. Views cover search, trace, compare,
evidence, corpus/detail, checklist generation/preview, system health, settings,
and not-found handling. `frontend/src/api/client.ts` owns HTTP wrappers;
`types.ts` defines their TypeScript response/request types.

Components own presentation: app shell/navigation, result cards, provenance
display, checklist table/review flags/export controls, status/errors/loading,
and synthesis output. Hooks and utilities contain shared browser behavior.

`frontend/dist/` is generated and gitignored. Build with
`bash build/build-frontend.sh`; do not edit output directly.
The API serves the build when present and otherwise serves API-only.
The SPA fallback handles dotted document keys for corpus/checklist/trace routes
without treating them as missing static files.

## Call paths and boundaries

- Interactive shell → CLI command handlers.
- CLI ingest/batch → pipeline orchestrator → stage modules → indexers.
- CLI ask → core query/render wrapper → shared retrieval.
- Other CLI analysis commands → structured services → CLI formatting.
- HTTP routers → config/shared services → HTTP envelopes.
- MCP tools → config/shared services → protocol tool results.
- Browser → HTTP client wrappers → API.
- Search service → `core.ask.retrieve()`; synthesis consumers → `core.synthesis`.
- Reindex/checklist → shared artifact resolver.
- Init/settings API → shared configuration service.

Keep pipeline sequencing in `run_pipeline.py` rather than adding alternate
stage-order implementations in interfaces. Stage/helper imports already exist
(e.g. normalization helpers used by enrichment/gating); do not assume the stages
form a completely isolated import graph.

Docling's parsed `AncestryResult` is passed in memory from parsing to chunking
to avoid parsing the PDF twice. Durable ancestry/chunk files are still written.
Most later stage boundaries use filesystem artifacts.

Keep retrieval logic in core and presentation in interfaces. CLI JSON rendering
is not uniformly identical to HTTP/MCP response serialization; test the actual
interface contract when changing either.

## Dependencies and configuration

[pyproject.toml](pyproject.toml) declares Python runtime/optional/dev dependencies
and the `reqbot` entry point. [frontend/package.json](frontend/package.json) and
its lockfile define the frontend stack (React, TypeScript, Tailwind, Vite).
The frontend build script enforces the project's supported Node versions.

Base runtime includes Docling, FastEmbed, Qdrant/Ollama clients, FastAPI/uvicorn,
OpenPyXL, requests, aiofiles, and RapidFuzz. Optional integration extras include
remote synthesis SDKs, MCP, MiniCheck, and FlashRank. The
[deployment guide](docs/DEPLOYMENT.md) explains preparation and offline assets.

[Configuration](docs/CONFIGURATION.md) is the canonical defaults/env reference.
URLs and model identifiers should come from configured roles in user entry
points. Direct stage scripts can have their own defaults; document that boundary.
Service URLs describe external processes; ReqBot does not manage their lifecycle.

Processed artifacts and Qdrant backing collections have separate lifecycles.
The Compose example persists Qdrant in a named volume and processed files in a
bind mount. There is no current installer-managed upgrade directory contract.

## Changes that need coordinated review

| Change | Consumers / validation to inspect |
|---|---|
| Config keys/defaults/env map | CLI/init, config service, HTTP settings model, MCP setup, Configuration guide. |
| Normalized payload/schema | Enrichment/gates/indexers, retrieval/trace/compare/evidence, checklist exports, frontend types. |
| Quote validation or parent reconstruction | Accepted record identities, rejection reasons, downstream enrichment, representative corpus replay. |
| Artifact names or freshness | Resolver, reindex, checklist, document listing, resume, Operations guide. |
| Chunk identity/hierarchy | Normalization, context index UUIDs, search/trace/evidence context joins. |
| Embedding/vector schema | Both indexers, query services, dimension/provenance warnings, complete reindex. |
| `retrieve()` envelope | Search service and CLI wrapper; preserve results/total/timing/synthesis/warnings consumers. |
| HTTP request/response | Routes, shared services, browser types/wrappers, API guide and API tests. |
| MCP tools/signatures | Client-discovered schemas, MCP tests, AI tools guide. |
| Checklist envelope/export columns | CLI/API/MCP/GUI and assessor tooling; preserve stable IDs and provenance. |
| Frontend routes/static serving | Browser refresh/direct navigation, dotted document keys, installed package and Docker build. |
| Model-dependent behavior | Fresh independent evaluation, affected corpus slices, failure/fallback paths, offline assets. |

Reindex swaps each collection after that build succeeds; requirements/context
are not a single transaction. Source artifacts remain authoritative.
See [Operations](docs/OPERATIONS.md) for recovery semantics.

## Local verification

After installing an editable development environment:

```bash
python3 -m pytest tests/unit/ -q
python3 -m ruff check .
```

For frontend changes, run `npm ci` and `npm run test` in `frontend/`, and build
the frontend. Real model/pipeline evaluation and disconnected deployment
qualification are separate from mocked unit tests and startup smoke tests.

[Contributing](CONTRIBUTING.md) covers licensing and contribution requirements.
Keep user documentation aligned when a public command, setting, artifact,
endpoint, or tool changes.
