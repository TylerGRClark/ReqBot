# Operations runbook

[Documentation index](README.md) · [Deployment](DEPLOYMENT.md) · [CLI](CLI.md)

This guide covers an installed deployment. Use `reqbot` from the active
environment; `python3 cli/reqbot.py` is equivalent from a source checkout.
See [Deployment](DEPLOYMENT.md) for installation and model preparation.

## Check health and corpus state

```bash
reqbot status
reqbot docs
reqbot ask "Find requirements in my library"
```

Check that Ollama and Qdrant are reachable and the configured model names are
installed. A successful `status` exit code alone is not a health signal:
the command returns 0 even when its output says a service is unreachable.

`docs` reads the latest normalized artifacts under configured `processed_dir`.
Search and trace exercise the live Qdrant index. Counts can differ after a
failed index, an artifact-only ingest, or a partial reindex.

For containers, prefix commands with `docker compose exec reqbot`.
`localhost` inside a container refers to that container. Inspect effective
settings through `GET /api/config` when URLs or paths are unexpected.

## Ingest a document

```bash
reqbot ingest /path/to/policy.pdf
reqbot docs
reqbot ask "A requirement topic from this PDF"
```

Keep the original PDF and the complete output run directory. Default artifact
directories are `<processed_dir>/<pdf_stem>_<YYYYMMDD>_<HHMMSS>/`.
Use `--no-index` to inspect artifacts before indexing, or `--output-dir` for
an explicitly managed run directory.

Read logs for rejected quotes, skipped enrichment, skipped entailment checks,
and description-gate failures. See [Architecture](ARCHITECTURE.md) for artifacts
and validation boundaries.

On an Ollama host with GPU support, `ollama ps` or its API helps inspect model
placement. This is independent of Docling's parsing work on the ReqBot host.

## Resume an interrupted run

Resume in the **same run directory** to retain Step C's prompt-hash cache.
From a source checkout, use the original PDF:

```bash
python3 pipeline/run_pipeline.py /path/to/policy.pdf \
  --output-dir /path/to/existing_run \
  --skip-to C \
  --ollama-url http://localhost:11434 \
  --extraction-model llama3.1:8b-instruct-q4_K_M \
  --enrichment-model llama3.1:8b-instruct-q4_K_M
```

Replace the URL and model names with those from the original run. The direct
script has its own defaults; it does not inherit the CLI config for service
URLs, model roles, or `processed_dir`. Its default output path is relative to
the repository. Always specify the existing output directory for resume.

| Resume option | Required existing artifacts / behavior |
|---|---|
| `--skip-to A` | Run all stages. |
| `--skip-to B` | The parser runs to obtain the in-memory Docling document, then chunks again. |
| `--skip-to C` | Existing matching chunks; extract or reuse valid cached responses. |
| `--skip-to D` | Existing chunks and extracted requirements; normalize, reconstruct, enrich/check, and export. |
| `--skip-to E` | Existing normalized requirements; aggregate without rerunning D.5/D.6. |

The original PDF is still required because the script checks its existence and
normalization uses its content identity. Changing model/prompt inputs can
invalidate cached extraction work. Non-default profiles bypass Step C's cache;
the direct script has no profile flag and uses `cybersecurity`.

Other direct-script options are `--model` (sets both role models),
`--max-chunks`, `--timeout` (per-request seconds, default 120),
`--skip-enrichment`, `--skip-description-gate`, and `--qdrant-url`.
The direct script does **not** index unless `--index` is supplied.
Its `--index` path uses indexing-module defaults, so for a deployment with a
custom embedding model, finish the resume and use configured `reqbot reindex`
over its processed directory instead.

Use `--skip-to D` to rerun validation/enrichment; `--skip-to E` selects normalized
input and is not a shortcut for exporting an existing gated artifact.
Preserve originals before a rerun if you need to compare outcomes.

## Rebuild the search indexes

```bash
reqbot reindex
```

This re-embeds existing artifacts with the configured embedding model, rebuilding
requirements and source context. It does not rerun extraction or enrichment.

Artifact selection is based on **modification times**, not directory timestamps:

1. Group files by PDF stem and run directory.
2. Choose the run whose requirement artifacts have the most recent modification.
3. Within it, prefer gated, then enriched, then normalized, but skip a higher tier
   if it is older than a lower tier.

This prevents an old gated artifact from masking a more recent normalization
rerun. The [shared resolver](../core/artifact_resolver.py) defines this rule.

Each collection is built in a temporary collection. Before its live alias is
switched, reindex checks that the replacement holds every point it should (one per
distinct requirement ID, or per document chunk). If any are missing, for example
because an embedding failed and was skipped, the replacement is deleted, the missing
items are logged, and the live index stays as it was. After a successful check the
alias is switched and the old backing collection is removed. Requirements and
context are rebuilt **sequentially**, not as one transaction. If requirements
succeed and context fails, the new requirements remain live while old context
remains live. Inspect logs and retry after fixing the context failure.

A document with no chunks file is skipped with a warning that names it; its context
will be absent from the new context index. Real context indexing
errors abort that context replacement; if no context documents can be indexed,
the command reports failure. Initial migration of a plain collection to an alias
can create a brief availability gap.

For an artifact-only requirements change with unchanged embeddings/context:

```bash
reqbot reindex --requirements-only
```

Do not use that shortcut after changing the embedding model: both indexes need
the new vectors. Reindex excludes files outside configured `processed_dir`;
an ingest using a separate `--output-dir` may need its artifacts moved into the
managed library before a full rebuild.

### Single-file indexing

```bash
reqbot index /path/to/policy_requirements_gated.jsonl
reqbot index-context /path/to/policy_chunks.jsonl \
  --document-id CONTENT-HASH-FROM-REQUIREMENTS \
  --source-pdf policy.pdf
```

These commands directly upsert records. They do not promise removal of obsolete
points left by earlier versions of a document. Prefer a full rebuild when you
need the index to match the artifact library exactly.
`--recreate` replaces an entire target collection; it is not a single-document
cleanup option.

## Back up and restore

Back up original PDFs, all processed run directories, and the ReqBot config and
authority registry. Qdrant can be rebuilt, but its snapshots can reduce recovery
time when managed by your Qdrant deployment.

For default source-install paths, after a completed run:

```bash
tar -czf reqbot-artifacts.tar.gz -C "$HOME" documents/processed .config/reqbot
tar -tzf reqbot-artifacts.tar.gz
```

Change the paths for custom deployments and back up PDFs separately. Quiesce
artifact writers before taking a backup; copying files during ingestion can
produce an inconsistent run. Archive tools should retain file modification
times because the resolver relies on them.

Restore into a staging directory first:

```bash
mkdir -p ~/reqbot-restore
tar -xzf reqbot-artifacts.tar.gz -C ~/reqbot-restore
```

Inspect the restored files, put them at the intended configured paths while
preserving timestamps, verify model/service configuration, then run
`reqbot reindex`, search, and trace. Restore Ollama models/caches separately if
the replacement host cannot download them.

For Compose, artifacts are in the host bind mount; Qdrant storage is a named
volume. `docker compose down -v` deletes named volumes, so it is not a routine
restart command for a library you intend to retain.

## Update an installation

For a source package, install the intended revision with `pip install .` from
that checkout, in the same virtual environment as the existing install.
Rebuild the GUI before a non-editable package install so its package data includes
the new frontend. For an editable development install, rebuilding updates the
checkout's served files.

For Docker, preserve mounts and file-only configuration, rebuild/recreate the
ReqBot service, and verify status/search/trace afterward. Container replacement
can lose unmounted model caches or config.

A code upgrade does not automatically regenerate old extraction artifacts.
Reindex updates vectors/payloads from existing files; re-ingest only when you
intend to refresh extraction or validation outputs.

## Troubleshooting

| Symptom | Next check |
|---|---|
| `reqbot` runs an old version | Inspect `command -v reqbot` and `reqbot --version`; check PATH and reinstall the intended revision. |
| `pip` refuses to install (`externally-managed-environment`) | Install inside a virtual environment; see [Deployment](DEPLOYMENT.md#source-installation). |
| Ingest fails at Step A with `libGL.so.1` or `libxcb.so.1` not found | Install the system libraries: `sudo apt install libgl1 libglib2.0-0`. The Docker image includes them. |
| Ollama model not found | Compare configured roles to `ollama list` on the configured service. |
| Browser root returns no GUI | Build frontend before package install; API may still be available at `/api-docs`. |
| Browser shows old frontend | Reload/hard-refresh; for a packaged install, rebuild and reinstall/recreate. |
| Document listed, no search results | Check indexing logs, collection reachability, filters, and query topic. |
| Trace has no context | Verify matching chunks exist and were indexed using the requirements' document_id. |
| Reindex chose an unexpected run | Compare artifact modification times, including stale higher-tier files. |
| Embedding mismatch or dimension error | Restore intended model settings or rebuild both indexes with the new model. |
| Settings update returns 403 | The API requires a loopback client; container/proxy connections may not qualify. |
| Offline ingest downloads/fails | Warm and transfer the missing assets, then repeat network-disabled qualification. |

Remote workspace port forwarding is a separate layer from ReqBot's listener:
forward port 8000 through that workspace tool, and inspect its tunnel if the
server responds locally but your browser cannot connect.
