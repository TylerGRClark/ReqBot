# Text scan

How duties that nobody extracted are found.

```mermaid
flowchart TD
    CH[("Chunks: raw text")]
    EXT[("Every extracted quote<br/>the root, the explained text,<br/>and any merged roots")]

    U1["Cut each chunk into paragraphs:<br/>at numbered, lettered or bulleted markers when there are two or more,<br/>otherwise at sentence ends"]
    U2["Take off a bare bullet<br/>(remembered: the row is still a list item)"]
    U3{"Skip the paragraph?"}
    U3a["Skipped: under 40 characters,<br/>already seen, ends in a colon (a lead-in),<br/>or looks like a table row (two or more pipes)"]
    U4{"A duty cue?"}
    U4a["Not a candidate"]
    U5["Candidate paragraph<br/>cue: a modal (shall, must, will, should, required to,<br/>is or are responsible, is or are to),<br/>or an opening imperative verb,<br/>or a later sentence that opens with one"]

    U1 --> U2
    U2 --> U3
    U3 -->|yes| U3a
    U3 -->|no| U4
    U4 -->|no| U4a
    U4 -->|yes| U5

    subgraph SENT["Judged sentence by sentence"]
        S1{"Sentence of 20 or more characters<br/>with a modal or an opening imperative?"}
        S2{"Only a purpose statement<br/>(The purpose is to ...)<br/>with no strong modal?"}
        S3{"Covered by an extracted quote?<br/>The quote has 25 or more characters and either text<br/>contains the other, or the two are identical"}
        S4["Uncovered duty sentence"]
        S5["Covered: counted"]
        S1 -->|no| S6["Not a duty sentence"]
        S1 -->|yes| S2
        S2 -->|yes| S6
        S2 -->|no| S3
        S3 -->|yes| S5
        S3 -->|no| S4
    end

    U5 --> S1
    EXT --> S3

    R1{"Result for the paragraph"}
    S4 --> R1
    S5 --> R1
    S6 --> R1
    R1 -->|"one or more uncovered duty sentences"| PROMO["Promoted: one row per sentence<br/>the whole sentence, cited and located like any extracted row<br/>flagged found_by_text_scan<br/>the paragraph's own number if it has one, else inferred<br/>bulleted: flagged list_item"]
    R1 -->|"no duty sentence of its own, and some were already covered<br/>or an extracted row contains the paragraph"| DROP["Dropped: nothing is missing"]
    R1 -->|"no duty sentence of its own, and nothing covers it"| MISS["Possible missed: one row, listed apart<br/>below the checklist, not counted as an item"]

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef drop fill:#f3f4f6,stroke:#6b7280,color:#374151;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef side fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class PROMO ok;
    class U3a,U4a,S6,DROP,S5 drop;
    class CH,EXT data;
    class MISS side;
```

A rule-based net for a reader. A paragraph with no duty sentence of its own is listed apart and is not counted as an item.

Back to the [diagram index](README.md).
