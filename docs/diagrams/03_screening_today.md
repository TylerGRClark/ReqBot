# Screening

Which quotes are rejected, and in what order the checks run.

```mermaid
flowchart TD
    Q["A quote returned by requirement finding<br/>(the root: kept exactly as returned)"]
    FAIL[("Failures file<br/>one line per rejected quote, with the reason")]
    PASS["Quote passes<br/>goes on to anchoring, unchanged"]

    Q --> C1{"Empty?"}
    C1 -->|"yes: empty_source_quote"| FAIL
    C1 -->|no| C2{"Is its chunk known?"}
    C2 -->|"no: the two grounding checks are skipped"| C5
    C2 -->|yes| C3{"Fuzzy match against the chunk text<br/>below 60?"}
    C3 -->|"yes: quote_not_grounded_in_chunk"| FAIL
    C3 -->|no| C4{"Share of its words found in the chunk<br/>below 0.8?"}
    C4 -->|"yes: quote_words_not_in_chunk"| FAIL
    C4 -->|no| C5{"Repeats a heading from its own section path<br/>(90 percent or more alike, any level)?"}
    C5 -->|"yes: heading_echo_quote"| FAIL
    C5 -->|no| C6{"Ends in a bare colon<br/>(a list header with no content of its own)?"}
    C6 -->|"yes: unrepairable_fragment_quote"| FAIL
    C6 -->|no| C7{"Opens with 'Term, as defined in ...'<br/>and nothing independent after the citation?"}
    C7 -->|"yes: orphaned_list_item_quote"| FAIL
    C7 -->|no| C8{"First word is is, are, was or were<br/>(subject missing), and no question mark anywhere?"}
    C8 -->|no| C9
    C8 -->|yes| C8b{"Does the chunk have a parent header<br/>that could supply the subject?"}
    C8b -->|"no: dangling_clause_quote"| FAIL
    C8b -->|"yes: kept; the subject is added later<br/>by parent-stem reconstruction"| C9

    subgraph OFF["Checks that read a generated description (inactive while descriptions are switched off)"]
        D1{"Description starts with<br/>'not explicitly stated'?"}
        D2{"Description is a short 'change X to Y' entry<br/>(under 100 characters)?"}
        D1 -->|"yes: not_actionable"| FAIL
        D1 -->|no| D2
        D2 -->|"yes: errata_change_entry"| FAIL
    end

    C9{"A generated description present?<br/>(none while descriptions are switched off)"}
    C9 -->|no| PASS
    C9 -->|yes| D1
    D2 -->|no| PASS

    classDef fail fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef off fill:#f1f5f9,stroke:#94a3b8,color:#64748b,stroke-dasharray: 5 5;
    class FAIL fail;
    class PASS ok;
    class C9,D1,D2 off;
```

Every rejection is written to the failures file with the label shown on the arrow. Passing quotes continue unchanged.

Back to the [diagram index](README.md).
