# Web UI parity plan: who sees what, and running long jobs from the browser (proposal; nothing in it is built)

*Status 2026-10-12: stage 3 (the job engine, section 5) is built and merged, and stage 4 (section 6) is built: the uploads, inbox, start-ingest, cancel and retry routes and the same-name rule, the Corpus screen with a drop zone for files or a folder, the access-code prompt, the progress banner and the job list (all merged), and replace-without-a-gap (`reqbot ingest --replace`, `pipeline/index_replace.py`). Stage 6, the jobs behind "write draft audit questions" and "rebuild library" (`reqbot jobs add questions|reindex`, `POST /api/jobs/questions|reindex`, `--progress-json` on both commands), and their buttons (the checklist screen and System) are built. Removing a document is built too: `reqbot remove` and `POST /api/documents/remove` (run folders to a trash folder, rows out of search, only with the exact key repeated) and the "Remove this document…" button on the document page with a typed-name confirmation. The first-run setup wizard is built (section 9a): shared checks with `reqbot init --check`, the five-step page at `/setup`, and a prompt until a configuration is saved. Only the access-code role source exists (plus trusted-network mode). Written 2026-10-11 from a discussion with the owner, then revised the same day after a review against the code and after the owner narrowed the direction (section 1). This is a plan for review: no code, no data and no behavior changes with this PR. Each stage in section 9 becomes its own PR, with its tests and pass rules written down before building.*

## 1. Direction (the owner, 2026-10-11)

- **Two audiences.** End users need Ask and checklists (with Excel export), and nothing to install. The admin chooses and adds the documents, and runs ingest, draft questions, rebuild and settings. End-user doors only read; admin doors change things.
- **Only admins add documents**, by drag and drop in the admin screens (and the CLI). There is no end-user upload route, so the untrusted-upload design (quarantine, per-user quotas, same-name collisions between users, transfer from many devices) is not part of this plan. Fetching AFIs and DoDIs automatically from the official sites is a later, separate piece: a quick search found no documented API or feed for the Air Force e-Publishing site or the DoD issuances site, so it would be page polling, and where it runs (our side with signed content updates, or the customer's) is open.
- **End users get:** a web page (reader mode: Library, Checklists with export, and Search that returns the documents' own passages with citations and no model-written answer), and **Ask as a network MCP service** that their own AI tool connects to.
- **Sign-in is agnostic.** Customers will have Okta, Entra ID, Keycloak, a CAC-fronted proxy and so on. ReqBot gets no account system of its own (section 3).
- **Deployment is modular.** The web server, the pipeline runner, the model machine, Qdrant and the shared files may all be one machine (today's development setup) or be split across machines (section 7).

## 2. Where things stand

The web page reads. Every command that writes, or runs for more than a few seconds, is CLI-only. MCP is stdio only: a subprocess the user's own AI client starts on the user's own machine (`docs/AI_TOOLS.md`).

| CLI command | In the web page today | Plan |
|---|---|---|
| `ask`, `trace`, `compare`, `evidence` | Search, Trace, Compare, Evidence | reader mode keeps Search; Trace, Compare and Evidence stay admin-only for now (section 10) |
| `docs`, `checklist` (with export) | Corpus, Checklists | reader mode: Library, Checklists |
| `status` | System | admin |
| `init` (guided setup) | Settings edits the config (`POST /api/config`, same machine only) | role rule (stage 1); first-run wizard built (section 9a) |
| `ingest`, `batch` | **none** ("Ingest documents via the CLI") | **stages 3 and 4**, admin |
| `questions` (draft audit questions) | Checklist screen: "Write draft audit questions" | built (stage 6) |
| `reindex` (rebuild the search library) | System: "Rebuild the library" | built (stage 6) |
| `mcp` | not a web feature; local only | **stage 2** (network service) |
| `kinds` | none | when something reads the kinds (nothing does yet) |
| `index`, `index-context` | none | not planned: ingest and rebuild cover them |
| `remove` (take a document out of the library) | Document page: "Remove this document…" with a typed-name confirmation | built (stage 6) |

## 3. Roles and sign-in (stage 1)

There are two roles. **Reader:** the library, checklists and their export, and Search without synthesis. **Admin:** everything, including jobs, uploads, System and Settings.

ReqBot has no accounts and no passwords. For each request it asks one question, "what role does this request have?", answered from one of these:

1. **A sign-in layer in front of it** (a reverse proxy such as oauth2-proxy, Authelia or Keycloak, or the customer's own gateway) that passes the identity on as trusted headers, with a configured mapping from a group or claim name to a role. The headers are trusted only from the configured proxy address; from anywhere else they are ignored, because otherwise anyone could forge them.
2. **A bearer token verified as OIDC/JWT** (issuer, audience and keys configured), used mainly by the network MCP door.
3. **The owner-level fallback: access codes** (`reqbot token` creates them; `REQBOT_ACCESS_TOKEN`-style variables set them for a container), one for readers and one for admins. This is the earlier decision D1, kept as a stopgap for a single owner, not the answer for an organization.

Rules:

- With no role source configured, nothing changes from today: the API reads, and admin routes answer 403. There is no separate on/off switch; configuring a role source is the switch.
- **Settings:** the "same machine only" rule is replaced by the admin role when a role source is configured, so the service addresses can be changed from the owner's own computer. Without a role source the old rule stays. Environment variables still win after a successful edit.
- **Readers cannot spend the model machine.** `POST /api/ask` has an optional `synthesize` flag (default false); for a reader it is refused, as is any remote-provider synthesis.
- Codes and tokens are never returned by any route (`GET /api/config` and Settings cannot reveal them), never logged, compared in constant time, and failed attempts are delayed. Every started job records who asked and when.
- **TLS is a requirement beyond a trusted network.** Codes and tokens travel in clear text on plain HTTP. `reqbot serve` prints a notice when a role source is configured and the server listens on a non-loopback address; the Docker example already binds to loopback only.
- **Not planned here:** built-in accounts, per-document permissions (everyone sees every document), and per-user private workspaces.

## 4. Network MCP (stage 2)

Today a user's machine would need a full ReqBot install, direct reach to Qdrant and the model machine, and a copy of the processed files. The installed MCP SDK already has network transports and an auth module, so this is wiring:

- A transport switch on the assistant command (streamable HTTP; SSE if a client needs it), with identity as in section 3.
- The tools stay read-only: status, list documents, search, trace, compare, evidence mapping and checklist generation. The default is retrieval only: server-side synthesis is off for readers, because their own AI tool writes the answer.
- A floor on the `mcp` extra in `pyproject.toml` (it is `>=1.0.0` today, which predates the network transports), and an image variant that includes the extra (the Docker image installs the base package only).
- **To check with the customer first:** whether the AI tools they are allowed to use can connect to a remote MCP server.

## 5. The job service (stage 3)

Everything long-running becomes a **job**: ingest of one PDF, a batch, draft questions for one document, a rebuild of the library. One engine runs them all, so there is one place that knows how to run, show, cancel and recover work.

- **It runs the existing CLI command as a child process** (`reqbot ingest ...`, `reqbot questions ...`, `reqbot reindex`). The web server never imports the pipeline. The CLI stays the one implementation; Docling's memory and a crash stay out of the server; cancelling is ending a process.
- **One job at a time, in a queue.** There is one model machine and Docling is heavy. The queue is first in, first out and is saved to disk.
- **State survives a restart.** Each job is a small JSON file plus its log under `<processed_dir>/.jobs/` (`rglob("*_requirements_normalized.jsonl")` does not see it). States: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`. An interrupted or failed ingest can be retried in the same run folder (the job creates it and passes it to `reqbot ingest --output-dir`), where requirement finding reuses the answers it already has (`docs/OPERATIONS.md`, "Resume an interrupted run").
- **A child that outlives its server is dealt with before the queue moves.** Each job starts in its own process group; the job file records the group and a start-time stamp, so a reused number is not mistaken for it. At server start, for every job left `running`, a still-live group is stopped (a graceful stop, then a forced one after a grace period) and waited for; only then is the job marked `interrupted` and the next one started. Reattaching to a live child is not planned. Acceptance: kill the server with a job running, restart it, and never see two pipelines at once.
- **Claim and heartbeat, so a runner can be another machine (stage 5).** A runner claims a job by writing a lease (runner, attempt number, expiry) into the job file and renews it while its child runs. A runner that cannot renew stops its own child; an expired lease makes the job `interrupted`, and the attempt number keeps a stale runner from writing over a newer one. The first runner is the local one.
- **Pre-flight before the work.** At job start the runner checks that the model machine and Qdrant are reachable (and that the model is present), and fails at once naming the one that is not. Today ingest checks the model machine only inside requirement finding (after PDF reading and chunking), and Qdrant is not touched until the last step, so a wrong address fails a long run at the end.
- **Progress is machine-readable, not scraped from log prose.** An additive, off-by-default option (`--progress-json`) prints lines such as `{"step": "finding", "done": 120, "total": 427}`. The job file keeps the last progress line and a log tail.
- **Cancel** ends the child process. The run folder is kept (it is what a retry resumes from).
- **Not included:** scheduling, parallel jobs, priorities, notifications.

Also in this stage: `reqbot jobs` (list, show, cancel) and read-only job routes for the admin.

## 6. Getting PDFs in (admin only; stage 4)

- **Drag and drop, files or a whole folder.** The browser sends each PDF as one request with the raw PDF as the body, so no multipart library is needed (`python-multipart` is installed here but not declared in `pyproject.toml`; this plan adds no dependency).
- **Checks on every upload:** the name ends in `.pdf` and is reduced to a plain file name; the first bytes are `%PDF-`; a size cap (default 100 MB) and a page cap. The server **writes to disk as the file arrives and enforces the cap while it streams**, because a chunked upload need not carry a length. Proxies in front commonly cap request bodies and time out; the deployment page says so.
- **Stored under** `<processed_dir>/.uploads/<job id>/<original file name>.pdf`, so the PDF's stem, which is the document key everywhere in ReqBot, is what the admin uploaded.
- **"Point it at a folder" on the server** means one configured **inbox folder** (default `<processed_dir>/.inbox`), not an arbitrary path. It is optional: drag and drop is the main way in, and the inbox suits PDFs that are already on the server or copied over a network share. "Import from the inbox" creates one ingest job per PDF and skips a file whose content was already ingested. This is also where an automatic fetcher would later drop files.
- **The same file name:** compare content. The same content is skipped. Different content asks the admin, **replace** (the new edition becomes the document's current one; older run folders stay on disk) or **keep both** under a new name. It is never silent.
- **Replace without a gap.** The indexing step first writes the new run's points (a point's ID comes from its requirement ID, so unchanged requirements are overwritten in place). Only after the document's indexing finishes and the completeness check passes (the check reindex already uses: every expected point present) are the document's points that are not in the new expected set removed. The document is never missing from search; a failure leaves the old points plus some new ones, and a retry converges. This changes what the indexing step does and is confirmed again at build time (stop-and-ask). Acceptance: a failure injected after half the batches leaves the old document fully searchable, and the retry leaves no stale point (backlog item 42).
- **Handling a file you did not write.** Even an official source is not trusted absolutely. The pipeline runs in the pipeline container with a time limit and a memory limit and no more network than it needs; there is no end-user quarantine because there is no end-user upload. An optional virus scan can come later.
- **Profile picker:** hidden until a second domain profile exists. **Draft questions after ingest:** an "also write draft audit questions" tick box, off by default (stage 6).

## 7. Where the work runs, and deployment shapes

| Role | Today | May be |
|---|---|---|
| Browser | any device | any device |
| ReqBot server (web page, API, MCP) | one machine with everything | its own machine |
| Pipeline runner (Docling, checks, writing files) | child process of the server | another machine, over the shared folder (stage 5) |
| Model machine (Ollama: extraction, embeddings, questions) | one address in config, shared by all model work | its own GPU machine |
| Qdrant (search index, rebuildable) | one address in config | its own machine |
| Files (`processed_dir`, the record) | the server's disk | a shared folder both server and runner see |

What must reach what: the browser reaches the server only; the server reaches Qdrant (search) and the model machine (embedding a query, optional synthesis); the runner reaches the model machine and Qdrant (indexing); the server and the runner share the processed folder.

- **File movement goes behind one interface**, with a **shared-folder** implementation first (a network mount or shared volume). A transfer-over-HTTP implementation can replace it later without touching the rest, for a deployment that cannot share a folder. Decided (the owner left this technical choice to the implementer).
- **A runner on another machine (stage 5)** is a small command on that machine that mounts the shared folder and claims jobs by the lease in section 5. Nothing is pushed to it, so it needs no inbound access.
- A one-page **deployment shapes** document (all in one, three boxes, enterprise) lists the above for each shape.

## 8. The web screens

- **Reader mode (stage 1):** Library (the Corpus list), Checklists with export, and Search.
- **Admin (stages 4 and 6):** the Corpus drop zone with "Import from inbox", a banner for the running job ("afi17-203.pdf: finding requirements, chunk 120 of 427"), a job history with state, times, a log tail and Cancel or Retry; on the checklist screen "Write draft audit questions" with row progress (unchanged rows are reused by the existing hash rule); on System "Rebuild library" and a note that searches are slower while a job runs.
- The page polls the job list every few seconds while a job runs; there is no new front-end dependency. A closed browser tab does not stop a job.

## 9. Stages and what each must show

| Stage | Change | Must show |
|---|---|---|
| 0 | This plan | the owner's answers to section 10 |
| 1 | Roles and reader mode: role from headers, token or access code; role checks on routes; reader screens; `synthesize` refused for readers; Settings by role | a reader reaches no admin route; headers are ignored from an address that is not the configured proxy; codes and tokens absent from every response and log; screen tests |
| 2 | Network MCP service | a test client connects over the network, lists the tools and searches; a request without a valid token is refused; stdio behavior unchanged |
| 3 | Job engine, claim and lease, process-group reconcile, pre-flight, `--progress-json`, `reqbot jobs`, read-only job routes | with a stub command: success, failure, cancel, **server restart with a live child (no second job starts until it is gone)**, lease expiry, queue order, one at a time, progress parsing, an unreachable machine named by the pre-flight; the real `reqbot ingest` unchanged when the option is absent (output byte-identical) |
| 4 | Admin upload and import routes, start-ingest route, the same-name rule, replace without a gap | refusals (not a PDF, wrong extension, too large, too many pages, path parts in the name, not an admin); a small PDF through the real pipeline from an upload writes the same files a CLI run writes; **a failure injected mid-indexing leaves the old document searchable and the retry leaves no stale point** |
| 5 | The pipeline runner as its own command on a second machine over the shared folder; the deployment shapes page | a job queued by the server runs on the other machine and appears in the server's Library; killing the runner mid-job makes it `interrupted` and a retry finishes it |
| 6 | Draft-questions and rebuild jobs and their buttons; remove a document (run folders move to a trash folder, points are deleted, with a confirmation); first-run wizard | the sidecar equals what `reqbot questions` writes; an interrupted rebuild leaves each live collection untouched; nothing deleted without a confirmation |

**Build order (the implementer's, 2026-10-11).** The stage numbers group the work; they are not the order. The owner's first ask was ingesting from the web page, while enterprise sign-in, a network MCP service and a runner on a second machine are only needed once a customer environment exists. So: stage 3 (job engine), then stage 4 (admin upload and import), each with only the access-code role source of section 3 (item 3) and the one role check the job and upload routes need (admin or not); then the draft-questions and rebuild jobs and buttons from stage 6; then stage 1's header and token sources and the reader screens, stage 2 and stage 5, when a customer environment calls for them; removing a document and the first-run wizard last. Every stage keeps its own acceptance rules, and each is its own pull request.

**Rebuild atomicity, stated correctly.** The CLI rebuilds each collection in a temporary one and swaps it only when complete, but the two collections are swapped one after the other, not together: if requirements succeed and context fails, the new requirements are live beside the old context (`docs/OPERATIONS.md`). The rebuild job reports which half succeeded and a retry fixes it. Making both swap together is outside this plan.

No stage adds a model call (jobs run commands that already exist), changes extraction, changes the record schema, or adds a dependency. The CLI's behavior is unchanged throughout. Not planned: MCP tools that start jobs (an assistant starting GPU jobs unattended is its own decision).

## 9a. The first-run setup wizard (stage 6; the owner approved the shape on 2026-10-12)

The owner asked for a full guided wizard and set the rule it is built under: **everything above the command line is a wrapper, so there is one set of checks and one writer, not a second implementation in the page.**

- **Shared checks.** `services/setup_service.py` holds the connection tests, the "is this model installed" rule (the one a queued job's pre-flight check uses, so "the wizard says it is there" and "the job will find it" are the same statement), the documents-folder check and the list of models ReqBot will ask for. `reqbot init`, `reqbot init --check` and the web page all call it.
- **Shared writer.** The page saves through `POST /api/config`, which writes through `config_service.update_config`, the same function `reqbot init` ends in.
- **Steps.** (1) Ollama and Qdrant addresses, each tested as typed; (2) the models, each with what it is for, whether it is installed, and the exact `ollama pull` command for a missing one; (3) who writes answers (local, remote with the name of the key variable, or retrieval only); (4) the documents folder (shown and checked, not changed) and admin protection (shown, with the command); (5) a review of exactly what changes, and Save.
- **Required or optional.** Search and adding documents need the embedding model and the extraction model; draft questions, written answers and query understanding are optional features, so a missing optional model is reported but does not make the setup "not ready".
- **What the page does not do, on purpose.** It does not switch admin protection: a route that could turn the access code off is the one thing an attacker would want, and the loopback test is not proof of presence behind a proxy. The code is never returned over HTTP, so the page shows the state and the command (`reqbot token`, `reqbot token --open`, `reqbot token --require`) to run on the server. It does not change the documents folder (Settings cannot either), and it never takes an API key: the remote step takes the name of an environment variable.
- **Where it runs.** The test route makes the server call the addresses it is given, so it answers only a direct loopback client, accepts only plain http(s) addresses and follows no redirects. A prompt at the top of every page leads to `/setup` until a configuration file exists; it can be run again at any time.
- **Pass rules.** The addresses and models it reports are the ones a job would find or not find; a check writes nothing; saving sends only what changed; nothing in the page can switch admin protection or reveal the code.

## 10. Decisions for the owner

1. **Decided 2026-10-11:** the two audiences; admin-only upload; reader mode with Library, Checklists and Search; Ask as a network MCP service; agnostic sign-in with no accounts of our own; modular deployment with the runner seam built in.
2. **File movement between the server and a runner: decided (left to the implementer).** A shared folder behind an interface; transfer over HTTP only if a deployment cannot share a folder.
3. **Trace, Compare and Evidence: decided, not in reader mode for now.** The owner rarely uses them. They only read, so they can be switched on for readers later without design work.
4. **The same-name rule and the inbox folder: decided (left to the implementer).** Content-aware and never silent, as in section 6; an optional inbox under the processed folder.
5. **Still open, and not needed yet:**
   - Users' own documents: whether they would ever join the shared library or stay private to the uploader (separate workspaces, a much larger design). Not needed while only admins add documents.
   - Automatic fetching of official documents: a later piece; where it runs is open.
   - To check with the customer before stage 2: whether the AI tools they may use can connect to a remote MCP server.

## 11. What this plan does not claim

It does not estimate how long a given document takes (the 164-page dress code took 49 minutes; an AFI-sized document takes minutes). It rests on a read of the code on 2026-10-11 and has not been built or tried against a browser or a second machine. The role source, the replace-without-a-gap rule and the claim-and-lease design are the three places where the design could change once built; each is tested in its own stage before the next depends on it.
