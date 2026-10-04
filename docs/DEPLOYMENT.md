# Deployment guide

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Operations](OPERATIONS.md)

Choose Docker for a packaged CLI/API/GUI, or a source install for development
and direct pipeline access. Both use the same Python package. The commands below
use a POSIX shell; replace example PDF paths and service URLs with your own.

## Prerequisites and models

ReqBot needs reachable Qdrant and Ollama services. The example Compose file
starts Qdrant; it points at an existing Ollama instance. A source install does
not start either service.

Install Ollama using its distribution's instructions. On the Ollama host, pull
the default embedding and extraction/enrichment/rewrite models:

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b-instruct-q4_K_M
ollama list
```

For local generated answers, also pull `qwen2.5:14b`, or configure a synthesis
model that fits your hardware. You can begin with synthesis disabled.

The required RAM/VRAM and ingest speed depend on selected models, PDF complexity,
and hardware. Docling parsing can run on CPU; Ollama acceleration is configured
on the Ollama host. Installing Python dependencies does not install Ollama
models or populate every parsing/tokenizer/model cache.

## Docker installation

Install Docker with Compose, then clone and prepare the example:

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
cp docker-compose.example.yml docker-compose.yml
```

Before starting, edit `docker-compose.yml`:

- Keep `REQBOT_QDRANT_URL: "http://qdrant:6333"` for the included Qdrant service.
- Set `REQBOT_OLLAMA_URL` to an Ollama URL reachable **from the container**.
  The example uses `http://host.docker.internal:11434` and adds a host-gateway
  mapping. A loopback-only Ollama listener on the host may need a different
  reachable listener or deployment arrangement.
- For a first retrieval-only setup, add
  `REQBOT_SYNTHESIS_BACKEND: "none"` under the ReqBot service's environment.
  This avoids needing the synthesis model.

The example's commented Ollama service is an alternative; enabling it requires
setting the ReqBot Ollama URL to `http://ollama:11434` and preparing its models.
GPU passthrough depends on your host and container runtime.

```bash
docker compose config
docker compose up -d --build
docker compose logs --tail=50 reqbot
docker compose exec reqbot reqbot status
```

The Docker build installs the Python package and builds the frontend inside a
Node build stage. The host does not need Python or Node. The default GUI is at
`http://127.0.0.1:8000`; API documentation is at
`http://127.0.0.1:8000/api-docs`.

### Container storage and configuration

The example persists:

| Container path | Host storage | Purpose |
|---|---|---|
| `/root/documents/processed` | `./documents/processed` | Processed artifacts. |
| `/qdrant/storage` in Qdrant | Named volume `qdrant-storage` | Search indexes. |

Copy input PDFs into the container, or add an input-directory bind mount.
Keep the originals in your document archive.

Configuration normally comes from Compose environment variables. The example
does **not** persist `/root/.config/reqbot` or model caches. If you use
`docker compose exec reqbot reqbot init`, mount the config directory to preserve
the resulting file across container recreation. File-only remote-provider and
authority settings also need a persistent config file. See
[Configuration](CONFIGURATION.md#settings-api-and-container-persistence).

### Container first document

```bash
# Replace the host path with a real PDF.
docker compose cp /path/to/policy.pdf reqbot:/tmp/policy.pdf
docker compose exec reqbot reqbot ingest /tmp/policy.pdf
docker compose exec reqbot reqbot docs
docker compose exec reqbot reqbot ask "What are the access control requirements?"
```

Proceed to [First document](#first-document) to inspect results and provenance.

## Source installation

Use Python 3.12+ and a virtual environment. This avoids changing an
externally-managed system Python.

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

If you want the GUI in the installed package, build it **before** installing:

```bash
# Requires Node 20.19+, 22.12+, or a newer supported even-numbered release, and npm.
bash build/build-frontend.sh
python3 -m pip install .
```

For CLI/API-only use, omit the frontend build and run
`python3 -m pip install .`. A missing frontend does not remove the HTTP API.
Developers can install with `python3 -m pip install -e ".[dev]"`; the editable
install reads Python source and generated frontend files from the checkout.

### Services for a local source install

Connect to existing services, or start a local Qdrant container:

```bash
docker volume create reqbot-qdrant-storage
docker run -d --name reqbot-qdrant \
  -p 127.0.0.1:6333:6333 \
  -v reqbot-qdrant-storage:/qdrant/storage \
  qdrant/qdrant:v1.17.1
```

With Ollama running and models pulled, configure ReqBot:

```bash
reqbot init
reqbot status
```

Enter the reachable service URLs; choose **None** for synthesis initially.
The wizard writes `~/.config/reqbot/config.json` and tests service connections.
It does not install or start the services.

### Optional extras

Run these from the repository root in the active virtual environment:

| Install command | Adds |
|---|---|
| `python3 -m pip install ".[remote]"` | Remote synthesis provider SDKs. |
| `python3 -m pip install ".[mcp]"` | MCP server support for local AI clients. |
| `python3 -m pip install ".[grounding-check]"` | MiniCheck entailment scoring in the description gate. |
| `python3 -m pip install ".[rerank]"` | Experimental reranker for programmatic/evaluation use; no public CLI switch. |
| `python3 -m pip install ".[dev]"` | Test and lint tools. |

Docling is a base dependency and the only current PDF parsing path. There is no
legacy parsing fallback or `--layout-mode` switch.

The `grounding-check` extra installs MiniCheck from the pinned Git source in
`pyproject.toml`; an unrelated PyPI package has the same name. Also prepare:

```bash
python3 -c "import nltk; nltk.download('punkt_tab')"
```

Model weights can require additional first-use downloads. Without a working
MiniCheck installation, the deterministic description checks still run, but
the entailment check is skipped. Logs report this distinction.

## First document

For a source install:

```bash
reqbot ingest /path/to/policy.pdf
reqbot docs
reqbot ask "What are the access control requirements?"
reqbot trace REQ-returned-id --context
```

Replace the trace ID with an actual search result. Successful ingestion writes
a run directory beneath `processed_dir` and indexes requirements plus source
chunks. Check ingestion logs, inspect the quote/page/section returned by trace,
and compare against the original PDF.

`reqbot docs` lists processed normalized artifacts; its presence alone does
not prove indexing succeeded. A search and trace exercise the Qdrant path.
Some PDFs yield no relevant results for a particular question; choose a query
whose obligation you can locate in your test PDF.

If the frontend was built, run:

```bash
reqbot serve
```

Open `http://127.0.0.1:8000`. Search, trace, comparison, evidence, corpus,
checklists, system status, and settings are available through the GUI.
Without a frontend build, use `/api-docs` and the CLI.

## Air-gapped deployment

An exported base image is only one part of an offline installation. Prepare
Ollama models, ReqBot's parsing/tokenizer/sparse-model caches, optional model
assets, configuration, and artifacts before disconnecting. The stock image
build does not exercise ingestion or retrieval to populate all those caches.

The following is a **staging procedure**, not a claim of a tested offline
release bundle. Qualify the staged result with your PDF types and selected
extras before relying on it.

### Prepare a warmed image on a connected staging host

Use a fresh staging deployment with local services, synthesis disabled, and
non-sensitive representative PDFs. Complete the Docker setup above, then
exercise parsing, indexing, rewriting, keyword retrieval, and trace:

```bash
docker compose cp /path/to/sample.pdf reqbot:/tmp/sample.pdf
docker compose exec reqbot reqbot ingest /tmp/sample.pdf
docker compose exec reqbot reqbot ask "Find requirements stated in this document"
# Substitute a requirement ID returned by the search.
docker compose exec reqbot reqbot trace REQ-returned-id --context
```

Use additional samples to exercise required OCR/table paths. If deploying
optional extras, prepare their packages/resources/models and exercise them
as well; the stock Dockerfile installs base dependencies only.

Stop the ReqBot service and capture its warmed writable layer:

```bash
REQBOT_STAGE_CONTAINER=$(docker compose ps -q reqbot)
docker compose stop reqbot
docker commit "$REQBOT_STAGE_CONTAINER" reqbot:offline
docker save reqbot:offline | gzip > reqbot-offline.tar.gz
docker pull qdrant/qdrant:v1.17.1
docker save qdrant/qdrant:v1.17.1 | gzip > qdrant-image.tar.gz
```

`docker commit` includes the container's writable filesystem and configuration,
but **not mounted volumes**. Keep caches in the captured filesystem, or transfer
and remount them separately if staging used cache mounts. Artifacts, Qdrant data,
and Ollama model storage need separate transfer/restore when retaining a library.
Use your Ollama deployment's model-store transfer/import process and verify the
same model names exist at the destination with `ollama list`.

### Load and start on the offline host

Transfer both image archives and the prepared Compose file. In that file, set
the ReqBot service image to `reqbot:offline`, set service URLs for the destination,
and retain the persistent storage mounts. Then:

```bash
gunzip -c reqbot-offline.tar.gz | docker load
gunzip -c qdrant-image.tar.gz | docker load
docker compose config
docker compose up -d --no-build --pull never
docker compose exec reqbot reqbot status
```

Explicitly disabling builds and pulls prevents Compose from trying to fetch
images or rebuild source. Confirm Ollama/Qdrant connectivity, then ingest a new
representative PDF, search, and trace **with external network access disabled**.
If a component requests a missing asset, prepare it on staging and repeat the
qualification. Test again after changing package versions, models, or enabled
extras; a warm cache for one configuration does not qualify every configuration.

## Network access

`reqbot serve` binds to `127.0.0.1:8000` by default. Compose starts the process
on all container interfaces but publishes its port only on host loopback.
The API currently has no application authentication. If exposing it beyond
loopback, provide access control, TLS, and network restrictions in your deployment.
`POST /api/config` additionally checks the direct client's loopback address;
browser access through a container bridge may fail that check.

For problems after installation, see the [operations runbook](OPERATIONS.md).
