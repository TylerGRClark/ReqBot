"""Checklist export — serialize a checklist envelope dict to CSV, JSON, Markdown, or XLSX.

Input:  the dict returned by services/checklist_service.py::generate()
Output: a string (CSV/JSON/Markdown) or bytes (XLSX); caller writes to file or stdout.

All display and export logic lives here and in cli/reqbot.py (WP-21.5).
"""
import csv
import io
import json
import math
from datetime import datetime

from core.display import citation_label

# CSV column order: locate → ask → record → verify → trace
_CSV_COLUMNS = [
    "source_ref",
    "citation",
    "section_title_path",
    "section_heading",
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


def _attention_reasons(item: dict) -> list:
    """The review reasons worth showing on the sheet. Low confidence says nothing (it is true of nearly every row; the number stays in the Conf. column), and a missing source
    reference is moot when the sheet shows a citation read from the document in its place."""
    reasons = [r for r in (item.get("review_reasons") or []) if r != "low-confidence"]
    if _ref(item):
        reasons = [r for r in reasons if r != "missing-source-ref"]
    return reasons


def _needs_attention(item: dict) -> bool:
    """A row worth a reader's second look in the sheet: a specific hint (item_flags) or a specific review reason (see `_attention_reasons`). Confidence alone no longer marks
    every row (the pipeline's confidence is below the review threshold on nearly every record, so it separated nothing); the number itself stays in its column and
    `requires_human_review` stays in JSON."""
    return bool(item.get("item_flags")) or bool(_attention_reasons(item))


def _ref(item: dict) -> str:
    """The citation to show: the paragraph citation (possibly inferred and marked so), else whatever the extractor recorded. The stored "Front matter" is shown as "Opening pages";
    the JSON export keeps the stored string."""
    return citation_label(item.get("citation") or item.get("source_ref") or "")


def _section(item: dict) -> str:
    """The section to show: the heading read from the paragraph numbering when there is one (the converter's section path can be nested wrongly), else the section path."""
    return item.get("section_heading") or _join(item.get("section_title_path") or [], " > ")


def _parent_label(item: dict) -> str:
    """"2.17 MAJCOM/DRUs." : the parent paragraph's number and its text, copied from the document; empty when there is none."""
    text = item.get("parent_text") or ""
    return f"{item.get('parent_ref', '')} {text}".strip() if text else ""


def _csv_row(item: dict) -> dict:
    raw = {
        "source_ref": item.get("source_ref", ""),
        "citation": item.get("citation", ""),
        "section_title_path": _join(item.get("section_title_path") or [], " > "),
        "section_heading": item.get("section_heading", ""),
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
    section = _section(item)
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
    lines.append(f"**Audit Question (draft):** {audit_q if audit_q else '*(not generated)*'}  ")

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


# Rows of the workbook: a title and a subtitle, then the column groups and the column headers, then the data
_XLSX_GROUP_ROW = 3
_XLSX_HEADER_ROW = 4
_XLSX_FIRST_DATA_ROW = 5

# The sheet's columns, in reading order: what to check, the question to ask, where to write the finding, the surrounding text, where to find it, then the trace.
# (header, item key, width, wrap, group). Section, Applies to, Parent para. and Reasons are left off the sheet (they stay in the CSV, JSON and Markdown exports).
_XLSX_COLUMNS = [
    ("Review",                 "attention",          7, False, "Ask"),
    ("Requirement",            "source_quote",      48, True,  "Ask"),
    ("Audit Question (draft)", "audit_question",    48, True,  "Ask"),
    ("Status",                 "status",            16, False, "Record"),
    ("Notes",                  "assessor_notes",    30, True,  "Record"),
    ("Check",                  "item_flags",        22, True,  "Record"),
    ("Passage (click to read all)", "passage",      56, True,  "Context"),
    ("Ref",                    "ref",               14, False, "Locate"),
    ("Pages",                  "page_refs",          8, False, "Locate"),
    ("Item ID",                "checklist_item_id", 11, False, "Trace"),
    ("Req IDs",                "requirement_ids",   11, False, "Trace"),
    ("Conf.",                  "confidence",         7, False, "Trace"),
    ("Tags",                   "domain_tags",       14, False, "Trace"),
]
# group -> (band color, header tint). White on the band and dark text on the tint both read at 4.5:1 or better.
_XLSX_GROUP_COLORS = {
    "Ask": ("047857", "D1FAE5"),
    "Record": ("B45309", "FEF3C7"),
    "Context": ("6D28D9", "EDE9FE"),
    "Locate": ("1D4ED8", "DBEAFE"),
    "Trace": ("4B5563", "E5E7EB"),
}
_SMALL_KEYS = frozenset({"checklist_item_id", "requirement_ids"})  # identifiers for tracing: kept, but small and quiet

# Row height. A row is as tall as the text that must be read at a glance needs (the requirement, the question, the hints, and notes already written), never as tall as
# the passage: a passage can run to thousands of characters, and the full text stays in its cell (click it and Excel's formula bar shows all of it).
_LINE_POINTS = 13.0       # one line of Calibri 10
_PADDING_POINTS = 4.0
_MIN_LINES = 2            # a row always shows at least two lines of the passage
_MAX_ROW_POINTS = 409.0   # Excel's own limit is 409.5
_HEIGHT_KEYS = ("source_quote", "audit_question", "item_flags", "assessor_notes")


def _wrapped_lines(text: object, width: float) -> int:
    """How many lines a cell's text takes in a wrapping column of this width (a little pessimistic: a line that is cut short by a long word still counts as a line)."""
    per_line = max(1, int(width * 0.95))
    return sum(max(1, math.ceil(len(part) / per_line)) for part in str(text or "").split("\n"))


def _row_height(values: dict, widths: dict) -> float:
    """The row's height in points: the tallest of the glance-and-read cells, at least two lines, at most Excel's limit."""
    lines = max([_MIN_LINES] + [_wrapped_lines(values.get(k), widths[k]) for k in _HEIGHT_KEYS])
    return min(_MAX_ROW_POINTS, lines * _LINE_POINTS + _PADDING_POINTS)


def _xlsx_title(checklist: dict) -> str:
    """The document's name for the sheet: the PDF it was read from, else its id (the same fallback the Markdown export uses)."""
    doc = checklist.get("document") or {}
    return doc.get("source_pdf") or doc.get("document_id") or "Unknown document"


def _when(stamp: object) -> str:
    """"2026-10-11 15:04 UTC" from the envelope's ISO time; the text as it is when it cannot be read."""
    text = str(stamp or "")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    suffix = " UTC" if parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0 else ""
    return parsed.strftime("%Y-%m-%d %H:%M") + suffix


def _xlsx_values(item: dict) -> dict:
    """One item's cell values by column key; text cells are guarded against being read as formulas."""
    return {
        "attention": "!" if _needs_attention(item) else "",
        "source_quote": _csv_safe(item.get("source_quote") or ""),
        "audit_question": _csv_safe(item.get("audit_question") or ""),
        "status": _csv_safe(item.get("status") or ""),
        "assessor_notes": _csv_safe(item.get("assessor_notes") or ""),
        # the tool's hints, then the specific review reasons: the Reasons column is not on the sheet, so a row marked "!" for a reason alone still says why
        "item_flags": _csv_safe(_join(list(item.get("item_flags") or []) + _attention_reasons(item), "; ")),
        "passage": _csv_safe(item.get("passage") or ""),
        "ref": _csv_safe(_ref(item)),
        "page_refs": _csv_safe(_join(item.get("page_refs") or [], ", ")),
        "checklist_item_id": _csv_safe(item.get("checklist_item_id") or ""),
        "requirement_ids": _csv_safe(_join(item.get("requirement_ids") or [], ", ")),
        "confidence": item.get("confidence") or 0.0,
        "domain_tags": _csv_safe(_join(item.get("domain_tags") or [], ", ")),
    }


def to_xlsx(checklist: dict) -> bytes:
    """Return the checklist items as an Excel workbook (XLSX) in bytes.

    Layout (rows): 1 the document's name, 2 a line of facts (profile, when, how many items, how many are flagged, how many possible missed), 3 the column groups (Ask, Record,
    Context, Locate, Trace), each in its own color, 4 the column headers in the lighter shade of the group's color, then one row per item, then the possible-missed block.
    Columns: Review (a narrow marker: "!" in an amber cell on a row worth a second look), Requirement, Audit Question, Status (a drop-down, colored by what is chosen), Notes,
    Check (the tool's hints and review reasons for the row), Passage, Ref, Pages, then the small Item ID and Req IDs, then Conf. and Tags (hidden when no row has a value). Rows alternate in
    color by a conditional-format rule, so the stripes stay even when the sheet is sorted or filtered. A row is as tall as its requirement, question and hints need; a long
    passage is cut off at that height and read by clicking its cell (the whole text is in the cell).

    Requires openpyxl (approved WP-23.2 dependency).
    """
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.page import PageMargins

    face = "Calibri"
    ink, soft = "111827", "4B5563"
    hairline = Side(style="thin", color="D1D5DB")
    box = Border(left=hairline, right=hairline, top=hairline, bottom=hairline)
    marker_fill = PatternFill("solid", fgColor="FDE68A")

    keys = [c[1] for c in _XLSX_COLUMNS]
    col_of = {key: n for n, key in enumerate(keys, start=1)}
    widths = {c[1]: c[2] for c in _XLSX_COLUMNS}
    status_col, conf_col = col_of["status"], col_of["confidence"]
    last_col = len(_XLSX_COLUMNS)

    items_all = checklist.get("items", [])
    missed = checklist.get("possible_missed", [])
    title = _xlsx_title(checklist)

    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "047857"
    wb.properties.title = f"Audit checklist: {title}"
    wb.properties.creator = "ReqBot"

    # Rows 1 and 2: which document this is, and the facts about the sheet
    ws.cell(row=1, column=1, value=_csv_safe(f"Audit checklist: {title}")).font = Font(name=face, size=16, bold=True, color=ink)
    ws.row_dimensions[1].height = 26
    ws.cell(row=1, column=1).alignment = Alignment(vertical="center")
    facts = []
    if checklist.get("profile"):
        facts.append(f"Profile: {checklist['profile']}")
    if checklist.get("generated_at"):
        facts.append(f"Generated: {_when(checklist['generated_at'])}")
    facts.append(f"{len(items_all)} item{'' if len(items_all) == 1 else 's'}")
    shaded = sum(1 for i in items_all if _needs_attention(i))
    if shaded:
        facts.append(f"{shaded} of them flagged (!) for a second look")  # the possible-missed rows below are flagged too: they are counted on their own
    if missed:
        facts.append(f"{len(missed)} possible missed, listed at the bottom")
    ws.cell(row=2, column=1, value=_csv_safe(" · ".join(facts))).font = Font(name=face, size=10, color=soft)
    ws.row_dimensions[2].height = 16

    # Row 3: the column groups, each band in its own color (a group is a run of neighbouring columns)
    spans: list[tuple[str, int, int]] = []
    for n, (_h, _k, _w, _wrap, group) in enumerate(_XLSX_COLUMNS, start=1):
        if spans and spans[-1][0] == group:
            spans[-1] = (group, spans[-1][1], n)
        else:
            spans.append((group, n, n))
    for group, c_start, c_end in spans:
        band = _XLSX_GROUP_COLORS[group][0]
        for col in range(c_start, c_end + 1):
            ws.cell(row=_XLSX_GROUP_ROW, column=col).fill = PatternFill("solid", fgColor=band)
        cell = ws.cell(row=_XLSX_GROUP_ROW, column=c_start, value=group)
        cell.font = Font(name=face, size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if c_start != c_end:
            ws.merge_cells(start_row=_XLSX_GROUP_ROW, start_column=c_start, end_row=_XLSX_GROUP_ROW, end_column=c_end)
    ws.row_dimensions[_XLSX_GROUP_ROW].height = 18

    # Row 4: the column headers, in the lighter shade of their group's color
    for col_idx, (header, _key, _w, _wrap, group) in enumerate(_XLSX_COLUMNS, start=1):
        band, tint = _XLSX_GROUP_COLORS[group]
        cell = ws.cell(row=_XLSX_HEADER_ROW, column=col_idx, value=header)
        cell.font = Font(name=face, size=10, bold=True, color=ink)
        cell.fill = PatternFill("solid", fgColor=tint)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = Border(left=hairline, right=hairline, top=hairline, bottom=Side(style="medium", color=band))
    ws.row_dimensions[_XLSX_HEADER_ROW].height = 30

    # Freeze below the headers and after the marker and the requirement (the requirement stays in view while the rest scrolls)
    ws.freeze_panes = f"C{_XLSX_FIRST_DATA_ROW}"

    # Status column data validation (dropdown)
    dv = DataValidation(
        type="list",
        formula1='"not-started,in-progress,compliant,non-compliant,not-applicable"',
        allow_blank=True,
    )
    ws.add_data_validation(dv)

    # Column widths
    for col_idx, (_h, _k, width, _wrap, _g) in enumerate(_XLSX_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Tags and confidence are no longer assigned by the pipeline: hide those two columns (kept, so a reader of an older run still has them) unless some row has a value
    for key, present in (("confidence", lambda v: v is not None), ("domain_tags", bool)):
        if not any(present(i.get(key)) for i in items_all):
            ws.column_dimensions[get_column_letter(col_of[key])].hidden = True

    # Data rows
    def write_item(item):
        values = _xlsx_values(item)

        row_num = ws.max_row + 1
        for col_idx, (_h, key, _w, wrap, _g) in enumerate(_XLSX_COLUMNS, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=values[key])
            if key in _SMALL_KEYS:
                cell.font = Font(name=face, size=8, color="6B7280")
            elif key == "attention":
                cell.font = Font(name=face, size=10, bold=True, color="92400E")
                if values[key]:
                    cell.fill = marker_fill  # a filled cell, not a shaded row: the row's own color is left to the alternating stripes
            else:
                cell.font = Font(name=face, size=10, bold=(key == "ref"), color=ink)
            cell.alignment = Alignment(vertical="top", wrap_text=wrap, horizontal="center" if key in ("status", "attention") else None)
            cell.border = box

        ws.row_dimensions[row_num].height = _row_height(values, widths)  # not the passage's height: see _row_height

        # Confidence as percentage (value is 0–1 float)
        ws.cell(row=row_num, column=conf_col).number_format = "0%"
        # Status: register with data validation
        dv.add(ws.cell(row=row_num, column=status_col))

    for item in items_all:
        write_item(item)

    # Auto-filter covers the extracted rows only; the possible-missed section below is separate
    last_item_row = ws.max_row

    if missed:
        banner_row = ws.max_row + 2
        banner = ws.cell(
            row=banner_row, column=1,
            value=f"POSSIBLE MISSED REQUIREMENTS ({len(missed)}): found in the document text but not extracted. Confirm each; they are not counted above.",
        )
        banner.font = Font(name=face, size=10, bold=True, color="92400E")
        banner.fill = PatternFill("solid", fgColor="FEF3C7")
        banner.alignment = Alignment(vertical="center")
        ws.merge_cells(start_row=banner_row, start_column=1, end_row=banner_row, end_column=last_col)
        ws.row_dimensions[banner_row].height = 24
        for item in missed:
            write_item(item)

    # The Status cell takes the color of what was chosen (not-started stays plain)
    status_letter = get_column_letter(status_col)
    status_range = f"{status_letter}{_XLSX_FIRST_DATA_ROW}:{status_letter}{max(ws.max_row, _XLSX_FIRST_DATA_ROW)}"
    for value, fill, ink_color in (
        ("compliant", "DCFCE7", "166534"),
        ("non-compliant", "FEE2E2", "991B1B"),
        ("in-progress", "DBEAFE", "1E40AF"),
        ("not-applicable", "E5E7EB", "4B5563"),
    ):
        ws.conditional_formatting.add(
            status_range,
            CellIsRule(operator="equal", formula=[f'"{value}"'], fill=PatternFill(start_color=fill, end_color=fill, fill_type="solid"), font=Font(color=ink_color, bold=True)),
        )

    # Alternating rows: a conditional format, so the stripes stay even when the sheet is sorted or filtered (SUBTOTAL counts only the rows still showing). Added after the Status
    # colors so those win on their own cells; the marker column is striped only where it is empty, so a "!" keeps its amber.
    last_row = max(ws.max_row, _XLSX_FIRST_DATA_ROW)
    anchor = get_column_letter(col_of["source_quote"])  # a column every item has a value in
    stripe = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    even = f"MOD(SUBTOTAL(103,${anchor}${_XLSX_FIRST_DATA_ROW}:${anchor}{_XLSX_FIRST_DATA_ROW}),2)=0"
    marker_letter = get_column_letter(col_of["attention"])
    ws.conditional_formatting.add(
        f"{get_column_letter(col_of['attention'] + 1)}{_XLSX_FIRST_DATA_ROW}:{get_column_letter(last_col)}{last_row}",
        FormulaRule(formula=[even], fill=stripe),
    )
    ws.conditional_formatting.add(
        f"{marker_letter}{_XLSX_FIRST_DATA_ROW}:{marker_letter}{last_row}",
        FormulaRule(formula=[f'AND({marker_letter}{_XLSX_FIRST_DATA_ROW}="",{even})'], fill=stripe),
    )

    # Auto-filter: set after rows are written so range covers all data rows
    ws.auto_filter.ref = f"A{_XLSX_HEADER_ROW}:{get_column_letter(last_col)}{max(last_item_row, _XLSX_HEADER_ROW)}"

    # Printing: landscape letter, the group and header rows repeat on every page, the document's name and the page number sit in the footer
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.print_title_rows = f"{_XLSX_GROUP_ROW}:{_XLSX_HEADER_ROW}"
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6)
    ws.oddFooter.left.text = title[:100].replace("&", "&&")  # an ampersand is a code in a header or footer
    ws.oddFooter.left.size = 8
    ws.oddFooter.right.text = "Page &P of &N"
    ws.oddFooter.right.size = 8

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
