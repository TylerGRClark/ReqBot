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

_GRAMMAR_FIELDS = frozenset({"gap_tolerance", "enclosure_pattern", "dotted_headings", "integer_headings"})
_MAX_GAP = 20


@dataclass(frozen=True)
class Grammar:
    """The per-document-type data the shared rules need."""
    gap_tolerance: int = 6
    enclosure_pattern: str | None = None  # regex on a heading's text; group 1 is the enclosure id
    dotted_headings: bool = True
    integer_headings: bool = True


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
    return Grammar(
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

    def text(self) -> str:
        """"Encl A, 5.k", "2.10.b(3)", "5.(4)"-style gaps rendered as "5(4)"; empty when nothing is numbered."""
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


def label_items(items: Sequence[Item], grammar: Grammar) -> list[Ref]:
    """Label each item with the reference it sits under, after applying that item's own marker."""
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
                elif integer and not top_dotted and _forward(top, integer.group(1), gap, False):
                    top, letter, number, sub = integer.group(1), None, None, None
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
