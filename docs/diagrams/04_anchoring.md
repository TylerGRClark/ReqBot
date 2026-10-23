# Anchoring

Where each row sits in its chunk. Since clause labeling, this is a fact the splitter records, not a search.

```mermaid
flowchart TD
    S["The splitter cuts the chunk's raw text into clauses<br/>and records each clause's start and end"]
    R["The row carries them: anchor_start, anchor_end, anchor_text<br/>anchor_status is always exact"]
    N{"Normalizing checks: the raw text between<br/>anchor_start and anchor_end, whitespace tidied,<br/>equals the row's source_quote?"}
    OK["Kept: the explained text and the checklist's passage<br/>are located from these offsets"]
    BAD["Rejected: clause_offset_mismatch<br/>(the chunk file changed after labeling;<br/>re-run requirement finding)"]
    NOTE["The search ladder that used to run here (exact, marker removed,<br/>lead-in glued, words trimmed, fuzzy, not found) was deleted with the<br/>list-writing step: it existed to find where a model's copy of a quote came from."]

    S --> R --> N
    N -->|yes| OK
    N -->|no| BAD

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef none fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef note fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class OK,R ok;
    class BAD none;
    class NOTE note;
```

Records from before the switch keep the anchor statuses they were written with; nothing reads them to accept or reject a row.

Back to the [diagram index](README.md).
