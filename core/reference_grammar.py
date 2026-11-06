"""Shared reference grammar: the paragraph reference every item of a document sits under.

Regulatory documents number their paragraphs in outline form ("1." > "a." > "(1)" > "(a)"),
sometimes under dotted section headings ("2.10.  TITLE"), and sometimes restart the numbering in
each enclosure. A row cited only as "(inferred) section 2.10" cannot be audited; "2.10.b(3)" can.

This module walks a document's items IN READING ORDER and labels each with the reference it sits
under, for example "Encl A, 5.k" or "2.10.b(3)". It is pure: it reads no files and calls no model.
A document style (core/doc_styles.py) supplies the small amount of per-document-type data in a
Grammar; every rule lives here once, so a fix reaches every style.

Levels, outermost first:
    top      "4" (outline heading or "4." list marker) or "2.10" (dotted heading text)
    letter   "a."
    number   "(1)"
    sub      "(a)"

Rules (each one is there because a real document needed it):
  * A marker counts only when it is a small step forward from the current value at its level
    (gap_tolerance, default 6). The reader can drop an item, so skipping a few numbers is allowed;
    going backwards or repeating is a stray list and is ignored. Without this, a stray "9." list
    near the front of a document took over the numbering of the whole document.
  * A new top level, or an enclosure change, clears every lower level.
  * A dotted heading ("2.10.  TITLE") names its number outright, so it needs no sequence check.
  * Table-of-contents lines (dot leaders and a page number) are never markers.
  * Only heading, list_item and text items carry markers; tables, captions and the rest are ignored.
    A heading may be a top-level number ("2.10.  TITLE", "4.  TITLE") or, like any other item, a
    lettered or parenthesized paragraph the reader happened to file as a heading ("a.  Component heads").

Control-ID documents (NIST SP 800-53, 800-171, 800-53A) are a second family, switched on by `id_heading_patterns`: a control is a heading ("AC-2 ACCOUNT MANAGEMENT",
"03.01.01 Account Management"), its enhancements are headings ("(1) ACCOUNT MANAGEMENT | ..."), its statement is lettered and numbered items ("a.", "1."), and "Discussion" /
"References" / "Related Controls" are parts of the control that are not the statement. References read "AC-2 d.1", "AC-2(1)", "AC-2 Discussion", "03.01.01 f.3".

Tables of controls (CNSSI 1253) are a third, separate piece, switched on by `table_id_pattern`: a table row whose first cell is a control id ("IA-5(8)") is cited by it, the rows
beneath with a blank first cell inherit it (also across a page break, where the header row repeats), and a leading part marker in the second cell is added ("CM-7(1)(b)",
"RA-5 a"). `label_table_lines` does this for one table's markdown; the caller carries the control id from table to table in reading order.

Known limit: numbering that restarts without an enclosure heading (a second numbered list under
the same top level) is read as a stray list and ignored.
"""

import re
from dataclasses import dataclass
from typing import Sequence

_KINDS_WITH_MARKERS = frozenset({"heading", "list_item", "text"})

_DOTTED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,3})+)\.?\s+\S")
_INT_HEADING = re.compile(r"^(\d{1,2})\.\s+\S")
_TEXT_MARKER = re.compile(r"^((?:\d{1,2}|[a-z])\.|\(\d{1,2}\)|\([a-z]\))\s+\S")
_TOC_LINE = re.compile(r"\.{4,}\s*\d+\s*$|\s\.\s\.\s\.")

_GRAMMAR_FIELDS = frozenset({"gap_tolerance", "enclosure_pattern", "dotted_headings", "integer_headings",
                             "id_heading_patterns", "enhancement_pattern", "statement_patterns", "part_patterns", "reset_patterns", "table_id_pattern"})
_MAX_GAP = 20


@dataclass(frozen=True)
class Grammar:
    """The per-document-type data the shared rules need."""
    gap_tolerance: int = 6
    enclosure_pattern: str | None = None  # regex on a heading's text; group 1 is the enclosure id
    dotted_headings: bool = True
    integer_headings: bool = True
    # control-ID family (empty id_heading_patterns = the outline family above)
    id_heading_patterns: tuple[str, ...] = ()        # heading text that names a control; group 1 is its id
    enhancement_pattern: str | None = None            # the shape of an enhancement heading ("ACCOUNT MANAGEMENT | DISABLE ACCOUNTS"); its number is the "(n)" marker or text prefix
    statement_patterns: tuple[str, ...] = ()          # heading or text that (re)starts the control statement ("Control:", "Control Enhancements:")
    part_patterns: tuple[tuple[str, str], ...] = ()   # (name, regex): heading or text that starts a part that is not the statement ("Discussion")
    reset_patterns: tuple[str, ...] = ()              # headings that end the current control (a chapter, an appendix, the bibliography)
    table_id_pattern: str | None = None               # first-cell text that names a control in a table of controls ("IA-5(8)"); works in either family


def _compile(pattern: str, field: str, groups: int):
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"reference_grammar.{field} is not a valid pattern: {e}") from e
    if groups and compiled.groups < groups:
        raise ValueError(f"reference_grammar.{field} needs one group that captures the id")
    return compiled


def _pattern_list(data: dict, field: str, groups: int) -> tuple[str, ...]:
    value = data.get(field, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"reference_grammar.{field} must be a list of pattern strings")
    for v in value:
        _compile(v, field, groups)
    return tuple(value)


def parse_grammar(data: dict) -> Grammar:
    """Validate a style's reference_grammar object and return the Grammar.

    Raises ValueError for unknown fields, wrong types, an out-of-range gap, or a bad pattern.
    """
    if not isinstance(data, dict):
        raise ValueError(f"reference_grammar must be an object or null, got {type(data).__name__}")
    unknown = set(data) - _GRAMMAR_FIELDS
    if unknown:
        raise ValueError(f"Unknown reference_grammar fields: {sorted(unknown)}")
    gap = data.get("gap_tolerance", 6)
    if isinstance(gap, bool) or not isinstance(gap, int) or not 1 <= gap <= _MAX_GAP:
        raise ValueError(f"reference_grammar.gap_tolerance must be a whole number from 1 to {_MAX_GAP}")
    pattern = data.get("enclosure_pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ValueError("reference_grammar.enclosure_pattern must be a string or null")
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"reference_grammar.enclosure_pattern is not a valid pattern: {e}") from e
        if compiled.groups < 1:
            raise ValueError("reference_grammar.enclosure_pattern needs one group that captures the enclosure id")
    for flag in ("dotted_headings", "integer_headings"):
        if flag in data and not isinstance(data[flag], bool):
            raise ValueError(f"reference_grammar.{flag} must be true or false")
    ids = _pattern_list(data, "id_heading_patterns", groups=1)
    statements = _pattern_list(data, "statement_patterns", groups=0)
    resets = _pattern_list(data, "reset_patterns", groups=0)
    enhancement = data.get("enhancement_pattern")
    if enhancement is not None:
        if not isinstance(enhancement, str):
            raise ValueError("reference_grammar.enhancement_pattern must be a string or null")
        _compile(enhancement, "enhancement_pattern", groups=0)
        if not ids:
            raise ValueError("reference_grammar.enhancement_pattern needs id_heading_patterns")
    parts_raw = data.get("part_patterns", {})
    if not isinstance(parts_raw, dict):
        raise ValueError("reference_grammar.part_patterns must be an object of name: pattern")
    parts = []
    for name, rx in parts_raw.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(rx, str):
            raise ValueError("reference_grammar.part_patterns entries must be a non-empty name and a pattern string")
        _compile(rx, f"part_patterns.{name}", groups=0)
        parts.append((name, rx))
    table_id = data.get("table_id_pattern")
    if table_id is not None:
        if not isinstance(table_id, str):
            raise ValueError("reference_grammar.table_id_pattern must be a string or null")
        _compile(table_id, "table_id_pattern", groups=0)
    if (statements or parts or resets) and not ids:
        raise ValueError("reference_grammar.statement_patterns, part_patterns and reset_patterns need id_heading_patterns")
    return Grammar(table_id_pattern=table_id, id_heading_patterns=ids, reset_patterns=resets, enhancement_pattern=enhancement, statement_patterns=statements, part_patterns=tuple(parts),
        gap_tolerance=gap,
        enclosure_pattern=pattern,
        dotted_headings=data.get("dotted_headings", True),
        integer_headings=data.get("integer_headings", True),
    )


@dataclass(frozen=True)
class Item:
    """One document item in reading order. kind: heading, list_item, text, or anything else
    (ignored). marker is the list number the reader kept separately ("4.", "c."), when it has one."""
    kind: str
    text: str = ""
    marker: str = ""
    page: int | None = None


@dataclass(frozen=True)
class Ref:
    """The reference an item sits under. Every part is None until the document names it."""
    enclosure: str | None = None
    top: str | None = None
    letter: str | None = None
    number: str | None = None
    sub: str | None = None
    tail: str | None = None   # control-ID family: the statement item ("d.1", "d.1(a)")
    part: str | None = None   # control-ID family: a part that is not the statement ("Discussion")

    def text(self) -> str:
        """"Encl A, 5.k", "2.10.b(3)", "5.(4)"-style gaps rendered as "5(4)"; empty when nothing is numbered."""
        if self.tail is not None or self.part is not None:   # control-ID family: "AC-2(1) d.1", "AC-2 Discussion"
            if not (self.top or self.tail):
                return ""
            glue = "" if (self.tail or "").startswith("(") else " "   # "AC-2(3)(a)" and "AC-2 d.1"
            return (self.top or "") + (glue + self.tail if self.tail else "") + (" " + self.part if self.part else "")
        parts = ""
        if self.top:
            parts = self.top
        if self.letter:
            parts += ("." if parts else "") + self.letter
        if self.number:
            parts += f"({self.number})"
        if self.sub:
            parts += f"({self.sub})"
        if not parts:
            return ""
        return f"Encl {self.enclosure}, {parts}" if self.enclosure else parts


def _forward(current: str | None, new: str, gap: int, letters: bool) -> bool:
    """True when `new` is a small step forward from `current` (or a plausible first value)."""
    n = ord(new) - 96 if letters else int(new)
    if current is None:
        return 1 <= n <= gap
    c = ord(current) - 96 if letters else int(current)
    return 0 < n - c <= gap


def _label_control_items(items: Sequence[Item], grammar: Grammar) -> list[Ref]:
    """The control-ID family (see the module docstring). State: control id, enhancement, part, and inside the statement the letter / number / sub-item markers.

    A marker is kept in the form the document uses: "d." and "1." read "d.1"; "(b)" and "(1)" read "(b)(1)"; "d.1" then "(a)" reads "d.1(a)"."""
    id_rxs = [re.compile(p) for p in grammar.id_heading_patterns]
    enh_rx = re.compile(grammar.enhancement_pattern) if grammar.enhancement_pattern else None
    stmt_rxs = [re.compile(p) for p in grammar.statement_patterns]
    part_rxs = [(name, re.compile(p)) for name, p in grammar.part_patterns]
    reset_rxs = [re.compile(p) for p in grammar.reset_patterns]
    gap = grammar.gap_tolerance
    cid = enh = part = None
    letter = number = sub = None          # display forms: "d" or "(b)"; "1" or "(1)"; "(a)"
    letter_n = number_n = sub_n = None    # the values, for the forward-step check
    out: list[Ref] = []

    def clear_items():
        nonlocal letter, number, sub, letter_n, number_n, sub_n
        letter = number = sub = letter_n = number_n = sub_n = None

    def tail() -> str:
        t = ""
        for tok in (letter, number, sub):
            if tok:
                t += tok if (tok.startswith("(") or not t) else "." + tok
        return t

    for item in items:
        text = (item.text or "").strip()
        marker = (item.marker or "").strip()
        if item.kind in _KINDS_WITH_MARKERS and not _TOC_LINE.search(text):
            is_heading = item.kind == "heading"
            m_id = next((m for rx in id_rxs if is_heading and (m := rx.match(text))), None)
            lead = re.match(r"^\((\d{1,2})\)", marker or text)
            m_enh = bool(enh_rx and cid and not m_id and enh_rx.match(re.sub(r"^\(\d{1,2}\)\s*", "", text)))
            if m_id:
                cid, enh, part = m_id.group(1), None, None
                clear_items()
            elif is_heading and cid and any(rx.match(text) for rx in reset_rxs):
                cid = enh = part = None
                clear_items()
            elif m_enh:
                enh = lead.group(1) if lead else str(int(enh) + 1 if enh and enh.isdigit() else 1)
                part = None
                clear_items()
            elif cid and any(rx.match(text) for rx in stmt_rxs):
                enh = part = None
                clear_items()
            elif cid and (named := next((n for n, rx in part_rxs if rx.match(text)), None)):
                part = named
                clear_items()
            elif cid and part is None and item.kind != "heading":
                mk = marker
                if not mk:
                    tm = _TEXT_MARKER.match(text)
                    mk = tm.group(1) if tm else ""
                if re.fullmatch(r"[a-z]\.", mk):                      # "d."
                    if _forward(letter_n, mk[0], gap, True):
                        letter, letter_n = mk[0], mk[0]
                        number = sub = number_n = sub_n = None
                elif re.fullmatch(r"\d{1,2}\.", mk):                  # "1." under a lettered item
                    if _forward(number_n, mk[:-1], gap, False):
                        number, number_n = mk[:-1], mk[:-1]
                        sub = sub_n = None
                elif re.fullmatch(r"\([a-z]\)", mk):                  # "(b)": a letter-level item under an enhancement, or a sub-item under a number
                    next_letter = letter is not None and letter.startswith("(") and _forward(letter_n, mk[1], gap, True)
                    if number is None or next_letter:   # "(a)" "(b)" "(c)" is one series even after a "(b)(1)" list; under a dotted letter, "(a)" after "1." is a sub-item
                        if _forward(letter_n, mk[1], gap, True):
                            letter, letter_n = mk, mk[1]
                            number = sub = number_n = sub_n = None
                    elif _forward(sub_n, mk[1], gap, True):
                        sub, sub_n = mk, mk[1]
                elif re.fullmatch(r"\(\d{1,2}\)", mk):               # "(1)" under a "(b)"
                    if letter and _forward(number_n, mk[1:-1], gap, False):
                        number, number_n = mk, mk[1:-1]
                        sub = sub_n = None
        base = (cid + (f"({enh})" if enh else "")) if cid else None
        out.append(Ref(top=base, tail=tail(), part=part))
    return out


def label_items(items: Sequence[Item], grammar: Grammar) -> list[Ref]:
    """Label each item with the reference it sits under, after applying that item's own marker."""
    if grammar.id_heading_patterns:
        return _label_control_items(items, grammar)
    enclosure_rx = re.compile(grammar.enclosure_pattern) if grammar.enclosure_pattern else None
    gap = grammar.gap_tolerance
    enc = top = letter = number = sub = None
    top_dotted = False
    out: list[Ref] = []

    for item in items:
        text = (item.text or "").strip()
        marker = (item.marker or "").strip()
        if item.kind in _KINDS_WITH_MARKERS and not _TOC_LINE.search(text):
            if item.kind == "heading" and enclosure_rx is not None:
                m = enclosure_rx.match(text)
                if m and m.group(1) != enc:
                    enc, top, letter, number, sub, top_dotted = m.group(1), None, None, None, None, False
            kind_marker = ""
            if item.kind == "heading":
                dotted = _DOTTED_HEADING.match(text) if grammar.dotted_headings else None
                integer = _INT_HEADING.match(text) if grammar.integer_headings and not dotted else None
                if dotted:
                    top, top_dotted, letter, number, sub = dotted.group(1), True, None, None, None
                elif integer:
                    if not top_dotted and _forward(top, integer.group(1), gap, False):
                        top, letter, number, sub = integer.group(1), None, None, None
                elif marker:
                    kind_marker = marker
                else:
                    # a lettered or parenthesized paragraph the reader filed as a heading ("a.  Component heads")
                    m = _TEXT_MARKER.match(text)
                    kind_marker = m.group(1) if m else ""
            else:
                if marker:
                    kind_marker = marker
                else:
                    m = _TEXT_MARKER.match(text)
                    kind_marker = m.group(1) if m else ""
            if kind_marker:
                if re.fullmatch(r"\d{1,2}\.", kind_marker):
                    value = kind_marker[:-1]
                    if grammar.integer_headings and not top_dotted and _forward(top, value, gap, False):
                        top, letter, number, sub = value, None, None, None
                elif re.fullmatch(r"[a-z]\.", kind_marker):
                    if _forward(letter, kind_marker[0], gap, True):
                        letter, number, sub = kind_marker[0], None, None
                elif re.fullmatch(r"\(\d{1,2}\)", kind_marker):
                    value = kind_marker[1:-1]
                    if (letter or top) and _forward(number, value, gap, False):
                        number, sub = value, None
                elif re.fullmatch(r"\([a-z]\)", kind_marker):
                    if number and _forward(sub, kind_marker[1], gap, True):
                        sub = kind_marker[1]
        out.append(Ref(enc, top, letter, number, sub))
    return out


_TABLE_PART = re.compile(r"^(\(?[a-z]\)|[a-z]\.(?:\d{1,2}\.?)*)(?=\s)")
_TABLE_HEADER_CELLS = frozenset({"id", "control", "control id", "control number"})


def label_table_lines(markdown: str, grammar: Grammar, carry: str | None = None) -> tuple[list[str | None], str | None]:
    """The reference of each line of a table's markdown grid, and the control id to carry into the next table.

    A row whose first cell matches `table_id_pattern` is cited by that id; a row with a blank first cell inherits the last id (a long table's rows continue across pages, where the header row repeats and the
    id cell is blank); any other first cell ends the control. The second cell may open with a part marker ("(b)", "a.", "b.1."), which is added: "CM-7(1)(b)", "RA-5 a", "IA-1 b.1". Lines that are not table
    rows, the header row and the separator row have no reference (None)."""
    if not grammar.table_id_pattern:
        return [None] * len(markdown.split("\n")), carry
    rx = re.compile(grammar.table_id_pattern)
    current = carry
    refs: list[str | None] = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            refs.append(None)
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not any(cells) or set("".join(cells)) <= set("-: "):
            refs.append(None)
            continue
        if rx.match(cells[0]):
            current = cells[0]
        elif cells[0].lower() in _TABLE_HEADER_CELLS:
            refs.append(None)                      # the header row, repeated at the top of each page's part of a table
            continue
        elif cells[0]:
            current = None                         # some other first cell: no control here
        if current is None:
            refs.append(None)
            continue
        part = _TABLE_PART.match(cells[1]) if len(cells) > 1 else None
        if part:
            tok = part.group(1).rstrip(".")
            refs.append(current + (tok if tok.startswith("(") else " " + tok))
        else:
            refs.append(current)
    return refs, current
