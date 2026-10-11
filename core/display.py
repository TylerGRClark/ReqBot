"""The text a reader sees as a requirement (docs/PIPELINE_REDESIGN_PLAN.md).

A record carries the root, `source_quote` (exactly what requirement finding returned, a fragment more often than the sentence), and the explained layer, `explained_text` (the whole
sentence, with a lead-in the source backs). Readers show the explained text first. Older records have no explained text and fall back to the description and then the quote, as before.
"""


def requirement_text(record) -> str:
    """explained text, else description, else the root quote, from a Qdrant payload or a record dict."""
    if not record:
        return ""
    return (record.get("explained_text") or record.get("description") or record.get("source_quote") or "").strip()


def requirement_citation(record) -> str:
    """The reference a reader shows for a requirement: `citation` (read from the document when the index was built: a paragraph number, "Table 3.1", "Front matter", marked
    "(inferred)" when it was worked out from the text before the quote), else the `source_ref` the extractor recorded. `source_ref` itself is never replaced: Evidence groups by
    it and the index embeds it."""
    if not record:
        return ""
    return (record.get("citation") or record.get("source_ref") or "").strip()
