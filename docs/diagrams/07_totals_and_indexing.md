# Totals and search indexing

What is written at the end, and what goes into search.

```mermaid
flowchart TD
    N[("Normalized records file")]

    subgraph TOT["Totals and final file"]
        T1["Count the records, and read the side files:<br/>pages, chunks, normalization failures,<br/>label batches by status (complete, unparsed, failed)"]
        T2[("Final output file<br/>document metadata and every record")]
        T3[("Statistics file<br/>chunks created, label batches unparsed and failed,<br/>rows by clause label,<br/>records before and after the checks,<br/>records per 1,000 characters,<br/>how many records have a reference<br/>and a heading trail")]
        T1 --> T2
        T1 --> T3
    end

    subgraph IDX["Search indexing - Qdrant, rebuildable from the files"]
        subgraph REQIDX["Requirements collection"]
            I1{"Quote empty?"}
            I1a["Skipped, with a warning"]
            I2["Text to embed, first that exists:<br/>the explained text, the quote<br/>then a line: Ref and the source reference"]
            I3["Dense vector from the Ollama embedding model<br/>and a sparse keyword (BM25) vector<br/>in batches of 32; a failed batch is retried one by one;<br/>a record that still fails is skipped"]
            I4["One point per requirement<br/>its ID comes from the requirement ID, so re-indexing overwrites<br/>payload: quote, explained text, clause label, citation label, metadata<br/>(the label is shown, never embedded)"]
            I1 -->|yes| I1a
            I1 -->|no| I2
            I2 --> I3
            I3 --> I4
        end
        subgraph CTXIDX["Context collection"]
            C1["Each chunk's prompt text,<br/>first 1,500 characters"]
            C2["Dense and sparse vectors,<br/>same batching and fallback"]
            C3["One point per chunk<br/>its ID comes from the document and chunk number"]
            C1 --> C2
            C2 --> C3
        end
    end

    WHEN["The CLI ingest command indexes by default.<br/>The direct pipeline script indexes only when asked."]

    N --> T1
    N --> I1
    CH[("Chunks file")] --> C1
    WHEN -.-> IDX

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef drop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef note fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class I1a drop;
    class N,CH,T2,T3 data;
    class WHEN note;
```

The files are the record. The search index can always be rebuilt from them.

Back to the [diagram index](README.md).
