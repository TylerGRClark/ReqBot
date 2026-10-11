# Web UI parity plan: running ReqBot's long jobs from the browser (proposal; nothing in it is built)

*Written 2026-10-11 from a discussion with the owner, who asked for ingesting PDFs from the web page (drag and drop, or a folder) with the whole pipeline behind it, and said that most if not all CLI functionality should be in the UI. This is a plan for review: no code, no data and no behavior changes with this PR. Each stage in section 6 becomes its own PR, with its tests and pass rules written down before building.*

## 1. Where things stand

The web page reads. Every command that writes, or that runs for more than a few seconds, is CLI-only:

| CLI command | In the web page today | Plan |
|---|---|---|
| `ask`, `trace`, `compare`, `evidence` | Search, Trace, Compare, Evidence | done |
| `docs`, `status`, `checklist` (with export) | Corpus, System, Checklists | done |
| `init` (guided setup) | Settings edits the config (`POST /api/config`, same machine only) | first-run wizard later (stage 5) |
| `ingest`, `batch` | **none** ("Ingest documents via the CLI") | **stages 1 to 3** |
| `questions` (draft audit questions) | none; the checklist shows them only if the CLI wrote them | **stage 4** |
| `reindex` (rebuild the search library) | none | **stage 4** |
| `kinds` | none | when something reads the kinds (nothing does yet) |
| `index`, `index-context` | none | not planned: ingest and rebuild cover them |
| `serve`, `mcp` | not web features | not applicable |
| *(no command)* remove a document | none, in the CLI either | stage 5 |

The previous UI direction (`docs/ReqBot Consolidated UI Direction.dc.html`, "Ingest and job history") drew a drop zone, a profile picker, a job banner and a jobs list, and parked them because the service layer had no job abstraction. This plan builds that abstraction first.

## 2. The job service (stage 1)

Everything long-running becomes a **job**: ingest of one PDF, a batch (several ingest jobs), draft questions for one document, rebuild of the library. One engine runs them all, so there is one place that knows how to run, show, cancel and recover work, and the CLI, the web page and (later) MCP read the same thing.

- **It runs the existing CLI command as a child process** (the same Python, `reqbot ingest ...`, `reqbot questions ...`, `reqbot reindex`). The web server never imports the pipeline. Reasons: the CLI stays the one implementation ("the CLI is the source of truth"); Docling's memory and a crash stay out of the server; cancelling is ending a process.
- **One job at a time, in a queue.** There is one Ollama machine and Docling is heavy; two ingests at once would slow both and risk memory. The queue is first in, first out and is saved to disk.
- **State survives a restart.** Each job is a small JSON file plus its log under `<processed_dir>/.jobs/` (inside the folder the Docker example already mounts, so existing deployments keep it; `rglob("*_requirements_normalized.jsonl")` does not see it). States: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`. At server start a job left `running` becomes `interrupted`; the next queued job starts by itself. An interrupted or failed ingest can be retried. The job creates its run folder itself and passes it to `reqbot ingest --output-dir`, so the retry runs in the same folder, where requirement finding reuses the answers it already has (`docs/OPERATIONS.md`, "Resume an interrupted run"): finished chunks are not paid for twice, and reading and chunking the PDF are repeated (a few minutes).
- **Progress is machine-readable, not scraped from log prose.** An additive, off-by-default option on the commands (`--progress-json`) prints lines such as `{"step": "finding", "done": 120, "total": 427}`. Steps for ingest: reading, chunking, finding (chunk i of N), checking, totals, indexing, indexing context. For questions: row i of N. For reindex: document i of N. The job file keeps the last progress line and a log tail.
- **Cancel** ends the child process. The run folder is kept (it is what a retry resumes from); nothing is deleted.
- **Not included:** scheduling, parallel jobs, priorities, notifications.

Also in stage 1: `reqbot jobs` (list, show, cancel) and read-only API routes (`GET /api/jobs`, `GET /api/jobs/{id}`), so the engine can be exercised and read before anything can start a job from the browser.

## 3. Getting PDFs in (stage 2)

- **Drag and drop, files or a whole folder.** A dropped folder is read by the browser, which sends the PDFs inside it (subfolders included). Each file is one upload request with the raw PDF as the body, so no multipart library is needed (`python-multipart` is installed here but not declared in `pyproject.toml`; this plan adds no dependency). Upload progress comes from the browser's own request object.
- **Checks on every upload:** the name must end in `.pdf` and is reduced to a plain file name (no path parts); the first bytes must be `%PDF-`; the size is capped (default 100 MB, a config value); the same file twice in the queue is refused.
- **Stored under** `<processed_dir>/.uploads/<job id>/<original file name>.pdf`, so the PDF's stem, which is the document key everywhere in ReqBot, is what the person uploaded. The uploaded copy is never edited.
- **"Point it at a folder" on the server** means one configured **inbox folder** (config key, default `<processed_dir>/.inbox`), not an arbitrary path: a box that accepts any path on the server would let anyone who can reach the page make the server read any PDF it can see. "Import from the inbox" creates one ingest job per PDF there and skips a file whose content was already ingested. A network share or a copied file can feed the inbox.
- **A document already in the library** (same file name): the default is **replace**. The new run becomes the document's current one, and the indexing step first removes that document's earlier points (matched by `source_pdf`) so a changed rule cannot leave a stale row behind (backlog item 42). Older run folders stay on disk. This is a change to what the indexing step does and is confirmed again at build time (stop-and-ask).
- **Profile picker:** hidden until a second domain profile exists (domain-profile work is paused).
- **Draft questions after ingest:** an "also write draft audit questions" tick box, off by default, queues a questions job for the document when the ingest finishes (stage 4).

## 4. Who may start a job (the security question)

Today the web page cannot change anything. The API is documented read-only, CORS allows GET and POST only, and the one write route (`POST /api/config`) only accepts the machine ReqBot runs on, as a stopgap because ReqBot has no login (authentication and multi-user hosting are on the backburner, `docs/TODO_future_improvements.txt`). Starting jobs changes that: anyone who could reach the page could start 50-minute jobs on the owner's Ollama machine and add files to the library.

Decided with the owner on 2026-10-11 (D1): **one rule for every case, an access code.** The owner opens the page from the same machine on some days and from another computer or a virtual machine on others, and expects the model machine and the Qdrant machine to be elsewhere, so the rule must not depend on where the browser is.

1. **Jobs can be started only when an access code is configured.** `reqbot token` creates a random code and saves it in the config; a container can set `REQBOT_ACCESS_TOKEN` instead. With no code configured the page stays read-only exactly as today and the job routes answer 403. There is no separate on/off switch: setting a code is the switch.
2. **The page asks for the code the first time something needs it and keeps it in that browser.** The code is never sent by any API route (so `GET /api/config` and Settings cannot reveal it), never logged, compared in constant time, and failed attempts are delayed.
3. **Same machine or another computer makes no difference.** "Same machine only", the rule `POST /api/config` has, is not used here: behind a container, a virtual machine or a proxy the server can see the gateway's or proxy's address instead of loopback, which would lock the owner out of their own page in exactly the setups they use.
4. **Always:** uploads are checked as in section 3; one job runs at a time; the log text is the pipeline's existing log (no document text beyond it); `reqbot serve` prints a notice when a code is set and the server listens on a non-loopback address; every started job records who asked (client address) and when.
5. **What this is not:** a multi-user login (authentication and multi-user hosting stay on the backburner). The code travels over plain HTTP on a trusted network; anything beyond that is the operator's reverse proxy with TLS, as the Docker example already says.

**Where the work runs.** A job runs on the machine ReqBot runs on and reaches the Ollama and Qdrant machines by the addresses in the config, exactly as `reqbot ingest` does, so those can be anywhere. PDF reading (Docling) runs on the ReqBot machine. A separate worker machine is not planned; a job is a saved command plus its progress lines, so nothing in this design prevents one later.

## 5. The web screens (stage 3, then stage 4)

- **Corpus:** a "+ Add documents" drop zone (files or a folder), an "Import from inbox" button, an inline banner for the running job ("afi17-203.pdf: finding requirements, chunk 120 of 427"), and a job history list with a state, start and end time, a log tail, and Cancel or Retry.
- **After a job succeeds** the document appears in the Corpus list and the banner links to its checklist.
- **Checklist screen and Corpus detail (stage 4):** "Write draft audit questions" with row progress; unchanged rows are reused (the existing hash rule), so running it again is cheap.
- **System (stage 4):** "Rebuild library" with the same all-or-nothing rule the CLI has (the live index is untouched until the new one is complete), and a note that searches are slower while a job runs.
- The page polls the job list every few seconds while a job is running; there is no new front-end dependency.
- A closed browser tab does not stop a job: the job belongs to the server.

## 6. Stages and what each must show

| Stage | Change | Must show |
|---|---|---|
| 0 | This plan | the owner's decisions D2 and D3 (D1 is decided) |
| 1 | Job engine, `--progress-json`, `reqbot jobs`, read-only job routes | with a stub command: success, failure, cancel, server restart (`running` becomes `interrupted`), queue order, one at a time, progress parsing; the real `reqbot ingest` unchanged when the option is absent (output byte-identical) |
| 2 | Upload and import routes, "start ingest" route, `reqbot token` and the access-code check, replace-on-reingest in indexing | refusals (not a PDF, wrong extension, too large, path parts in the name, no code configured, missing or wrong code); the code absent from every API response and log; a small PDF through the real pipeline from an upload: the run folder holds the same files a CLI run writes and `reqbot docs` lists it; a second upload of the same file leaves no stale point |
| 3 | Corpus drop zone, banner, job list | component tests (a dropped folder yields the PDFs inside it, progress renders, errors show); the owner drops a document and watches it finish |
| 4 | Draft-questions and rebuild jobs and their buttons | the sidecar equals what `reqbot questions` writes; an interrupted rebuild leaves the live index untouched |
| 5 | Remove a document (its run folders move to a trash folder, its points are deleted, with a confirmation), first-run wizard | nothing deleted without a confirmation; the document leaves search and the Corpus list |

No stage adds a model call (jobs run commands that already exist), changes extraction, changes the record schema, or adds a dependency. The CLI's behavior is unchanged throughout. Not planned: MCP tools that start jobs (an assistant starting GPU jobs unattended is its own decision).

## 7. Decisions for the owner

1. **D1, who may start jobs: decided 2026-10-11.** An access code for every case (section 4). Nothing more is needed from the owner on this.
2. **D2, a document already in the library (needed before stage 2).** Recommended: replace, as in section 3. The alternative is to keep both versions searchable, which makes the same paragraph appear twice in every search.
3. **D3, the inbox folder (needed before stage 2).** Default `<processed_dir>/.inbox`; say if another place suits your setup.

## 8. What this plan does not claim

It does not estimate how long a given document takes (the 164-page dress code took 49 minutes; an AFI-sized document takes minutes). It rests on a read of the code on 2026-10-11 and has not been built or tried against a browser. The progress option, the replace-on-reingest rule and the access rule are the three places where the design could change once built; each is tested in its own stage before the next depends on it.
