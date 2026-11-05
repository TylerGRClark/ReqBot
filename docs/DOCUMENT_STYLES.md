# Document styles

A **document style** says how one kind of document is laid out and numbered. It is separate from a
[domain profile](PROFILES.md), which says what a document is *about* (duty wording, sections to
skip). A document has both. Styles live in `doc_styles/<name>.json`; the loader is
`core/doc_styles.py`.

| Style | What it does |
|---|---|
| `general` | The default. No document-type rules; behaves exactly as ReqBot always has. |
| `outline-dod` | DoD instructions and CJCS instructions numbered `1.` > `a.` > `(1)` > `(a)`, with or without dotted section headings (`2.10.`), and with enclosures that restart the numbering. |

## What `outline-dod` changes

The checklist and the search index cite each row by the paragraph it sits under. For documents
numbered in outline form, ReqBot could not cite the row at all (blank) or only the section it was
worked out from (`2.10 (inferred)`). Under `outline-dod` the citation names the paragraph the
document itself uses, for example `Encl A, 5.k` or `2.10.b(3)`.

It changes **only the citation**. Requirement records, requirement IDs, the quotes and the text
embedded for search are untouched; the labels are kept in a separate file beside the document,
`<doc>_references.json`, and read when a citation is worked out. Rules that protect existing
behavior:

- A label replaces only a blank citation or an inferred one, never a number read from the row
  itself.
- An inferred number is only made more exact: `2.1 (inferred)` can become `2.1.a`, but never `2.2`.
- A quote that sits under two different references (a sentence repeated at the top of several
  sections) is left alone rather than guessed.
- A missing or unreadable labels file means the document is cited as before.

## Using a style

For a new document, choose the style at ingest:

```bash
python3 cli/reqbot.py ingest "DODI 8410.03.pdf" --style outline-dod
```

For a document that is already ingested, label it without re-running anything else (needs the PDF
and an environment with Docling):

```bash
python3 pipeline/reference_labels.py --pdf raw_pdfs/"DODI 8410.03.pdf" \
    --run-dir ~/documents/processed/"DODI 8410.03_<timestamp>" --style outline-dod
```

Then rebuild the checklist, or refresh the index's citation field only (no re-embedding;
`reqbot-agent-docs` keeps `tools/refresh_citations.py` for this).

Pick the style that matches the document. A style on the wrong kind of document is held in check
by the rules above (an AFI labeled `outline-dod` keeps every citation it has today), but it will
not help it.

## Known limits

- Numbering that restarts with no enclosure heading is read as a stray list and ignored.
- If the PDF reader files an enclosure's title after that enclosure's first items (seen once, on
  the CJCSI 6510.02G close-out template page), those items are labeled under the previous
  enclosure.
- Looking a quote up needs at least 30 letters and digits of it; shorter clauses stay as they are.
