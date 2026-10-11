# Anchoring

How exactly each quote is found in its chunk.

```mermaid
flowchart TD
    IN["Input: the root quote, the chunk's raw text, the chunk's heading trail<br/>Spacing and bracket spacing are ignored when matching; nothing else is"]
    NOTE["Anchoring only records where the root sits and how exact the match is.<br/>It never changes the root and it rejects nothing."]

    IN --> A0{"Root or chunk text empty?"}
    A0 -->|yes| NF1["not_found"]
    A0 -->|no| A1{"How many times does the root<br/>appear in the chunk?"}
    A1 -->|"exactly once"| EX["exact<br/>start and end recorded"]
    A1 -->|"more than once"| AMB["exact_ambiguous<br/>no position given"]
    A1 -->|"not at all"| A2{"With its leading list number or dash taken off<br/>(piece of 25 or more characters),<br/>does it appear exactly once?"}
    A2 -->|yes| MR["marker_removed"]
    A2 -->|no| A3{"A lead-in glued on the front: a colon within the<br/>first 160 characters, and the item after it<br/>(25 or more characters) appears exactly once?"}
    A3 -->|yes| A3a{"Where is the lead-in line?"}
    A3a -->|"earlier in the chunk"| LJ["lead_in_joined<br/>lead-in and its position kept"]
    A3a -->|"not in the body, but the actor<br/>is named in the heading trail"| LH["lead_in_from_heading"]
    A3a -->|"nowhere"| LN["lead_in_not_in_source<br/>the lead-in is not vouched for"]
    A3 -->|no| A4{"Take 1 to 7 words off the front or the end:<br/>does a piece of 25 or more characters<br/>appear exactly once?"}
    A4 -->|yes| WT["words_trimmed<br/>number of words and which side recorded"]
    A4 -->|no| A5{"Did any attempt above match<br/>more than once?"}
    A5 -->|yes| AMB2["exact_ambiguous<br/>no arbitrary position given"]
    A5 -->|no| A6{"Closest span in the chunk<br/>at least 85 percent similar?"}
    A6 -->|yes| FZ["fuzzy<br/>closest span and its score recorded"]
    A6 -->|no| NF2["not_found<br/>best score recorded"]

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef loose fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef none fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef note fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class EX,MR,LJ,LH ok;
    class AMB,AMB2,LN,WT,FZ loose;
    class NF1,NF2 none;
    class NOTE note;
```

A ladder: the first rung that matches decides the status. Statuses are records only; nothing is accepted or rejected on them.

Back to the [diagram index](README.md).
