# ReqBot documentation

New here? Start with [Getting started](GETTING_STARTED.md): it takes you from
nothing to your first search. These guides describe the implementation in this
repository; use the documentation from your deployed Git revision when versions
differ.

## User and integration guides

| Guide | Contents |
|---|---|
| [Getting started](GETTING_STARTED.md) | Step-by-step first run: Ollama, install, first PDF, first search. |
| [Deployment](DEPLOYMENT.md) | Every install variant: Docker, source, extras, networking, and offline preparation. |
| [Architecture](ARCHITECTURE.md) | Document-to-requirement flow, retrieval, validation, and component ownership. |
| [Configuration](CONFIGURATION.md) | Defaults, precedence, environment variables, and model changes. |
| [Connecting AI tools](AI_TOOLS.md) | MCP setup, subprocess configuration, tools, and troubleshooting. |
| [CLI reference](CLI.md) | Every public subcommand and its options. |
| [API reference](API.md) | HTTP endpoints, request fields, response envelopes, exports, and errors. |
| [Operations](OPERATIONS.md) | Health checks, resume, backup/restore, reindex, and troubleshooting. |
| [Profiles](PROFILES.md) | Domain profile schema and current limitations. |

## Development and planning

- [Developer architecture reference](../ARCHITECTURE.md): package map and import
  boundaries for code contributors.
- [Contributing](../CONTRIBUTING.md): contribution process, licensing, and code
  standards.
- [Product requirements](PRODUCT_PRD.md): product direction.
- [Future improvements](TODO_future_improvements.txt): engineering backlog.
- `PHASE*_REQUIREMENTS.md` files: work-package plans and measured outcomes.
- [Archive](../archive/): historical plans and retired approaches.

Planning documents can describe proposed behavior. The user guides describe
available behavior; a future work package is not an installation instruction.
