# Kind labels

How each row is labelled by what sort of statement it is.

```mermaid
flowchart TD
    IN["A checklist row:<br/>its text, citation and hint flags"]
    L0{"Opens with an 'as follows:' lead-in<br/>that has no duty word?"}
    L0a["The item after the lead-in is judged,<br/>not the lead-in"]
    IN --> L0
    L0 -->|yes| L0a
    L0 -->|no| K1
    L0a --> K1

    K1{"Cited by a figure caption?"} -->|yes| A1["form_template_text"]
    K1 -->|no| K2{"Front matter, and says who<br/>the document applies to?"}
    K2 -->|yes| A2["applicability"]
    K2 -->|no| K3{"Front matter, with no duty word<br/>(or 'This ... provides, describes ...')?"}
    K3 -->|yes| A3["cover_page_text"]
    K3 -->|no| K4{"Cited by a table caption?"}
    K4 -->|yes| A4["table_row"]
    K4 -->|no| K5{"Says who the document applies to?"}
    K5 -->|yes| A2
    K5 -->|no| K6{"Points elsewhere (can be found in ...,<br/>refer to ...) with no strong duty word?"}
    K6 -->|yes| A6["pointer"]
    K6 -->|no| K7{"A negation of an obligation or permission?"}
    K7 -->|"yes, a permission comes first"| A7a["permission"]
    K7 -->|"yes, otherwise"| A7["prohibition"]
    K7 -->|no| K8{"Says something does not apply<br/>or is not required?"}
    K8 -->|"yes, a duty comes first"| A8a["duty_with_actor"]
    K8 -->|"yes, otherwise"| A8["exemption"]
    K8 -->|no| K9{"Flagged as a definition or description,<br/>or gives examples, with no duty word?"}
    K9 -->|yes| A9["definition_or_description"]
    K9 -->|no| K10{"Opens with a purpose clause (To ...)<br/>and no obligation word?"}
    K10 -->|yes| A10["unknown"]
    K10 -->|no| K11{"Opens with a command verb<br/>and names no subject?"}
    K11 -->|yes| A11["duty_imperative"]
    K11 -->|no| K12{"Names its actor, a colon, then a command?<br/>Or has an obligation word?<br/>Or says who retains or has a responsibility?"}
    K12 -->|yes| A8a
    K12 -->|no| K13{"Says should?"}
    K13 -->|yes| A13["recommendation"]
    K13 -->|no| K14{"Says what may be done?"}
    K14 -->|yes| A7a
    K14 -->|no| K15{"Opens with a command verb,<br/>or flagged as no stated actor?"}
    K15 -->|yes| A11
    K15 -->|no| A10b["unknown<br/>no wording cue"]

    TAGS["Then tags, whatever the kind:<br/>refers_back, list_item, fragment, front_matter<br/>A kind decided by position also records<br/>what its words alone would give"]
    OUT[("Side file: one record per row<br/>kind, the rule that fired and the words it matched,<br/>tags, rules version")]
    A1 --> TAGS
    A2 --> TAGS
    A3 --> TAGS
    A4 --> TAGS
    A6 --> TAGS
    A7 --> TAGS
    A7a --> TAGS
    A8 --> TAGS
    A8a --> TAGS
    A9 --> TAGS
    A10 --> TAGS
    A10b --> TAGS
    A11 --> TAGS
    A13 --> TAGS
    TAGS --> OUT

    NOTE["Nothing reads these labels yet.<br/>They are never a reason to drop or change a row."]

    classDef pos fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef kind fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef unk fill:#f3f4f6,stroke:#6b7280,color:#374151;
    classDef data fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class A1,A3,A4 pos;
    class A2,A6,A7,A7a,A8,A8a,A9,A11,A13 kind;
    class A10,A10b unk;
    class OUT,NOTE data;
```

The first rule that matches decides. Nothing reads these labels yet; they never drop or change a row.

Back to the [diagram index](README.md).
