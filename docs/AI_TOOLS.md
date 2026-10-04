# Connecting AI tools

[Documentation index](README.md) · [Deployment](DEPLOYMENT.md) · [API](API.md)

ReqBot exposes your library through a Model Context Protocol (MCP) server.
A compatible AI client launches `reqbot mcp` as a local subprocess and exchanges
tool calls over **stdio**. The server shares ReqBot's configuration and services.

There is no HTTP/SSE/streamable-HTTP MCP endpoint in the current implementation.
`reqbot serve` starts the HTTP API, not the MCP server. A client that only
accepts a remote MCP URL cannot connect directly to this stdio server.

## Prepare the environment

On the machine where the client will launch the subprocess, install ReqBot from
a source checkout with the optional MCP dependency, in a virtual environment
as described in [Deployment](DEPLOYMENT.md#source-installation). The Docker image
installs only the base package, so it does not include the MCP server.

```bash
pip install ".[mcp]"
reqbot init
reqbot status
reqbot docs
reqbot ask "Find requirements in my library"
command -v reqbot
```

Use the absolute executable path reported by the last command (inside an
activated virtual environment it points into that environment, so the client does
not need the environment activated). The client process may have a different PATH
from your terminal.
Ingest at least one document before testing search tools.

The subprocess needs the running account's ReqBot config, reachable Ollama and
Qdrant services, and access to processed artifacts. Search/trace use Qdrant;
document listing and checklists read `processed_dir`. Copying only the config
does not copy the library.

## Configure a subprocess client

For a client that accepts an `mcpServers` configuration, the entry has this
shape. Replace the absolute path with your installed executable:

```json
{
  "mcpServers": {
    "reqbot": {
      "command": "/absolute/path/to/reqbot",
      "args": ["mcp"],
      "env": {
        "REQBOT_OLLAMA_URL": "http://localhost:11434",
        "REQBOT_QDRANT_URL": "http://localhost:6333",
        "REQBOT_PROCESSED_DIR": "/absolute/path/to/documents/processed",
        "REQBOT_SYNTHESIS_BACKEND": "none"
      }
    }
  }
}
```

This is a subprocess configuration template; the settings-file location and
registration UI belong to the chosen client. Clients with another configuration
format still need the same executable, `mcp` argument, and environment.

If the client runs in a container or on another host, `localhost` refers to
that environment. Use service URLs and artifact mounts reachable by the
subprocess. The config file is read from the account running that subprocess.
Restart/reload the client connection after saving its configuration.

Do not add a shell banner or wrapper that writes ordinary text to stdout.
That stream carries MCP protocol messages; logs belong on stderr.
Running `reqbot mcp` manually waits for protocol input, not an interactive prompt.

## Available tools

| Tool | Inputs and defaults | Returns |
|---|---|---|
| `get_status` | No arguments. | Service URLs/reachability, installed models, configured roles, and processed-document inventory. |
| `list_documents` | No arguments. | `docs`, `total_docs`, and `total_reqs` from processed normalized artifacts. |
| `search_requirements` | Required `question`; `top_k=20`; optional `document_ids`, `domain_tags`, `requirement_types`; `context=false`. | Ranked requirement payloads, provenance, metadata, and warnings. Always retrieval-only. |
| `trace_requirement` | Required `requirement_id`; `include_context=false`. | Requirement payload, related citation matches, and optional source context. |
| `compare_documents` | Required `doc_id_1`, `doc_id_2`, `topic`; `top_k=10`. | Exact or semantic comparison, with canonical source PDF names. |
| `map_evidence` | Required `topic`; optional `document_ids`, `domain_tags`, `requirement_types`; `synthesize=false`, `top_k=10`. | Grouped requirements, source payloads, optional synthesis text, and warnings. |
| `generate_checklist` | Required `doc_key`; `profile="cybersecurity"`. | Checklist envelope with provenance and review flags. |

`top_k` must be 1–100 where exposed. Search uses the configured `min_score`;
it has no tool argument to override it. Search rewriting and HyDE are enabled
through the shared search path, with no tool arguments to disable them.

`document_ids` in search/evidence accepts PDF stems or source PDF filenames,
despite the parameter's name. Values must resolve against the Qdrant corpus;
unknown documents return an error. Compare accepts document keys/source PDF
names and returns `doc_pdf_1`/`doc_pdf_2` to identify the result's document keys.
`generate_checklist` needs the artifact `doc_key`, not a requirement ID.

Document listing describes artifacts and does not independently verify the live
index. A search result is the source of a real requirement ID for trace.
Tools do not ingest documents, edit assessments, or export files. Use the
CLI/API/GUI export paths for downloadable checklists.

## First useful interaction

Ask the client to perform these steps:

1. Call `get_status` and `list_documents`.
2. Call `search_requirements` for an obligation you know exists in a listed PDF.
3. Call `trace_requirement` on a returned ID, with `include_context=true`.
4. Present the quote, source PDF, citation, and page information alongside its
   interpretation, and mark missing provenance instead of inventing it.

For a comparison, supply two document keys from the listing and a topic.
For a checklist, supply one document key and inspect
`requires_human_review`/`review_reasons`.

Tool-backed matches are evidence about source documents, not proof that an
organization meets the requirements. Shared citations alone do not establish
equivalent obligations across documents.

## Synthesis and data handling

`search_requirements` never synthesizes an answer. `map_evidence` can synthesize
when requested, using the configured local/remote/none backend. In remote mode,
the provider SDK and named API-key environment variable must be available to
the subprocess. A missing key causes this tool to fall back to local synthesis.

The external client can independently send returned quotes/context to its own
model provider. Keeping ReqBot's synthesis backend local or disabled does not
control that client's data handling. Select the client/provider to match your
document requirements.

## Troubleshooting

| Symptom | Check |
|---|---|
| Executable not found | Use an absolute path; confirm the client account can execute it. |
| Missing `mcp` module | Install the extra in the executable's Python environment. |
| Protocol connection closes | Inspect client stderr logs; remove stdout banners and verify dependencies. |
| No documents listed | Check the running account, `processed_dir`, and artifact access. |
| Documents list but search fails | Confirm indexing completed and Ollama/Qdrant are reachable from the subprocess. |
| Context is unavailable | Confirm matching source chunks were indexed using the requirement's document_id. |
| Wrong URLs/models | Inspect `get_status`; environment overrides beat the file settings. |

Tool exceptions are reported through MCP's tool-error mechanism. They are not
successful empty-result responses. For HTTP integrations instead, see [API](API.md).
