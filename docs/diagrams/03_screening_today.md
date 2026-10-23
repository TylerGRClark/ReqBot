# Screening

Which rows are rejected in normalizing, and in what order the checks run.

```mermaid
flowchart TD
    Q["A row from requirement finding<br/>(the clause: the document's own words)"]
    OLD{"Every row has a clause_index?"}
    STOP["The whole file is refused:<br/>it was written by the deleted list-writing step;<br/>run requirement finding again on that folder"]
    FAIL[("Failures file<br/>one line per rejected row, with the reason")]
    PASS["Row passes<br/>goes on to de-duplication, unchanged"]

    Q --> OLD
    OLD -->|no| STOP
    OLD -->|yes| C1{"Empty?"}
    C1 -->|"yes: empty_source_quote"| FAIL
    C1 -->|no| C2{"Do its offsets in its chunk's raw text,<br/>whitespace tidied, give back the clause?<br/>(never expected to fail: both come from the splitter)"}
    C2 -->|"no: clause_offset_mismatch"| FAIL
    C2 -->|yes| C5{"Repeats a heading from its own section path<br/>(90 percent or more alike, any level)?"}
    C5 -->|"yes: heading_echo_quote"| FAIL
    C5 -->|no| C7{"Opens with 'Term, as defined in ...'<br/>and nothing independent after the citation?"}
    C7 -->|"yes: orphaned_list_item_quote"| FAIL
    C7 -->|no| PASS

    classDef fail fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    class FAIL,STOP fail;
    class PASS ok;
```

Every rejection is written to the failures file with the label shown on the arrow. The fuzzy-match and word-share grounding checks and the missing-subject rejection were deleted with the list-writing step: a clause is the document's own line, so there is nothing invented to catch, and a subject-less line ("Is responsible for ...") is a real line under its list's lead-in.

Back to the [diagram index](README.md).
