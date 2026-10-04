# ReqBot

ReqBot turns regulatory PDFs into a searchable library of compliance requirements.
Search a requirement, follow its quote back to the source, compare documents, or
export a checklist from the CLI or web interface.

ReqBot runs on infrastructure you control, using Ollama for local models and
Qdrant for search. Processed JSONL files are the durable source of record; Qdrant
is a rebuildable index. Cloud answer synthesis is an optional integration.

## What It Does

- Extracts requirements while preserving document, page, and section provenance.
- Validates extracted quotes and checks generated descriptions before indexing.
- Searches with dense and keyword retrieval, with optional source context.
- Compares requirements across documents and builds evidence packs.
- Exports compliance checklists as CSV, JSON, Markdown, or XLSX.
- Provides a CLI, interactive shell, web GUI, HTTP API, and local MCP server.

Extraction and generated answers still need human review. A matching citation
across documents helps navigation; it does not establish equivalent obligations
or prove compliance.

## Requirements

- **Source install:** Python 3.12+ and Git. Building the web GUI also requires
  Node.js 20.19+, 22.12+, or a newer even-numbered release supported by the build
  script, with npm.
- **Container install:** Docker Engine/Desktop with Docker Compose.
- **Both:** reachable Ollama and Qdrant services, and models installed in Ollama.
  ReqBot configures connections; it does not install or start those services.

## Install / Deployment

The [deployment guide](docs/DEPLOYMENT.md) covers Docker, source installation,
model preparation, and air-gapped transfer. Use it for a fresh machine.

## Quick Start

This example uses a source install with Ollama and Qdrant already running at
`http://localhost:11434` and `http://localhost:6333`.

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
pip3 install --break-system-packages .

# Run these against the Ollama instance ReqBot will use.
ollama pull nomic-embed-text
ollama pull llama3.1:8b-instruct-q4_K_M

reqbot init
reqbot status
```

For the first run, choose **None** for answer synthesis in `reqbot init`.
Retrieval still uses local embedding and query models.

```bash
# Replace this path with a real PDF. Ingestion indexes requirements and context.
reqbot ingest /path/to/policy.pdf
reqbot docs
reqbot ask "What are the access control requirements?"

# Replace the ID with one returned by the search.
reqbot trace REQ-returned-id --context
```

The [deployment guide](docs/DEPLOYMENT.md#first-document) explains what to check
after ingestion and how to start the browser interface.

## Core Commands

See the [CLI reference](docs/CLI.md) for commands, options, and examples. Run
`reqbot --help` or `reqbot <command> --help` for help from your installed version.
Running `reqbot` without a command opens the interactive shell.

## Configuration

Use `reqbot init` for guided setup. The [configuration reference](docs/CONFIGURATION.md)
lists every supported setting, its default, and its environment override where
one exists.

## Documentation

| Guide | Start here when you want to… |
|---|---|
| [Deployment](docs/DEPLOYMENT.md) | Install ReqBot with containers, from source, or offline. |
| [Architecture](docs/ARCHITECTURE.md) | Understand the pipeline and component responsibilities. |
| [Configuration](docs/CONFIGURATION.md) | Set service URLs, models, paths, and synthesis options. |
| [Connecting AI tools](docs/AI_TOOLS.md) | Expose your library to a local MCP client. |
| [CLI reference](docs/CLI.md) | Ingest, search, trace, compare, and export from a terminal. |
| [API reference](docs/API.md) | Build an integration using HTTP requests and responses. |
| [Operations](docs/OPERATIONS.md) | Resume ingestion, back up artifacts, or rebuild indexes. |
| [Profiles](docs/PROFILES.md) | Understand domain configuration and checklist profiles. |

The [documentation index](docs/README.md) also links to development notes,
planning documents, and the backlog.

## Contributing and License

Read [CONTRIBUTING.md](CONTRIBUTING.md), including the contributor license
agreement, before submitting changes. ReqBot is licensed under
[AGPL-3.0-or-later](LICENSE).
