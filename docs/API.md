# HTTP API reference

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Connecting AI tools](AI_TOOLS.md)

Start the server with `reqbot serve`. The default base URL is
`http://127.0.0.1:8000/api`. The API works without a built web frontend.

- Swagger UI: `http://127.0.0.1:8000/api-docs`
- ReDoc: `http://127.0.0.1:8000/api-redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

Use the OpenAPI output of your installed revision for request constraints.
Most responses are returned as dictionaries without detailed response models,
so generated OpenAPI does not fully describe their nested payloads. This page
documents the envelopes returned by the routes and shared services.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | Service health and models. |
| GET | `/api/docs` | Processed-document inventory. |
| POST | `/api/ask` | Requirement retrieval and optional answer synthesis. |
| GET | `/api/trace/{req_id}` | Requirement provenance and citation matches. |
| POST | `/api/compare` | Compare two documents on a topic/control. |
| POST | `/api/evidence` | Group requirements into an evidence pack. |
| GET | `/api/profiles` | Available profile names. |
| POST | `/api/checklist` | Generate a checklist. |
| POST | `/api/checklist/export` | Download a checklist file. |
| GET | `/api/config` | Effective configuration and environment overrides. |
| POST | `/api/config` | Partially update settings; loopback-only. |

Request/response bodies are JSON except file exports. There are no HTTP ingest,
index-rebuild, or assessor-edit endpoints in this implementation.

## Status and document inventory

```bash
curl -sS http://127.0.0.1:8000/api/status
curl -sS http://127.0.0.1:8000/api/docs
```

`status` returns:

| Field | Shape |
|---|---|
| `ollama_url`, `qdrant_url` | Configured URL strings. |
| `ollama` | `{reachable: bool, models: [{name, size_gb}]}` |
| `qdrant` | `{reachable: bool, collections: [{name, points}]}`; points may be `"?"` if unavailable. |
| `configured_models` | Role-to-model mapping for embedding, extraction, enrichment, rewrite, synthesis. |
| `processed_documents` | List of normalized artifact `{path, count}` entries, potentially including older runs. |

Unreachable services are reported with `reachable=false` in a successful HTTP
response; check those fields, not just HTTP 200.

`docs` returns `{docs: [...], total_reqs: int, total_docs: int}`. Each entry has
`doc_key`, `source_pdf`, `path`, `count`, `mode`, `run_date`, `profile`,
and `skip_sections_applied` (boolean or null). It deduplicates normalized files
by PDF stem and modification time under `processed_dir`.

These listings read filesystem artifacts. They are not live Qdrant inventories
and do not prove the corresponding documents were indexed.

## Search requirements

```bash
curl -sS http://127.0.0.1:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the access control requirements?","context":true}'
```

| Request field | Default / constraint |
|---|---|
| `question` | Required string. |
| `top_k` | 20; integer 1–100. |
| `min_score` | 0.02; number 0–1, with 0 disabling the RRF cutoff. |
| `synthesize` | false. |
| `model` | Empty string; otherwise override the synthesis model for the configured backend. |
| `rewrite_model` | Empty string; otherwise override the configured rewrite model. |
| `document_ids` | Empty string list; accepts doc_key/source_pdf values resolved against Qdrant. |
| `domain_tags`, `requirement_types` | Empty string lists. |
| `no_rewrite` | false. |
| `context` | false; include linked source text. |
| `hyde` | true; enable hypothetical-requirement retrieval augmentation. |

The numeric defaults are API defaults, not dynamically loaded `top_k` or
`min_score` file values. Despite its name, `document_ids` here expects PDF
stems or filenames, not content-hash IDs. An unknown document filter is an error.

Response envelope:

```json
{
  "query": "What are the access control requirements?",
  "filters": {
    "document_id": null,
    "domain_tag": null,
    "requirement_type": null
  },
  "results": [],
  "metadata": {
    "top_k": 20,
    "result_count": 0,
    "retrieval_ms": 12.5,
    "synthesis": null
  },
  "warnings": []
}
```

The example illustrates an empty result, not a measured response. Every nonempty
result is a flattened requirement payload with `score`, normally including
`requirement_id`, `document_id`, `source_pdf`, `source_quote`, `source_ref`,
`description`, page/chunk provenance, section paths, tags, type, and confidence.
`context_text` is added when requested and available; do not require it on
every hit. Fields can be absent in older indexed artifacts.

RRF scores are ranking scores, not calibrated relevance probabilities.
`metadata.retrieval_ms` excludes synthesis latency. `warnings` can report
embedding-model mismatches. Empty retrieval returns HTTP 200 with no results.

## Trace a requirement

```bash
# Substitute an actual requirement_id from a search result.
curl -sS 'http://127.0.0.1:8000/api/trace/REQ-returned-id?context=true'
```

The `context` query parameter defaults to false. The response is:

```json
{
  "requirement": {"requirement_id": "REQ-example", "source_quote": "Example source text"},
  "cross_matches": [],
  "context_text": null
}
```

This abbreviated example shows the envelope. `requirement` is the full stored
payload; `cross_matches` contains payloads from other documents sharing the
reference. `context_text` is null when not requested or unavailable. Matching
references do not prove equivalent obligations.

## Compare documents

```bash
curl -sS http://127.0.0.1:8000/api/compare \
  -H 'Content-Type: application/json' \
  -d '{"doc_id_1":"policy-a","doc_id_2":"policy-b","topic":"AC-2","top_k":10}'
```

Requires `doc_id_1`, `doc_id_2`, and `topic` strings. `top_k` defaults to 10
and must be 1–100. Use document keys/source filenames, not requirement IDs.

Both result modes return `query`, `mode`, `warnings`, the requested
`doc_id_1`/`doc_id_2`, and canonical `doc_pdf_1`/`doc_pdf_2`.

| Mode | Additional response fields |
|---|---|
| `exact` | `source_ref` and `groups`: a source-PDF-to-requirement-payload mapping. |
| `semantic` | `ref_order`: ordered references; `ref_groups`: reference → source PDF → requirement payload. |

Recognized control IDs take the exact-reference path; free text takes hybrid
retrieval. Resolve document columns using `doc_pdf_1`/`doc_pdf_2`, since those
are the mapping keys. A group may appear in one document or both. The service
selects representative requirements; it is not an exhaustive diff.

## Evidence mapping

```bash
curl -sS http://127.0.0.1:8000/api/evidence \
  -H 'Content-Type: application/json' \
  -d '{"topic":"incident response","synthesize":false,"show_context":true}'
```

| Request field | Default / constraint |
|---|---|
| `topic` | Required string. |
| `document_ids` | Empty list; doc_key/source_pdf filters. |
| `domain_tags`, `requirement_types` | Empty lists. |
| `synthesize` | false. |
| `top_k` | 10; integer 1–100. |
| `show_context` | false. |

Response fields are `query`, `timestamp` (UTC ISO 8601), `group_order`,
`groups`, `total_sources`, `synthesis_text`, and `warnings`.

`group_order` lists keys in rank order. Each `groups[key]` has:

- `source_ref`: display reference.
- `representative`: selected full requirement payload.
- `sources`: all matched payloads in that group.
- `context_text`: optional surrounding source text, or null.

Use `groups[key].source_ref` for display, not the raw key: records without usable
references can have synthetic per-requirement keys. `synthesis_text` is an empty
string when skipped or unavailable. No matching evidence is reported as a
not-found error rather than the search endpoint's empty-result envelope.

## Profiles and checklists

```bash
curl -sS http://127.0.0.1:8000/api/profiles
curl -sS http://127.0.0.1:8000/api/checklist \
  -H 'Content-Type: application/json' \
  -d '{"doc_key":"policy","profile":"cybersecurity"}'
```

`profiles` returns an object such as `{"profiles":["cybersecurity"]}`.
It lists JSON files available in the running installation; source checkouts can
also expose test fixture profiles, which are not supported production domains.
Checklist requests require `doc_key`; `profile` defaults to
`cybersecurity`. Checklists read selected processed artifacts, not Qdrant.

The checklist envelope contains:

| Field | Shape / meaning |
|---|---|
| `format`, `format_version` | `"reqbot-checklist"`, `"1.1"` (1.1 added `applies_to`, `passage`, `item_flags` and `summary.items_with_flags`; nothing was removed). |
| `generated_at` | UTC ISO 8601 timestamp. |
| `generator` | `{tool, command}`. |
| `document` | `{document_id, source_pdf}`. |
| `profile` | Selected profile name. |
| `summary` | `{total_items, items_requiring_review, items_with_flags, possible_missed}`. |
| `items` | Checklist item objects. |
| `possible_missed` | Item-shaped objects for passages of the document that look like obligations but were not extracted, found by a rule-based text scan (modal word or imperative opener, not a lead-in ending in a colon, not covered by any extracted quote). Their `checklist_item_id` starts with `MISS-`, `item_flags` contains `possible_missed`, and they are not counted in `total_items`. A prompt to check, not requirements: some are descriptions or examples. Empty when the chunk file is not beside the requirements. |

Each item includes `checklist_item_id`, `requirement_ids`, `domain_tags`,
`source_ref`, `page_refs`, `section_title_path`, `source_quote`, `confidence`,
`requires_human_review`, and `review_reasons`. For audit use it also carries
`section_heading` (the section the paragraph sits in, up to two levels, read from the paragraph numbering, e.g. `3.6 Incident Analysis`; the converter's `section_title_path` can be nested wrongly), `citation` (the paragraph number: `source_ref` when that is one, else read back from
the document and marked `(inferred)`; `source_ref` itself is never replaced),
`applies_to` (the responsible party: for a row with a dotted paragraph number the title of the nearest numbered ancestor when it names a party, never the converter's path, else the path rule), `parent_ref` / `parent_text` (the parent paragraph read from
the document's own numbering, verbatim: 2.17.22 sits under 2.17; empty for a
generic label or a non-numbered reference), `passage` (the document's own text around the quote, with
the requirement marked `>> <<`; for a list item or a quote that starts
mid-sentence, the end of the previous chunk is put in front) and `item_flags`
(rule-based hints such as `starts_mid_sentence`, `list_item`, `table_fragment`,
`no_stated_actor`, `definition_or_description`, `no_passage`; a flagged row is
never dropped). None of these is model-generated. It also initializes
`audit_question`, `evidence_to_request`, `generation_notes`, `assessor_notes`,
and `status` (`"not-started"`). Those initially empty fields are not completed
assessments or automatically generated evidence.

### File exports

```bash
curl -sS --fail http://127.0.0.1:8000/api/checklist/export \
  -H 'Content-Type: application/json' \
  -d '{"doc_key":"policy","profile":"cybersecurity","format":"xlsx"}' \
  -o checklist.xlsx
```

Requires `doc_key`; `profile` defaults to `cybersecurity`, `format` to
`csv`. API format names are `csv`, `json`, `markdown`, and `xlsx` (the CLI
uses `md` for Markdown).

The response body is the file, with `Content-Disposition: attachment` and the
appropriate media type: `text/csv`, `application/json`, `text/markdown`, or
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

## Configuration endpoints

```bash
curl -sS http://127.0.0.1:8000/api/config
curl -sS http://127.0.0.1:8000/api/config \
  -H 'Content-Type: application/json' \
  -d '{"synthesis_backend":"none","rewrite_model":null}'
```

GET returns `{config: {...}, env_overridden: [...]}`.
POST returns the same envelope after partially merging submitted fields into
the file. Omitted fields stay unchanged.

Writable fields are service URLs, all model-role settings, `top_k`,
`min_score`, `synthesis_backend`, `remote_provider`, `remote_model`, and
`api_key_env`. See [Configuration](CONFIGURATION.md#supported-settings) for
defaults. `processed_dir`, `authority_registry`, and derived `authority`
are not editable through this endpoint.

`top_k` is constrained to 1–100 and `min_score` to 0–1. Synthesis backend is
`local|remote|none`; provider is `anthropic|openai`. Explicit null is allowed
only for `extraction_model`, `enrichment_model`, and `rewrite_model`, restoring
inheritance from `default_model`; null for another writable field is rejected.

POST accepts only direct loopback client addresses. Containers, proxies, or
remote browsers may appear as non-loopback clients and receive 403. Environment
overrides still win after a successful file update. CLI sessions started before
the edit should be restarted to load new settings.

## Errors and access

Route-generated errors have `{"detail":"message"}`. Request-validation errors
use HTTP 422 with a `detail` array; explicit invalid-null settings use 422 with
a string detail.

| Status | Typical condition |
|---|---|
| 400 | Unsupported export format, missing profile, or rejected settings update. |
| 403 | Configuration POST from a non-loopback client. |
| 404 | Unknown search document filter, unknown requirement/document key, or no comparison/evidence matches. |
| 422 | Missing/invalid request field or out-of-range numeric value. |
| 503 | Backend connection failure or required processed artifacts unavailable. |

Some unexpected failures can still surface as HTTP 500; the table is not a
guarantee that every possible exception is normalized.

The API has no application authentication, pagination contract, or general
request timeout setting exposed here. Keep the default loopback listener or
provide deployment-level access controls. Config POST is a mutation despite the
other endpoints primarily retrieving or exporting data.

For synthesis, local/remote/none selection comes from configuration. API
synthesis falls back to local when remote mode is selected but its key is missing.
Choose `synthesize=false` for retrieval-only responses, and inspect provenance
and warnings when using generated text.
