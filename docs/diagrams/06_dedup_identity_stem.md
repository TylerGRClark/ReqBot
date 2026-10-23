# De-duplication and identity

De-duplication and requirement IDs.

```mermaid
flowchart TD
    subgraph DEDUP["De-duplication (before context attaching)"]
        D0["Rows that passed screening"]
        D1{"Same reference and same normalized quote<br/>as one already seen?<br/>(two identical table lines under one caption, for example)"}
        D2["Kept"]
        D3["Only one stays: the shorter quote<br/>(the confidence score is switched off,<br/>so length decides; a tie keeps the first)"]
        D0 --> D1
        D1 -->|no| D2
        D1 -->|yes| D3
    end

    CA["Context attaching<br/>(see its own diagram)"]
    D2 --> CA
    D3 --> CA

    subgraph ID["Identity (after context attaching)"]
        I1{"What does the record have?"}
        I2["Reference and quote:<br/>document ID : reference : normalized quote"]
        I3["Quote only:<br/>document ID : normalized quote"]
        I4["Neither:<br/>document ID : chunk : type : description"]
        I5["REQ- plus the first 12 characters of the sha256<br/>always from the root, so improving the<br/>explained text never changes an ID"]
        I6{"Two records ended with the same ID?"}
        I7["The first is kept, the rest dropped with a warning"]
        I1 -->|"reference and quote"| I2
        I1 -->|"quote only"| I3
        I1 -->|"no quote"| I4
        I2 --> I5
        I3 --> I5
        I4 --> I5
        I5 --> I6
        I6 -->|yes| I7
    end

    CA --> I1
    I6 -->|no| W
    I7 --> W
    W[("Written: the normalized records file<br/>and the failures file")]

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef keep fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef data fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class D2,D3,I5 ok;
    class I7 keep;
    class W data;
```

De-duplication runs before context attaching; IDs come after it. Parent-stem reconstruction, which used to run on the written file, was deleted with the list-writing step: the lead-in rule in context attaching gives a list item its governing line from the document itself.

Back to the [diagram index](README.md).
