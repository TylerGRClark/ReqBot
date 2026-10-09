# Command-line reference

[Documentation index](README.md) · [Deployment](DEPLOYMENT.md) · [Configuration](CONFIGURATION.md)

After installing the package, use `reqbot`. From an active source checkout,
`python3 cli/reqbot.py` accepts the same subcommands. An installed package
uses its installed Python files; reinstall after source edits, or use an editable
install for development.

```bash
reqbot --help
reqbot --version
reqbot ask --help
```

Pass options after their subcommand. Every subcommand accepts `--help`.
Unless listed otherwise, service URL flags default to the effective
[configuration](CONFIGURATION.md).

## Commands at a glance

| Command | Purpose |
|---|---|
| `init` | Configure service connections, models, and synthesis. |
| `status` | Display service reachability, available/configured models, and artifacts. |
| `ingest` | Process a PDF and index its requirements/context. |
| `batch` | Ingest PDFs in a directory. |
| `docs` | List processed documents and normalized requirement counts. |
| `ask` | Retrieve requirements and optionally generate an answer. |
| `trace` | Look up a requirement's provenance and related citations. |
| `compare` | Compare a control or topic across documents. |
| `evidence` | Export a grouped evidence pack. |
| `checklist` | Export a checklist from processed requirement artifacts. |
| `questions` | Write draft audit questions for a document's checklist rows (local model; shown by `checklist`). |
| `reindex` | Rebuild indexes from processed artifacts without extraction. |
| `index` | Index one requirement JSONL file directly. |
| `index-context` | Index one source-chunk JSONL file directly. |
| `serve` | Start the HTTP API and built web GUI. |
| `mcp` | Start a local stdio MCP server. |
| `setup` | Deprecated alias for `init`. |

## init and setup

```bash
reqbot init
```

The wizard configures Qdrant/Ollama URLs, models, and local/remote/disabled
synthesis, then writes `~/.config/reqbot/config.json`. Services must already
be running; the wizard does not install them or pull models.

`reqbot setup` runs the same flow. Its legacy `--advanced` option is accepted
but has no effect.

## status and docs

```bash
reqbot status
reqbot docs
```

Both accept `--ollama-url URL` and `--qdrant-url URL`. `status` uses the URLs
for connectivity checks; `docs` reads local artifacts instead.

`status` returns exit code 0 even when it reports a service as unreachable.
Inspect the printed reachability or the API status fields for monitoring.
`docs` counts the latest normalized JSONL per document under `processed_dir`;
it does not verify that those files were indexed into Qdrant.

## ingest

```bash
reqbot ingest /path/to/policy.pdf
reqbot ingest /path/to/policy.pdf --no-index --output-dir /path/to/run
```

Default output is `<processed_dir>/<pdf_stem>_<YYYYMMDD>_<HHMMSS>/`.
Requirements and source context are indexed automatically after the pipeline.

| Option | Behavior/default |
|---|---|
| `--output-dir DIR` | Explicit artifact directory; otherwise create a timestamped run. |
| `--extraction-model MODEL` | Step C model; defaults to configured extraction role. |
| `--enrichment-model MODEL` | Step D.5 model; defaults to configured enrichment role. |
| `--model MODEL` | Sets both roles; when supplied, wins over individual role flags. |
| `--profile NAME` | Domain profile; default `cybersecurity`. |
| `--max-chunks N` | Limit Step C extraction for inspection/testing; produces a partial corpus. |
| `--no-index` | Write artifacts without indexing. |
| `--skip-enrichment` | Skip LLM enrichment; deterministic parent-stem reconstruction still runs. |
| `--skip-description-gate` | Skip Step D.6 description checks. Independent of enrichment. |
| `--ollama-url URL` | Override the Ollama connection. |
| `--qdrant-url URL` | Override the Qdrant connection. |

The old `--index` flag is still accepted but does nothing: indexing is already
the default. For resume, use the [direct pipeline procedure](OPERATIONS.md#resume-an-interrupted-run);
there is no CLI `ingest --skip-to` flag.

## batch

```bash
reqbot batch /path/to/pdfs
reqbot batch /path/to/pdfs --skip-enrichment
```

Processes immediate `*.pdf` and `*.PDF` files in the directory, not recursive
subdirectories. Accepts `--extraction-model`, `--enrichment-model`, `--model`,
`--skip-enrichment`, `--skip-description-gate`, `--ollama-url`, and
`--qdrant-url`, with the same role/URL behavior as `ingest`.

Unlike `ingest`, it has no `--profile`, `--output-dir`, `--max-chunks`, or
`--no-index` option. It uses the default profile and indexes each completed PDF.

## ask

```bash
reqbot ask "What are the access control requirements?"
reqbot ask "encryption at rest" --context --json
reqbot ask "incident response" --document-id policy --synthesize
```

Retrieval is the default; generated answers require `--synthesize` and an
enabled synthesis backend.

| Option | Behavior/default |
|---|---|
| `--top-k N` | Maximum results; configured `top_k`, built-in 20. |
| `--min-score F` | RRF cutoff; configured `min_score`, built-in 0.02; 0 disables the cutoff. |
| `--synthesize` | Generate an answer from retrieved requirements. |
| `--model MODEL` | Override the synthesis model, using the configured backend. |
| `--domain-tag TAG` | Repeatable tag filter. |
| `--requirement-type TYPE` | Repeatable type filter. |
| `--document-id DOC` | Repeatable **doc_key or source_pdf** filter, resolved against Qdrant. |
| `--json` | Emit structured retrieval output. |
| `--context` | Include linked source-chunk text in results and synthesis context. |
| `--no-rewrite` | Disable LLM keyword rewriting. |
| `--no-hyde` | Disable the hypothetical-requirement retrieval leg. |
| `--rewrite-model MODEL` | Override the configured rewrite/HyDE model. |
| `--context-collection NAME` | Source-context collection; default `grc_context`. |
| `--ollama-url URL`, `--qdrant-url URL` | Override service connections. |

Despite the flag name, search's `--document-id` expects a filename stem or
source PDF filename, not the PDF-content hash. Unknown values fail explicitly.
`--no-rewrite` and `--no-hyde` are independent; use both to avoid those query
model calls. Dense embedding and sparse retrieval still run.

## trace

```bash
# Use an ID returned by ask.
reqbot trace REQ-returned-id --context
reqbot trace REQ-returned-id --json
```

Accepts `--json`, `--context`, and `--qdrant-url URL`.
Returns provenance, other requirements sharing the reference, and optionally
linked source text. The requirement must exist in Qdrant.

## compare

```bash
reqbot compare "AC-2"
reqbot compare "encryption at rest" --markdown
reqbot compare "incident response" --document-id CONTENT-HASH-1 --document-id CONTENT-HASH-2 --json
```

The positional argument is **one control ID or free-text query**. The CLI does
not take two document names plus a topic; the API/MCP expose that interface.

Accepts `--top-k N` (configured default, for semantic retrieval), `--json`,
`--markdown`, repeatable `--document-id ID`, `--ollama-url URL`, and
`--qdrant-url URL`. Here, unlike `ask`, the document filter uses the
**content-derived document_id** from search/trace payloads.

Recognized control IDs use an exact citation match; free text uses hybrid
retrieval. Results select representatives per document/reference, rather than
listing every obligation. Shared citations do not establish equivalent scope.

## evidence

```bash
reqbot evidence "incident response" --output evidence.md
reqbot evidence "access control" --document-id policy --format json --output evidence.json
```

| Option | Behavior/default |
|---|---|
| `--format FORMAT` | `markdown` (default) or `json`. |
| `--output FILE` | Write to file instead of stdout. |
| `--context` | Include surrounding source text. |
| `--top-k N` | Retrieval limit; fixed default 20. |
| `--document-id DOC` | Repeatable doc_key/source_pdf filter. |
| `--domain-tag TAG`, `--requirement-type TYPE` | Repeatable classification filters. |
| `--ollama-url URL`, `--qdrant-url URL` | Override service connections. |

The CLI requests evidence synthesis using the configured backend; it has no
per-command `--synthesize` or disable-synthesis flag. Set
`synthesis_backend=none` for retrieval-only evidence. API/MCP evidence instead
default to `synthesize=false`. Evidence packs collect requirements and source
references; they do not assert that your organization has implemented a control.

## questions

```bash
reqbot questions --doc policy
reqbot checklist --doc policy --format xlsx --output checklist.xlsx   # the Audit Question column is now filled
```

Writes one draft yes/no audit question per checklist row to `<doc>_audit_questions.jsonl` beside the document's requirements, using the local Ollama model (default `qwen2.5:14b`; `--model`, `--ollama-url`). Rows that look like fragments, definitions or descriptions get no question. A question that mentions a number, acronym or name not found in the row's own text is kept and marked in the row's notes. Questions are drafts for the auditor to check; rerunning reuses unchanged rows and retries failed ones. Building a checklist never calls a model.

## checklist

```bash
reqbot checklist --doc policy --format csv --output checklist.csv
reqbot checklist --doc policy --format xlsx --output checklist.xlsx
```

Requires `--doc DOC_KEY` (PDF stem shown by `docs`). Accepts `--profile NAME`
(default `cybersecurity`), `--format csv|json|md|xlsx` (default `csv`), and
`--output FILE`. XLSX requires an output file.

Checklists read processed artifacts rather than searching Qdrant. They include
quote/citation/page provenance, the document's own surrounding passage, an
"applies to" heading where the structure names one, and specific hints (the
Check column). The sheet is one list in document order with a Status dropdown
(not-started, in-progress, compliant, non-compliant, not-applicable) and a Notes
column. Passages that look like obligations but were not extracted are listed
after the items under a clear banner ("possible missed requirements"; CSV rows
carry the `possible_missed` flag). Assessor fields begin empty; generation does
not complete an assessment.

## reindex

```bash
reqbot reindex
reqbot reindex --requirements-only
```

Reads selected requirement artifacts and matching chunks beneath configured
`processed_dir`. No extraction or enrichment is rerun. Uses the current
embedding model. Accepts `--requirements-only`, `--ollama-url URL`, and
`--qdrant-url URL`.

The artifact-selection and per-collection alias-swap behavior is documented in
[Operations](OPERATIONS.md#rebuild-the-search-indexes). Reindex after an embedding
model change, and preserve artifact modification times when restoring backups.

## index and index-context

```bash
reqbot index /path/to/policy_requirements_gated.jsonl
reqbot index-context /path/to/policy_chunks.jsonl --document-id CONTENT-HASH --source-pdf policy.pdf
```

Both accept `--recreate`, `--batch-size N` (effective default 32),
`--ollama-url URL`, and `--qdrant-url URL`.
`index-context` also accepts `--document-id ID` and `--source-pdf NAME`.
For manually indexed context, use the document_id from the requirements so
trace/context can join them. If omitted, context indexing derives a filename ID.

These are low-level collection operations. **`--recreate` replaces the target
collection**, affecting other indexed documents; it is not a single-document
refresh. Prefer `reindex` for a complete library rebuild.

## serve and mcp

```bash
reqbot serve
reqbot serve --host 127.0.0.1 --port 8000
```

`serve` accepts `--host` (default `127.0.0.1`) and a positive `--port`
(default 8000). The built GUI is at `/`, Swagger at `/api-docs`, and endpoints
under `/api/`. A frontend build is optional for API use.

`reqbot mcp` starts the stdio server and has no transport, host, or port flags.
It requires the `mcp` extra and is normally launched by an AI client.
See [Connecting AI tools](AI_TOOLS.md).

## Interactive shell

Run `reqbot` with no command, then use `help` or `help ask` for shell-specific
syntax. `show` displays session settings; `set` changes them and `unset`
clears filters. `exit` or `quit` closes the shell.

The shell also provides corpus helpers such as `tags`, `analyze`, and
`authority`; these are not standalone CLI subcommands. Session settings are
not equivalent to writing the persistent configuration file.

## Output and errors

Commands normally report operational failures with exit code 1 and messages
on stderr. Argument errors are reported by argparse (exit code 2).
As noted above, `status` does not fail its exit code for unreachable services.

JSON formats differ between CLI commands and HTTP endpoints. Use the
[API reference](API.md) for the HTTP envelopes; do not assume a CLI JSON export
can substitute unchanged for an HTTP response.
