# Context attaching

How the explained text beside each row is built.

```mermaid
flowchart TD
    IN["A kept row: the clause (the root), its anchor_start,<br/>and its chunk's raw text"]
    S1{"Does the clause open with a list marker,<br/>a paragraph number or a bullet?<br/>(a. , (3) , 3.6.1. , - )"}
    S2["Sentence: the clause with the marker taken off<br/>note: list number or dash taken off"]
    S3["Sentence: the clause as it is"]

    IN --> S1
    S1 -->|yes| S2
    S1 -->|no| S3

    S2 --> L
    S3 --> L
    L{"Is the row a list item with a lead-in?<br/>Rule: nearest earlier line ending in a colon<br/>that is not a sibling of the item,<br/>up to 40 paragraph units back, 300 characters or fewer;<br/>this chunk, or the end of the previous chunk<br/>only if it is in the same section"}
    L -->|"found, and the sentence does not already begin with it"| L3["Lead-in attached in front<br/>note: lead-in attached from the line above that ends with a colon"]
    L -->|none| L4["Sentence only"]

    L3 --> M
    L4 --> M
    M["The row gets explained_text, explained_parts<br/>(lead_in, then sentence) and explain_notes<br/>the root and anchor fields untouched<br/>one row out for each row in: nothing is merged"]

    classDef ok fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef keep fill:#fef3c7,stroke:#d97706,color:#78350f;
    class S2,S3,L3,M ok;
    class L4 keep;
```

The explained text is a separate layer beside the root, built only from the document's own words. Stretching a partial quote to its whole sentence and merging rows that reached the same sentence were deleted with the list-writing step: a clause is already a whole line of the document.

Back to the [diagram index](README.md).
