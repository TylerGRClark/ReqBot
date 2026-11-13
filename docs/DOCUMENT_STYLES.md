# Document styles

A **document style** says how one kind of document is laid out and numbered. It is separate from a
[domain profile](PROFILES.md), which says what a document is *about* (duty wording, sections to
skip). A document has both. Styles live in `doc_styles/<name>.json`; the loader is
`core/doc_styles.py`.

| Style | What it does |
|---|---|
| `general` | The default. No document-type rules; behaves exactly as ReqBot always has. |
| `outline-dod` | DoD instructions and CJCS instructions numbered `1.` > `a.` > `(1)` > `(a)`, with or without dotted section headings (`2.10.`), and with enclosures that restart the numbering. |
| `nist-controls` | NIST control documents (SP 800-53, 800-171, 800-53A): a control is a heading (`AC-2 ACCOUNT MANAGEMENT`, `03.01.01 Account Management`), its statement is lettered and numbered items, and Discussion, References and Related Controls are parts that are not the statement. References read `AC-2 d.1`, `AC-2(3)(a)`, `AC-19(4)(b)(1)`, `AC-2 Discussion`, `03.01.01 f.3`. |
| `control-tables` | Documents whose controls are rows of tables (CNSSI 1253 baselines and overlays): a row is cited by the control id in its first cell (`IA-5(8)`), a row with a blank first cell inherits it (also across a page break), and a part marker in the second cell is added (`CM-7(1)(b)`, `RA-5 a`). Numbered paragraphs elsewhere use the outline rules. |

## What a style adds

The checklist and the search index cite each row by the paragraph it sits under. For documents
numbered in outline form, ReqBot could not cite the row at all (blank) or only the section it was
worked out from (`2.10 (inferred)`). Under `outline-dod` each requirement record carries a new
field, `reference`, with the paragraph the document itself uses, for example `Encl A, 5.k` or
`2.10.b(3)`, and the citation uses it.

## How it is recorded

1. **Reading the PDF (Step A/B).** The PDF reader's items still carry the document's numbering (list
   markers, heading numbers, enclosure headings); the chunk text does not. So the shared reference
   grammar (`core/reference_grammar.py`) labels every item in reading order, and chunking records,
   on each chunk, where each labeled item sits in the chunk's `raw_text`:
   `reference_spans = [[start, end, reference], ...]`.
2. **Normalizing (Step D).** Each record's `reference` is read from the span that holds the
   clause's own offset (`anchor_start`). No text is searched and no page is guessed. It is `""`
   when the document has no labels or the clause is in no labeled item (a table, for instance).
3. **Readers.** The checklist and the search index read `record["reference"]`. Nothing else.

`reference` is a separate field. It is **never** part of `source_ref`, so requirement IDs (hashed
from the document, `source_ref` and the quote) do not change, and the quotes and the text embedded
for search are untouched. A record without the field is read as `""`.

Rules that protect existing behavior:

- A reference replaces only a blank or inferred citation, never a number read from the row itself,
  a table caption, or a "Front matter" / "Figure" label.
- An inferred number is only made more exact: `2.1 (inferred)` can become `2.1.a`, but never `2.2`.
- The section-heading column still uses the old citation.

## Choosing a style

`reqbot ingest` takes `--style`, and its default is **`auto`**. The order of priority is:

1. **A style you name always wins.** `--style outline-dod` (or `general`, or any style in `doc_styles/`) is used as given; detection is not consulted.
2. **Otherwise ReqBot detects it.** Once the PDF has been read, it compares the text at the top of the first page and the PDF's file name with the families listed in `doc_styles/detection.json`. The rules, in order: if the file name and the first page name different families, the answer is `general` (a wrong style does more harm than none); if both name the same family, that one; if only the first page names families, the one that appears *earliest* wins, because a document identifies itself before it cites others; if only the file name names one family, that one.
3. **If it cannot tell, it uses `general`**, which changes nothing.

What was asked for, what was chosen and why are written into the run's stats (`pipeline.doc_style`: `name`, `version`, `requested`, `family`, `confidence`, `reason`), so nothing is silent. The families are data, not code: adding a style adds its own entry to `detection.json`, and a test checks that every shipped style has one.

```bash
python3 cli/reqbot.py ingest "DODI 8410.03.pdf"                      # auto: chooses outline-dod
python3 cli/reqbot.py ingest "DODI 8410.03.pdf" --style general      # your choice wins
```

Tested on the 23 documents of the library (title and file name together, the title alone, the file name alone: 23 of 23 each), on the PDF reader's real first pages with the file name hidden (8 of 8), and on cases built to fool it (an Air Force cover that cites a DoD instruction, a DoD instruction that mentions the Chairman of the Joint Chiefs, a file name that contradicts the page).

A resumed run (`--skip-to` past chunking) keeps the style its folder was chunked under; naming a different style then is refused, because the style only acts while chunking. Start again from PDF reading to change it.

Known limits: only the first page and the file name are read, so a scanned first page with no text relies on the file name; NIST SP 800-171A (the assessment companion) is not recognized and gets `general`; documents of types not listed get `general`.

For a document that is already ingested, add the references without a model run (needs the PDF and
an environment with Docling):

```bash
python3 pipeline/reference_labels.py --pdf raw_pdfs/"DODI 8410.03.pdf" \
    --run-dir ~/documents/processed/"DODI 8410.03_<timestamp>" --style outline-dod
```

That re-reads the PDF, checks that every chunk's text is exactly what is stored, re-runs
normalizing on the stored extraction, and **refuses to replace anything unless every record is
identical except for the new `reference` field** (same IDs, same order, same quotes). The old files
are kept as `*.before-references`. Then rebuild the checklist, or refresh the index's citation
field (payload only, no re-embedding; the notes repo keeps `tools/refresh_citations.py`).

Pick the style that matches the document. A style on the wrong kind of document is held in check by
the rules above (an AFI labeled `outline-dod` keeps every citation it has today), but it will not
help it.

## Known limits

- Numbering that restarts with no enclosure heading is read as a stray list and ignored.
- If the PDF reader files an enclosure's title after that enclosure's first items (seen once, on
  the CJCSI 6510.02G close-out template page), those items are labeled under the previous
  enclosure.
- A chunk the reader merged from generic table references has no spans; its rows keep their
  existing citation.
