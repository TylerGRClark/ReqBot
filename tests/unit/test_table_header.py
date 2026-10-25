"""PROPOSED (PREREG11): a table grid line is labeled with its table's caption and column headers. Expected values are written out by hand."""
from pipeline import clause_labeling as cl

TABLE = ("Table 2.1. End User Device Refresh Rate\n\n"
         "| Device Type | Recommended |\n"
         "|-------------|-------------|\n"
         "| Tablet      | 4 years     |\n"
         "| Phone       | 2 years     |\n")


def _ctx(chunks):
    return {c["text"]: c["ctx_table"] for c in cl.document_clauses(chunks)}


def test_grid_line_gets_caption_and_column_headers_and_the_header_row_gets_none():
    got = _ctx([{"chunk_id": 0, "raw_text": TABLE}])
    want = "Table 2.1. End User Device Refresh Rate. Column headers: Device Type | Recommended"
    assert got["| Tablet      | 4 years     |"] == want
    assert got["| Phone       | 2 years     |"] == want
    assert got["| Device Type | Recommended |"] is None
    assert got["Table 2.1. End User Device Refresh Rate"] is None


def test_repeated_header_in_a_later_chunk_takes_the_caption_from_the_earlier_chunk():
    later = "| Device Type | Recommended |\n|---|---|\n| Laptop | 5 years |\n"
    got = _ctx([{"chunk_id": 0, "raw_text": TABLE}, {"chunk_id": 1, "raw_text": later}])
    assert got["| Laptop | 5 years |"] == "Table 2.1. End User Device Refresh Rate. Column headers: Device Type | Recommended"


def test_table_without_caption_gives_headers_only_and_empty_cells_are_dropped():
    raw = "The terms are:\n| Term | | Meaning |\n|---|---|---|\n| Asset | | Something owned |\n"
    got = _ctx([{"chunk_id": 0, "raw_text": raw}])
    assert got["| Asset | | Something owned |"] == "Column headers: Term | Meaning"
    assert got["The terms are:"] is None


def test_plain_prose_and_a_table_with_no_header_row_get_none():
    raw = "The ISSM will:\n- Keep logs.\n\n|---|---|\n| a1 | b1 |\n"
    got = _ctx([{"chunk_id": 0, "raw_text": raw}])
    assert set(got.values()) == {None}


def test_long_caption_and_header_are_cut_to_300_characters():
    raw = "Table 9. " + "x" * 200 + "\n\n| " + " | ".join("Col%02d" % i for i in range(60)) + " |\n|" + "---|" * 60 + "\n| " + " | ".join(["vv"] * 60) + " |\n"
    ctx = _ctx([{"chunk_id": 0, "raw_text": raw}])["| " + " | ".join(["vv"] * 60) + " |"]
    assert ctx.startswith("Table 9. " + "x" * 91 + ". Column headers: Col00 | Col01")
    assert len(ctx) == 300


def test_clause_block_shows_the_table_context_after_the_lead_in_and_is_unchanged_without_it():
    item = {"text": "| Tablet | 4 years |", "heading": "2.5 Refresh", "ref": "2.5", "ctx_lead": None, "ctx_table": "Column headers: Device Type | Recommended"}
    assert cl.clause_block([item]) == "[1]\nContext: Heading: 2.5 Refresh | Paragraph: 2.5 | Table context: Column headers: Device Type | Recommended\nClause: | Tablet | 4 years |"
    plain = {"text": "Second.", "heading": "", "ref": "", "ctx_lead": None, "ctx_table": None}
    assert cl.clause_block([plain]) == "[1]\nContext: (none)\nClause: Second."
    assert cl.clause_block([{k: v for k, v in plain.items() if k != "ctx_table"}]) == "[1]\nContext: (none)\nClause: Second."
