"""PREREG11 rule (pure functions, no model): the column-header row, and the caption when there is one, for a table grid line.

A grid line is a clause whose text starts with '|'. Its table is the run of consecutive lines starting with '|' that contains it. The header row is the line right above the
table's first separator line (|---|---|). A grid line that is itself the header row gets nothing. The caption is the nearest non-blank line above the table in the same chunk when it
starts with "Table <id>"; a table that begins a chunk (Docling repeats the header there) takes the caption last seen above a table with the same header in an earlier chunk.
"""
import re

from pipeline.sentence_expand import tidy

SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
CAPTION = re.compile(r"^\s*(Table\s+[A-Za-z0-9][A-Za-z0-9.\-]*[:.\s].*)$")
CAPTION_CHARS, MAX_CHARS = 100, 300


def _cells(line: str) -> str:
    return " | ".join(re.sub(r"\s+", " ", c).strip() for c in line.strip().strip("|").split("|") if c.strip())


def table_of(lines: list[str], idx: int):
    """(first, last) line index of the '|' run around line idx, or None."""
    if not lines[idx].lstrip().startswith("|"):
        return None
    a = idx
    while a > 0 and lines[a - 1].lstrip().startswith("|"):
        a -= 1
    b = idx
    while b + 1 < len(lines) and lines[b + 1].lstrip().startswith("|"):
        b += 1
    return a, b


def header_info(raw: str, start: int):
    """(header_cells, caption_or_None, is_header_row) for the grid line at offset `start` of `raw`; None when it is not a grid line or its table has no header row."""
    lines = raw.split("\n")
    idx = raw[:start].count("\n")
    t = table_of(lines, idx)
    if t is None:
        return None
    a, b = t
    seps = [i for i in range(a, b + 1) if SEP.match(lines[i])]
    if not seps or seps[0] == a:
        return None
    h = seps[0] - 1
    cap = None
    j = a - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j >= 0:
        m = CAPTION.match(lines[j])
        cap = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    return _cells(lines[h]), cap, idx == h


def _split_row(line: str) -> list[str]:
    """The cells of a grid line in order, empty ones kept (so a cell keeps its column), each with its whitespace squeezed."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [re.sub(r"\s+", " ", c).strip() for c in body.split("|")]


def row_with_headers(raw: str, start: int, end: int):
    """(header_cells, row_cells, caption_or_None) for the clause raw[start:end] of a table grid line, cells in column order, or None. A clause that starts the line and runs to its end
    must have as many cells as the header row. One that starts the line and stops inside a cell (the splitter cut a long cell at a sentence end) has the cells up to there, the last one
    partial, matched to the first columns. None also when the table has no header row, the clause is the header row, or the cells and columns do not line up (nothing is said then)."""
    info = header_info(raw, start)
    if info is None or info[2]:
        return None
    lines = raw.split("\n")
    idx = raw[:start].count("\n")
    line = lines[idx]
    clause = " ".join(raw[start:end].split())
    flat = " ".join(line.split())
    line_start = raw.rfind("\n", 0, start) + 1
    if not line.lstrip().startswith("|") or raw[line_start:start].strip() or not clause.startswith("|") or not flat.startswith(clause) or SEP.match(line):
        return None
    a, _ = table_of(lines, idx)
    sep = next((i for i in range(a, idx + 1) if SEP.match(lines[i])), None)
    if sep is None:
        # idx sits before the table's first separator row (e.g. a duplicated/garbled
        # header-looking line Docling repeated above the real one) -- not a data row
        # under any header yet, so there is nothing to attach here.
        return None
    headers, cells = _split_row(lines[sep - 1]), _split_row(clause)
    whole = clause == flat
    if (whole and len(headers) != len(cells)) or len(cells) > len(headers):
        return None
    return headers[:len(cells)], cells, info[1]


MAX_LABEL_CHARS = 80
MAX_LABEL_WORDS = 8


def _is_label(h: str) -> bool:
    """A header cell is used as a label when it is short text with at least two letters. A bare number or one letter ("5", "B": the converter's own column marks, or a first data row it took for a
    header) and a header as long as a sentence (over 8 words or 80 characters) (a caption repeated in a merged cell, a data row) say nothing about the column, so the value is shown without it."""
    return len(h) <= MAX_LABEL_CHARS and len(h.split()) <= MAX_LABEL_WORDS and sum(ch.isalpha() for ch in h) >= 2


def labeled_row(headers: list[str], cells: list[str]) -> str:
    """'Header: value | Header: value', cell order kept. An empty cell is left out; a cell with no header text is shown as its value alone; a value repeated by the next column (a merged
    cell) is shown once under both headers ('Header A / Header B: value'). Only words of the table are used."""
    out: list[list[str]] = []
    for h, c in zip(headers, cells):
        if not c:
            continue
        h = h if _is_label(h) else ""
        if out and out[-1][1] == c:
            if h and h not in out[-1][0]:
                out[-1][0].append(h)
            continue
        out.append([[h] if h else [], c])
    return " | ".join((" / ".join(h) + ": " + c) if h else c for h, c in out)


def render(cells: str, caption: str | None) -> str:
    head = ("%s. " % caption[:CAPTION_CHARS].rstrip(" .")) if caption else ""
    return (head + "Column headers: " + cells)[:MAX_CHARS]


def resolved_captions(chunks: list[dict]) -> dict[tuple, str | None]:
    """{(chunk_id, index of the table's first line): caption to show} for every table with a header row, in document order. A table's own caption, else the one last seen above an
    earlier table with the same header (never a later table's)."""
    caps: dict[str, str] = {}  # header cells -> last caption seen above a table with that header
    resolved: dict[tuple, str | None] = {}
    for ch in chunks:
        cid = ch["chunk_id"]
        r = ch.get("raw_text") or ch.get("text") or ""
        lines = r.split("\n")
        pos = 0
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("|") and (i == 0 or not lines[i - 1].lstrip().startswith("|")):
                info = header_info(r, pos + (len(ln) - len(ln.lstrip())))
                if info:
                    resolved[(cid, i)] = info[1] or caps.get(info[0])
                    if info[1]:
                        caps[info[0]] = info[1]
            pos += len(ln) + 1
    return resolved


def table_start_line(raw: str, start: int) -> int:
    """Index of the first line of the '|' run that holds offset `start`."""
    lines = raw.split("\n")
    first = raw[:start].count("\n")
    while first > 0 and lines[first - 1].lstrip().startswith("|"):
        first -= 1
    return first


def document_table_context(chunks: list[dict], clauses: list[dict]) -> None:
    """Sets clause["ctx_table"] (str or None) on every clause of the document, in place. Clauses must come in chunk order. Each table's caption is resolved when the
    table is reached, in document order (resolved_captions)."""
    raw = {c["chunk_id"]: (c.get("raw_text") or c.get("text") or "") for c in chunks}
    resolved = resolved_captions(chunks)
    for c in clauses:
        r = raw[c["chunk_id"]]
        info = header_info(r, c["start"])
        c["ctx_table"] = None
        if info and not info[2]:
            c["ctx_table"] = render(info[0], resolved.get((c["chunk_id"], table_start_line(r, c["start"]))))


def table_context_text(raw: str, start: int, end: int, caption: str | None):
    """The self-contained rendering of the grid line raw[start:end]: '<caption>. Header: value | Header: value', or None when the line is not a whole row of a table with a header row
    (row_with_headers) or every cell is empty."""
    got = row_with_headers(raw, start, end)
    if got is None:
        return None
    body = labeled_row(got[0], got[1])
    if not body:
        return None
    cap = re.sub(r"\s+", " ", caption or got[2] or "").strip().rstrip(" .")
    return tidy((cap + ". " if cap else "") + body)
