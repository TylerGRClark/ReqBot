"""PREREG11 rule (pure functions, no model): the column-header row, and the caption when there is one, for a table grid line.

A grid line is a clause whose text starts with '|'. Its table is the run of consecutive lines starting with '|' that contains it. The header row is the line right above the
table's first separator line (|---|---|). A grid line that is itself the header row gets nothing. The caption is the nearest non-blank line above the table in the same chunk when it
starts with "Table <id>"; a table that begins a chunk (Docling repeats the header there) takes the caption last seen above a table with the same header in an earlier chunk.
"""
import re

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


def render(cells: str, caption: str | None) -> str:
    head = ("%s. " % caption[:CAPTION_CHARS].rstrip(" .")) if caption else ""
    return (head + "Column headers: " + cells)[:MAX_CHARS]


def document_table_context(chunks: list[dict], clauses: list[dict]) -> None:
    """Sets clause["ctx_table"] (str or None) on every clause of the document, in place. Clauses must come in chunk order."""
    raw = {c["chunk_id"]: (c.get("raw_text") or c.get("text") or "") for c in chunks}
    caps: dict[str, str] = {}  # header cells -> last caption seen above a table with that header, as of the chunk being read
    ctx = {}
    for ch in chunks:
        cid = ch["chunk_id"]
        r = raw[cid]
        lines = r.split("\n")
        pos = 0
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("|") and (i == 0 or not lines[i - 1].lstrip().startswith("|")):
                info = header_info(r, pos + (len(ln) - len(ln.lstrip())))
                if info and info[1]:
                    caps[info[0]] = info[1]
            pos += len(ln) + 1
        ctx[cid] = dict(caps)
    for c in clauses:
        info = header_info(raw[c["chunk_id"]], c["start"])
        c["ctx_table"] = None
        if info and not info[2]:
            cells, cap, _ = info
            c["ctx_table"] = render(cells, cap or ctx[c["chunk_id"]].get(cells))
