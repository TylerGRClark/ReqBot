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
| GET | `/api/access` | Which way admin actions are protected here: `{"admin": "unconfigured"`, `"code"` or `"open"}`. Public; never the code. |
| GET | `/api/jobs` | The jobs, newest first (admin access code required). |
| GET | `/api/jobs/{job_id}` | One job with the tail of its log (admin access code required). |
| POST | `/api/uploads?filename=NAME.pdf` | Store one PDF sent as the raw body; returns its id and where it stands against the library (admin). |
| POST | `/api/jobs/ingest` | Start the full pipeline for an uploaded PDF (admin). |
| GET | `/api/inbox` | The PDFs waiting in the inbox folder and where each stands (admin). |
| POST | `/api/jobs/inbox` | Start one ingest per PDF in the inbox (admin). |
| POST | `/api/documents/remove` | Remove a document: run folders to the trash, rows out of search. Needs `confirm: true` and the exact key (admin). |
| POST | `/api/jobs/questions` | Write draft audit questions for one document, as a job (admin). Body `{"doc_key"}`. |
| POST | `/api/jobs/reindex` | Rebuild the search library from the saved documents, as a job (admin). Body `{"requirements_only": false}`. |
| POST | `/api/jobs/{job_id}/cancel` | Cancel a queued job, or ask a running one to stop (admin). |
| POST | `/api/jobs/{job_id}/retry` | Queue a failed, cancelled or interrupted job again, in the same run folder (admin). |

Request/response bodies are JSON except file exports and the PDF upload (the raw
body). The only endpoints that change anything besides settings are the admin
routes for adding documents and managing jobs (see [Jobs](#jobs) and
[Adding documents](#adding-documents-admin)); there are no index-rebuild or
assessor-edit endpoints in this implementation.

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
`citation`, `description`, page/chunk provenance, section paths, tags, type, and
confidence. `citation` is the reference to show: the label the checklist gives the
row, read from the document when the index was built (a paragraph number, a table
such as `Table 3.1`, `Front matter`; `(inferred)` marks a paragraph number worked
out from the text before the quote). It is empty when the index was built without
one or the document has nothing to cite, and then `source_ref` is the one to show.
`source_ref` is the reference as the extractor recorded it and is never replaced:
Evidence groups by it and the index embeds it.
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
references can have synthetic per-requirement keys (such a group is labeled by the
record's `citation` when it has one, else `(no ref)`). `synthesis_text` is an empty
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
| `summary` | `{total_items, items_requiring_review, items_with_flags, found_by_text_scan, possible_missed}`. |
| `items` | Checklist item objects. |
| `possible_missed` | Item-shaped objects for passages of the document that look like obligations but were not extracted, found by a rule-based text scan (modal word or imperative opener, not a lead-in ending in a colon, not covered by any extracted quote). Their `checklist_item_id` starts with `MISS-`, `item_flags` contains `possible_missed`, and they are not counted in `total_items`. A prompt to check, not requirements: some are descriptions or examples. Empty when the chunk file is not beside the requirements. A candidate with a duty sentence is not listed here but promoted into `items` (below), whether or not its paragraph carries a number; one whose duty sentences are all extracted already is dropped. What remains here is a passage with a modal word but no duty sentence of its own (for example a statement of purpose). |

Each item includes `checklist_item_id`, `requirement_ids`, `domain_tags`,
`source_ref`, `page_refs`, `section_title_path`, `source_quote`, `confidence`,
`requires_human_review`, and `review_reasons`. For audit use it also carries
`section_heading` (the section the paragraph sits in, up to two levels, read from the paragraph numbering, e.g. `3.6 Incident Analysis`; the converter's `section_title_path` can be nested wrongly), `citation` (the paragraph number: `source_ref` when that is one, else read back from
the document and marked `(inferred)`; a row from a table is cited by the table's own caption, e.g. `Table 3.1`, with the caption as its `section_heading` and no `applies_to`, because the converter files a table under the last heading it saw; `source_ref` itself is never replaced),
`applies_to` (the responsible party: for a row with a dotted paragraph number the title of the nearest numbered ancestor when it names a party, never the converter's path, else the path rule), `parent_ref` / `parent_text` (the parent paragraph read from
the document's own numbering, verbatim: 2.17.22 sits under 2.17; empty for a
generic label or a non-numbered reference), `passage` (the document's own text around the quote, with
the requirement marked `>> <<`; for a list item or a quote that starts
mid-sentence, the end of the previous chunk is put in front) and `item_flags`
(rule-based hints such as `starts_mid_sentence`, `list_item`, `table_fragment`,
`no_stated_actor`, `definition_or_description`, `applicability_statement`, `no_passage`; a flagged row is
never dropped). A paragraph the text scan found but extraction missed is promoted into `items`, in its place in the document, numbered or not: one row for each sentence that holds a duty (the whole sentence, without the paragraph number; an unnumbered paragraph is cited by inference, marked `(inferred)`, or has an empty `citation`), flagged first with `found_by_text_scan`, counted in `total_items` and `found_by_text_scan`, with empty `requirement_ids` and `extracted_quote`, `review_reasons` `["not-extracted"]`, and the same citation, section, passage and parent paragraph as any other row. None of these is model-generated. It also initializes
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

## Jobs

`GET /api/jobs` returns `{"jobs": [...], "running": "<job id>" | null, "queued": <count>}`
(query `limit`, 1 to 200, default 50); `GET /api/jobs/{job_id}` returns one job
plus `log_tail`. A job has `id`, `kind`, `title`, `state` (`queued`, `running`,
`succeeded`, `failed`, `cancelled`, `interrupted`), `attempt`, `command`,
`progress` (the last `{"step", "done", "total", "at"}`), `error`, `exit_code`,
`run_dir`, `requested_by`, `created_at`, `started_at`, `finished_at`.

These routes are **admin only**. Send the admin access code created by
`reqbot token` as `Authorization: Bearer <code>` (or `X-ReqBot-Token: <code>`).
With no code configured on the server they answer 403 and the API behaves as it
did before; a missing or wrong code is 401. If the operator ran `reqbot token --open`
(or set `REQBOT_ADMIN_OPEN=1`) for a network they trust, no code is asked for;
`GET /api/access` tells a screen which of the three modes it is in. No route returns the code, and
`GET /api/config` does not include it. The code travels in clear text on plain
HTTP, so beyond a trusted network put TLS in front. Cancelling and retrying are
`POST /api/jobs/{job_id}/cancel` and `/retry`; starting is described next.

## Removing a document (admin)

`POST /api/documents/remove` with `{"doc_key": "afi17-203", "confirm": true, "confirm_name": "afi17-203"}`.
It is never a delete: the document's run folders are moved to
`<processed_dir>/.trash/<removal time>/` and its rows are taken out of both search
collections. Without `confirm: true` and the exact key repeated as `confirm_name`
nothing happens (422 `confirmation_required`). 404 `no_such_document`; 409
`jobs_active` while an ingest or draft-questions job for it is queued or running
(with the job ids); 503 `index_unreachable` when the search index could not be
cleaned, in which case nothing was moved and the request can simply be repeated.
200 returns `{"document", "run_folders_moved", "trash", "points_removed": {"requirements", "context"}}`.

## Adding documents (admin)

Adding a document is two requests, so a question can be asked in between.

1. `POST /api/uploads?filename=afi17-203.pdf` with the PDF as the raw request
   body (`Content-Type: application/pdf`). The file is checked and stored, and
   the answer (201) says what it is and where it stands:
   `{"upload_id", "filename", "stem", "size", "pages", "sha256", "library": {"status", "document"}}`.
   `library.status` is `new`, `same_content` (this name is already in the library
   with identical content), `same_content_other_name`, `same_name_different_content`
   or `queued`. A refusal has `detail: {code, message}`: `not_pdf` (415),
   `too_large` (413), `too_many_pages` (422), `unreadable` (422), `bad_name` (400).
2. `POST /api/jobs/ingest` with `{"upload_id": "...", "if_exists": "ask" | "replace" | "keep_both"}`.
   202 with `{"result": "queued", "document", "job"}` when queued; 200 with
   `{"result": "skipped", "reason"}` when there is nothing to do (same content,
   or the name is already queued); 409 `same_name_different_content` with
   `options: ["replace", "keep_both"]` when the name is in the library with
   different content and `if_exists` is `ask`. It is never decided silently.
   `keep_both` ingests under a new name (`<name>_2`, ...); `replace` makes the new
   run the document's current one and runs the ingest with `--replace`: once the
   new run is fully indexed and verified, the document's earlier points that it
   no longer has are removed from search (never before).

`POST /api/jobs/questions` (`{"doc_key": "afi17-203"}`) and `POST /api/jobs/reindex`
(`{"requirements_only": false}`) queue the other two long commands. 202 with
`{"result": "queued", "job"}`; 200 `{"result": "skipped"}` when the same thing is already
queued or running (one questions job per document, one rebuild at a time); 404
`no_such_document` for a key not in the library. A rebuild swaps the requirements
collection and then the context collection, one after the other: if the second
fails the job fails and its log says the new requirements are already live beside
the old context, and running it again brings the context up to date.

`GET /api/inbox` lists the PDFs in the configured inbox folder (default
`<processed_dir>/.inbox`, `REQBOT_INBOX_DIR`) with the same standing, and
`POST /api/jobs/inbox` (`{"files": [names] | null, "if_exists"}`) queues one ingest
per PDF. No path is ever taken from a request: only an upload id this server
made, or a file name that is a PDF directly in the inbox. The limits are
environment variables: `REQBOT_MAX_UPLOAD_MB` (100), `REQBOT_MAX_PDF_PAGES`
(1500). The server runs the queue (`reqbot serve`, or `reqbot jobs worker`).

## Errors and access

Route-generated errors have `{"detail":"message"}`. Request-validation errors
use HTTP 422 with a `detail` array; explicit invalid-null settings use 422 with
a string detail.

| Status | Typical condition |
|---|---|
| 400 | Unsupported export format, missing profile, or rejected settings update. |
| 401 | A job route without the admin access code, or with a wrong one. |
| 403 | Configuration POST from a non-loopback client; a job route when no admin access code is configured. |
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
