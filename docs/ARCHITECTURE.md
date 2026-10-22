# Architecture overview

[Documentation index](README.md) · [Configuration](CONFIGURATION.md) · [Operations](OPERATIONS.md)

ReqBot has two main workflows: turn PDFs into validated requirement artifacts,
then query an index built from those artifacts. The CLI, web application, HTTP
API, and MCP server expose those workflows.

## Components and ownership

| Component | Responsibility |
|---|---|
| `pipeline/` | Parse PDFs, chunk source text, extract/validate/enrich requirements, export artifacts, and build indexes. |
| `core/` | Configuration, profiles, artifact selection, retrieval, synthesis, and shared utilities. |
| `services/` | Return structured search, trace, comparison, evidence, checklist, status, and configuration results; `job_service.py` queues long commands and runs them one at a time as child processes (state under `<processed_dir>/.jobs/`). |
| `cli/` | CLI and interactive-shell command parsing and presentation. |
| `api/` | HTTP request validation, error mapping, and frontend serving. |
| `mcp_server/` | Read-only tools over shared services: stdio for a local AI client, and an optional HTTP door (`network.py`) for other machines. |
| `frontend/` | Browser screens and presentation; calls the HTTP API. |
| Ollama | Dense embeddings and local extraction, enrichment, query, and synthesis model calls. |
| Qdrant | Rebuildable dense/sparse requirements and source-context indexes. |

Interfaces own presentation and request validation. Retrieval belongs in
`core/ask.py`; pipeline sequencing belongs in `pipeline/run_pipeline.py`.
The [developer reference](../ARCHITECTURE.md) contains the module/import map.

## From document to requirements

| Stage | Work | Main output |
|---|---|---|
| PDF reading | Docling reads layout, headings, tables, and page provenance. | `*_ancestry.json` and an in-memory parsed document. |
| Chunking | Structure-aware chunking adds section paths and parent context; the profile can exclude sections. | `*_chunks.jsonl` |
| Requirement finding | Ollama returns, for each chunk, the quotes that look like duties, with references. The prompt is inclusive: it asks for anything that tells a party what it must, should, may or must not do. Raw responses and parse failures are retained. This output is the **root** of each requirement and is never edited. | `*_extracted_requirements.jsonl` |
| Normalizing and checking | One step today, doing several jobs: validate fields and quote grounding, drop junk (headings, fragments; there is no working change-log rejection yet), attach page and section metadata, deduplicate, record where each quote sits in its chunk and how exactly it matches (the `anchor_*` fields), build the explained text (the whole sentence it sits in), and assign IDs (hashed from the root). Deterministic parent-stem reconstruction follows. | `*_requirements_normalized.jsonl` |
| Enrichment | **Switched off** (October 2026): the code stays, but the pipeline no longer adds descriptions, domain tags or requirement types. | `*_requirements_enriched.jsonl` |
| Description check | **Switched off** with enrichment: there are no generated descriptions to check. | `*_requirements_gated.jsonl` |
| Totals and final file | Aggregate the selected output and record statistics. | `*_final_output.json`, `*_stats.json` |
| Index requirements | Embed selected requirement artifacts with dense Ollama embeddings and sparse BM25 features. | Qdrant `grc_requirements` |
| Index context | Embed source chunks with the same dense/sparse strategy. | Qdrant `grc_context` |

Older documents, log lines and command options name the stages by letter; the naming map
in section 6 of the [redesign plan](PIPELINE_REDESIGN_PLAN.md) translates them. New work uses
the names by job.

The same flow as a picture, laid out as the [redesign plan](PIPELINE_REDESIGN_PLAN.md) lays it out:
one job per step (GitHub draws it from the text below it). Green steps are built and run on
their own; amber steps work today but still run inside the normalizing module together with other jobs;
grey dashed steps are in the plan and not built, or switched off. The steps run in order, but not
every record takes every path: records that cannot be anchored or are empty are set aside, and
only rows the faithfulness check flags go through repair.

```mermaid
flowchart TD
    subgraph READ["Read the document"]
        N1["1 PDF reading<br/>PDF to a structured document"]
        N2["2 Chunking<br/>cut into chunks, keep the raw text"]
    end
    subgraph FIND["Find the requirements"]
        N3["3 Requirement finding<br/>one call per chunk returns the quotes<br/>local 8B model"]
        N4["4 Anchoring<br/>find the quote in the chunk text,<br/>record where and whether exact<br/>(inside the normalizing module today)"]
        N5["5 De-duplication<br/>collapse the same quote<br/>from the same reference<br/>(inside the normalizing module today)"]
    end
    subgraph BUILD["Build what a reader sees"]
        N6["6 Context attaching<br/>whole sentence and lead-in kept beside<br/>the quote, never replacing it<br/>(inside the normalizing module today)"]
        N7["7 Screening<br/>flag the clear non-requirements,<br/>judging the explained text<br/>(not built: junk filters still<br/>run first, in the<br/>normalizing module)"]
    end
    subgraph CHECK["Check and repair (planned)"]
        N8["8 Faithfulness check<br/>does the explained text still mean<br/>what the quote means? 14B model<br/>(not built)"]
        N9["9 Repair<br/>one attempt at a better version<br/>(not built)"]
        N10["10 Re-check<br/>the same check on the repaired text<br/>(not built)"]
    end
    subgraph PUBLISH["Publish"]
        N11["11 Totals and final file"]
        N12["12 Search indexing<br/>dense and sparse vectors into Qdrant"]
    end
    FAIL["Rejected records<br/>kept in a failures file"]
    CL["On demand: checklist building<br/>citation, passage, flags, draft questions<br/>no model call"]
    DQ["On demand: draft questions<br/>14B model, written to a side file<br/>(reqbot questions)"]
    OFF["Switched off: tagging, requirement types,<br/>descriptions and the description check"]

    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 --> N6
    N6 --> N7
    N7 --> N8
    N2 -.->|"chunk text"| N4
    N2 -.->|"chunk text"| N6
    N4 -->|"cannot be anchored and fails grounding"| FAIL
    N7 -->|"empty, heading echo"| FAIL
    N8 -->|"ok"| N11
    N8 -->|"flagged rows only"| N9
    N9 --> N10
    N10 -->|"kept, and flagged if it still fails"| N11
    N11 --> N12
    N6 --> CL
    CL -.->|"rows to ask about"| DQ
    DQ -.->|"read back by the checklist"| CL

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef inside fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef planned fill:#f3f4f6,stroke:#6b7280,color:#374151,stroke-dasharray: 5 5;
    classDef side fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class N1,N2,N3,N11,N12,CL,DQ built;
    class N4,N5,N6 inside;
    class N7,N8,N9,N10,OFF planned;
    class FAIL side;
```

### How one requirement is treated, by kind

Not every requirement takes the same path. This chart follows one quote through the places where
the code makes a different choice depending on what the quote is. Red boxes are records that are
set aside. Where a box says "the plan flags these instead", the redesign plan replaces a
rejection with a flag.

```mermaid
flowchart TD
    Q["A quote returned by requirement finding<br/>(one prompt for every chunk)"]
    SCAN["Text scan finds a duty sentence<br/>that nobody extracted"]

    Q --> E1{"Empty, or a heading repeated<br/>as if it were a requirement?"}
    E1 -->|yes| R1["Rejected"]
    E1 -->|no| E2{"Found in its chunk?<br/>(fuzzy match and word coverage)"}
    E2 -->|no| R2["Rejected: not grounded"]
    E2 -->|yes| E3{"Cut-off fragment (including a lead-in<br/>that ends in a colon), or a definition<br/>pointer such as X, as defined in Y?"}
    E3 -->|yes| R3["Rejected today<br/>(the plan flags these instead)"]
    E3 -->|no| E4{"Dangling clause with no subject?"}
    E4 -->|"yes, and no section header supplies one"| R4["Rejected"]
    E4 -->|"no, or a header supplies the subject"| A["Anchored: where it sits in its chunk,<br/>exact or not"]

    A --> X{"Whole sentence found exactly once,<br/>2 or more words, under 700 characters?"}
    X -->|yes| X1["Whole sentence kept beside the quote"]
    X -->|no| X2["Quote used as it is"]
    X1 --> L{"A list item?"}
    X2 --> L
    L -->|"yes, and a line above ends in a colon"| L1["That lead-in attached in front"]
    L -->|"yes, no such line"| L2["Stays a bare list item"]
    L -->|no| C0
    L1 --> C0
    L2 --> C0
    SCAN --> C0

    C0{"Where does it sit?"}
    C0 -->|"in a table"| C1["Cited by the table caption;<br/>no responsible party read from the heading"]
    C0 -->|"a numbered paragraph"| C2["Cited by its paragraph number;<br/>party from the numbered ancestors"]
    C0 -->|"an unnumbered paragraph"| C3["Cited by the nearest number before it,<br/>marked inferred; party from the section path"]
    C0 -->|"cover pages, or a template"| C4["Cited as Front matter (shown as Opening pages),<br/>or by the figure caption"]

    C1 --> Y
    C2 --> Y
    C3 --> Y
    C4 --> Y
    Y{"Starts in lower case, a table scrap,<br/>a definition, or not found in its passage?"}
    Y -->|yes| Z1["Row kept and flagged; no draft question"]
    Y -->|no| P{"Wording with a negation?<br/>(shall not, must not, cannot, never, prohibited, forbidden,<br/>a sentence that opens with Do not, or is not authorized,<br/>permitted, allowed, appropriate, acceptable)"}
    P -->|yes| P1["Prompt adds: this forbids something,<br/>ask whether it is avoided"]
    P -->|no| P2["Standard prompt"]
    P1 --> M["Model writes one question,<br/>or null for a permission,<br/>a description or a fragment"]
    P2 --> M
    M --> K["Marked for review if a term, or the actor,<br/>is not in the row itself"]

    classDef reject fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef keep fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef note fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class R1,R2,R3,R4 reject;
    class Z1 note;
    class K keep;
```

What this chart does not show is that several things are *not* decided by kind. Requirement
finding sends every chunk through the same prompt, whether it holds a paragraph, a list, a
table or a definition. No stored field records what kind of requirement a quote is (a duty, a
prohibition, a permission, a definition, a statement of who the document applies to, a table
row, an instruction inside a form template); the later steps each rediscover the parts of that
they need, from the wording, with their own rules.

One of those rules is under test: the negation test in the chart reads a plain "does not" in a
condition or a description ("... if this capability does not exist") as a prohibition, which can
turn a duty into the question "does the unit avoid ...". A narrower test is being evaluated.

A note on the red boxes: the code has six rejection checks, but in the October 2026 runs of
the 13 documents only three kinds of rejection occurred: not found in the chunk (117 records),
cut-off fragment (93) and repeated heading (40). The empty-quote, definition-pointer and
dangling-clause checks did not fire. A change-log rejection does not exist: an earlier one read a
generated description, which is always empty, and was removed.

### Planned changes

The [pipeline redesign plan](PIPELINE_REDESIGN_PLAN.md) describes where the pipeline is
going. Built so far: the anchor fields, the root kept untouched with the explained text
beside it, enrichment and the description check switched off, `confidence` dropped, and
readers showing the explained text. Still to come: the normalizing module split into separate steps and
screening on the explained text. In short: the root stays exactly as the model returned it and is never edited;
checking that the root is word for word in the source becomes its own early step
(anchoring); the whole-sentence expansion and lead-in attachment move into a separate
"explained" layer beside the root; screening judges that explained text; the normalizing module is split
so each step does one job; and tagging, typing, descriptions and the description check
are switched off, with the explained text used in their place.

The CLI `ingest` command runs indexing by default. The direct pipeline script
writes artifacts by default and requires `--index` to index. See [CLI](CLI.md)
and [Operations](OPERATIONS.md#resume-an-interrupted-run).

### What validation establishes

Normalizing and checking applies known-chunk grounding checks that combine
fuzzy character matching and a word-coverage threshold. They reject some invented quotes
while preserving formatting variants and list obligations the model joined to their
lead-in. These are heuristic checks, not proof that every quote is verbatim or
semantically faithful: in the October 2026 run of the 13 reference documents, 7% of
accepted quotes (172 of 2,419) are not word for word in their chunk (most often a lead-in glued onto a list item, or a dropped
list number), and the checklist marks them `quote_not_located_in_passage`.

Each accepted quote is then expanded, best effort, to the whole sentence it sits in
(verbatim, with spacing tidied; `pipeline/sentence_expand.py`). A quote that cannot be
found exactly once in its chunk, or whose sentence is very long, or that is a single
word, is left as the model returned it, so some accepted quotes stay incomplete or not
word for word. The expansion never replaces `source_quote`, which stays exactly as
requirement finding returned it (the root); the expanded sentence is stored beside it in
`explained_text`, with the pieces it was built from in `explained_parts` and a short
note of what was done in `explain_notes`. Where the source backs it, a lead-in the
model glued onto a list item is kept in front of the sentence.

Parent-stem reconstruction attaches `parent_stem` and combined `embedding_text`
to fragment records while preserving their `source_quote`.
Generated descriptions are distinct from source quotes. The description check has
deterministic checks and, when the optional MiniCheck dependency is available,
an entailment check. A rejected description is cleared; its requirement remains.

Enrichment failures can fall back to normalized artifacts. A description-gate
failure can fall back to the pre-gate artifact, with a log warning. Inspect logs
and failure artifacts when assessing a run; completion alone does not mean every
optional check executed. Human review of source quotes remains necessary.

## Checklists

A checklist is built on demand from the newest processed run of a document; building it
never calls a model. Each row is one requirement with its citation, section heading,
the paragraph it sits under (read from the document's own numbering), who it applies to,
the surrounding passage with the quote marked, and hint flags (for example "starts
mid-sentence" or "table fragment"). Duty sentences in paragraphs (numbered or not) that look like duties but were not
extracted become ordinary rows in their place in the document, flagged `found_by_text_scan` (a paragraph with no number of its own is cited
by inference, marked "(inferred)", or not at all); other passages of that kind, such as a purpose statement with no duty sentence, are listed
separately as possible missed requirements. Draft audit questions
come from `reqbot questions`, which writes a sidecar file (`*_audit_questions.jsonl`) that
the checklist reads; they are drafts for the auditor to check.

How one checklist is put together. Building it reads files only; the one model call is the
separate `reqbot questions` step, whose output the checklist reads back:

```mermaid
flowchart TD
    RUN[("Newest processed run<br/>requirements file: gated, else enriched, else normalized<br/>*_chunks.jsonl")]
    ROWS["Rows from extracted requirements<br/>citation, section heading, parent paragraph,<br/>who it applies to, passage with the quote marked,<br/>hint flags"]
    SCAN["Text scan<br/>duty sentences that were not extracted"]
    FOUND["Found rows (found_by_text_scan)<br/>duty sentences, placed in document order"]
    POSS["Possible missed requirements<br/>passages with no duty sentence of their own"]
    MERGE["Rows in document order"]
    SIDE[("Draft questions<br/>*_audit_questions.jsonl")]
    APPLY["Question and review marks added<br/>no model call"]
    OUT["Checklist: sheet, CSV, JSON, Markdown,<br/>web screen, MCP tool"]
    WRITE["reqbot questions --doc<br/>separate step, local model<br/>asks for a question for each eligible row<br/>(none for fragments, definitions, descriptions, permissions)"]

    RUN --> ROWS
    RUN --> SCAN
    SCAN --> FOUND
    SCAN --> POSS
    ROWS --> MERGE
    FOUND --> MERGE
    MERGE --> APPLY
    SIDE --> APPLY
    APPLY --> OUT
    POSS -->|"listed below the rows"| OUT
    MERGE -.->|"rows to ask about"| WRITE
    WRITE --> SIDE
```

## Artifacts and the source of record

Keep original PDFs and complete processed run directories. They allow inspection,
resume, later validation, and rebuilding without asking the extraction model
to regenerate the corpus.

| Artifact | Purpose |
|---|---|
| `*_ancestry.json`, `*_chunks.jsonl` | Source structure and the text shown to extraction. |
| `*_raw_responses.jsonl` | Extraction model responses and resume/cache evidence. |
| `*_extracted_requirements.jsonl`, `*_parse_failures.jsonl` | Parsed extraction output and parsing errors. |
| `*_requirements_normalized.jsonl`, `*_normalization_failures.jsonl` | Accepted normalized records and rejection reasons. |
| `*_requirements_enriched.jsonl` | Added descriptions/classifications before description checking. |
| `*_requirements_gated.jsonl`, `*_description_gate_failures.jsonl` | Post-check records and rejected-description evidence. |
| `*_final_output.json`, `*_stats.json` | Aggregated export and run metrics. |
| `*_audit_questions.jsonl` | Draft audit questions written by `reqbot questions`; read by the checklist. |
| `*_criticality.jsonl` | Rough criticality scores written by `reqbot questions` (a second model call per row); read by the checklist, which shows a Critical, High, Medium or Low band by rank within the document. |
| `*_cleanup.jsonl` | Optional "probably not a requirement" flags written by `reqbot questions --cleanup` (a third model call per row); read by the checklist, which adds `· junk` to the priority cell. Nothing is removed. |

Some artifacts are absent when their stage is skipped or fails. Reindex and
checklist generation share an artifact resolver: pick the run with the most
recently modified requirement artifact, then prefer gated over enriched over
normalized, provided the higher tier is not older than a lower tier. A stale
gated file must not override a later normalization rerun.

The document-listing service instead counts the latest normalized files. Its
counts describe processed artifacts, not a live Qdrant inventory.

## Search and trace

Search can rewrite the question into retrieval keywords and generate a HyDE
hypothesis. Dense question/hypothesis embeddings and sparse keyword features
retrieve candidates; reciprocal rank fusion combines the ranked lists.
Document, tag, and requirement-type filters constrain results.

An RRF score is a ranking score, not a probability of correctness. Optional
context fetches the source chunks linked to returned requirements from
`grc_context`. It does not alter stored requirements.

Trace looks up a known requirement ID and returns its payload, other records
sharing its citation, and optional surrounding chunk text. Shared references
help comparison; matching `source_ref` values are not proof of equivalent scope.

Answer synthesis is a separate, optional step over retrieved records. It can
use local Ollama, an explicitly configured remote provider, or be disabled.
Local retrieval still requires Ollama when remote synthesis is selected.
The experimental cross-encoder reranker is opt-in programmatically and has not
become a default retrieval step.

## Indexes and identity

`grc_requirements` stores requirement payloads and vectors. `grc_context` stores
source chunks and vectors. Indexed payloads retain embedding model/dimension
provenance; result warnings help identify a corpus built with another model.
Each requirement payload also carries `citation`, the reference the checklist gives
that row (a paragraph number, a table such as `Table 3.1`, `Front matter`, which readers see as "Opening pages"), read from
the document's own text when the index is built by the same function the checklist
uses (`services/checklist_service.py`, passed to the indexer by the CLI's indexing commands and by the direct scripts' `--index` path). It
sits beside `source_ref` and never replaces it: Evidence groups by `source_ref`, and
the embedded text carries it, so the label changes no vector. Readers show
`citation`, else `source_ref` (`core/display.py: requirement_citation`).

- `doc_key`: PDF filename stem used for artifact lookup and checklists.
- `source_pdf`: PDF filename used in source filters and presentation.
- `document_id`: PDF-content-derived identifier in normalized/indexed records.
- `requirement_id`: record identifier returned by search and accepted by trace.
- `chunk_id`: link to the source chunk within that document.

Use returned identifiers instead of fabricating IDs. A filename stem is not
interchangeable with the content hash in every interface.

Reindex builds replacement collections and swaps aliases after each successful
build. Requirements and context have separate swaps; the pair is not one
transaction. Migrating a plain collection to an alias can require a brief
availability gap. See [Operations](OPERATIONS.md#rebuild-the-search-indexes).

## Deployment boundaries

The default API listener is loopback, with no application authentication.
The MCP server is a subprocess using stdio. The optional network door (`reqbot mcp --http`) serves the same read-only tools over HTTP to other machines, only with a valid per-tool access code, and is not running unless started; see the [network MCP diagram](diagrams/13_network_mcp.md).
The web GUI requires a frontend build. See [Deployment](DEPLOYMENT.md),
[Connecting AI tools](AI_TOOLS.md), and [API](API.md) for those interfaces.
