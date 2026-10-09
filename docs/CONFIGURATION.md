# Configuration reference

[Documentation index](README.md) · [Deployment](DEPLOYMENT.md) · [CLI](CLI.md)

Run `reqbot init` for guided setup. Settings are stored in
`~/.config/reqbot/config.json` for the account running ReqBot. In a container,
that is the container account's home directory, not your host account's home.

## Precedence and inspection

The configuration loader applies these layers in order:

1. Built-in defaults.
2. Recognized keys in `~/.config/reqbot/config.json`.
3. Supported `REQBOT_*` environment variables.

Command-line flags override the loaded value for that command where a flag is
available. There is no general `--config` flag or configurable config-file path.

`reqbot status` shows service reachability and configured model roles. For a
complete effective configuration, start `reqbot serve` and request:

```bash
curl -sS http://127.0.0.1:8000/api/config
```

The response has `config` and `env_overridden` fields. Saving a file setting does
not override an active environment variable. Set environment variables before
starting the CLI, API, or MCP process; restart a running process after changing
its environment. Start a new CLI/shell session after changing its config file.
API and MCP requests load configuration on each call.

## Supported settings

Defaults below are from [core/config.py](../core/config.py). **None** in the last
column means no dedicated `REQBOT_*` override is implemented.

| Setting | Built-in default | Purpose | Environment override |
|---|---|---|---|
| `ollama_url` | `http://localhost:11434` | Ollama for embeddings, extraction, enrichment, rewrite, and local synthesis. | `REQBOT_OLLAMA_URL` |
| `qdrant_url` | `http://localhost:6333` | Qdrant requirements/context indexes. | `REQBOT_QDRANT_URL` |
| `default_model` | `llama3.1:8b-instruct-q4_K_M` | Fallback for the three inheriting model roles below. | `REQBOT_DEFAULT_MODEL` |
| `extraction_model` | `null` → `default_model` | Requirement finding (Step C). | `REQBOT_EXTRACTION_MODEL` |
| `enrichment_model` | `null` → `default_model` | Enrichment (Step D.5): descriptions, tags, and types. | `REQBOT_ENRICHMENT_MODEL` |
| `rewrite_model` | `null` → `default_model` | Search query rewriting and HyDE hypotheses. | `REQBOT_REWRITE_MODEL` |
| `synthesis_model` | `qwen2.5:14b` | Local answer/evidence synthesis. | `REQBOT_SYNTHESIS_MODEL` |
| `embedding_model` | `nomic-embed-text` | Dense embeddings for indexing and querying. | `REQBOT_EMBEDDING_MODEL` |
| `top_k` | `20` | Default result limit for CLI `ask` and `compare`. | `REQBOT_TOP_K` |
| `min_score` | `0.02` | Default RRF score cutoff for CLI search and MCP search. | `REQBOT_MIN_SCORE` |
| `processed_dir` | `~/documents/processed` | Durable processed artifacts; `~` expands for the running account. | `REQBOT_PROCESSED_DIR` |
| `authority_registry` | `null` → `~/.config/reqbot/authority.json` | Optional document authority metadata. | None |
| `synthesis_backend` | `local` | Answer generation: `local`, `remote`, or `none`. | `REQBOT_SYNTHESIS_BACKEND` |
| `remote_provider` | `anthropic` | Remote provider: `anthropic` or `openai`. | None |
| `remote_model` | `claude-sonnet-4-6` | Model identifier used for remote synthesis. | None |
| `api_key_env` | `ANTHROPIC_API_KEY` | Name of the environment variable containing the provider key. | None |

The loader also exposes `authority`, derived from the registry. It is not a
persisted config setting.

HTTP request defaults are defined by the API request models: for example,
`/api/ask` defaults to `top_k=20` and `min_score=0.02` even if those file settings
have changed. MCP and CLI commands also have some fixed per-command defaults;
consult their references instead of assuming all defaults come from this table.

## Example file

```json
{
  "ollama_url": "http://localhost:11434",
  "qdrant_url": "http://localhost:6333",
  "default_model": "llama3.1:8b-instruct-q4_K_M",
  "extraction_model": null,
  "enrichment_model": null,
  "rewrite_model": null,
  "embedding_model": "nomic-embed-text",
  "synthesis_backend": "none",
  "processed_dir": "~/documents/processed"
}
```

Omitted keys use built-in defaults. Use JSON numbers for numeric settings.
`null` or an empty string for extraction/enrichment/rewrite means inherit
`default_model`; an explicit model name pins that role independently.
`synthesis_model` and `embedding_model` never inherit `default_model`.

The file loader is not a general schema validator. Unknown keys are ignored;
unreadable or malformed JSON falls back to defaults/environment. Malformed
numeric environment values are ignored. Prefer `init` or the settings API to
hand editing, and inspect effective values after edits.

## Local, remote, and retrieval-only operation

- **Local:** install the configured synthesis model in Ollama and use
  `synthesis_backend: "local"`.
- **None:** `synthesis_backend: "none"` disables generated answer text. Local
  embedding and retrieval-related model calls still run.
- **Remote:** install the `remote` extra, choose a provider/model, and supply the
  provider key in the environment of the ReqBot process. Only synthesis uses
  this provider; ingestion and local retrieval model roles still use Ollama.

Example remote settings:

```json
{
  "synthesis_backend": "remote",
  "remote_provider": "anthropic",
  "remote_model": "claude-sonnet-4-6",
  "api_key_env": "ANTHROPIC_API_KEY"
}
```

Do not store the key itself in `config.json`. `api_key_env` names the variable
that contains it. For OpenAI, set the provider, an available model identifier,
and the corresponding key variable together.

API/MCP synthesis routes fall back to local synthesis when remote mode is
configured but the named key variable is missing. CLI synthesis paths also
support a local fallback. Request `synthesize=false` when you only want retrieved
records. Remote synthesis sends selected requirement text to the provider;
`context`/`show_context` can add source text. An external AI client can also send
MCP tool results to its own model provider regardless of ReqBot's synthesis mode.

## Changing models

ReqBot does not pull models automatically. Install the selected models on the
Ollama service before using them.

Changing extraction or enrichment affects later pipeline runs; it does not
rewrite existing JSONL. Changing rewrite or synthesis affects subsequent queries.
Changing **embedding_model** requires rebuilding both indexes:

```bash
reqbot reindex
```

Search responses warn when returned records were embedded with another model.
This is not a guarantee that incompatible vectors can be searched: a vector
dimension mismatch can cause Qdrant to reject the query before results exist.
Keep the old model/config available until the rebuild succeeds.

## Authority registry

An optional registry supplies authority labels/weights for CLI trace, comparison,
evidence display, and interactive-shell inspection. It does not currently
reweight retrieval or add authority fields to indexed payloads.
Its top-level `documents` list contains entries such as:

```json
{
  "documents": [
    {
      "source_pdf": "policy.pdf",
      "authority_weight": 1,
      "document_type": "policy",
      "framework": "example",
      "revision": "1",
      "publication_date": "2026-01-01"
    }
  ]
}
```

`source_pdf` identifies an entry; `authority_weight` defaults to 1 when omitted,
and the other metadata fields default to empty strings. Match the source PDF filename.
A missing/unreadable registry is treated as empty. If a configured path is
missing, the loader also tries the default registry path. Registry edits are
picked up by a new CLI/shell session; reindex is not required.

## Settings API and container persistence

`POST /api/config` partially updates supported settings and writes the file with
owner-only permissions. It accepts only loopback clients and cannot edit
`processed_dir`, `authority_registry`, or derived `authority`. See
[API settings](API.md#configuration-endpoints) for fields and errors.

The example Compose deployment persists processed artifacts and Qdrant storage,
but does not mount the container's config directory. Prefer Compose environment
variables for supported fields. For file-only settings, mount a prepared config
directory at `/root/.config/reqbot` so it survives container replacement.
