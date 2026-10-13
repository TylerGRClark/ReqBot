import csv
import io
import json

import openpyxl

from pipeline.checklist_export import (
    _CSV_COLUMNS,
    _csv_row,
    _csv_safe,
    to_csv,
    to_json,
    to_markdown,
    to_xlsx,
)

# Minimal fully-populated checklist item for fixture use
COMPLETE_ITEM = {
    "checklist_item_id": "CHK-abcdef1234567890",
    "requirement_ids": ["REQ-abc123"],
    "domain_tags": ["access-control", "authentication"],
    "source_ref": "4.2.1",
    "page_refs": [12, 13],
    "section_title_path": ["Access Control", "MFA Policy"],
    "source_quote": "The system shall enforce MFA for all privileged accounts.",
    "audit_question": "",
    "evidence_to_request": [],
    "generation_notes": "",
    "assessor_notes": "",
    "status": "not-started",
    "confidence": 0.9,
    "requires_human_review": False,
    "review_reasons": [],
}

REVIEW_ITEM = {
    **COMPLETE_ITEM,
    "checklist_item_id": "CHK-bbbbbbbbbbbbbbbb",
    "requirement_ids": ["REQ-def456"],
    "source_ref": "",
    "section_title_path": [],
    "page_refs": [],
    "domain_tags": [],
    "confidence": 0.6,
    "requires_human_review": True,
    "review_reasons": ["missing-source-ref", "low-confidence", "missing-page-refs", "missing-section-title-path", "missing-domain-tags"],
}

ENVELOPE = {
    "format": "reqbot-checklist",
    "format_version": "1.0",
    "generated_at": "2026-07-19T12:00:00+00:00",
    "generator": {"tool": "reqbot", "command": "reqbot checklist --doc test-doc --profile cybersecurity"},
    "document": {"document_id": "abc123", "source_pdf": "test-doc.pdf"},
    "profile": "cybersecurity",
    "summary": {"total_items": 2, "items_requiring_review": 1},
    "items": [COMPLETE_ITEM, REVIEW_ITEM],
}

EMPTY_ENVELOPE = {**ENVELOPE, "summary": {"total_items": 0, "items_requiring_review": 0}, "items": []}


# --- _csv_row ---

def test_csv_row_array_joins():
    row = _csv_row(COMPLETE_ITEM)
    assert row["section_title_path"] == "Access Control > MFA Policy"
    assert row["page_refs"] == "12, 13"
    assert row["requirement_ids"] == "REQ-abc123"
    assert row["domain_tags"] == "access-control, authentication"


def test_csv_row_review_reasons_semicolon_join():
    row = _csv_row(REVIEW_ITEM)
    assert "missing-source-ref" in row["review_reasons"]
    assert ";" in row["review_reasons"]


def test_csv_row_empty_arrays_produce_empty_strings():
    row = _csv_row(REVIEW_ITEM)
    assert row["section_title_path"] == ""
    assert row["page_refs"] == ""
    assert row["domain_tags"] == ""
    assert row["review_reasons"].count(";") >= 1  # multiple reasons joined


def test_csv_row_none_arrays_produce_empty_strings():
    item = {**COMPLETE_ITEM, "section_title_path": None, "page_refs": None, "domain_tags": None, "review_reasons": None}
    row = _csv_row(item)
    assert row["section_title_path"] == ""
    assert row["page_refs"] == ""
    assert row["domain_tags"] == ""
    assert row["review_reasons"] == ""


# --- to_csv ---

def test_to_csv_returns_string():
    result = to_csv(ENVELOPE)
    assert isinstance(result, str)


def test_to_csv_column_order():
    result = to_csv(ENVELOPE)
    reader = csv.reader(io.StringIO(result))
    header = next(reader)
    assert header == _CSV_COLUMNS


def test_to_csv_row_count():
    result = to_csv(ENVELOPE)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 3  # header + 2 items


def test_to_csv_empty_items():
    result = to_csv(EMPTY_ENVELOPE)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 1  # header only


def test_to_csv_source_quote_present():
    result = to_csv(ENVELOPE)
    assert "The system shall enforce MFA" in result


def test_to_csv_requires_human_review_serialized():
    result = to_csv(ENVELOPE)
    assert "False" in result
    assert "True" in result


def test_to_csv_confidence_in_output():
    result = to_csv(ENVELOPE)
    assert "0.9" in result


def test_to_csv_no_crash_on_missing_item_fields():
    sparse_item = {"requirement_ids": ["REQ-001"], "source_quote": "Minimal."}
    checklist = {**EMPTY_ENVELOPE, "items": [sparse_item]}
    result = to_csv(checklist)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 2


# --- to_json ---

def test_to_json_returns_valid_json():
    result = to_json(ENVELOPE)
    parsed = json.loads(result)
    assert parsed["format"] == "reqbot-checklist"


def test_to_json_roundtrip_preserves_items():
    result = to_json(ENVELOPE)
    parsed = json.loads(result)
    assert len(parsed["items"]) == 2


def test_to_json_is_pretty_printed():
    result = to_json(ENVELOPE)
    assert "\n" in result


def test_to_json_empty_items():
    result = to_json(EMPTY_ENVELOPE)
    parsed = json.loads(result)
    assert parsed["items"] == []


def test_to_json_preserves_envelope_fields():
    result = to_json(ENVELOPE)
    parsed = json.loads(result)
    assert parsed["profile"] == "cybersecurity"
    assert parsed["document"]["source_pdf"] == "test-doc.pdf"


# --- to_markdown ---

def test_to_markdown_returns_string():
    result = to_markdown(ENVELOPE)
    assert isinstance(result, str)


def test_to_markdown_title_includes_source_pdf():
    result = to_markdown(ENVELOPE)
    assert "test-doc.pdf" in result


def test_to_markdown_profile_present():
    result = to_markdown(ENVELOPE)
    assert "cybersecurity" in result


def test_to_markdown_source_quote_present():
    result = to_markdown(ENVELOPE)
    assert "The system shall enforce MFA" in result


def test_to_markdown_section_title_path_in_heading():
    result = to_markdown(ENVELOPE)
    assert "Access Control" in result
    assert "MFA Policy" in result


def test_to_markdown_page_refs_in_heading():
    result = to_markdown(ENVELOPE)
    assert "p. 12" in result


def test_to_markdown_review_flag_shown_for_flagged_item():
    result = to_markdown(ENVELOPE)
    assert "Requires Review" in result
    assert "low-confidence" in result


def test_to_markdown_no_review_flag_for_clean_item():
    result = to_markdown({**EMPTY_ENVELOPE, "items": [COMPLETE_ITEM]})
    # Verify the item itself rendered (not just an empty list)
    assert "The system shall enforce MFA" in result
    assert "Requires Review" not in result


def test_to_markdown_audit_question_blank_shows_not_generated():
    result = to_markdown(ENVELOPE)
    assert "*(not generated)*" in result


def test_to_markdown_audit_question_shown_when_present():
    item = {**COMPLETE_ITEM, "audit_question": "Has MFA been enforced?"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_markdown(checklist)
    assert "Has MFA been enforced?" in result


def test_to_markdown_empty_items_no_crash():
    result = to_markdown(EMPTY_ENVELOPE)
    assert "test-doc.pdf" in result
    assert "0 total" in result


def test_to_markdown_item_id_and_req_id_in_output():
    result = to_markdown(ENVELOPE)
    assert "CHK-abcdef1234567890" in result
    assert "REQ-abc123" in result


def test_to_markdown_no_source_pdf_falls_back_to_document_id():
    checklist = {**EMPTY_ENVELOPE, "document": {"document_id": "abc123", "source_pdf": ""}}
    result = to_markdown(checklist)
    assert "abc123" in result


def test_to_markdown_null_confidence_renders_as_zero():
    item = {**COMPLETE_ITEM, "confidence": None}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_markdown(checklist)
    assert "0.00" in result


# --- _csv_safe (formula injection prevention) ---

def test_csv_safe_equals_prefix_escaped():
    assert _csv_safe("=SUM(A1:A10)") == "'=SUM(A1:A10)"


def test_csv_safe_plus_prefix_escaped():
    assert _csv_safe("+1234") == "'+1234"


def test_csv_safe_minus_prefix_escaped():
    assert _csv_safe("-DROP TABLE") == "'-DROP TABLE"


def test_csv_safe_at_prefix_escaped():
    assert _csv_safe("@user") == "'@user"


def test_csv_safe_whitespace_then_formula_escaped():
    assert _csv_safe("  =dangerous") == "'  =dangerous"


def test_csv_safe_tab_then_formula_escaped():
    assert _csv_safe("\t=foo") == "'\t=foo"


def test_csv_safe_normal_text_unchanged():
    assert _csv_safe("Systems must enforce MFA.") == "Systems must enforce MFA."


def test_csv_safe_empty_string_unchanged():
    assert _csv_safe("") == ""


def test_csv_safe_whitespace_only_unchanged():
    assert _csv_safe("   ") == "   "


def test_csv_safe_nonstring_bool_unchanged():
    assert _csv_safe(True) is True


def test_csv_safe_nonstring_float_unchanged():
    assert _csv_safe(0.9) == 0.9


# --- CSV formula injection integration ---

def test_to_csv_formula_source_quote_escaped():
    item = {**COMPLETE_ITEM, "source_quote": "=HYPERLINK(\"http://evil.example\",\"click\")"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_csv(checklist)
    assert "'=HYPERLINK" in result


def test_to_csv_formula_source_ref_escaped():
    item = {**COMPLETE_ITEM, "source_ref": "+1.2.3"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_csv(checklist)
    assert "'+1.2.3" in result


def test_to_json_formula_value_not_escaped():
    """JSON export must not mutate the checklist envelope."""
    item = {**COMPLETE_ITEM, "source_quote": "=dangerous"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_json(checklist)
    parsed = json.loads(result)
    assert parsed["items"][0]["source_quote"] == "=dangerous"


def test_to_markdown_formula_value_not_escaped():
    """Markdown export must not apply CSV escaping."""
    item = {**COMPLETE_ITEM, "source_quote": "=Systems shall enforce MFA."}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    result = to_markdown(checklist)
    assert "=Systems shall enforce MFA." in result
    assert "'=Systems" not in result


# --- to_xlsx ---

def _load_xlsx(data: bytes):
    """Helper: load xlsx bytes as an openpyxl workbook."""
    return openpyxl.load_workbook(io.BytesIO(data))


def _col(ws, header: str) -> int:
    """The column number of a header in the sheet's header row (row 4)."""
    return next(c for c in range(1, ws.max_column + 1) if ws.cell(row=4, column=c).value == header)


def test_to_xlsx_returns_bytes():
    result = to_xlsx(ENVELOPE)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_to_xlsx_opens_as_workbook():
    result = to_xlsx(ENVELOPE)
    wb = _load_xlsx(result)
    assert wb is not None


def test_to_xlsx_sheet_name():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    assert "Checklist" in wb.sheetnames


def test_to_xlsx_group_headers_in_row_3():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    group_values = [ws.cell(row=3, column=c).value for c in range(1, 14)]  # rows 1 and 2 are the document's name and the facts about the sheet
    assert [g for g in group_values if g] == ["Ask", "Record", "Context", "Locate", "Trace"]


def test_to_xlsx_column_order():
    # the owner's order: what to check, the question, where to write the finding, the surrounding text, where to find it, then the trace
    expected_headers = [
        "Review",
        "Requirement", "Audit Question (draft)",
        "Status", "Notes", "Check",
        "Passage (click to read all)",
        "Ref", "Pages",
        "Item ID", "Req IDs", "Conf.", "Tags",
    ]
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    actual = [ws.cell(row=4, column=c).value for c in range(1, 14)]
    assert actual == expected_headers
    assert ws.max_column == 13


def test_to_xlsx_leaves_section_applies_to_parent_and_reasons_off_the_sheet_but_not_off_the_other_exports():
    headers = [c.value for c in _load_xlsx(to_xlsx(ENVELOPE))["Checklist"][4]]
    for gone in ("Section", "Applies to", "Parent para.", "Reasons"):
        assert gone not in headers
    csv_header = next(csv.reader(io.StringIO(to_csv(ENVELOPE))))
    assert {"section_title_path", "applies_to", "parent_paragraph", "review_reasons"} <= set(csv_header)


def test_to_xlsx_keeps_the_trace_ids_but_small_and_narrow():
    ws = _load_xlsx(to_xlsx(ENVELOPE))["Checklist"]
    for header in ("Item ID", "Req IDs"):
        col = _col(ws, header)
        assert ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width <= 12
        assert ws.cell(row=5, column=col).font.size == 8


def test_to_xlsx_freeze_panes():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    assert ws.freeze_panes == "C5"  # the marker and the requirement stay in view; the headers stay on top


def test_to_xlsx_auto_filter_covers_data_rows():
    # ENVELOPE has 2 items → 4 title and header rows + 2 data rows = max_row 6; the filter starts at the column headers (row 4) and must end at row 6
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    assert ws.auto_filter.ref == "A4:M6", f"expected the filter on A4:M6, got {ws.auto_filter.ref}"


def test_to_xlsx_auto_filter_empty_checklist_is_the_header_row_alone():
    wb = _load_xlsx(to_xlsx(EMPTY_ENVELOPE))
    ws = wb["Checklist"]
    assert ws.auto_filter.ref is not None
    assert ws.auto_filter.ref == "A4:M4", f"expected the filter on the header row alone, got {ws.auto_filter.ref}"


def test_to_xlsx_status_data_validation_exists():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    assert len(ws.data_validations.dataValidation) > 0


def test_to_xlsx_row_count():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    # 4 title and header rows + 2 data rows
    assert ws.max_row == 6


def test_to_xlsx_source_quote_present():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    all_values = [ws.cell(row=r, column=_col(ws, "Requirement")).value for r in range(5, ws.max_row + 1)]
    assert any("enforce MFA" in str(v) for v in all_values if v)


def test_to_xlsx_empty_items_no_crash():
    result = to_xlsx(EMPTY_ENVELOPE)
    wb = _load_xlsx(result)
    ws = wb["Checklist"]
    assert ws.max_row == 4  # only the title and header rows


def test_to_xlsx_flagged_row_has_a_filled_marker_cell_and_no_row_shading():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    # REVIEW_ITEM is second data row (row 6); COMPLETE_ITEM is row 5
    assert ws.cell(row=6, column=1).value == "!"
    assert ws.cell(row=6, column=1).fill.patternType == "solid"
    assert ws.cell(row=5, column=1).value in (None, "")
    assert ws.cell(row=5, column=1).fill.patternType is None
    # the rest of the row is left to the alternating stripes: no static fill on any other cell
    assert all(ws.cell(row=6, column=c).fill.patternType is None for c in range(2, 14))


def test_to_xlsx_confidence_percentage_format():
    wb = _load_xlsx(to_xlsx(ENVELOPE))
    ws = wb["Checklist"]
    conf_cell = ws.cell(row=5, column=_col(ws, "Conf."))
    assert conf_cell.number_format == "0%"


def test_to_xlsx_formula_injection_protection():
    item = {**COMPLETE_ITEM, "source_quote": "=HYPERLINK(\"http://evil.example\",\"click\")"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    wb = _load_xlsx(to_xlsx(checklist))
    ws = wb["Checklist"]
    value = ws.cell(row=5, column=_col(ws, "Requirement")).value
    assert value is not None
    assert str(value).startswith("'")


def test_to_xlsx_sparse_item_no_crash():
    sparse = {"requirement_ids": ["REQ-001"], "source_quote": "Minimal requirement."}
    checklist = {**EMPTY_ENVELOPE, "items": [sparse]}
    result = to_xlsx(checklist)
    wb = _load_xlsx(result)
    assert wb["Checklist"].max_row == 5


def test_audit_layout_fields_reach_every_export_format():
    item = {**COMPLETE_ITEM, "applies_to": "AF/A3", "parent_ref": "2.17", "parent_text": "MAJCOM/DRUs.", "passage": "Lead-in:\n>> The requirement. <<", "item_flags": ["list_item", "no_passage"]}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    row = next(csv.DictReader(io.StringIO(to_csv(checklist))))
    assert row["applies_to"] == "AF/A3" and row["passage"].startswith("Lead-in:") and row["item_flags"] == "list_item; no_passage"
    assert row["parent_paragraph"] == "2.17 MAJCOM/DRUs."
    md = to_markdown(checklist)
    assert "**Applies to:** AF/A3" in md and "**Parent paragraph:** 2.17 MAJCOM/DRUs." in md and ">> The requirement. <<" in md and "**Check:** list_item, no_passage" in md
    ws = _load_xlsx(to_xlsx(checklist))["Checklist"]
    assert [ws.cell(row=5, column=_col(ws, h)).value for h in ("Passage (click to read all)", "Check")] == ["Lead-in:\n>> The requirement. <<", "list_item; no_passage"]
    status_cell = ws.cell(row=5, column=_col(ws, "Status"))
    assert status_cell.value == item["status"] and any(status_cell.coordinate in dv.sqref for dv in ws.data_validations.dataValidation)


def test_old_items_without_the_new_fields_still_export():
    old = {k: v for k, v in COMPLETE_ITEM.items() if k not in ("applies_to", "passage", "item_flags")}
    checklist = {**EMPTY_ENVELOPE, "items": [old]}
    assert "source_quote" in to_csv(checklist) and "Checklist" in to_markdown(checklist)
    assert _load_xlsx(to_xlsx(checklist))["Checklist"].max_row == 5


def test_sheet_marks_only_rows_with_a_specific_reason_not_low_confidence_alone():
    only_confidence = {**COMPLETE_ITEM, "requires_human_review": True, "review_reasons": ["low-confidence"], "item_flags": []}
    flagged = {**COMPLETE_ITEM, "checklist_item_id": "CHK-2", "requires_human_review": True, "review_reasons": ["low-confidence"], "item_flags": ["table_fragment"]}
    ws = _load_xlsx(to_xlsx({**EMPTY_ENVELOPE, "items": [only_confidence, flagged]}))["Checklist"]
    assert ws.cell(row=5, column=1).value in (None, "") and ws.cell(row=5, column=1).fill.patternType is None
    assert ws.cell(row=6, column=1).value == "!" and ws.cell(row=6, column=1).fill.patternType == "solid"
    headers = [c.value for c in ws[4]]
    assert "Flag" not in headers  # a column that is Yes on every row says nothing
    assert "Reasons" not in headers
    assert all("low-confidence" not in str(c.value) for row in ws.iter_rows(min_row=5) for c in row)


def test_the_citation_is_what_the_sheet_and_markdown_show_in_the_ref_position():
    item = {**COMPLETE_ITEM, "source_ref": "(T-2)", "citation": "3.4.4.3 (inferred)"}
    checklist = {**EMPTY_ENVELOPE, "items": [item]}
    row = next(csv.DictReader(io.StringIO(to_csv(checklist))))
    assert row["source_ref"] == "(T-2)" and row["citation"] == "3.4.4.3 (inferred)"  # the extracted value is never replaced in the data
    assert "**Source Ref:** 3.4.4.3 (inferred)" in to_markdown(checklist)
    ws = _load_xlsx(to_xlsx(checklist))["Checklist"]
    assert ws.cell(row=5, column=_col(ws, "Ref")).value == "3.4.4.3 (inferred)"


def test_xlsx_hides_the_tags_and_confidence_columns_when_no_row_has_a_value():
    from io import BytesIO

    from openpyxl import load_workbook

    base = {"checklist_item_id": "CHK-1", "requirement_ids": ["REQ-1"], "source_ref": "1.1", "page_refs": [1], "section_title_path": ["A"], "source_quote": "Systems must log.",
            "item_flags": [], "review_reasons": [], "status": "not-started", "assessor_notes": "", "audit_question": "", "applies_to": "", "parent_text": "", "passage": ""}

    def hidden(item):
        ws = load_workbook(BytesIO(to_xlsx({"items": [item], "possible_missed": [], "summary": {}, "document": {}}))).active
        letters = [openpyxl.utils.get_column_letter(_col(ws, h)) for h in ("Conf.", "Tags")]
        return ws.column_dimensions[letters[0]].hidden, ws.column_dimensions[letters[1]].hidden

    assert hidden({**base, "domain_tags": [], "confidence": None}) == (True, True)
    assert hidden({**base, "domain_tags": ["x"], "confidence": 0.9}) == (False, False)


# --- the look of the sheet ---

def _sheet(checklist):
    return _load_xlsx(to_xlsx(checklist))["Checklist"]


def test_the_sheet_says_which_document_it_is_and_the_facts_about_it():
    checklist = {**ENVELOPE, "document": {"source_pdf": "afi17-203.pdf"}, "profile": "cybersecurity", "generated_at": "2026-10-11T15:04:12+00:00"}
    ws = _sheet(checklist)
    assert ws["A1"].value == "Audit checklist: afi17-203.pdf"
    facts = ws["A2"].value
    assert "Profile: cybersecurity" in facts and "Generated: 2026-10-11 15:04 UTC" in facts and "2 items" in facts
    assert "of them flagged (!) for a second look" in facts  # ENVELOPE has one row with a specific reason; the count is of the extracted items


def test_the_title_falls_back_to_the_document_id_and_the_facts_survive_a_bare_envelope():
    ws = _sheet({"items": [], "possible_missed": [], "summary": {}, "document": {"document_id": "abc123"}})
    assert ws["A1"].value == "Audit checklist: abc123"
    ws = _sheet({"items": [], "possible_missed": [], "summary": {}, "document": {}})
    assert ws["A1"].value == "Audit checklist: Unknown document"
    assert ws["A2"].value == "0 items"


def test_a_time_that_cannot_be_read_is_shown_as_it_is():
    ws = _sheet({**EMPTY_ENVELOPE, "generated_at": "yesterday afternoon"})
    assert "Generated: yesterday afternoon" in ws["A2"].value


def test_a_document_name_that_looks_like_a_formula_is_not_one():
    ws = _sheet({**EMPTY_ENVELOPE, "document": {"source_pdf": "=HYPERLINK(\"http://evil.example\")"}})
    assert not str(ws["A1"].value).startswith("=")
    assert str(ws["A1"].value).startswith("Audit checklist: ")


def test_each_column_group_has_its_own_color_and_the_headers_carry_the_lighter_shade():
    ws = _sheet(ENVELOPE)
    bands = {ws.cell(row=3, column=c).value: ws.cell(row=3, column=c).fill.fgColor.rgb for c in (1, 4, 7, 8, 10)}
    assert list(bands) == ["Ask", "Record", "Context", "Locate", "Trace"]
    assert len(set(bands.values())) == 5
    assert ws.cell(row=3, column=1).font.color.rgb.endswith("FFFFFF")
    # a header sits under its group and is shaded in the group's lighter tint, so the groups read down the page
    assert ws.cell(row=4, column=1).fill.fgColor.rgb == ws.cell(row=4, column=3).fill.fgColor.rgb != ws.cell(row=4, column=4).fill.fgColor.rgb
    assert ws.cell(row=4, column=1).font.bold


def test_the_audit_question_column_has_room():
    ws = _sheet(ENVELOPE)
    col = openpyxl.utils.get_column_letter(_col(ws, "Audit Question (draft)"))
    assert ws.column_dimensions[col].width >= 40  # the column people read most was 22 characters wide


def test_the_status_cell_is_colored_by_what_is_chosen():
    ws = _sheet(ENVELOPE)
    rules = [r for ranges in ws.conditional_formatting for r in ranges.rules if r.type == "cellIs"]  # the stripes are expression rules, tested on their own
    wanted = {r.formula[0].strip('"') for r in rules}
    assert wanted == {"compliant", "non-compliant", "in-progress", "not-applicable"}
    assert any("D5" in str(rng.sqref) for rng in ws.conditional_formatting)  # the Status column


def test_the_sheet_prints_landscape_with_the_headers_repeated_and_the_document_in_the_footer():
    ws = _sheet({**ENVELOPE, "document": {"source_pdf": "Q&A policy.pdf"}})
    assert ws.page_setup.orientation == "landscape"
    assert ws.print_title_rows == "$3:$4"  # absolute, as Excel stores it
    assert ws.oddFooter.left.text == "Q&&A policy.pdf"  # an ampersand is a code in a footer, so it is doubled
    assert "Page &P of &N" in ws.oddFooter.right.text


def test_the_possible_missed_block_has_a_colored_banner():
    checklist = {**ENVELOPE, "possible_missed": [{**COMPLETE_ITEM, "checklist_item_id": "MISS-1"}]}
    ws = _sheet(checklist)
    banner = next(r for r in range(5, ws.max_row + 1) if str(ws.cell(row=r, column=1).value or "").startswith("POSSIBLE MISSED"))
    assert ws.cell(row=banner, column=1).fill.patternType == "solid"
    assert "1 possible missed" in ws["A2"].value


def test_the_facts_count_flagged_items_apart_from_the_possible_missed_block():
    flagged = {**COMPLETE_ITEM, "checklist_item_id": "CHK-F", "item_flags": ["table_fragment"]}
    missed = {**COMPLETE_ITEM, "checklist_item_id": "MISS-1", "item_flags": ["possible_missed"]}
    facts = _sheet({**EMPTY_ENVELOPE, "items": [flagged], "possible_missed": [missed]})["A2"].value
    assert "1 item · 1 of them flagged (!) for a second look · 1 possible missed, listed at the bottom" in facts
    only_missed = _sheet({**EMPTY_ENVELOPE, "items": [], "possible_missed": [missed]})["A2"].value
    assert "0 items" in only_missed and "of them flagged" not in only_missed and "1 possible missed" in only_missed


# --- row height ---

def _row_heights(item: dict) -> tuple[float, str]:
    ws = _sheet({**EMPTY_ENVELOPE, "items": [item]})
    return ws.row_dimensions[5].height, ws.cell(row=5, column=_col(ws, "Passage (click to read all)")).value


def test_a_huge_passage_does_not_make_the_row_tall_and_is_kept_whole_in_its_cell():
    passage = "Lead-in text. " * 300  # about 4,000 characters
    short = {**COMPLETE_ITEM, "source_quote": "Units shall log access.", "audit_question": "Do units log access?", "passage": passage, "item_flags": []}
    height, kept = _row_heights(short)
    assert height <= 4 * 13 + 4  # a couple of lines, not 80
    assert kept == passage  # nothing is cut from the data: the cell still holds all of it


def test_a_row_is_as_tall_as_its_requirement_or_its_question_needs():
    long_quote = "The commander shall ensure that every member completes the required training before access is granted. " * 4
    long_question = "Do all members complete the required training before access is granted, and is that recorded? " * 6
    base = {**COMPLETE_ITEM, "item_flags": [], "passage": "x " * 2000, "assessor_notes": ""}
    quote_h, _ = _row_heights({**base, "source_quote": long_quote, "audit_question": "Short?"})
    question_h, _ = _row_heights({**base, "source_quote": "Short.", "audit_question": long_question})
    both_short_h, _ = _row_heights({**base, "source_quote": "Short.", "audit_question": "Short?"})
    assert quote_h > both_short_h and question_h > both_short_h
    assert quote_h >= (len(long_quote) // 48) * 13  # about as many lines as the text needs in a 48-wide column


def test_a_row_has_at_least_two_lines_and_never_more_than_excel_allows():
    empty_h, _ = _row_heights({**COMPLETE_ITEM, "source_quote": "", "audit_question": "", "item_flags": [], "passage": ""})
    assert empty_h == 2 * 13 + 4
    huge_h, _ = _row_heights({**COMPLETE_ITEM, "source_quote": "word " * 20000, "audit_question": ""})
    assert huge_h <= 409.5


def test_the_possible_missed_rows_are_capped_the_same_way():
    missed = {**COMPLETE_ITEM, "checklist_item_id": "MISS-1", "item_flags": ["possible_missed"], "source_quote": "Short.", "audit_question": "", "passage": "p " * 3000}
    ws = _sheet({**EMPTY_ENVELOPE, "items": [], "possible_missed": [missed]})
    last = ws.max_row
    assert ws.row_dimensions[last].height <= 4 * 13 + 4


# --- the review marker and the alternating stripes ---

def test_rows_alternate_by_a_rule_that_follows_sorting_and_filtering():
    ws = _sheet(ENVELOPE)
    stripes = [(str(rng.sqref), r) for rng in ws.conditional_formatting for r in rng.rules if r.type == "expression"]
    assert stripes, "no alternating-row rule"
    assert all("SUBTOTAL(103" in r.formula[0] and "MOD(" in r.formula[0] for _s, r in stripes)  # counts the rows still showing, so a filter keeps the stripes even
    covered = {rng for rng, _r in stripes}
    assert any(rng.startswith("B5:") for rng in covered)  # every column after the marker
    assert any(rng.startswith("A5:A") for rng in covered)  # the marker column too, where it is empty


def test_the_status_colors_outrank_the_stripes():
    ws = _sheet(ENVELOPE)
    status = [r.priority for rng in ws.conditional_formatting for r in rng.rules if r.type == "cellIs"]
    stripe = [r.priority for rng in ws.conditional_formatting for r in rng.rules if r.type == "expression"]
    assert status and stripe and max(status) < min(stripe)  # a lower number wins


def test_the_marker_column_is_narrow_and_says_what_it_is():
    ws = _sheet(ENVELOPE)
    assert ws.cell(row=4, column=1).value == "Review"
    assert ws.column_dimensions["A"].width <= 8
    assert "(!)" in ws["A2"].value  # the facts line says what the mark means


def test_a_possible_missed_row_carries_the_marker_too():
    missed = {**COMPLETE_ITEM, "checklist_item_id": "MISS-1", "item_flags": ["possible_missed"]}
    ws = _sheet({**EMPTY_ENVELOPE, "items": [], "possible_missed": [missed]})
    assert ws.cell(row=ws.max_row, column=1).value == "!"

