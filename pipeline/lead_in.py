"""Find the lead-in that governs a list item, from the document's own text (pure functions; docs/PIPELINE_REDESIGN_PLAN.md, context attaching).

A list item such as "Include the mission owner in the process." means little without the line above it that ends with a colon ("The Director will:"). This finds that line: the nearest
earlier line, in the same chunk or at the end of the previous chunk, that ends with a colon and is not a sibling of the item. Nothing is guessed: the lead-in is an exact line of the
source, or there is none.

When a list item has no such line at all because the list opens a section whose heading is itself the governing statement ("1. DoD CHIEF INFORMATION OFFICER (DoD CIO). The DoD CIO, shall:"
and the chunk text starts at "- a. Provide strategy ..."), the heading is the lead-in (PREREG10, PROPOSED: `heading_lead_in`, used only when the caller passes the chunk's section title path).
"""
import re

from pipeline.sentence_expand import _LEADING_NUMBER, _MARKER, _TERMINAL, _is_sentence_end, tidy

MAX_UNITS_BACK = 40
MAX_LEAD_IN_CHARS = 300
_DOTTED = re.compile(r"^(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?\s")
_COLON_END = re.compile(r":(\s*\(T-\d\)\.?)?$")  # same rule as pipeline/clauses._LEAD_IN_END: "will:" and, after a tier tag, "options: (T-2)."
_TAG_AFTER_COLON = re.compile(r"(?<=:)\s*\(T-\d\)\.?$")
_MODAL_END = re.compile(r"\b(?:shall|will|must|should|may)\s*$", re.I)
_JUNK_HEADING = re.compile(r"^\W*(?:(?:UNCLASSIFIED|CUI|FOUO|CONFIDENTIAL|SECRET|TOP SECRET)(?:\s*//.*)?|(?:page\s+)?\d{1,4}(?:\s+of\s+\d{1,4})?)\W*$", re.I)
MIN_HEADING_WORDS = 2
_DANGLING_END = re.compile(r"\b(?:to|of|for|by|with|from|on|in|at|per)\s*:?$", re.I)  # "Reply to:" names no party
_STYLES = (
    ("alpha_p", re.compile(r"^\([a-z]{1,2}\)\s")),
    ("alpha", re.compile(r"^[a-z]{1,2}[.)]\s")),
    ("ALPHA_p", re.compile(r"^\([A-Z]{1,2}\)\s")),
    ("ALPHA", re.compile(r"^[A-Z][.)]\s")),
    ("num_p", re.compile(r"^\(\d{1,3}\)\s")),
    ("num", re.compile(r"^\d{1,3}[.)]\s")),
)


def _units(text: str) -> list[tuple[int, str]]:
    """(start offset, text) of each paragraph unit: split at list markers, with any text before the first marker as a unit of its own."""
    starts = sorted({m.start() for m in _MARKER.finditer(text)})
    bounds = ([0] if (not starts or starts[0] > 0) else []) + starts + [len(text)]
    return [(a, text[a:b]) for a, b in zip(bounds, bounds[1:]) if text[a:b].strip()]


def _marker_style(unit: str) -> tuple[str, int]:
    """(style, depth): `none` for a plain paragraph; `dotted` with its depth (3.4.3.1 is 4); else a letter or number style. A bare bullet is `bullet`."""
    body = unit.lstrip()
    bullet = bool(re.match(r"^[-•*]\s+", body))
    body = re.sub(r"^[-•*]\s+", "", body)
    if _DOTTED.match(body):
        return "dotted", len(re.match(r"^(?:[A-Z]{1,2})?(\d+(?:\.\d+)+)", body).group(1).split("."))
    for name, pat in _STYLES:
        if pat.match(body):
            return name, 0
    return ("bullet" if bullet else "none"), 0


def _text_of(unit: str) -> str:
    """The unit's words without its marker, and for a long unit only its last sentence (the one that ends in the colon)."""
    body = unit.strip()
    m = _LEADING_NUMBER.match(body)
    body = tidy(body[m.end():] if m else body)
    cut = _TAG_AFTER_COLON.search(body)
    scan = body[:cut.start()] if cut else body  # the tier tag after the colon is not a sentence end; it stays in the returned text
    last_start = 0
    for t in _TERMINAL.finditer(scan):
        if _is_sentence_end(scan, t):  # abbreviations ("U.S. Cyber Command") and initials do not end a sentence
            last_start = t.end()
    return body[last_start:].strip()


def _candidate(units: list[tuple[int, str]], index: int, item_style: tuple[str, int]):
    """Scan back from unit `index - 1`: (lead-in text, units used) or None. Stops at a plain paragraph that does not end with a colon."""
    for j in range(index - 1, max(-1, index - 1 - MAX_UNITS_BACK), -1):
        unit = units[j][1]
        style = _marker_style(unit)
        text = _text_of(unit)
        if _COLON_END.search(text):
            same_style = style[0] == item_style[0] and style[0] not in ("none", "bullet")
            if same_style and not (style[0] == "dotted" and style[1] < item_style[1]):
                continue  # a sibling that also introduces a list (or a deeper one), not the item's parent
            if style[0] == "dotted" and item_style[0] == "dotted" and style[1] >= item_style[1]:
                continue
            return text if len(text) <= MAX_LEAD_IN_CHARS else None
        if style[0] == "none":
            return None  # an ordinary paragraph: the list, if there was one, began after it
    return None


def is_junk_heading(entry: str) -> bool:
    """A section-path entry that is a page header or footer (a classification banner or a page number), not a heading."""
    return bool(_JUNK_HEADING.match((entry or "").strip()))


def heading_lead_in(title_path) -> str | None:
    """The lead-in a section heading gives to the list under it: the last sentence of the nearest real heading (page-header junk skipped; only that one entry is looked at) when it
    ends in a colon or a modal ("The DoD CIO, shall:", "The Services will"), has at least two words, does not end in a preposition ("Reply to:") and fits the cap; else None."""
    entries = [e for e in (title_path or []) if isinstance(e, str) and e.strip() and not is_junk_heading(e)]
    if not entries:
        return None
    text = _text_of(entries[-1])
    if len(text.split()) < MIN_HEADING_WORDS or len(text) > MAX_LEAD_IN_CHARS or _DANGLING_END.search(text.replace(" :", ":").rstrip()):
        return None
    return text if (_COLON_END.search(text) or _MODAL_END.search(text.rstrip(".;,"))) else None


_BARE_NUMBER_START = re.compile(r"\d{1,3}[ \t]+\S")


def _is_plain_line_after_marker_line(raw: str, item_start: int, unit_start: int) -> bool:
    """True when the item is a line of its own that begins with a bare number (no dot or bracket, so not a list marker), sits inside an earlier list item's unit (the unit started on
    an earlier line), and follows a line that ended a sentence or a colon. Units split only at markers, so such a line would otherwise count as part of the list item above it."""
    line_start = raw.rfind("\n", 0, item_start) + 1
    if line_start <= unit_start or raw[line_start:item_start].strip() or not _BARE_NUMBER_START.match(raw, item_start):
        return False
    return raw[:line_start].rstrip()[-1:] in (".", ":", "?", "!", '"', "'", ")")


def find_lead_in(raw: str, item_start: int, prev_raw: str = "", heading_path=None) -> str | None:
    """The lead-in line for the list item that starts at `item_start` in the chunk's `raw` text, looking in `prev_raw` (the previous chunk) when the list began there; None when the
    item is not a list item or no governing line is found. With `heading_path` (the chunk's section title path), a list item that has no lead-in line and no plain paragraph above it in the
    chunk or in the previous chunk of its section gets the section heading's lead-in when there is one (`heading_lead_in`)."""
    if item_start is None or not raw:
        return None
    units = _units(raw)
    index = max((i for i, (start, _) in enumerate(units) if start <= item_start), default=None)
    if index is None:
        return None
    if _is_plain_line_after_marker_line(raw, item_start, units[index][0]):
        return None  # a plain sentence that starts with a bare number ("24 AF is designated as ...") on a line of its own, after a list item: not itself a list item
    item_style = _marker_style(units[index][1])
    if item_style[0] == "none":
        return None  # a plain sentence stands on its own
    found = _candidate(units, index, item_style)
    if found:
        return found
    if any(_marker_style(u)[0] == "none" for _, u in units[:index]):
        return None  # an ordinary paragraph comes before the item in this chunk: the list began after it
    prev_units = _units(prev_raw) if prev_raw else []
    found = _candidate(prev_units, len(prev_units), item_style) if prev_units else None
    if found or any(_marker_style(u)[0] == "none" for _, u in prev_units):
        return found  # a lead-in line, or a plain paragraph in the previous chunk: the list does not open straight under the heading
    return heading_lead_in(heading_path) if heading_path else None
