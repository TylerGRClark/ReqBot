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

- **Container install (recommended):** Docker Engine/Desktop with Docker Compose.
  The image includes Python, Node-built web interface, and system libraries.
- **Source install:** Python 3.12+ and Git, installed in a virtual environment.
  On a minimal Debian/Ubuntu system, also `libgl1` and `libglib2.0-0`. Building
  the web GUI also requires Node.js 20.19+, 22.12+, or a newer even-numbered
  release supported by the build script, with npm.
- **Both:** reachable Ollama and Qdrant services, and models installed in Ollama.
  ReqBot configures connections; it does not install or start those services.
  The Docker example starts Qdrant for you.

## Get Started

New to ReqBot? Follow the [Getting started guide](docs/GETTING_STARTED.md). It
walks through every step, with a check after each one:

1. Install Ollama and download two models.
2. Install ReqBot, with Docker Compose (recommended) or Python.
3. Ingest a PDF with `reqbot ingest`.
4. Search with `reqbot ask` or the web interface at `http://127.0.0.1:8000`.

The [deployment guide](docs/DEPLOYMENT.md) covers every install variant,
including optional extras and air-gapped transfer.

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
| [Getting started](docs/GETTING_STARTED.md) | Go from nothing to your first search, step by step. |
| [Deployment](docs/DEPLOYMENT.md) | See every install variant: containers, source, extras, or offline. |
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
