"""The text a reader sees as a requirement (docs/PIPELINE_REDESIGN_PLAN.md).

A record carries the root, `source_quote` (exactly what requirement finding returned, a fragment more often than the sentence), and the explained layer, `explained_text` (the whole
sentence, with a lead-in the source backs). Readers show the explained text first. Older records have no explained text and fall back to the description and then the quote, as before.
"""


def requirement_text(record) -> str:
    """explained text, else description, else the root quote, from a Qdrant payload or a record dict."""
    if not record:
        return ""
    return (record.get("explained_text") or record.get("description") or record.get("source_quote") or "").strip()


# Text ahead of a document's first numbered paragraph is cited "Front matter" in what is stored (the checklist, the search index, the kind rules and every side file hold that
# string, so it does not change). A reader is shown the plainer name below. The JSON the API and MCP return keeps the stored string.
STORED_OPENING_LABEL = "Front matter"
SHOWN_OPENING_LABEL = "Opening pages"


def citation_label(label) -> str:
    """A stored citation label as a reader sees it: only the opening-pages label is renamed; a paragraph number, "Table 3.1" or "Figure A3.1" is shown as it is stored."""
    text = (label or "").strip()
    return SHOWN_OPENING_LABEL if text == STORED_OPENING_LABEL else text


def requirement_citation(record) -> str:
    """The reference a reader shows for a requirement: `citation` (read from the document when the index was built: a paragraph number, "Table 3.1", "Front matter" shown as
    "Opening pages", marked "(inferred)" when it was worked out from the text before the quote), else the `source_ref` the extractor recorded. `source_ref` itself is never
    replaced: Evidence groups by it and the index embeds it."""
    if not record:
        return ""
    return citation_label(record.get("citation") or record.get("source_ref") or "")
