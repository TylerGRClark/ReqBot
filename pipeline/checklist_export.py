"""Checklist export — serialize a checklist envelope dict to CSV, JSON, Markdown, or XLSX.

Input:  the dict returned by services/checklist_service.py::generate()
Output: a string (CSV/JSON/Markdown) or bytes (XLSX); caller writes to file or stdout.

All display and export logic lives here and in cli/reqbot.py (WP-21.5).
"""
import csv
import io
import json

# CSV column order: locate → ask → record → verify → trace
_CSV_COLUMNS = [
    "source_ref",
    "citation",
    "section_title_path",
    "page_refs",
    "applies_to",
    "parent_paragraph",
    "source_quote",
    "passage",
    "audit_question",
    "status",
    "assessor_notes",
    "item_flags",
    "requires_human_review",
    "review_reasons",
    "confidence",
    "checklist_item_id",
    "requirement_ids",
    "domain_tags",
]


_FORMULA_CHARS = frozenset("=+-@")


def _join(values: list, sep: str) -> str:
    return sep.join(str(v) for v in values)


def _csv_safe(value: object) -> object:
    """Prefix formula-like string cells with a single quote to block spreadsheet injection.

    Excel and LibreOffice treat cells whose effective first character is =, +, -, or @
    as formulas regardless of CSV quoting. Prefixing with ' is the standard mitigation.
    Non-string values (bool, float) are returned unchanged.
    """
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped and stripped[0] in _FORMULA_CHARS:
            return "'" + value
    return value


def _needs_attention(item: dict) -> bool:
    """A row worth a reader's second look in the sheet: a specific hint (item_flags) or a missing citation/tag. Confidence alone no longer shades every row (the pipeline's
    confidence is below the review threshold on nearly every record, so it separated nothing); the number itself stays in its column and `requires_human_review` stays in JSON."""
    if item.get("item_flags"):
        return True
    return any(r != "low-confidence" for r in (item.get("review_reasons") or []))


def _sheet_reasons(item: dict) -> list:
    """The reasons worth showing on the sheet: low confidence is left out (it is true of nearly every row, so it says nothing; the number stays in the Conf. column)."""
    return [r for r in (item.get("review_reasons") or []) if r != "low-confidence"]


def _ref(item: dict) -> str:
    """The citation to show: the paragraph citation (possibly inferred and marked so), else whatever the extractor recorded."""
    return item.get("citation") or item.get("source_ref") or ""


def _parent_label(item: dict) -> str:
    """"2.17 MAJCOM/DRUs." : the parent paragraph's number and its text, copied from the document; empty when there is none."""
    text = item.get("parent_text") or ""
    return f"{item.get('parent_ref', '')} {text}".strip() if text else ""


def _csv_row(item: dict) -> dict:
    raw = {
        "source_ref": item.get("source_ref", ""),
        "citation": item.get("citation", ""),
        "section_title_path": _join(item.get("section_title_path") or [], " > "),
        "page_refs": _join(item.get("page_refs") or [], ", "),
        "applies_to": item.get("applies_to", ""),
        "parent_paragraph": _parent_label(item),
        "source_quote": item.get("source_quote", ""),
        "passage": item.get("passage", ""),
        "audit_question": item.get("audit_question", ""),
        "status": item.get("status", ""),
        "assessor_notes": item.get("assessor_notes", ""),
        "item_flags": _join(item.get("item_flags") or [], "; "),
        "requires_human_review": item.get("requires_human_review", False),
        "review_reasons": _join(item.get("review_reasons") or [], "; "),
        "confidence": item.get("confidence", 0.0),
        "checklist_item_id": item.get("checklist_item_id", ""),
        "requirement_ids": _join(item.get("requirement_ids") or [], ", "),
        "domain_tags": _join(item.get("domain_tags") or [], ", "),
    }
    return {k: _csv_safe(v) for k, v in raw.items()}


def to_csv(checklist: dict) -> str:
    """Return the checklist items as a CSV string (UTF-8, Excel-friendly)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for item in checklist.get("items", []) + checklist.get("possible_missed", []):
        writer.writerow(_csv_row(item))
    return buf.getvalue()


def to_json(checklist: dict) -> str:
    """Return the full checklist envelope as a pretty-printed JSON string."""
    return json.dumps(checklist, indent=2, default=str)


def _md_item(item: dict, index: int) -> str:
    section = _join(item.get("section_title_path") or [], " > ")
    pages = _join(item.get("page_refs") or [], ", ")
    header_parts = []
    if section:
        header_parts.append(section)
    if pages:
        header_parts.append(f"p. {pages}")
    heading = " — ".join(header_parts) if header_parts else f"Item {index}"

    lines = [f"## {heading}", ""]

    source_ref = _ref(item)
    if source_ref:
        lines.append(f"**Source Ref:** {source_ref}  ")
    tags = _join(item.get("domain_tags") or [], ", ")
    if tags:
        lines.append(f"**Domain Tags:** {tags}  ")
    conf = item.get("confidence")
    if conf is None:
        conf = 0.0
    lines.append(f"**Confidence:** {conf:.2f}  ")
    lines.append("")

    applies = item.get("applies_to", "")
    if applies:
        lines.append(f"**Applies to:** {applies}  ")
    parent = _parent_label(item)
    if parent:
        lines.append(f"**Parent paragraph:** {parent}  ")
    if applies or parent:
        lines.append("")
    quote = item.get("source_quote", "")
    lines.append(f"> {quote}")
    lines.append("")
    passage = item.get("passage", "")
    if passage:
        lines.append("**Passage** (the requirement is marked >> <<):")
        lines.append("")
        lines.extend(f"    {ln}" for ln in passage.splitlines())
        lines.append("")
    flags = _join(item.get("item_flags") or [], ", ")
    if flags:
        lines.append(f"**Check:** {flags}  ")
        lines.append("")

    audit_q = item.get("audit_question", "")
    lines.append(f"**Audit Question:** {audit_q if audit_q else '*(not generated)*'}  ")

    status = item.get("status", "not-started")
    assessor = item.get("assessor_notes", "")
    lines.append(f"**Status:** {status}  ")
    lines.append(f"**Assessor Notes:** {assessor if assessor else '*(none)*'}  ")
    lines.append("")

    if item.get("requires_human_review"):
        reasons = _join(item.get("review_reasons") or [], "; ")
        lines.append(f"> ⚠ **Requires Review:** {reasons}  ")
        lines.append("")

    req_ids = _join(item.get("requirement_ids") or [], ", ")
    lines.append(f"*ID: {item.get('checklist_item_id', '')} | Req: {req_ids}*")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def to_xlsx(checklist: dict) -> bytes:
    """Return the checklist items as an Excel workbook (XLSX) in bytes.

    Requires openpyxl (approved WP-23.2 dependency).
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    # Column definitions: (display_header, item_key, col_width, wrap_text)
    _COLS = [
        ("Ref",            "source_ref",            14, False),
        ("Section",        "section_title_path",     28, False),
        ("Pages",          "page_refs",               9, False),
        ("Applies to",     "applies_to",             24, True),
        ("Parent para.",   "parent_text",            30, True),
        ("Requirement",    "source_quote",            36, True),
        ("Passage",        "passage",                 52, True),
        ("Audit Question", "audit_question",          22, True),
        ("Status",         "status",                  15, False),
        ("Notes",          "assessor_notes",          22, True),
        ("Check",          "item_flags",              20, False),
        ("Reasons",        "review_reasons",          22, False),
        ("Conf.",          "confidence",               7, False),
        ("Item ID",        "checklist_item_id",       26, False),
        ("Req IDs",        "requirement_ids",         20, False),
        ("Tags",           "domain_tags",             20, False),
    ]

    # Column groups: (label, first_col_1based, last_col_1based)
    _GROUPS = [
        ("Locate",  1,  5),
        ("Ask",     6,  8),
        ("Record",  9, 10),
        ("Verify", 11, 13),
        ("Trace",  14, 16),
    ]

    _GROUP_FILL = PatternFill("solid", fgColor="E2E8F0")
    _FLAGGED_FILL = PatternFill("solid", fgColor="FFFBEB")
    _HEADER_FONT = Font(bold=True, size=9)

    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"

    # Row 1: group header row
    for label, c_start, c_end in _GROUPS:
        cell = ws.cell(row=1, column=c_start, value=label)
        cell.font = _HEADER_FONT
        cell.fill = _GROUP_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if c_start != c_end:
            ws.merge_cells(
                start_row=1, start_column=c_start,
                end_row=1, end_column=c_end,
            )

    # Row 2: column header row
    for col_idx, (header, _, _, _) in enumerate(_COLS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _GROUP_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center")

    # Freeze panes below both header rows, after Locate group (3 cols)
    ws.freeze_panes = "D3"

    # Status column data validation (dropdown)
    dv = DataValidation(
        type="list",
        formula1='"not-started,in-progress,compliant,non-compliant,not-applicable"',
        allow_blank=True,
    )
    ws.add_data_validation(dv)

    # Column widths
    for col_idx, (_, _, width, _) in enumerate(_COLS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows
    def write_item(item):
        flagged = _needs_attention(item)
        row_fill = _FLAGGED_FILL if flagged else None
        confidence_val = item.get("confidence") or 0.0

        values = [
            _csv_safe(_ref(item)),
            _csv_safe(_join(item.get("section_title_path") or [], " > ")),
            _csv_safe(_join(item.get("page_refs") or [], ", ")),
            _csv_safe(item.get("applies_to") or ""),
            _csv_safe(_parent_label(item)),
            _csv_safe(item.get("source_quote") or ""),
            _csv_safe(item.get("passage") or ""),
            _csv_safe(item.get("audit_question") or ""),
            _csv_safe(item.get("status") or ""),
            _csv_safe(item.get("assessor_notes") or ""),
            _csv_safe(_join(item.get("item_flags") or [], "; ")),
            _csv_safe(_join(_sheet_reasons(item), "; ")),
            confidence_val,
            _csv_safe(item.get("checklist_item_id") or ""),
            _csv_safe(_join(item.get("requirement_ids") or [], ", ")),
            _csv_safe(_join(item.get("domain_tags") or [], ", ")),
        ]

        row_num = ws.max_row + 1
        for col_idx, (_, _, _, wrap) in enumerate(_COLS, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=values[col_idx - 1])
            cell.alignment = Alignment(vertical="top", wrap_text=wrap)
            if row_fill:
                cell.fill = row_fill

        # Confidence as percentage (value is 0–1 float)
        ws.cell(row=row_num, column=13).number_format = "0%"
        # Status: register with data validation
        dv.add(ws.cell(row=row_num, column=9))

    for item in checklist.get("items", []):
        write_item(item)

    # Auto-filter covers the extracted rows only; the possible-missed section below is separate
    last_item_row = ws.max_row

    missed = checklist.get("possible_missed", [])
    if missed:
        banner_row = ws.max_row + 2
        banner = ws.cell(
            row=banner_row, column=1,
            value=f"POSSIBLE MISSED REQUIREMENTS ({len(missed)}): found in the document text but not extracted. Confirm each; they are not counted above.",
        )
        banner.font = Font(bold=True, size=10)
        ws.merge_cells(start_row=banner_row, start_column=1, end_row=banner_row, end_column=len(_COLS))
        for item in missed:
            write_item(item)

    # Auto-filter: set after rows are written so range covers all data rows
    ws.auto_filter.ref = f"A2:{get_column_letter(len(_COLS))}{last_item_row}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_markdown(checklist: dict) -> str:
    """Return the checklist as a Markdown string."""
    doc = checklist.get("document", {})
    source_pdf = doc.get("source_pdf", "")
    title = source_pdf if source_pdf else doc.get("document_id", "Unknown Document")

    summary = checklist.get("summary", {})
    total = summary.get("total_items", 0)
    review_count = summary.get("items_requiring_review", 0)

    lines = [
        f"# Checklist: {title}",
        "",
        f"**Profile:** {checklist.get('profile', '')}  ",
        f"**Generated:** {checklist.get('generated_at', '')}  ",
        f"**Items:** {total} total, {review_count} requiring review  ",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(checklist.get("items", []), start=1):
        lines.append(_md_item(item, i))

    missed = checklist.get("possible_missed", [])
    if missed:
        lines += [
            "# Possible missed requirements",
            "",
            f"{len(missed)} passage(s) look like obligations but were not extracted (found by a text scan). Confirm each; they are not counted above.",
            "",
            "---",
            "",
        ]
        for i, item in enumerate(missed, start=1):
            lines.append(_md_item(item, i))

    return "\n".join(lines)
