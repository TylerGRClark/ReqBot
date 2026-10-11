# PDF reading and chunking

How a PDF becomes chunks that know which section they sit in.

```mermaid
flowchart TD
    PDF[("Source PDF")]

    subgraph READ["PDF reading"]
        A1["Docling converts the PDF<br/>layout, headings, lists, tables, page numbers"]
        A2["Walk every item in document order"]
        A3{"Is the item a heading?"}
        A3a["Skipped: a table-of-contents line<br/>(5 or more dots in a row)<br/>never enters the heading trail"]
        A4["Depth from its numbering<br/>(3.1.4 is depth 3; a prose title is depth 1)<br/>Reference from its number or keyword<br/>(3.1.4, A4.2, ENCLOSURE-3), empty for prose"]
        A5["Headings at the same or a deeper depth<br/>leave the trail, then this one is added"]
        A6["The item records the current heading trail:<br/>reference path, title path, parent header text"]
        A7["Body text under the nearest heading is collected<br/>(first 5 paragraphs, 600 characters)"]
        A8["Parent context for each item:<br/>that section's collected body text,<br/>or the parent header text if there is none"]
        FAILWALK["If the walk fails: an empty trail and a warning<br/>the document object is kept"]
        A1 --> A2
        A2 --> A3
        A3 -->|"yes, and a ToC line"| A3a
        A3 -->|"yes"| A4
        A4 --> A5
        A3 -->|"no"| A6
        A6 --> A7
        A5 --> A8
        A7 --> A8
    end

    ANC[("Ancestry file<br/>heading trail for every item")]

    subgraph CHUNK["Chunking"]
        C1["HybridChunker cuts the document into chunks"]
        C2["Raw text of the chunk: its body items, headings left out<br/>a table is written once, as a grid,<br/>on the first chunk that holds it"]
        C3{"More than 40 percent of its lines<br/>are dotted-leader lines?"}
        C4{"Raw text empty?<br/>(heading only, or a table already written)"}
        C5{"Every body item sits under a skipped section?<br/>(the profile's skip list, matched by heading,<br/>ignoring case; unknown ancestry keeps the chunk)"}
        D1["Dropped: table of contents"]
        D2["Dropped: no body text"]
        D3["Dropped: skipped section"]
        C6["Kept: page range, and the deepest heading trail<br/>among its items (the last one wins a tie)"]
        C7["Breadcrumb: the headings joined with  >  <br/>Prompt text: the breadcrumb in brackets, then the raw text"]
        C1 --> C2
        C2 --> C3
        C3 -->|yes| D1
        C3 -->|no| C4
        C4 -->|yes| D2
        C4 -->|no| C5
        C5 -->|yes| D3
        C5 -->|no| C6
        C6 --> C7
    end

    OUT[("Chunks file<br/>chunk number in kept order, pages, raw text,<br/>breadcrumb, prompt text, heading trail,<br/>parent header, parent context")]

    PDF --> A1
    A8 --> ANC
    ANC --> C1
    A1 -.->|"the document object, in memory"| C1
    C7 --> OUT

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef drop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef note fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class D1,D2,D3,A3a drop;
    class PDF,ANC,OUT data;
    class FAILWALK note;
```

Three kinds of chunk are dropped before any model sees them: table of contents, no body text, and skipped sections. A chunk is kept whenever its section is uncertain.

Back to the [diagram index](README.md).
