# Requirement finding

What happens to each chunk when the model is asked for the duties in it.

```mermaid
flowchart TD
    IN["A chunk: its prompt text<br/>(breadcrumb and raw text)"]
    R1{"Finished in an earlier run?<br/>(same chunk, same prompt,<br/>status complete or truncated)"}
    REUSE["Reused: no model call"]
    R2["Build the prompt:<br/>the inclusive duty prompt with the profile's obligation verbs<br/>plus candidate source references scanned from the text<br/>plus the chunk text"]
    R3["Local model, structured output<br/>(quote and source reference)<br/>8B by default"]
    R4{"The request failed?"}
    F1["Failure recorded: ollama_request_failed<br/>chunk status failed, retried on the next run"]
    R5["Read the answer as a list, trying in order:<br/>1. plain, or inside an object with a requirements list<br/>2. the outermost square brackets<br/>3. recover the complete items of a cut-off list"]
    R6{"Cut off?<br/>(hit the output limit, or recovered<br/>from a cut-off list)"}
    R7{"Room left in the context window<br/>for a bigger answer?"}
    R8["One retry with the largest allowance that fits<br/>taken if it parsed and finished,<br/>or recovered at least as many items"]
    R9["First answer kept, with a warning"]
    R10{"A list was read?"}
    F2["Failure recorded: json_parse_failed<br/>in the parse failures file, chunk status failed"]
    R11["Each item needs a quote, or it is dropped<br/>the chunk number is added<br/>flagged recovered_truncated if the list was cut off<br/>(an empty list is a valid answer)"]
    OUT[("Extracted requirements file<br/>the roots, exactly as returned")]
    RAW[("Raw responses file<br/>written last for each chunk,<br/>with its status: complete, truncated or failed")]

    IN --> R1
    R1 -->|yes| REUSE
    R1 -->|"no (failed chunks are retried)"| R2
    R2 --> R3
    R3 --> R4
    R4 -->|yes| F1
    R4 -->|no| R5
    R5 --> R6
    R6 -->|yes| R7
    R6 -->|no| R10
    R7 -->|yes| R8
    R7 -->|no| R9
    R8 --> R10
    R9 --> R10
    R10 -->|no| F2
    R10 -->|yes| R11
    R11 --> OUT
    R11 --> RAW
    F1 --> RAW
    F2 --> RAW

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef fail fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef side fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class F1,F2 fail;
    class OUT,RAW data;
    class REUSE side;
```

A chunk that failed is retried on the next run; a finished chunk is reused, not asked again. The quotes that come back are the roots and are never edited.

Back to the [diagram index](README.md).
