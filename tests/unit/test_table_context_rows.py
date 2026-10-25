"""A row from a table grid is shown with its table's caption and column headers (explained layer, kind table_context). The root never changes; expected values are written out by hand."""
from pipeline import sentence_expand as SE
from pipeline.embed_and_index import build_embedding_text
from services import checklist_service as CS

CNSSI = ("Table E-1:  Security Control Parameter Values for NSS\n\n"
         "| ID      | Control Text                                | Defined Value for NSS                                 |\n"
         "|---------|---------------------------------------------|-------------------------------------------------------|\n"
         "| CP-9(1) | [Assignment: organization-defined frequency] | At least monthly or as defined in the contingency plan. |\n"
         "| CP-4    | a. [Assignment: organization-defined tests] | a. At a frequency as defined in the contingency plan. Tests as defined in the contingency plan. |\n"
         "| AC-2(3) |                                             | Not to exceed 90 days. |\n")


def _rec(chunk_id, raw, line_start_text, quote=None):
    start = raw.index(line_start_text)
    end = start + len(quote if quote is not None else line_start_text)
    return {"chunk_id": chunk_id, "source_quote": " ".join(raw[start:end].split()), "anchor_start": start, "anchor_end": end}


def _explain(raws, rec):
    out, counts = SE.explain_records([rec], raws)
    return out[0], counts


def test_a_whole_grid_line_reads_with_caption_and_labeled_cells_and_the_root_is_unchanged():
    line = "| CP-9(1) | [Assignment: organization-defined frequency] | At least monthly or as defined in the contingency plan. |"
    rec = _rec(1, CNSSI, line)
    out, counts = _explain({1: CNSSI}, rec)
    assert out["source_quote"] == line
    assert out["explained_text"] == ("Table E-1: Security Control Parameter Values for NSS. ID: CP-9(1) | Control Text: [Assignment: organization-defined frequency] | "
                                     "Defined Value for NSS: At least monthly or as defined in the contingency plan.")
    assert out["explained_parts"] == [{"kind": "table_context", "text": out["explained_text"], "origin": "rule"},
                                      {"kind": "sentence", "text": line, "origin": "rule"}]
    assert out["explain_notes"] == ["table caption and column headers attached"]
    assert counts == {"marker_removed": 0, "lead_in_attached": 0, "table_context_attached": 1}


def test_an_empty_cell_is_left_out_and_keeps_its_column():
    rec = _rec(1, CNSSI, "| AC-2(3) |                                             | Not to exceed 90 days. |")
    out, _ = _explain({1: CNSSI}, rec)
    assert out["explained_text"] == "Table E-1: Security Control Parameter Values for NSS. ID: AC-2(3) | Defined Value for NSS: Not to exceed 90 days."


def test_a_clause_that_stops_inside_a_long_cell_gets_the_headers_of_the_cells_it_holds():
    first = "| CP-4    | a. [Assignment: organization-defined tests] | a. At a frequency as defined in the contingency plan."
    rec = _rec(1, CNSSI, first)
    out, _ = _explain({1: CNSSI}, rec)
    assert out["explained_text"] == ("Table E-1: Security Control Parameter Values for NSS. ID: CP-4 | Control Text: a. [Assignment: organization-defined tests] | "
                                     "Defined Value for NSS: a. At a frequency as defined in the contingency plan.")


def test_a_clause_that_continues_a_cell_from_the_middle_of_a_line_is_left_alone():
    cont = "Tests as defined in the contingency plan. |"
    rec = _rec(1, CNSSI, cont)
    out, counts = _explain({1: CNSSI}, rec)
    assert out["explained_text"] == "Tests as defined in the contingency plan. |" and counts["table_context_attached"] == 0


def test_the_header_row_itself_a_table_without_headers_and_a_row_that_does_not_line_up_are_left_alone():
    header = "| ID      | Control Text                                | Defined Value for NSS                                 |"
    nohdr = "|---|---|\n| a1 | b1 |\n"
    ragged = "| A | B | C |\n|---|---|---|\n| x | y |\n"
    for raw, text in ((CNSSI, header), (nohdr, "| a1 | b1 |"), (ragged, "| x | y |")):
        out, counts = _explain({1: raw}, _rec(1, raw, text))
        assert out["explained_text"] == " ".join(text.split()) and out["explained_parts"] == [{"kind": "sentence", "text": " ".join(text.split()), "origin": "rule"}]
        assert counts["table_context_attached"] == 0


def test_a_merged_cell_is_shown_once_under_both_headers_and_numbers_or_sentences_are_not_used_as_labels():
    raw = ("Table 4.2. Roles\n\n| Role | Office | Duty |\n|---|---|---|\n| Chief | Wing IP | Wing IP |\n")
    out, _ = _explain({1: raw}, _rec(1, raw, "| Chief | Wing IP | Wing IP |"))
    assert out["explained_text"] == "Table 4.2. Roles. Role: Chief | Office / Duty: Wing IP"
    raw2 = "| 5 | Review the plan and all of its attachments every single year | Notes |\n|---|---|---|\n| 6 | Approve it | Done |\n"
    out2, _ = _explain({1: raw2}, _rec(1, raw2, "| 6 | Approve it | Done |"))
    assert out2["explained_text"] == "6 | Approve it | Notes: Done"


def test_a_table_that_starts_a_chunk_takes_the_caption_seen_above_the_same_header_in_the_chunk_before():
    later = "| ID      | Control Text | Defined Value for NSS |\n|---|---|---|\n| CP-10 | [Assignment: organization-defined time period] | 24 hours. |\n"
    out, _ = _explain({0: CNSSI, 1: later}, _rec(1, later, "| CP-10 | [Assignment: organization-defined time period] | 24 hours. |"))
    assert out["explained_text"] == ("Table E-1: Security Control Parameter Values for NSS. ID: CP-10 | Control Text: [Assignment: organization-defined time period] | "
                                     "Defined Value for NSS: 24 hours.")


def test_prose_is_untouched():
    raw = "The ISSM will:\n- Keep logs.\n"
    out, counts = _explain({1: raw}, _rec(1, raw, "- Keep logs."))
    assert out["explained_text"] == "The ISSM will: Keep logs." and counts["table_context_attached"] == 0


def test_the_hints_on_the_sheet_are_judged_on_the_row_not_on_the_added_headers():
    line = "| CP-9(1) | [Assignment: organization-defined frequency] | At least monthly or as defined in the contingency plan. |"
    out, _ = _explain({1: CNSSI}, _rec(1, CNSSI, line))
    chunks = {1: {"chunk_id": 1, "raw_text": CNSSI, "section_title_path": []}}
    plain = dict(out, explained_text=line, explained_parts=[{"kind": "sentence", "text": line, "origin": "rule"}])
    where = CS._locate_row(out, chunks, {}, None, ())
    assert where == CS._locate_row(plain, chunks, {}, None, ())  # citation, table label, flags, passage: identical with and without the table context
    assert where["flags"] == ["table_fragment"] and where["found"]
    assert CS._quotes(out)[1].startswith("Table E-1: Security Control") and CS._quotes(out)[2] == line


def test_the_search_index_embeds_the_shown_text_and_so_needs_a_reindex():
    line = "| CP-9(1) | [Assignment: organization-defined frequency] | At least monthly or as defined in the contingency plan. |"
    out, _ = _explain({1: CNSSI}, _rec(1, CNSSI, line))
    assert build_embedding_text(out).startswith("Table E-1: Security Control Parameter Values for NSS. ID: CP-9(1) | Control Text:")
