# Deployment guide

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Operations](OPERATIONS.md)

This guide is the reference for every install variant. If you are setting up
ReqBot for the first time, follow [Getting started](GETTING_STARTED.md) instead,
which walks one path end to end.

Choose Docker for a packaged CLI/API/GUI, or a source install for development
and direct pipeline access. Both use the same Python package. The commands below
use a POSIX shell; replace example PDF paths and service URLs with your own.

## Prerequisites and models

ReqBot needs reachable Qdrant and Ollama services. The example Compose file
starts Qdrant; it points at an existing Ollama instance. A source install does
not start either service.

Install Ollama from <https://ollama.com/download> (or run it as a container).
On the Ollama host, pull the default embedding and extraction/enrichment/rewrite
models:

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
  mapping. On Linux, a container reaches the host through the Docker bridge, and
  Ollama listens only on loopback by default, so the connection is refused.
  Either set `OLLAMA_HOST=0.0.0.0:11434` for the host's Ollama service (it has
  no authentication, so restrict the port with a firewall) or use the Compose
  `ollama` service below. Docker Desktop on macOS and Windows normally reaches
  host services through `host.docker.internal` without that change.
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

The Docker build installs the Python package, the system libraries Docling needs,
and builds the frontend inside a Node build stage. The host does not need Python
or Node. CI builds this image and parses a test PDF inside it, though it does not
run a full ingest, because there is no Ollama in CI. The default GUI is at
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

Docker is the packaged way to run ReqBot, and CI exercises the image. A source
install is for development, direct pipeline access, or running the CLI directly
on a host. It needs Python 3.12 or newer and Git. Ubuntu 22.04 (Python 3.10) and
Debian 12 (Python 3.11) are too old, and `pip` stops with
`requires a different Python`; use Docker there or install a newer Python first.

**System libraries.** On a minimal Debian or Ubuntu system (server images,
containers, WSL), install the libraries that Docling's OCR dependency (OpenCV)
loads when it first converts a PDF. The Docker image already includes them.

```bash
sudo apt install libgl1 libglib2.0-0
```

Without them, the first `reqbot ingest` fails at PDF reading (Step A) with
`libGL.so.1: cannot open shared object file` (or `libxcb.so.1`). Desktop
systems usually have these already.

Use a virtual environment so ReqBot does not modify your system Python (recent
Debian and Ubuntu refuse a plain `pip install` there):

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
python3 -m venv ~/reqbot-venv
. ~/reqbot-venv/bin/activate
python --version
```

The `reqbot` command exists only while the environment is active. In a new
terminal, run `. ~/reqbot-venv/bin/activate` again, or call
`~/reqbot-venv/bin/reqbot` directly. A full install, including the dependencies
and the built web interface, used about 4 GB of disk in a clean-environment test.

If you want the GUI in the installed package, build it **before** installing:

```bash
# Requires Node 20.19+, 22.12+, or a newer supported even-numbered release, and npm.
bash build/build-frontend.sh
pip install .
```

For CLI/API-only use, omit the frontend build and run `pip install .`. A missing
frontend does not remove the HTTP API. Developers can install with
`pip install -e ".[dev]"`; the editable install reads Python source and generated
frontend files from the checkout. Contributors: the project's own development
workflow uses system Python instead of a virtual environment; see
[CONTRIBUTING.md](../CONTRIBUTING.md).

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

Run these from the repository root, in the same activated environment:

| Install command | Adds |
|---|---|
| `pip install ".[remote]"` | Remote synthesis provider SDKs. |
| `pip install ".[mcp]"` | MCP server support: stdio for local AI clients and the HTTP door for other machines. The Docker image includes it. |
| `pip install ".[grounding-check]"` | MiniCheck, used only by the evaluation scripts `eval/entailment_spike.py` and `eval/threshold_sweep.py` (the pipeline's description check that used it was removed). |
| `pip install ".[rerank]"` | FlashRank reranker for programmatic/evaluation use. The supported reranker is the optional `reranker` Compose service below. |
| `pip install ".[dev]"` | Test and lint tools. |

Docling is a base dependency and the only current PDF parsing path. There is no
legacy parsing fallback or `--layout-mode` switch.

The `grounding-check` extra installs MiniCheck from the pinned Git source in
`pyproject.toml`; an unrelated PyPI package has the same name. Also prepare:

```bash
python3 -c "import nltk; nltk.download('punkt_tab')"
```

Model weights can require additional first-use downloads.

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

Open `http://127.0.0.1:8000`. Search, trace, comparison, evidence, library,
checklists, system status, and settings are available through the GUI.
Without a frontend build, use `/api-docs` and the CLI.

## First-run downloads and caches

Besides the Ollama models, ReqBot downloads some model files from Hugging Face
the first time it needs them, so a connected first run is the easiest way to
warm the caches:

| When | What is downloaded | Where it is cached |
|---|---|---|
| First `ingest` | Docling layout and table models (about 0.5 GB measured: `docling-project/docling-layout-heron` and `docling-project/docling-models`). | `~/.cache/huggingface` |
| First search or index | A small keyword-ranking model (`Qdrant/bm25`). | `<system temp dir>/fastembed_cache` unless `FASTEMBED_CACHE_PATH` is set. |
| First use of the `grounding-check` extra | MiniCheck weights (about 5.9 GB measured). | `~/.cache/huggingface` |

The keyword model's default location is a temporary directory, which a reboot
can clear; set `FASTEMBED_CACHE_PATH` to a persistent path if that matters. In a
container, none of these locations is mounted by the example Compose file, so
replacing the container discards them.

## Air-gapped deployment

An exported base image is only one part of an offline installation. Prepare
Ollama models, ReqBot's parsing/tokenizer/sparse-model caches, optional model
assets, configuration, and artifacts before disconnecting. The stock image
build does not exercise ingestion or retrieval to populate all those caches.

Even with warm caches, an ingest run contacts huggingface.co to check Docling's
model revision (a `GET https://huggingface.co/...` line appears in the log).
Once the caches are warm, set `HF_HUB_OFFLINE=1` in the environment of the
ReqBot process on the offline host so those lookups are not attempted. With
warm caches and that variable set, document parsing, chunking, one extraction
call, and a search all completed, and the ingest log contained no
huggingface.co requests. This was a same-machine check, not a
disconnected-network test, so keep the qualification step below.

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

### Serving the MCP door

`reqbot mcp --http` (see [Connecting AI tools](AI_TOOLS.md#serve-the-library-to-other-machines))
is a separate process from `reqbot serve`, on its own port (8765), with its own
access codes. It speaks plain HTTP, so put a proxy that terminates TLS in front of
it as soon as it leaves a trusted network, and let your gateway do any company
sign-in. Keep the door's own listener on loopback and publish only the proxy:

```bash
reqbot mcp-code add anna-assistant
reqbot mcp --http --host 127.0.0.1 --port 8765 --allow-host reqbot.example.org
```

```caddyfile
reqbot.example.org {
    reverse_proxy 127.0.0.1:8765 {
        header_up Host {host}
    }
}
```

`--allow-host` must name the host name callers type, because the proxy forwards it.
In a container, run the same command in a second container (or `docker exec`)
from the same image, set `REQBOT_MCP_CODES`, and publish its port only to the
proxy. Searches use the model machine, so a limit on simultaneous calls applies
(`REQBOT_MCP_MAX_CONCURRENT`). If the AI tool is a hosted product that calls in
from the internet, the address must be reachable from there, which is a decision
for your network team; ReqBot's codes are not a substitute for their gateway.

For problems after installation, see the [operations runbook](OPERATIONS.md).

### Optional re-ranker service

The `reranker` service in `docker-compose.example.yml` runs a cross-encoder (`BAAI/bge-reranker-v2-m3`) that re-orders the top 50 search results. Start it with `docker compose --profile rerank up -d`, then set `REQBOT_RERANK_URL` (or `rerank_url` in `config.json`) to its address, for example `http://reranker:8732`. Leave it unset and search behaves exactly as before. If the service is down, search returns the normal order with a warning. It needs a GPU to be fast (about 0.3 seconds per search on an RTX 3070); the model downloads on first start. It unloads itself from GPU memory after 15 minutes of no searches (`RERANK_IDLE_SECONDS`; set to `0` to keep it always loaded) and reloads in about 5 seconds on the next search -- the API server also pings it to load at its own startup, so a cold reload usually happens before a real search needs it, not during one. The service has no authentication, so keep it on a private network.
