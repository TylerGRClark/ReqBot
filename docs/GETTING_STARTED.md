# Getting started

[Documentation index](README.md) · [Deployment details](DEPLOYMENT.md) · [Configuration](CONFIGURATION.md)

This guide takes you from nothing to searching your first PDF. It assumes
you have never used ReqBot, Ollama, or Qdrant. Follow it top to bottom; each
step ends with a check so you know it worked before moving on.

## How the pieces fit

ReqBot needs three programs running. They are separate, and each can run on a
different machine:

| Part | What it does | Who installs it |
|---|---|---|
| **ReqBot** | Reads PDFs, finds the requirements in them, and gives you search, a web page, and exports. | This guide. |
| **Ollama** | Runs the AI models on your own hardware. ReqBot asks it to read your PDFs and to understand your searches. | You (step 1). |
| **Qdrant** | A database that stores the search index. | Docker setup: included. Python setup: one command (step 2). |

Your documents stay on your machines unless you turn on the optional remote
answer-writing feature or connect an outside AI assistant. ReqBot does not
install or start Ollama or Qdrant for you; it only connects to them.

A few words you will see:

| Word | Meaning |
|---|---|
| **Ingest** | Process a PDF: read it, extract its requirements, check them, and index them. |
| **Chunk** | A section-sized piece of a document. The AI model reads one chunk at a time. |
| **Requirement** | A statement from the document that obliges, forbids, or recommends something. |
| **Requirement ID** | The `REQ-...` code ReqBot gives each requirement. You use it to trace one. |
| **Source quote** | The exact text of the requirement, copied from the PDF. |
| **Index** | The searchable copy of your requirements kept in Qdrant. It can always be rebuilt. |

## What you need

- ReqBot is built and tested on Linux. The Docker path should also work with
  Docker Desktop on macOS or Windows, but the project does not test those.
- A computer that can run an 8-billion-parameter AI model. The extraction
  model used by default is about 4.6 GB on disk, and Ollama needs roughly that
  much free memory (GPU memory if you have a GPU, otherwise ordinary RAM).
  A model server with a GPU is much faster than one without; we have not
  measured how much slower a CPU-only setup is.
- About 5 GB of free disk space for ReqBot itself (a measured Python install
  of ReqBot and its dependencies was 4.1 GB), plus the models, plus about
  0.5 GB of document-reading models that ReqBot downloads the first time you
  ingest a PDF.
- An internet connection for the first run. See
  [Deployment](DEPLOYMENT.md#air-gapped-deployment) for fully offline setups.
- **Either** Docker with Docker Compose (recommended: nothing else to install),
  **or** Python 3.12 or newer.
- One PDF to try, ideally one whose text you can select with your mouse and
  that is short (10 to 20 pages). Image-only scans depend on character
  recognition and are not a good first test.

## Step 1: Install Ollama and download the models

(Planning to run Ollama inside Docker Compose? Skip this step; Path A below
covers it.)

Install Ollama from <https://ollama.com/download>, then download the two models
ReqBot needs:

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b-instruct-q4_K_M
ollama list
```

**Check:** `ollama list` shows both names. The downloads are large (the second
is about 4.6 GB), so this step can take a while.

You can skip a third, optional model for now. `qwen2.5:14b` (about 8.4 GB)
writes summary answers; search, trace, compare, and checklists work without it.

## Step 2: Install ReqBot

Pick one path.

### Path A: Docker (recommended)

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
cp docker-compose.example.yml docker-compose.yml
```

Open `docker-compose.yml` in a text editor. Under the `reqbot` service's
`environment:` section, add a line that skips the optional summary-answer model
for now, and decide where Ollama is:

```yaml
    environment:
      REQBOT_QDRANT_URL: "http://qdrant:6333"
      REQBOT_OLLAMA_URL: "http://host.docker.internal:11434"
      REQBOT_SYNTHESIS_BACKEND: "none"
```

The default `REQBOT_OLLAMA_URL` above means "Ollama running on this same
computer, outside Docker". Choose one setup:

- **Ollama installed on this computer (step 1 as written).** On Docker Desktop
  (macOS or Windows) the default usually works as is. On **Linux**, Ollama
  listens only on loopback by default, and a container cannot reach that. Set
  `OLLAMA_HOST=0.0.0.0:11434` for the Ollama service and restart it (Ollama's
  documentation describes this for systemd). Ollama has no login, so keep that
  port behind a firewall.
- **Ollama inside Docker Compose** (no host setup, and not exposed to your
  network). Skip step 1's `ollama pull` commands for now. In
  `docker-compose.yml`, remove the leading `# ` from the commented-out
  `ollama:` service and from `# ollama-storage:` under `volumes:`, and change
  the URL to `"http://ollama:11434"`:

  ```yaml
      REQBOT_OLLAMA_URL: "http://ollama:11434"
  ```

  Then start Ollama alone and download the models into it:

  ```bash
  docker compose up -d ollama
  docker compose exec ollama ollama pull nomic-embed-text
  docker compose exec ollama ollama pull llama3.1:8b-instruct-q4_K_M
  ```

  Without a GPU passed through to the container, this runs on CPU and is slower;
  the example file's comments explain the GPU option.

Then start everything. The first build downloads and installs several GB and
takes several minutes:

```bash
docker compose up -d --build
docker compose exec reqbot reqbot status
```

**Check:** the status output says `Status: Running` under both Ollama and
Qdrant. If either says `NOT REACHABLE`, see [If something goes wrong](#if-something-goes-wrong).

The Docker setup is configured by the settings in `docker-compose.yml`, so you
do not run `reqbot init`. Skip ahead to [Step 4](#step-4-ingest-your-first-pdf).

### Path B: Python

This path installs ReqBot on your computer directly. It needs Python 3.12 or
newer, Git, and Qdrant running somewhere.

```bash
python3 --version
```

If that prints a version older than 3.12 (Ubuntu 22.04 and Debian 12 ship older
ones), use Path A instead or install a newer Python first.

Start Qdrant (this uses Docker; see Qdrant's own
[installation guide](https://qdrant.tech/documentation/guides/installation/)
if you cannot use Docker):

```bash
docker volume create reqbot-qdrant-storage
docker run -d --name reqbot-qdrant \
  -p 127.0.0.1:6333:6333 \
  -v reqbot-qdrant-storage:/qdrant/storage \
  qdrant/qdrant:v1.17.1
```

Install ReqBot. Building the web page needs Node.js 20.19+ or 22.12+ (later
even-numbered releases also work; odd-numbered ones are rejected). Skip the
`build-frontend.sh` command if you only want the command line:

```bash
git clone https://github.com/TylerGRClark/ReqBot.git
cd ReqBot
bash build/build-frontend.sh
pip3 install --break-system-packages .
reqbot --version
```

The project's own convention is system Python without a virtual environment,
which is why the flag above is needed on Debian and Ubuntu. If you would rather
not touch your system Python, a virtual environment works too (the same install
in a fresh environment was tested): run
`python3 -m venv ~/reqbot-venv && . ~/reqbot-venv/bin/activate` first and drop
`--break-system-packages` from the command.

**Check:** `reqbot --version` prints a version number. If your shell says
`reqbot: command not found`, pip installed the program into a folder that is
not on your `PATH` (usually `~/.local/bin`; pip prints a warning naming it).
Add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to `~/.bashrc` to keep it in new terminals.

## Step 3: Configure ReqBot (Python path only)

```bash
reqbot init
```

The wizard asks about a dozen questions. Each shows its default in square
brackets; pressing Enter accepts it. For a first run, press Enter for
everything **except** the last question:

| Question | What to enter |
|---|---|
| Qdrant URL | Enter (`http://localhost:6333`) |
| Ollama URL | Enter (`http://localhost:11434`), or the address of the machine running Ollama |
| Embedding model, default model, extraction/enrichment/rewrite, synthesis model | Enter for each |
| Default top-k, minimum relevance score, processed documents dir | Enter for each |
| `Synthesis:` menu | Type `3` (None: retrieval only) |

The wizard tests each connection as you go and prints a status report at the
end. **Check:** the last line is `=== ReqBot is ready ===`. If a connection test
fails, answer `n` to keep-this-URL, fix the address, and try again.

If you pick `3` now you can switch on written answers later by pulling
`qwen2.5:14b` and changing the synthesis setting; see
[Configuration](CONFIGURATION.md#local-remote-and-retrieval-only-operation).

## Step 4: Ingest your first PDF

Ingestion reads the PDF, extracts requirements with the AI model, checks them
against the source text, and indexes them for search. It is done from the
command line; the web page cannot ingest.

**Python path:**

```bash
reqbot ingest /path/to/your-document.pdf
```

**Docker path** (copy the file into the container, then ingest it):

```bash
docker compose cp /path/to/your-document.pdf reqbot:/tmp/your-document.pdf
docker compose exec reqbot reqbot ingest /tmp/your-document.pdf
```

What to expect:

- The first time, ReqBot downloads about 0.5 GB of document-reading models, so
  the first minute can be slow before any chunk lines appear.
- Then you will see lines such as `Chunk 9/25 (id=8): 1 requirements extracted`.
  The AI model reads the document in chunks, one at a time, so the run time
  grows with document length.
- One measured run: a 15-page PDF (25 chunks, 65 requirements) finished in
  about 3 minutes, with Ollama on a separate workstation and the PDF parsing
  done on CPU. That is one data point, not a benchmark. A 48-page document
  produced 129 chunks, so expect longer for longer documents. Run a short
  document first.
- It ends with `Pipeline complete` and then indexes the result into Qdrant.

**Check:**

```bash
reqbot docs
```

(Docker: `docker compose exec reqbot reqbot docs`.) Your PDF's name appears in
the list with a requirement count. This confirms the files were written; the
next step confirms search.

To ingest a whole folder of PDFs, use `reqbot batch /path/to/folder` (Docker:
copy the folder in first with `docker compose cp ./folder reqbot:/tmp/folder`).

## Step 5: Search

```bash
reqbot ask "What are the access control requirements?"
```

You get a ranked list like this (shortened):

```text
[1] Score: 0.5909 | REQ-a04b71eaf938
    Source: NIST.SP.800-125.pdf, p.15
    Existing authentication and authorization mechanisms is leveraged to
    restrict user access to the file and object resources according to the
    organization policy.
```

Each result shows the **requirement ID**, the **PDF and page** it came from, and
the **quote** taken from the document. The score ranks results against each
other; it is not a probability that the result is right. Ask about something
you know your PDF says, and compare the quote and page with the original.

Now follow a result back to its source, using an ID from your own results:

```bash
reqbot trace REQ-a04b71eaf938 --context
```

`trace` prints where the requirement came from (document, page, section) and,
with `--context`, the surrounding text from the PDF. This is how you check that
a requirement really says what ReqBot says it does.

## Step 6: Open the web page

```bash
reqbot serve
```

(Docker: it is already running.) Open <http://127.0.0.1:8000> in a browser.
The left-hand menu has:

| Page | Use it to |
|---|---|
| Search | Search your library and open a result's source. |
| Compare | Compare one control or topic across two documents. |
| Evidence | Gather requirements about a topic into an evidence pack. |
| Checklists | Build and download an audit checklist (CSV, JSON, Markdown, or Excel) for one document. |
| Corpus | See each ingested document and its requirements. |
| System | Check that Ollama and Qdrant are healthy. |
| Settings | Change service addresses and models. With Docker, edit `docker-compose.yml` instead; saving here may be refused for connections that come through the container. |

With synthesis set to None, the written-answer features (such as the
Evidence summary) stay empty; search, trace, compare, the corpus view, and
checklists work as normal.

The page works from the same computer by default. To reach it from another
machine, use an SSH tunnel (`ssh -L 8000:127.0.0.1:8000 you@server`), because
ReqBot has no login and should not be exposed to a network as is.

To get a checklist from the command line, use the document name shown by
`reqbot docs`:

```bash
reqbot checklist --doc your-document --format csv > checklist.csv
```

(Docker: `docker compose exec -T reqbot reqbot checklist --doc your-document --format csv > checklist.csv`.)

## Using the results responsibly

ReqBot's output is extracted by an AI model and then checked by automatic
rules. The quote and page let you verify each requirement, and you should.
It can miss requirements, split one requirement into pieces, or keep a
sentence that is not really a requirement. Two documents citing the same
control number does not mean they require the same thing. Evidence packs and
checklists are starting points for a human review, not proof that your
organization complies.

## If something goes wrong

| What you see | What to do |
|---|---|
| `reqbot: command not found` | Add pip's script folder to `PATH`; see Step 2, Path B. |
| `requires a different Python` during `pip install` | Your Python is older than 3.12. Use Path A or install a newer Python. |
| `Status: NOT REACHABLE` for Ollama or Qdrant | The program is not running, or the address is wrong. Start it, then run `reqbot status` again. In Docker, `localhost` means the container itself; use the Compose service name or `host.docker.internal`. |
| Docker: Ollama is running but ReqBot cannot reach it (Linux) | Ollama is listening on loopback only. See the Ollama options in Path A, step 2. |
| `Failed to connect to Ollama` | Same as above: Ollama is not reachable at the configured address. |
| Model not found or `not available on the configured Ollama server` | Pull the model on the machine running Ollama, then check `ollama list`. |
| `reqbot docs` says `Processed documents directory not found` (or the Corpus page shows the same error) | The documents folder does not exist yet. `reqbot init` creates it, and so does the first ingest. |
| `ask` returns no results | Confirm `reqbot docs` lists a document, and try a topic that the PDF covers. A search for words the document never uses returns little or nothing. |
| Stale or duplicate-looking results after ingesting the same PDF again | Run `reqbot reindex`. It rebuilds the search index from each document's latest run. |
| The web page says not found, but `/api-docs` works | The web page was not built. Build it (`bash build/build-frontend.sh`) **before** `pip3 install`, then install again. |
| Ingest stops partway | Run the same command again; it starts a new run folder. For a long document, the [operations guide](OPERATIONS.md#resume-an-interrupted-run) explains how to resume instead of restarting. |
| The first ingest or first search hangs with no network | ReqBot downloads small models once from Hugging Face. Connect once to cache them, or see [Deployment](DEPLOYMENT.md#air-gapped-deployment). |

## Start, stop, and where things live

- **Docker:** `docker compose stop` pauses everything and `docker compose up -d`
  starts it again. Avoid `docker compose down -v`; the `-v` deletes the search
  index (it can be rebuilt with `reqbot reindex`, but that takes time).
- **Python:** `reqbot serve` runs until you press Ctrl+C. Qdrant runs in its own
  container (`docker stop reqbot-qdrant`, `docker start reqbot-qdrant`); after
  a reboot, start it again with `docker start reqbot-qdrant`.
- **Your data:** each ingested document is a folder under
  `~/documents/processed` (Docker: `./documents/processed` next to
  `docker-compose.yml`). These files are the source of truth; the search index
  can always be rebuilt from them. Keep your original PDFs too.

## Where to go next

- [CLI reference](CLI.md): every command and option.
- [Configuration](CONFIGURATION.md): change models, addresses, and answer writing.
- [Connecting AI tools](AI_TOOLS.md): let an AI assistant search your library.
- [Operations](OPERATIONS.md): backups, rebuilding the index, resuming runs.
- [Deployment](DEPLOYMENT.md): offline installs and other ways to run ReqBot.
