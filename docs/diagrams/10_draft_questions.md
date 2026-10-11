# Draft audit questions

How a draft question is written, withheld and read back.

```mermaid
flowchart TD
    subgraph WRITE["Writing (the questions command; the only place a model is called)"]
        W0{"Row has requirement text?"}
        W0a["Not considered"]
        W1["Build the prompt from the row's own text:<br/>applies to, parent paragraph, the requirement,<br/>the passage (first 1,500 characters)"]
        W2{"Requirement forbids something?<br/>(shall not, must not, cannot, never, prohibited,<br/>forbidden, is not authorized or permitted,<br/>a sentence that opens with Do not)"}
        W2a["Prompt adds: ask whether it is avoided"]
        W3{"Same input as the saved record,<br/>no error, same withheld reasons?"}
        W3a["Reused: no model call<br/>unverified terms re-checked"]
        W4{"Any withholding flag?<br/>starts_mid_sentence, table_fragment,<br/>definition_or_description,<br/>quote_not_located_in_passage, no_passage"}
        W4a["Withheld: no question, reasons recorded<br/>the row itself stays on the checklist"]
        W5["Local 14B model, temperature 0.1<br/>answer as JSON: a question, or null"]
        W6{"The answer"}
        W6a["No question<br/>(null, or the word null as text, or empty)"]
        W6b["Malformed: one retry, then an error<br/>recorded and retried next run"]
        W6c["Request failed: retried twice with a wait;<br/>five failures in a row stop the run"]
        W7["A question<br/>terms in it that the row's text lacks are recorded<br/>(numbers, acronyms, capitalized names)"]
        W8[("Side file: one record per row<br/>saved every 25 rows and at the end")]
        W0 -->|no| W0a
        W0 -->|yes| W1
        W1 --> W2
        W2 -->|yes| W2a
        W2 -->|no| W3
        W2a --> W3
        W3 -->|yes| W3a
        W3 -->|no| W4
        W4 -->|yes| W4a
        W4 -->|no| W5
        W5 --> W6
        W6 -->|null| W6a
        W6 -->|malformed| W6b
        W6 -->|"model unreachable"| W6c
        W6 -->|question| W7
        W3a --> W8
        W4a --> W8
        W6a --> W8
        W6b --> W8
        W7 --> W8
    end

    subgraph READ["Reading (every time a checklist is built, no model)"]
        R1{"Row has a record with a question,<br/>no withholding flag now,<br/>and the record's input hash still matches<br/>the row's current prompt?"}
        R1a["Not shown (stale, or none)"]
        R2["Question shown, with a note:<br/>draft, check it before use"]
        R3{"Terms in the question that the row's text lacks?"}
        R3a["Review reason: question-has-terms-not-in-row<br/>the row requires review"]
        R4{"Actor terms found only in the surrounding text,<br/>not in the requirement, its Applies to line or parent?"}
        R4a["Review reason: question-actor-not-in-row<br/>the row requires review"]
        R1 -->|no| R1a
        R1 -->|yes| R2
        R2 --> R3
        R3 -->|yes| R3a
        R3 -->|no| R4
        R3a --> R4
        R4 -->|yes| R4a
    end

    W8 --> R1

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef drop fill:#f3f4f6,stroke:#6b7280,color:#374151;
    classDef bad fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef flag fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class W0a,W4a,W6a,R1a drop;
    class W6b,W6c bad;
    class W8 data;
    class R3a,R4a flag;
    class R2,W7 ok;
```

The questions command is the only model call in the checklist path. Withheld rows stay on the sheet; they just have no draft question.

Back to the [diagram index](README.md).
