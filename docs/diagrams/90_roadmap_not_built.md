# Roadmap: planned or switched off

What is planned or switched off, kept apart from what runs.

```mermaid
flowchart TD
    CA["Context attaching<br/>built"]
    KIND["Kind<br/>a label for what sort of statement each row is<br/>stage 1 built as a side file that changes nothing;<br/>the pipeline step itself is a proposal"]
    SCR["Screening on the explained text<br/>flag instead of reject<br/>not built: waits for the owner's decision<br/>on colon-ending lead-ins, and his rating"]
    FC{"Faithfulness check<br/>14B model: does the explained text still<br/>mean what the root means?<br/>not built"}
    RP["Repair<br/>one attempt, the model sees everything about the row<br/>not built"]
    RC{"Re-check<br/>the same check on the repaired text<br/>not built"}
    TF["Totals and final file<br/>built"]

    CA --> KIND
    KIND --> SCR
    SCR --> FC
    FC -->|"ok"| TF
    FC -->|"flagged"| RP
    RP --> RC
    RC -->|"kept, and flagged if it still fails"| TF

    subgraph OFF["Switched off (the code is still there)"]
        O1["Tagging and requirement types"]
        O2["Generated descriptions"]
        O3["Description check"]
        O4["Confidence score"]
    end

    RES["Model picks for prose documents<br/>not built: waits for rebuilt test groups"]
    DUP["A count of merged duplicates on each record<br/>planned, not recorded today"]

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef planned fill:#f3f4f6,stroke:#6b7280,color:#374151,stroke-dasharray: 5 5;
    classDef off fill:#f1f5f9,stroke:#94a3b8,color:#64748b;
    class CA,TF built;
    class KIND,SCR,FC,RP,RC,RES,DUP planned;
    class O1,O2,O3,O4 off;
```

Green boxes run today and are shown only to place the rest. No dashed box runs in the pipeline, and grey boxes are switched off. Kind labels exist only as a side file that nothing reads yet.

Back to the [diagram index](README.md).
