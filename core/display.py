"""The text a reader sees as a requirement (docs/PIPELINE_REDESIGN_PLAN.md).

A record carries the root, `source_quote` (exactly what requirement finding returned, a fragment more often than the sentence), and the explained layer, `explained_text` (the whole
sentence, with a lead-in the source backs). Readers show the explained text first. Older records have no explained text and fall back to the description and then the quote, as before.
"""


def requirement_text(record) -> str:
    """explained text, else description, else the root quote, from a Qdrant payload or a record dict."""
    if not record:
        return ""
    return (record.get("explained_text") or record.get("description") or record.get("source_quote") or "").strip()
