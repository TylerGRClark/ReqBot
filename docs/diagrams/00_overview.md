# Overview

The whole path today, in the order the code runs it.

```mermaid
flowchart TD
    PDF[("Source PDF")]

    subgraph READ["Read the document"]
        R1["PDF reading<br/>layout, headings, tables, page numbers"]
        R2["Chunking<br/>section-aware chunks, raw text kept<br/>as the one reference text"]
    end

    subgraph FIND["Find the requirements"]
        F1["Requirement finding<br/>one call per chunk to a local 8B model<br/>returns quotes that look like duties"]
    end

    subgraph SHAPE["Check and shape each quote (one pass, in this order)"]
        S1["Screening - today's checks<br/>junk filters on the quote as found"]
        S2["Anchoring<br/>where the quote sits in its chunk<br/>and how exact the match is"]
        S3["De-duplication<br/>same reference and same quote: keep one"]
        S4["Context attaching<br/>whole sentence and lead-in kept<br/>beside the quote, never replacing it"]
        S5["Identity<br/>requirement ID hashed from the quote"]
        S6["Parent-stem reconstruction<br/>a subject for fragments, from their own document"]
    end

    FAIL[("Failures file<br/>every rejected quote with its reason,<br/>kept for audit")]

    subgraph PUBLISH["Publish"]
        P1["Totals and final file<br/>counts, statistics, final output"]
        P2["Search indexing<br/>dense and keyword vectors in Qdrant<br/>requirements and context kept apart"]
    end

    subgraph DEMAND["On demand, read from the published records"]
        K1["Checklist building<br/>citation, passage, flags,<br/>text scan for missed duties<br/>no model call"]
        K2["Draft audit questions<br/>14B model, written to a side file"]
        K3["Kind labels<br/>rule-based, side file,<br/>changes nothing yet"]
        K4["Delivery<br/>CLI, web UI, Excel, CSV, MCP"]
    end

    PDF --> R1
    R1 --> R2
    R2 --> F1
    F1 --> S1
    S1 -->|"rejected"| FAIL
    S1 -->|"passes"| S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> S6
    S6 --> P1
    P1 --> P2
    R2 -.->|"chunk text"| S1
    R2 -.->|"chunk text"| S2
    R2 -.->|"chunk text"| S4
    S6 --> K1
    K1 --> K2
    K2 -.->|"read back by the checklist"| K1
    K1 --> K3
    K1 --> K4

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef fail fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef demand fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class R1,R2,F1,S1,S2,S3,S4,S5,S6,P1,P2 built;
    class FAIL fail;
    class PDF data;
    class K1,K2,K3,K4 demand;
```

Screening comes before anchoring because that is how the code runs. The plan moves screening onto the explained text; that is on the roadmap diagram, not here.

Back to the [diagram index](README.md).
